"""Session-based fall conversation service."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

from fastapi import BackgroundTasks

from agents.communication.session_agent import analyze_communication_turn
from agents.execution.execution_agent import requires_execution_grounding, run_execution_grounding
from agents.shared.config import get_genai_client
from app.fall.action_runtime_service import (
    apply_session_action_decision,
    reset_action_runtime_session,
    sync_action_state_with_assessment,
    sync_dispatch_confirmation_task,
)
from app.fall.assessment_service import build_interaction_summary, load_user_profile, run_fall_assessment, run_reasoning_assessment
from app.fall.contracts import (
    CommunicationAgentAnalysis,
    CommunicationSessionStateResponse,
    CommunicationTurnRequest,
    CommunicationTurnResponse,
    ConversationMessage,
    ExecutionUpdate,
    FallAssessment,
    PatientAnswer,
)
from app.fall.session_store import fall_session_store

logger = logging.getLogger(__name__)
_reasoning_tasks: dict[str, asyncio.Task[None]] = {}

STEP_ACKNOWLEDGEMENTS = {
    "done",
    "done.",
    "ok",
    "okay",
    "okay.",
    "next",
    "next step",
    "need next step",
    "got it",
    "understood",
}

STEP_REPAIR_SIGNALS = {
    "wrong",
    "did it wrong",
    "i did it wrong",
    "not sure",
    "confused",
    "messed up",
}


@dataclass(frozen=True)
class CommunicationDirective:
    """Deterministic turn instruction used to prioritize what the user hears next."""

    source: str
    message: str
    guidance_intent: str
    priority: int
    immediate_step: str | None = None
    question: str | None = None
    next_focus: str | None = None
    quick_replies: list[str] | None = None
    announcement_key: str | None = None
    suppress_question: bool = False


def _short_session_id(session_id: str | None) -> str:
    """Return a compact identifier for logs so long IDs stay readable."""
    if not session_id:
        return "unknown"
    return session_id.replace("phase4-", "")[:8]


def _clip_message(text: str, limit: int = 80) -> str:
    """Collapse whitespace and trim long messages before writing them to logs."""
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _normalized_message_key(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())


def _latest_human_message_key(conversation_history: list[ConversationMessage]) -> str:
    for message in reversed(conversation_history):
        if message.role not in {"assistant", "system"}:
            return _normalized_message_key(message.text)
    return ""


def _answers_from_turn_message(message_text: str, target: str) -> list[PatientAnswer]:
    """Convert the latest responder turn into the answer format used by reasoning."""
    normalized_text = (message_text or "").strip()
    if not normalized_text:
        return []
    question_id = "bystander_turn" if target == "bystander" else "patient_turn"
    return [PatientAnswer(question_id=question_id, answer=normalized_text)]


def _answers_from_conversation_history(conversation_history: list[ConversationMessage]) -> list[PatientAnswer]:
    """Flatten the stored transcript into synthetic answers for refresh passes."""
    answers: list[PatientAnswer] = []
    for index, message in enumerate(conversation_history):
        if message.role in {"assistant", "system"}:
            continue
        normalized_text = message.text.strip()
        if not normalized_text:
            continue
        answers.append(
            PatientAnswer(
                question_id=f"{message.role}_turn_{index + 1}",
                answer=normalized_text,
            )
        )
    return answers


def _patient_response_status_from_analysis(analysis: CommunicationAgentAnalysis) -> str:
    """Map communication-agent facts into the interaction-policy response states."""
    facts = set(analysis.extracted_facts)
    if analysis.responder_role == "no_response":
        return "no_response"
    if "unresponsive" in facts:
        return "unresponsive"
    if "confusion" in facts:
        return "confused"
    if analysis.patient_responded or "responsive" in facts:
        return "responsive"
    return "unknown"


def _message_role_from_analysis(analysis: CommunicationAgentAnalysis) -> str:
    """Choose the transcript role for the latest inbound human message."""
    if analysis.responder_role in {"patient", "bystander", "no_response"}:
        return analysis.responder_role
    if analysis.communication_target in {"patient", "bystander"}:
        return analysis.communication_target
    return "patient"


def _merge_assessment_into_analysis(
    *,
    analysis: CommunicationAgentAnalysis,
    assessment: FallAssessment | None,
) -> CommunicationAgentAnalysis:
    """Backfill missing analysis fields from the latest reasoning snapshot."""
    if assessment is None:
        return analysis

    immediate_step = analysis.immediate_step
    if immediate_step is None and assessment.action.recommended != "monitor" and assessment.guidance.steps:
        immediate_step = assessment.guidance.steps[0]

    return analysis.model_copy(update={"immediate_step": immediate_step})


def _normalize_reply_text(text: str | None) -> str:
    """Collapse whitespace so reply composition and comparisons stay stable."""

    return " ".join((text or "").strip().split())


def _strip_questions_from_text(text: str | None) -> str:
    """Remove question sentences when the current turn should stay instruction-first."""

    normalized = _normalize_reply_text(text)
    if not normalized:
        return ""

    sentences = [segment.strip() for segment in re.findall(r"[^.!?]+[.!?]?", normalized) if segment.strip()]
    statement_parts = [segment for segment in sentences if not segment.endswith("?")]
    return " ".join(statement_parts).strip()


def _compose_reply_text(
    *,
    primary_message: str,
    immediate_step: str | None = None,
    followup_question: str | None = None,
    include_question: bool = False,
) -> str:
    """Assemble a short reply from the turn's prioritized communication parts."""

    ordered_parts: list[str] = []
    for raw_part in [
        primary_message,
        immediate_step,
        followup_question if include_question else None,
    ]:
        normalized = _normalize_reply_text(raw_part)
        if not normalized:
            continue
        existing_text = " ".join(ordered_parts).lower()
        if normalized.lower() in existing_text:
            continue
        ordered_parts.append(normalized)
    return " ".join(ordered_parts).strip()


def _collect_effective_execution_updates(
    *,
    execution_updates: list[ExecutionUpdate],
    assessment: FallAssessment | None,
) -> list[ExecutionUpdate]:
    """Use the runtime-owned execution updates as the source of truth."""

    return [item.model_copy(deep=True) for item in execution_updates]


def _build_execution_directive(
    *,
    execution_updates: list[ExecutionUpdate],
    communication_target: str,
    announced_execution_types: set[str],
) -> CommunicationDirective | None:
    """Pick the highest-priority execution update that should be announced once."""

    target_key = communication_target if communication_target in {"patient", "bystander"} else "general"
    candidate_directives: list[CommunicationDirective] = []

    for update in execution_updates:
        update_identity = update.notification_key or str(update.occurrence_count or 1)
        announcement_key = f"{update.type}:{update.status}:{target_key}:{update_identity}"
        if announcement_key in announced_execution_types:
            continue

        if update.type == "emergency_dispatch" and update.status == "completed":
            if target_key == "bystander":
                candidate_directives.append(
                    CommunicationDirective(
                        source="execution",
                        message="Emergency help has been called.",
                        guidance_intent="instruction",
                        priority=500,
                        immediate_step="Stay with them and watch their breathing.",
                        next_focus="guided_action",
                        quick_replies=["Done", "Breathing okay", "Breathing strangely", "Not responding"],
                        announcement_key=announcement_key,
                        suppress_question=True,
                    )
                )
            elif target_key == "patient":
                candidate_directives.append(
                    CommunicationDirective(
                        source="execution",
                        message="Emergency help has been called.",
                        guidance_intent="instruction",
                        priority=500,
                        immediate_step="Stay where you are and move as little as possible.",
                        next_focus="guided_action",
                        quick_replies=["Okay", "Hard to breathe", "Bleeding", "Need help"],
                        announcement_key=announcement_key,
                        suppress_question=True,
                    )
                )
            else:
                candidate_directives.append(
                    CommunicationDirective(
                        source="execution",
                        message="Emergency help has been called.",
                        guidance_intent="instruction",
                        priority=500,
                        next_focus="guided_action",
                        announcement_key=announcement_key,
                        suppress_question=True,
                    )
                )
            continue

        if update.type == "emergency_dispatch" and update.status == "pending_confirmation":
            if target_key == "bystander":
                candidate_directives.append(
                    CommunicationDirective(
                        source="execution",
                        message="Emergency help may be needed.",
                        guidance_intent="question",
                        priority=450,
                        question="Is the patient awake and breathing normally?",
                        next_focus="breathing",
                        quick_replies=["Awake", "Breathing normally", "Breathing strangely", "Not responding"],
                        announcement_key=announcement_key,
                    )
                )
            elif target_key == "patient":
                candidate_directives.append(
                    CommunicationDirective(
                        source="execution",
                        message="Emergency help may be needed.",
                        guidance_intent="question",
                        priority=450,
                        question="Are you breathing normally right now?",
                        next_focus="breathing",
                        quick_replies=["Breathing okay", "Hard to breathe", "Need help", "Can't answer well"],
                        announcement_key=announcement_key,
                    )
                )
            else:
                candidate_directives.append(
                    CommunicationDirective(
                        source="execution",
                        message="Emergency help may be needed.",
                        guidance_intent="question",
                        priority=450,
                        question="Tell me if the patient is awake and breathing normally.",
                        next_focus="breathing",
                        announcement_key=announcement_key,
                    )
                )
            continue

        if update.type == "inform_family" and update.status in {"queued", "completed"}:
            if target_key == "bystander":
                message = "I have informed the family."
            elif target_key == "patient":
                message = "I have informed your family."
            else:
                message = "I have informed the family for support."
            if update.occurrence_count and update.occurrence_count > 1:
                message = f"{message} I also sent an updated family notification."
            candidate_directives.append(
                CommunicationDirective(
                    source="execution",
                    message=message,
                    guidance_intent="reassure",
                    priority=320 if update.status == "completed" else 310,
                    next_focus="monitoring",
                    announcement_key=announcement_key,
                    suppress_question=True,
                )
            )
            continue

        guidance_directives = {
            "cpr_in_progress": ("Start CPR now.", "Begin chest compressions."),
            "bleeding_control_guidance": ("Control the bleeding now.", "Apply firm pressure."),
            "recovery_position_guidance": ("Put them in the recovery position now.", "Roll them onto their side."),
            "keep_patient_still": ("Keep them still right now.", "Do not help them stand."),
        }
        if update.type in guidance_directives and update.status in {"active", "queued", "completed"}:
            message, immediate_step = guidance_directives[update.type]
            candidate_directives.append(
                CommunicationDirective(
                    source="execution",
                    message=message,
                    guidance_intent="instruction",
                    priority=400,
                    immediate_step=immediate_step,
                    next_focus="guided_action",
                    announcement_key=announcement_key,
                    suppress_question=True,
                )
            )

    if not candidate_directives:
        return None
    return max(candidate_directives, key=lambda directive: directive.priority)


def _build_analysis_directive(analysis: CommunicationAgentAnalysis) -> CommunicationDirective:
    """Use the communication-model output as the fallback directive."""

    suppress_question = analysis.guidance_intent in {"instruction", "reassure"} and bool(analysis.immediate_step)
    return CommunicationDirective(
        source="analysis",
        message=_normalize_reply_text(analysis.followup_text),
        guidance_intent=analysis.guidance_intent,
        priority=120,
        immediate_step=analysis.immediate_step,
        next_focus=analysis.next_focus,
        quick_replies=analysis.quick_replies,
        suppress_question=suppress_question,
    )


def _apply_priority_controller_to_reply(
    *,
    analysis: CommunicationAgentAnalysis,
    execution_updates: list[ExecutionUpdate],
    announced_execution_types: set[str],
    assessment: FallAssessment | None = None,
) -> tuple[CommunicationAgentAnalysis, list[str]]:
    """Choose the final reply using deterministic communication priorities."""

    effective_updates = _collect_effective_execution_updates(
        execution_updates=execution_updates,
        assessment=assessment,
    )
    execution_directive = _build_execution_directive(
        execution_updates=effective_updates,
        communication_target=analysis.communication_target,
        announced_execution_types=announced_execution_types,
    )
    analysis_directive = _build_analysis_directive(analysis)

    primary_directive = max(
        [directive for directive in [execution_directive, analysis_directive] if directive is not None],
        key=lambda directive: directive.priority,
    )

    backup_step = None
    if primary_directive.source == "execution":
        backup_step = analysis.immediate_step

    primary_message = primary_directive.message
    if primary_directive.suppress_question:
        primary_message = _strip_questions_from_text(primary_message) or primary_message

    immediate_step = primary_directive.immediate_step or backup_step
    include_question = not primary_directive.suppress_question and bool(primary_directive.question)
    final_text = _compose_reply_text(
        primary_message=primary_message,
        immediate_step=immediate_step if primary_directive.source != "analysis" else None,
        followup_question=primary_directive.question if include_question else None,
        include_question=include_question,
    )

    if not final_text:
        fallback_message = _strip_questions_from_text(analysis.followup_text) or _normalize_reply_text(analysis.followup_text)
        final_text = _compose_reply_text(
            primary_message=fallback_message,
            immediate_step=immediate_step,
            include_question=False,
        )

    updated_analysis = analysis.model_copy(
        update={
            "followup_text": final_text,
            "guidance_intent": primary_directive.guidance_intent,
            "next_focus": primary_directive.next_focus or analysis.next_focus,
            "immediate_step": immediate_step,
            "quick_replies": primary_directive.quick_replies or analysis.quick_replies,
        }
    )
    announced_keys = [primary_directive.announcement_key] if primary_directive.announcement_key else []
    return updated_analysis, announced_keys


def _apply_execution_context_to_reply(
    *,
    analysis: CommunicationAgentAnalysis,
    execution_updates: list[ExecutionUpdate],
    announced_execution_types: set[str],
    assessment: FallAssessment | None = None,
) -> tuple[CommunicationAgentAnalysis, list[str]]:
    """Apply deterministic execution and handoff priorities to the final reply."""

    return _apply_priority_controller_to_reply(
        analysis=analysis,
        execution_updates=execution_updates,
        announced_execution_types=announced_execution_types,
        assessment=assessment,
    )


def _build_automated_execution_message(
    *,
    assessment: FallAssessment,
    execution_updates: list[ExecutionUpdate],
    announced_execution_types: set[str],
) -> tuple[ConversationMessage | None, list[str]]:
    """Create a system-owned responder message for newly completed execution work.

    This path is intentionally narrow: it only emits automated status messages
    for confirmed execution updates after background reasoning completes. Normal
    conversational replies should still come from the communication agent.
    """

    target = "patient"
    if assessment.interaction and assessment.interaction.communication_target in {"patient", "bystander"}:
        target = assessment.interaction.communication_target

    directive = _build_execution_directive(
        execution_updates=execution_updates,
        communication_target=target,
        announced_execution_types=announced_execution_types,
    )
    if directive is None:
        return None, []

    final_text = _compose_reply_text(
        primary_message=directive.message,
        immediate_step=directive.immediate_step,
        include_question=False,
    )
    if not final_text:
        return None, []

    announced_keys = [directive.announcement_key] if directive.announcement_key else []
    return ConversationMessage(role="assistant", text=final_text), announced_keys


def _build_critical_status_message(
    *,
    assessment: FallAssessment,
    execution_updates: list[ExecutionUpdate],
    announced_execution_types: set[str],
) -> tuple[ConversationMessage | None, list[str]]:
    """Auto-inject a message ONLY for emergency dispatch or family notification.

    All other execution updates (monitor, guidance scripts, etc.) are stored
    silently and consumed by the communication agent on the next user turn.
    This prevents the reasoning agent from hijacking the conversation.
    """

    CRITICAL_TYPES = {"emergency_dispatch", "inform_family"}
    critical_updates = [u for u in execution_updates if u.type in CRITICAL_TYPES]

    if not critical_updates:
        return None, []

    target = "patient"
    if assessment.interaction and assessment.interaction.communication_target in {"patient", "bystander"}:
        target = assessment.interaction.communication_target

    directive = _build_execution_directive(
        execution_updates=critical_updates,
        communication_target=target,
        announced_execution_types=announced_execution_types,
    )
    if directive is None:
        return None, []

    final_text = _compose_reply_text(
        primary_message=directive.message,
        immediate_step=directive.immediate_step,
        include_question=False,
    )
    if not final_text:
        return None, []

    announced_keys = [directive.announcement_key] if directive.announcement_key else []
    return ConversationMessage(role="assistant", text=final_text), announced_keys


def _summarize_for_comm_agent(assessment: FallAssessment) -> str:
    """Build a short context summary for the communication agent's next turn.

    This is stored as pending_reasoning_context and consumed once. It gives the
    communication agent awareness of what reasoning decided without injecting
    messages or overwriting the analysis.
    """

    parts: list[str] = []
    parts.append(f"Severity: {assessment.clinical_assessment.severity}")
    parts.append(f"Action: {assessment.action.recommended}")

    if assessment.clinical_assessment.red_flags:
        parts.append(f"Red flags: {', '.join(assessment.clinical_assessment.red_flags[:3])}")
    if assessment.clinical_assessment.missing_facts:
        parts.append(f"Missing: {', '.join(assessment.clinical_assessment.missing_facts[:2])}")
    if assessment.response_plan.notification_actions:
        parts.append(
            f"Notifications: {', '.join(action.type for action in assessment.response_plan.notification_actions[:2])}"
        )
    if assessment.response_plan.bystander_actions:
        parts.append(f"Scene actions: {', '.join(action.type for action in assessment.response_plan.bystander_actions[:2])}")

    return " | ".join(parts)


def _apply_protocol_step_progression(
    *,
    session_id: str,
    analysis: CommunicationAgentAnalysis,
    assessment: FallAssessment | None,
    latest_message: str,
) -> CommunicationAgentAnalysis:
    """Advance or repeat grounded protocol steps based on the responder's latest message."""

    session = fall_session_store.get_session(session_id)
    if session is None or assessment is None:
        return analysis

    protocol = assessment.protocol_guidance
    steps = protocol.steps if protocol else []
    if not protocol.ready_for_communication or not protocol.protocol_key or not steps:
        return analysis

    current_index = min(session.active_protocol_step_index, len(steps) - 1)
    current_step = steps[current_index]

    latest_human_text = " ".join((latest_message or "").lower().split())
    if not latest_human_text:
        for message in reversed(session.conversation_history):
            if message.role not in {"assistant", "system"}:
                latest_human_text = " ".join(message.text.lower().split())
                break

    if latest_human_text in STEP_ACKNOWLEDGEMENTS or any(signal in latest_human_text for signal in ["what next", "what now"]):
        next_index = min(current_index + 1, len(steps) - 1)
        if next_index != current_index:
            fall_session_store.set_protocol_step_index(session_id=session_id, step_index=next_index)
            return analysis.model_copy(
                update={
                    "guidance_intent": "instruction",
                    "immediate_step": steps[next_index],
                    "next_focus": protocol.protocol_key,
                    "quick_replies": ["Done", "Need next step", "Condition worse"],
                }
            )
        return analysis.model_copy(
            update={
                "guidance_intent": "reassure",
                "immediate_step": current_step,
                "next_focus": protocol.protocol_key,
                "quick_replies": ["Condition worse", "Need help", "Okay"],
            }
        )

    if any(signal in latest_human_text for signal in STEP_REPAIR_SIGNALS):
        return analysis.model_copy(
            update={
                "guidance_intent": "instruction",
                "immediate_step": current_step,
                "next_focus": protocol.protocol_key,
                "quick_replies": ["Done", "Need next step", "Condition worse"],
            }
        )

    if current_step:
        return analysis.model_copy(
            update={
                "immediate_step": current_step,
                "next_focus": protocol.protocol_key,
                "quick_replies": analysis.quick_replies or ["Done", "Need next step", "Condition worse"],
            }
        )
    return analysis


def _schedule_session_reasoning_refresh(session_id: str) -> None:
    """Ensure each session has at most one active background reasoning task."""

    existing_task = _reasoning_tasks.get(session_id)
    if existing_task is not None and not existing_task.done():
        return

    task = asyncio.create_task(_run_session_reasoning_refresh(session_id))
    _reasoning_tasks[session_id] = task

    def _cleanup_task(completed_task: asyncio.Task[None]) -> None:
        current_task = _reasoning_tasks.get(session_id)
        if current_task is completed_task:
            _reasoning_tasks.pop(session_id, None)

    task.add_done_callback(_cleanup_task)


def reset_fall_conversation_session(session_id: str) -> dict[str, bool | str]:
    """Cancel active work for a session and remove its backend-held state."""

    task = _reasoning_tasks.pop(session_id, None)
    task_cancelled = False
    if task is not None and not task.done():
        task.cancel()
        task_cancelled = True
    reset_action_runtime_session(session_id)

    removed_session = fall_session_store.remove_session(session_id)
    if removed_session is not None:
        logger.info(
            "[Session %s] Reset requested | task_cancelled=%s",
            _short_session_id(session_id),
            task_cancelled,
        )

    return {
        "session_id": session_id,
        "reset": removed_session is not None,
        "task_cancelled": task_cancelled,
    }


async def run_fall_conversation_turn(
    request: CommunicationTurnRequest,
    *,
    background_tasks: Optional[BackgroundTasks] = None,
) -> CommunicationTurnResponse:
    """Run one session-based communication turn for an active fall incident.

    The turn lifecycle is:
    1. interpret the newest responder message
    2. refresh interaction metadata for reasoning policy
    3. prioritize execution or safety communication deterministically
    4. queue a background reasoning refresh only when the state changed enough
    """
    session = fall_session_store.get_session(request.session_id) if request.session_id else None
    if session is None:
        session = fall_session_store.create_session(
            event=request.event,
            vitals=request.vitals,
            interaction_input=request.interaction,
        )
        logger.info(
            "[Session %s] Started | user=%s motion=%s",
            _short_session_id(session.session_id),
            request.event.user_id,
            request.event.motion_state,
        )
    else:
        updated_session = fall_session_store.update_context(
            session_id=session.session_id,
            event=request.event,
            vitals=request.vitals,
            interaction_input=request.interaction,
        )
        session = updated_session or session

    existing_assessment = session.latest_assessment or request.previous_assessment
    conversation_history = session.conversation_history or request.conversation_history

    # Consume pending context from background reasoning (cleared after read)
    pending_reasoning_context, pending_execution_plan = fall_session_store.consume_pending_context(
        session.session_id
    )

    try:
        client = get_genai_client()
    except RuntimeError:
        client = None

    patient_profile = load_user_profile(request.event.user_id)
    analysis = await analyze_communication_turn(
        client=client,
        event=request.event,
        vitals=request.vitals,
        patient_profile=patient_profile,
        conversation_history=conversation_history,
        latest_message=request.latest_responder_message,
        previous_assessment=existing_assessment,
        previous_analysis=session.latest_analysis,
        pending_reasoning_context=pending_reasoning_context,
        execution_plan=pending_execution_plan,
        execution_updates=session.execution_updates,
        acknowledged_reasoning_triggers=session.reasoning_triggered_fact_keys,
    )
    logger.info(
        "[Session %s] Communication analyzed | role=%s target=%s reasoning_needed=%s message=\"%s\"",
        _short_session_id(session.session_id),
        analysis.responder_role,
        analysis.communication_target,
        analysis.reasoning_needed,
        _clip_message(request.latest_responder_message or "<session start>"),
    )

    enriched_interaction = request.interaction.model_copy(
        update={
            "patient_response_status": _patient_response_status_from_analysis(analysis),
            "bystander_available": analysis.bystander_present,
            "bystander_can_help": analysis.bystander_can_help,
            "message_text": request.latest_responder_message,
            "new_fact_keys": analysis.extracted_facts,
            "responder_mode_hint": analysis.responder_role if analysis.responder_role != "unknown" else None,
        }
    )

    fall_session_store.update_context(
        session_id=session.session_id,
        event=request.event,
        vitals=request.vitals,
        interaction_input=enriched_interaction,
        bump_reasoning_version=False,
    )

    answers = _answers_from_turn_message(
        request.latest_responder_message,
        analysis.communication_target if analysis.communication_target != "unknown" else "patient",
    )
    interaction = build_interaction_summary(
        interaction=enriched_interaction,
        patient_answers=answers,
        recommended_action=existing_assessment.action.recommended if existing_assessment else None,
    )

    final_analysis = _merge_assessment_into_analysis(
        analysis=analysis,
        assessment=existing_assessment,
    ).model_copy(
        update={
            "reasoning_needed": analysis.reasoning_needed,
            "reasoning_reason": analysis.reasoning_reason,
        }
    )
    final_analysis = _apply_protocol_step_progression(
        session_id=session.session_id,
        analysis=final_analysis,
        assessment=existing_assessment,
        latest_message=request.latest_responder_message,
    )
    current_session = fall_session_store.get_session(session.session_id) or session
    final_analysis, announced_execution_types = _apply_execution_context_to_reply(
        analysis=final_analysis,
        execution_updates=current_session.execution_updates,
        announced_execution_types=current_session.announced_execution_types,
        assessment=current_session.latest_assessment or existing_assessment,
    )

    reasoning_needed = final_analysis.reasoning_needed
    should_bootstrap_reasoning = existing_assessment is None
    is_duplicate_human_turn = (
        bool(request.latest_responder_message.strip())
        and _normalized_message_key(request.latest_responder_message) == _latest_human_message_key(conversation_history)
    )
    reasoning_needed = final_analysis.reasoning_needed
    reasoning_requested = should_bootstrap_reasoning or (reasoning_needed and not is_duplicate_human_turn)
    responder_reasoning_version = current_session.reasoning_input_version + (1 if reasoning_requested else 0)

    responder_messages: list[ConversationMessage] = []
    if request.latest_responder_message.strip():
        responder_messages.append(
            ConversationMessage(
                role=_message_role_from_analysis(analysis),
                text=request.latest_responder_message.strip(),
                reasoning_input_version=responder_reasoning_version,
                comm_reasoning_required=reasoning_requested,
                comm_reasoning_reason=final_analysis.reasoning_reason or interaction.reasoning_refresh.reason,
            )
        )

    if responder_messages:
        fall_session_store.append_messages(
            session.session_id,
            responder_messages,
            bump_reasoning_version=reasoning_requested,
        )

    assistant_message = ConversationMessage(
        role="assistant",
        text=final_analysis.followup_text,
        reasoning_input_version=responder_reasoning_version,
    )
    if assistant_message.text.strip():
        fall_session_store.append_messages(session.session_id, [assistant_message])
    for execution_type in announced_execution_types:
        fall_session_store.mark_execution_announced(
            session_id=session.session_id,
            execution_type=execution_type,
        )
    logger.info(
        "[Session %s] Assistant reply | target=%s text=\"%s\"",
        _short_session_id(session.session_id),
        interaction.communication_target,
        _clip_message(final_analysis.followup_text),
    )

    fall_session_store.store_turn_state(
        session_id=session.session_id,
        interaction_summary=interaction,
        latest_analysis=final_analysis,
    )

    if reasoning_requested:
        fall_session_store.register_reasoning_trigger_facts(
            session_id=session.session_id,
            fact_keys=final_analysis.extracted_facts,
        )
        should_start_now = fall_session_store.request_reasoning(
            session_id=session.session_id,
            reason=(
                "Initial event assessment is being prepared."
                if should_bootstrap_reasoning and not reasoning_needed
                else final_analysis.reasoning_reason or interaction.reasoning_refresh.reason
            ),
        )
        logger.info(
            "[Session %s] Reasoning %s | reason=%s",
            _short_session_id(session.session_id),
            "queued" if should_start_now else "already pending",
            final_analysis.reasoning_reason or interaction.reasoning_refresh.reason or "none",
        )
        if should_start_now:
            if background_tasks is not None:
                background_tasks.add_task(_run_session_reasoning_refresh, session.session_id)
            else:
                _schedule_session_reasoning_refresh(session.session_id)
    else:
        logger.info(
            "[Session %s] Reasoning skipped | continuing communication only",
            _short_session_id(session.session_id),
        )

    latest_session = fall_session_store.get_session(session.session_id) or session

    return CommunicationTurnResponse(
        session_id=session.session_id,
        interaction=interaction,
        communication_analysis=final_analysis,
        reasoning_invoked=reasoning_requested,
        reasoning_status=latest_session.reasoning_status,
        reasoning_run_count=latest_session.reasoning_run_count,
        reasoning_reason=latest_session.reasoning_reason,
        reasoning_error=latest_session.reasoning_error,
        assistant_message=final_analysis.followup_text,
        assistant_question=None,
        guidance_steps=[final_analysis.immediate_step] if final_analysis.immediate_step else [],
        quick_replies=final_analysis.quick_replies,
        assessment=existing_assessment,
        execution_updates=latest_session.execution_updates,
        action_states=latest_session.action_states,
        transcript_append=[assistant_message] if assistant_message.text.strip() else [],
        reasoning_runs=latest_session.reasoning_runs,
    )


async def _run_session_reasoning_refresh(session_id: str) -> None:
    """Two-phase background reasoning refresh.

    Phase 1 — Reasoning Agent:
      Uses Gemini Pro + optionally Vertex AI Search (reasoning-support only).
      Stores the clinical assessment and a short context summary for the
      communication agent to consume on the next user turn.
      Auto-injects a message ONLY for emergency dispatch or family notification.

    Phase 2 — Execution Agent (conditional):
      Uses Vertex AI Search (guidance/protocol only) — no Gemini call.
      Only fires when the reasoning agent determines an emergency action or
      bystander intervention is needed.
    """

    session = fall_session_store.begin_reasoning_run(session_id=session_id)
    if session is None:
        return

    try:
        logger.info(
            "[Session %s] Background reasoning started | input_version=%s requested_version=%s",
            _short_session_id(session_id),
            session.reasoning_active_version,
            session.reasoning_requested_version,
        )
        patient_answers = _answers_from_conversation_history(session.conversation_history)

        # ── Phase 1: Reasoning Agent (fast path) ──────────────────────
        assessment = await run_reasoning_assessment(
            event=session.event,
            vitals=session.vitals,
            patient_answers=patient_answers,
            interaction=session.interaction_input,
            trigger_dispatch=False,
            background_tasks=None,
        )
        if fall_session_store.get_session(session_id) is None:
            logger.info(
                "[Session %s] Background reasoning discarded after reset",
                _short_session_id(session_id),
            )
            return

        _, execution_updates = sync_action_state_with_assessment(
            session_id=session_id,
            assessment=assessment,
            patient_answers=patient_answers,
        )
        sync_dispatch_confirmation_task(session_id)

        # Auto-inject ONLY for emergency dispatch and family notification
        assistant_message, announced_execution_types = _build_critical_status_message(
            assessment=assessment,
            execution_updates=execution_updates,
            announced_execution_types=session.announced_execution_types,
        )

        # Summarize reasoning for the communication agent's next turn
        pending_context = _summarize_for_comm_agent(assessment)

        should_rerun = fall_session_store.complete_reasoning(
            session_id=session_id,
            processed_version=session.reasoning_active_version,
            assessment=assessment,
            assistant_message=assistant_message,
            execution_updates=execution_updates,
            pending_reasoning_context=pending_context,
        )
        for execution_type in announced_execution_types:
            fall_session_store.mark_execution_announced(
                session_id=session_id,
                execution_type=execution_type,
            )
        logger.info(
            "[Session %s] Phase 1 complete | severity=%s action=%s processed_version=%s rerun=%s",
            _short_session_id(session_id),
            assessment.clinical_assessment.severity,
            assessment.action.recommended,
            session.reasoning_active_version,
            should_rerun,
        )

        # ── Phase 2: Execution Agent (only if warranted) ──────────────
        bystander_actions = assessment.response_plan.bystander_actions if assessment.response_plan else []
        if requires_execution_grounding(
            action=assessment.action.recommended,
            bystander_actions=bystander_actions,
        ):
            logger.info(
                "[Session %s] Phase 2: Execution agent starting | action=%s",
                _short_session_id(session_id),
                assessment.action.recommended,
            )
            patient_profile = load_user_profile(session.event.user_id)
            execution_plan = await run_execution_grounding(
                action=assessment.action.recommended,
                clinical_assessment=assessment.clinical_assessment,
                patient_profile=patient_profile,
                patient_answers=patient_answers,
            )
            fall_session_store.store_execution_plan(session_id, execution_plan)
            logger.info(
                "[Session %s] Phase 2 complete | steps=%d protocol=%s source=%s",
                _short_session_id(session_id),
                len(execution_plan.steps),
                execution_plan.protocol_key or "none",
                execution_plan.source,
            )
        else:
            logger.info(
                "[Session %s] Phase 2 skipped | action=%s (no execution grounding needed)",
                _short_session_id(session_id),
                assessment.action.recommended,
            )

        if should_rerun:
            _reasoning_tasks.pop(session_id, None)
            _schedule_session_reasoning_refresh(session_id)
    except asyncio.CancelledError:
        logger.info("[Session %s] Background reasoning cancelled", _short_session_id(session_id))
        raise
    except Exception as exc:
        logger.exception("[Session %s] Background reasoning failed", _short_session_id(session_id))
        should_retry = fall_session_store.fail_reasoning(
            session_id=session_id,
            error_message=str(exc),
        )
        if should_retry:
            _reasoning_tasks.pop(session_id, None)
            _schedule_session_reasoning_refresh(session_id)


def get_fall_conversation_session_state(
    session_id: str,
) -> CommunicationSessionStateResponse | None:
    """Return the latest known state for a fall conversation session."""
    session = fall_session_store.get_session(session_id)
    if session is None:
        return None

    return CommunicationSessionStateResponse(
        session_id=session.session_id,
        version=session.version,
        reasoning_status=session.reasoning_status,
        reasoning_run_count=session.reasoning_run_count,
        reasoning_reason=session.reasoning_reason,
        reasoning_error=session.reasoning_error,
        interaction=session.interaction_summary,
        latest_analysis=session.latest_analysis,
        assessment=session.latest_assessment,
        execution_updates=session.execution_updates,
        action_states=session.action_states,
        conversation_history=session.conversation_history,
        reasoning_runs=session.reasoning_runs,
    )

