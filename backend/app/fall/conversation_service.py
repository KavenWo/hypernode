"""Session-based fall conversation service."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from fastapi import BackgroundTasks

from app.fall.action_runtime_service import (
    request_contact_family_action,
    request_emergency_dispatch_confirmation,
    reset_action_runtime_session,
    sync_action_state_with_assessment,
    sync_dispatch_confirmation_task,
)
from app.fall.agent_runtime import get_fall_agent_runtime
from app.fall.assessment_service import build_interaction_summary, load_user_profile, run_reasoning_assessment
from app.fall.contracts import (
    CommunicationAgentAnalysis,
    CommunicationState,
    CommunicationSessionStateResponse,
    CommunicationSessionStartRequest,
    CommunicationTurnRequest,
    CommunicationTurnResponse,
    ConversationMessage,
    DispatchStatus,
    ExecutionGuidance,
    ExecutionUpdate,
    ExecutionState,
    FallAssessment,
    InteractionSummary,
    PatientAnswer,
    ReasoningDecision,
    ReasoningRefreshSummary,
    SessionState,
)
from app.fall.session_store import FallSessionRecord, fall_session_store
from app.services.patient_incident_service import get_incident_by_realtime_session_id

logger = logging.getLogger(__name__)
_reasoning_tasks: dict[str, asyncio.Task[None]] = {}

EXECUTION_PROGRESS_SIGNALS = {
    "advance_step",
    "repeat_current_step",
    "repair_current_step",
    "request_cpr_guidance",
}
CPR_JOIN_SIGNALS = {
    "advance_step",
    "request_cpr_guidance",
}
CPR_GUIDANCE_JOIN_TIMEOUT_SECONDS = 2.5


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


def _is_no_response_message(text: str | None) -> bool:
    normalized = _normalized_message_key(text)
    return normalized == "no_response_"


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


def _execution_override_payload(
    *,
    execution_updates: list[ExecutionUpdate],
    communication_target: str,
    announced_execution_types: set[str],
) -> dict[str, object] | None:
    """Return the next narrow execution-owned communication override."""

    target_key = communication_target if communication_target in {"patient", "bystander"} else "general"

    for update in execution_updates:
        update_identity = update.notification_key or str(update.occurrence_count or 1)
        announcement_key = f"{update.type}:{update.status}:{target_key}:{update_identity}"
        if announcement_key in announced_execution_types:
            continue

        if update.type == "emergency_dispatch" and update.status == "completed":
            if target_key == "bystander":
                return {
                    "message": "Emergency help has been called.",
                    "guidance_intent": "instruction",
                    "immediate_step": "Stay with them and watch their breathing.",
                    "next_focus": "guided_action",
                    "quick_replies": ["Done", "Breathing okay", "Breathing strangely", "Not responding"],
                    "announcement_key": announcement_key,
                    "suppress_question": True,
                }
            if target_key == "patient":
                return {
                    "message": "Emergency help has been called.",
                    "guidance_intent": "instruction",
                    "immediate_step": "Stay where you are and move as little as possible.",
                    "next_focus": "guided_action",
                    "quick_replies": ["Okay", "Hard to breathe", "Bleeding", "Need help"],
                    "announcement_key": announcement_key,
                    "suppress_question": True,
                }
            return {
                "message": "Emergency help has been called.",
                "guidance_intent": "instruction",
                "immediate_step": None,
                "next_focus": "guided_action",
                "quick_replies": [],
                "announcement_key": announcement_key,
                "suppress_question": True,
            }

        if update.type == "emergency_dispatch" and update.status == "pending_confirmation":
            if target_key == "bystander":
                return {
                    "message": "Emergency help may be needed.",
                    "guidance_intent": "question",
                    "immediate_step": None,
                    "question": "Is the patient awake and breathing normally?",
                    "next_focus": "breathing",
                    "quick_replies": ["Awake", "Breathing normally", "Breathing strangely", "Not responding"],
                    "announcement_key": announcement_key,
                    "suppress_question": False,
                }
            if target_key == "patient":
                return {
                    "message": "Emergency help may be needed.",
                    "guidance_intent": "question",
                    "immediate_step": None,
                    "question": "Are you breathing normally right now?",
                    "next_focus": "breathing",
                    "quick_replies": ["Breathing okay", "Hard to breathe", "Need help", "Can't answer well"],
                    "announcement_key": announcement_key,
                    "suppress_question": False,
                }
            return {
                "message": "Emergency help may be needed.",
                "guidance_intent": "question",
                "immediate_step": None,
                "question": "Tell me if the patient is awake and breathing normally.",
                "next_focus": "breathing",
                "quick_replies": [],
                "announcement_key": announcement_key,
                "suppress_question": False,
            }

        if update.type == "inform_family" and update.status in {"queued", "completed"}:
            if target_key == "bystander":
                message = "I have informed the family."
            elif target_key == "patient":
                message = "I have informed your family."
            else:
                message = "I have informed the family for support."
            if update.occurrence_count and update.occurrence_count > 1:
                message = f"{message} I also sent an updated family notification."
            return {
                "message": message,
                "guidance_intent": "reassure",
                "immediate_step": None,
                "next_focus": "monitoring",
                "quick_replies": [],
                "announcement_key": announcement_key,
                "suppress_question": True,
            }

        guidance_directives = {
            "cpr_in_progress": ("Start CPR now.", "Begin chest compressions."),
            "bleeding_control_guidance": ("Control the bleeding now.", "Apply firm pressure."),
            "recovery_position_guidance": ("Put them in the recovery position now.", "Roll them onto their side."),
            "keep_patient_still": ("Keep them still right now.", "Do not help them stand."),
        }
        if update.type in guidance_directives and update.status in {"active", "queued", "completed"}:
            message, immediate_step = guidance_directives[update.type]
            return {
                "message": message,
                "guidance_intent": "instruction",
                "immediate_step": immediate_step,
                "next_focus": "guided_action",
                "quick_replies": [],
                "announcement_key": announcement_key,
                "suppress_question": True,
            }

    return None


def _apply_execution_status_override(
    *,
    analysis: CommunicationAgentAnalysis,
    execution_updates: list[ExecutionUpdate],
    announced_execution_types: set[str],
    assessment: FallAssessment | None,
) -> tuple[CommunicationAgentAnalysis, list[str]]:
    """Apply only narrow execution-owned status overrides.

    The canonical controller should prefer the ADK communication reply by
    default and override it only for clear execution-state announcements such
    as dispatch/family updates.
    """

    protocol_ready = bool(
        assessment is not None
        and assessment.protocol_guidance is not None
        and assessment.protocol_guidance.ready_for_communication
        and assessment.protocol_guidance.steps
    )

    execution_directive = _execution_override_payload(
        execution_updates=execution_updates,
        communication_target=analysis.communication_target,
        announced_execution_types=announced_execution_types,
    )
    if execution_directive is not None and protocol_ready and execution_directive.get("message") in {
        "I have informed the family.",
        "I have informed your family.",
        "I have informed the family for support.",
    }:
        logger.info(
            "[Session %s] Skipping execution announcement override | reason=protocol_ready protocol=%s",
            _short_session_id(getattr(getattr(assessment, "interaction", None), "session_id", None)),
            assessment.protocol_guidance.protocol_key if assessment and assessment.protocol_guidance else "none",
        )
        execution_directive = None

    if execution_directive is None:
        immediate_step = analysis.immediate_step
        if immediate_step is None and assessment is not None:
            if assessment.protocol_guidance.steps:
                immediate_step = assessment.protocol_guidance.steps[0]
            elif assessment.guidance.steps:
                immediate_step = assessment.guidance.steps[0]
        return analysis.model_copy(update={"immediate_step": immediate_step}), []

    primary_message = str(execution_directive["message"])
    if bool(execution_directive.get("suppress_question")):
        primary_message = _strip_questions_from_text(primary_message) or primary_message

    immediate_step = execution_directive.get("immediate_step") or analysis.immediate_step
    question = execution_directive.get("question")
    final_text = _compose_reply_text(
        primary_message=primary_message,
        immediate_step=immediate_step,
        followup_question=question if isinstance(question, str) else None,
        include_question=bool(question and not execution_directive.get("suppress_question")),
    )
    updated_analysis = analysis.model_copy(
        update={
            "followup_text": final_text or analysis.followup_text,
            "guidance_intent": str(execution_directive["guidance_intent"]),
            "next_focus": str(execution_directive.get("next_focus") or analysis.next_focus),
            "immediate_step": immediate_step,
            "quick_replies": list(execution_directive.get("quick_replies") or analysis.quick_replies),
        }
    )
    announcement_key = execution_directive.get("announcement_key")
    announced_keys = [announcement_key] if isinstance(announcement_key, str) and announcement_key else []
    return updated_analysis, announced_keys


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

    if assessment.protocol_guidance.ready_for_communication and assessment.protocol_guidance.steps:
        logger.info(
            "[Session %s] Suppressing critical status auto-message | reason=protocol_ready protocol=%s",
            _short_session_id(getattr(getattr(assessment, "interaction", None), "session_id", None)),
            assessment.protocol_guidance.protocol_key or "none",
        )
        return None, []

    target = "patient"
    if assessment.interaction and assessment.interaction.communication_target in {"patient", "bystander"}:
        target = assessment.interaction.communication_target

    directive = _execution_override_payload(
        execution_updates=critical_updates,
        communication_target=target,
        announced_execution_types=announced_execution_types,
    )
    if directive is None:
        return None, []

    immediate_step = directive.get("immediate_step")
    final_text = _compose_reply_text(
        primary_message=str(directive["message"]),
        immediate_step=immediate_step if isinstance(immediate_step, str) else None,
        include_question=False,
    )
    if not final_text:
        return None, []

    announcement_key = directive.get("announcement_key")
    announced_keys = [announcement_key] if isinstance(announcement_key, str) and announcement_key else []
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


def _summarize_execution_guidance(guidance: ExecutionGuidance) -> str:
    """Build a short one-time execution summary for the communication agent."""

    parts: list[str] = []
    if guidance.scenario:
        parts.append(f"Execution scenario: {guidance.scenario}")
    if guidance.primary_message:
        parts.append(f"Execution message: {guidance.primary_message}")
    if guidance.protocol_key:
        parts.append(f"Execution protocol: {guidance.protocol_key}")
    if guidance.steps:
        parts.append(f"Execution steps: {', '.join(guidance.steps[:2])}")
    if guidance.warnings:
        parts.append(f"Warnings: {', '.join(guidance.warnings[:2])}")
    return " | ".join(parts)


def _store_execution_guidance_state(*, session_id: str, session, guidance: ExecutionGuidance) -> None:
    """Project execution-agent guidance into canonical execution state."""

    previous_execution = session.execution_state or ExecutionState()
    guidance_protocol = guidance.protocol_key or previous_execution.guidance_protocol
    next_prompt = guidance.primary_message or (
        session.canonical_communication_state.latest_prompt
        if session.canonical_communication_state is not None
        else ""
    )
    communication_state = session.canonical_communication_state
    if communication_state is not None:
        communication_state = communication_state.model_copy(
            update={"latest_prompt": next_prompt}
        )

    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        communication_state=communication_state,
        execution_state=ExecutionState(
            phase=(previous_execution.phase if previous_execution.phase not in {"idle", ""} else "guidance"),
            countdown_seconds=previous_execution.countdown_seconds,
            family_notified_initial=previous_execution.family_notified_initial,
            family_notified_update=previous_execution.family_notified_update,
            dispatch_status=previous_execution.dispatch_status,
            guidance_protocol=guidance_protocol,
            guidance_step_index=0,
        ),
    )
    logger.info(
        "[Session %s] Stored execution state | scenario=%s protocol=%s phase=%s steps=%d primary=%s",
        _short_session_id(session_id),
        guidance.scenario or "none",
        guidance.protocol_key or "none",
        (previous_execution.phase if previous_execution.phase not in {"idle", ""} else "guidance"),
        len(guidance.steps or []),
        _clip_message(guidance.primary_message, 120),
    )


def _store_execution_guidance_assessment(*, session_id: str, session, guidance: ExecutionGuidance):
    """Persist execution guidance into the active assessment used by step progression.

    The communication execution loop advances steps from the session assessment.
    When Phase 2 execution returns grounded CPR or other protocol steps, they
    must be written back into the assessment so later "next step" turns do not
    fall back to generic reasoning-stage guidance.
    """

    assessment = getattr(session, "latest_assessment", None)
    if assessment is None:
        logger.warning(
            "[Session %s] Execution guidance could not be persisted into assessment | reason=no_assessment protocol=%s",
            _short_session_id(session_id),
            guidance.protocol_key or "none",
        )
        return None

    next_protocol_key = guidance.protocol_key or (
        assessment.protocol_guidance.protocol_key if assessment.protocol_guidance else ""
    )
    next_protocol_title = (
        next_protocol_key.replace("_", " ").title()
        if next_protocol_key
        else (assessment.protocol_guidance.title if assessment.protocol_guidance else "")
    )
    next_primary_message = guidance.primary_message or (
        guidance.steps[0]
        if guidance.steps
        else assessment.guidance.primary_message
    )
    next_steps = list(guidance.steps or [])
    next_warnings = list(guidance.warnings or [])
    next_escalation_triggers = list(guidance.escalation_triggers or [])

    updated_assessment = assessment.model_copy(
        update={
            "guidance": assessment.guidance.model_copy(
                update={
                    "primary_message": next_primary_message,
                    "steps": next_steps or list(assessment.guidance.steps),
                    "warnings": next_warnings or list(assessment.guidance.warnings),
                    "escalation_triggers": next_escalation_triggers or list(assessment.guidance.escalation_triggers),
                }
            ),
            "protocol_guidance": assessment.protocol_guidance.model_copy(
                update={
                    "protocol_key": next_protocol_key,
                    "title": next_protocol_title,
                    "grounding_required": bool(next_protocol_key),
                    "grounding_status": "ready" if next_steps else assessment.protocol_guidance.grounding_status,
                    "primary_message": next_primary_message,
                    "steps": next_steps,
                    "warnings": next_warnings,
                    "communication_message": next_primary_message,
                    "ready_for_communication": bool(next_steps),
                    "rationale": (
                        f"Execution guidance stored from {guidance.source or 'execution'} for active protocol progression."
                        if next_steps
                        else assessment.protocol_guidance.rationale
                    ),
                }
            ),
        }
    )
    stored = fall_session_store.set_latest_assessment(
        session_id=session_id,
        assessment=updated_assessment,
    )
    logger.info(
        "[Session %s] Stored execution assessment guidance | protocol=%s steps=%d warnings=%d source=%s",
        _short_session_id(session_id),
        next_protocol_key or "none",
        len(next_steps),
        len(next_warnings),
        guidance.source or "unknown",
    )
    if next_steps:
        logger.info(
            "[Session %s] Stored protocol step preview | protocol=%s steps=%s warnings=%s",
            _short_session_id(session_id),
            next_protocol_key or "none",
            next_steps[:5],
            next_warnings[:3],
        )
    return stored


def _execution_guidance_steps(session) -> list[str]:
    """Return the active execution guidance steps for the canonical session."""

    assessment = getattr(session, "latest_assessment", None)
    if assessment is None:
        return []

    protocol_steps = list(assessment.protocol_guidance.steps) if assessment.protocol_guidance else []
    if protocol_steps:
        logger.info(
            "[Session %s] Execution step source selected | source=protocol protocol=%s steps=%d preview=%s",
            _short_session_id(getattr(session, "session_id", None)),
            assessment.protocol_guidance.protocol_key if assessment.protocol_guidance else "none",
            len(protocol_steps),
            protocol_steps[:4],
        )
        return protocol_steps

    guidance_steps = list(assessment.guidance.steps) if assessment.guidance else []
    if guidance_steps:
        logger.info(
            "[Session %s] Execution step source selected | source=generic_guidance steps=%d",
            _short_session_id(getattr(session, "session_id", None)),
            len(guidance_steps),
    )
    return guidance_steps


def _has_active_execution_guidance(session) -> bool:
    """Return whether the canonical session currently has execution guidance to surface."""

    execution_state = getattr(session, "execution_state", None)
    if execution_state is None:
        return False

    if _execution_guidance_steps(session):
        return execution_state.phase in {"guidance", "dispatch_countdown", "dispatch_triggered"}

    return False


def _has_ready_cpr_guidance(session) -> bool:
    """Return whether grounded CPR guidance is already available for communication."""

    assessment = getattr(session, "latest_assessment", None)
    protocol_guidance = assessment.protocol_guidance if assessment is not None else None
    if protocol_guidance is None:
        return False
    return (
        protocol_guidance.protocol_key == "cpr"
        and protocol_guidance.ready_for_communication
        and bool(protocol_guidance.steps)
    )


async def _wait_for_cpr_guidance_ready(session_id: str, *, timeout_seconds: float) -> None:
    """Briefly wait for the in-flight background reasoning/execution task to publish CPR guidance."""

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        session = fall_session_store.get_session(session_id)
        if session is None:
            return
        if _has_ready_cpr_guidance(session):
            logger.info(
                "[Session %s] CPR guidance became ready during join wait",
                _short_session_id(session_id),
            )
            return

        task = _reasoning_tasks.get(session_id)
        if task is None or task.done():
            return

        await asyncio.sleep(0.1)


def _apply_cpr_guidance_hold_if_needed(*, session, analysis: CommunicationAgentAnalysis) -> CommunicationAgentAnalysis:
    """Return a controlled holding response if CPR guidance is still not ready."""

    signal = (analysis.execution_signal or "none").strip().lower()
    if signal not in CPR_JOIN_SIGNALS:
        return analysis
    if session.reasoning_status != "pending":
        return analysis
    if _has_ready_cpr_guidance(session):
        return analysis

    return analysis.model_copy(
        update={
            "followup_text": "Preparing CPR steps now. Start chest compressions if the patient is not breathing normally.",
            "guidance_intent": "instruction",
            "next_focus": "guided_action",
            "immediate_step": "Preparing CPR steps now. Start chest compressions if the patient is not breathing normally.",
            "quick_replies": [],
        }
    )


def _current_guidance_steps_for_response(session, analysis: CommunicationAgentAnalysis) -> list[str]:
    """Return the current visible guidance steps for the response payload."""

    if _has_active_execution_guidance(session):
        steps = _execution_guidance_steps(session)
        if steps and session.execution_state is not None:
            step_index = min(session.execution_state.guidance_step_index, max(len(steps) - 1, 0))
            return [steps[step_index]]
    if analysis.immediate_step:
        return [analysis.immediate_step]
    return []


def _advance_execution_guidance_if_needed(*, session_id: str, session, analysis: CommunicationAgentAnalysis, latest_message: str) -> None:
    """Advance or repair the execution step pointer based on the AI's controlled signal."""

    if not _has_active_execution_guidance(session):
        return

    steps = _execution_guidance_steps(session)
    if not steps:
        return

    current_index = (
        session.execution_state.guidance_step_index
        if session.execution_state is not None
        else session.active_protocol_step_index
    )
    current_step = steps[min(current_index, max(len(steps) - 1, 0))]
    current_step_lower = current_step.lower()
    protocol_key = (
        session.execution_state.guidance_protocol
        if session.execution_state is not None
        else session.active_protocol_key
    )
    signal = (analysis.execution_signal or "none").strip().lower()
    if signal not in EXECUTION_PROGRESS_SIGNALS:
        return

    if signal == "repeat_current_step":
        logger.info(
            "[Session %s] Repeating execution step | protocol=%s index=%d total=%d signal=%s message=%s",
            _short_session_id(session_id),
            protocol_key or "none",
            current_index,
            len(steps),
            signal,
            _clip_message(latest_message, 80),
        )
        return

    if signal == "repair_current_step":
        logger.info(
            "[Session %s] Repair requested for execution step | protocol=%s index=%d total=%d signal=%s message=%s",
            _short_session_id(session_id),
            protocol_key or "none",
            current_index,
            len(steps),
            signal,
            _clip_message(latest_message, 80),
        )
        return

    if signal == "request_cpr_guidance" and protocol_key == "cpr":
        if current_index != 0:
            logger.info(
                "[Session %s] Re-anchoring CPR guidance to first step | from=%d total=%d message=%s",
                _short_session_id(session_id),
                current_index,
                len(steps),
                _clip_message(latest_message, 80),
            )
            updated_session = fall_session_store.set_protocol_step_index(
                session_id=session_id,
                step_index=0,
            )
            if updated_session is not None and updated_session.canonical_communication_state is not None:
                fall_session_store.store_canonical_flow_state(
                    session_id=session_id,
                    communication_state=updated_session.canonical_communication_state.model_copy(
                        update={"latest_prompt": steps[0]}
                    ),
                )
        return

    should_advance = signal == "advance_step" or (
        signal == "request_cpr_guidance"
        and protocol_key == "cpr"
        and ("start cpr" in current_step_lower or "not breathing normally" in current_step_lower)
    )
    if not should_advance:
        return

    if current_index >= len(steps) - 1:
        return

    next_index = current_index + 1
    logger.info(
        "[Session %s] Advancing execution step | protocol=%s from=%d to=%d total=%d signal=%s message=%s",
        _short_session_id(session_id),
        protocol_key or "none",
        current_index,
        next_index,
        len(steps),
        signal,
        _clip_message(latest_message, 80),
    )
    updated_session = fall_session_store.set_protocol_step_index(
        session_id=session_id,
        step_index=next_index,
    )
    if updated_session is None:
        return

    communication_state = updated_session.canonical_communication_state
    if communication_state is None:
        return

    next_prompt = steps[next_index]
    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        communication_state=communication_state.model_copy(update={"latest_prompt": next_prompt}),
    )


def _apply_execution_guidance_prompt(*, session, analysis: CommunicationAgentAnalysis) -> CommunicationAgentAnalysis:
    """Attach execution-step guardrails while letting the AI render the wording."""

    if not _has_active_execution_guidance(session):
        return analysis

    if session.execution_state is None or session.execution_state.phase not in {"guidance", "dispatch_countdown", "dispatch_triggered"}:
        return analysis

    steps = _execution_guidance_steps(session)
    if not steps:
        return analysis

    step_index = min(
        session.execution_state.guidance_step_index,
        max(len(steps) - 1, 0),
    )
    current_step = steps[step_index]
    is_last_step = step_index >= len(steps) - 1

    return analysis.model_copy(
        update={
            "guidance_intent": "instruction",
            "next_focus": "guided_action",
            "immediate_step": current_step,
            "quick_replies": (["Okay"] if is_last_step else ["Done", "Need next step"]),
        }
    )


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


def _bootstrap_canonical_opening_state(*, session_id: str) -> None:
    """Initialize the canonical state machine for a newly created session.

    This is intentionally deterministic. A new session always starts with the
    family alert / monitoring stage already underway and the first responder-
    facing communication prompt fixed to "A fall is detected, are you okay?".
    """

    opening_prompt = "A fall is detected, are you okay?"
    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        state=SessionState.INITIAL_ACTIONS_STARTED,
        communication_state=CommunicationState(
            session_id=session_id,
            state=SessionState.INITIAL_ACTIONS_STARTED,
            latest_prompt=opening_prompt,
        ),
        execution_state=ExecutionState(
            phase="initial_actions",
            family_notified_initial=True,
        ),
    )
    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        state=SessionState.OPENING_CHECK,
        communication_state=CommunicationState(
            session_id=session_id,
            state=SessionState.OPENING_CHECK,
            latest_prompt=opening_prompt,
        ),
    )
    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        state=SessionState.AWAITING_OPENING_RESPONSE,
        communication_state=CommunicationState(
            session_id=session_id,
            state=SessionState.AWAITING_OPENING_RESPONSE,
            latest_prompt=opening_prompt,
        ),
    )
    session = fall_session_store.get_session(session_id)
    opening_already_present = bool(
        session is not None
        and session.conversation_history
        and session.conversation_history[0].role == "assistant"
        and session.conversation_history[0].text.strip() == opening_prompt
    )
    if not opening_already_present:
        fall_session_store.append_messages(
            session_id,
            [ConversationMessage(role="assistant", text=opening_prompt)],
        )


def _build_opening_turn_response(*, session) -> CommunicationTurnResponse:
    """Return the deterministic opening prompt for a brand-new session."""

    latest_prompt = (
        session.canonical_communication_state.latest_prompt
        if session.canonical_communication_state is not None
        else "A fall is detected, are you okay?"
    )
    opening_interaction = session.interaction_summary or _build_default_opening_interaction()
    opening_analysis = CommunicationAgentAnalysis(
        followup_text=latest_prompt,
        responder_role="unknown",
        communication_target="patient",
        patient_responded=False,
        bystander_present=False,
        bystander_can_help=False,
        extracted_facts=[],
        resolved_fact_keys=[],
        open_question_key="general_check",
        open_question_resolved=False,
        conversation_state_summary="Opening check started. Waiting for the patient to respond.",
        reasoning_needed=False,
        reasoning_reason="The canonical opening check must happen before deeper reasoning.",
        should_surface_execution_update=False,
        guidance_intent="question",
        next_focus="opening_check",
        immediate_step=None,
        quick_replies=["Yes", "No", "I need help"],
    )

    return CommunicationTurnResponse(
        session_id=session.session_id,
        state=session.state,
        canonical_communication_state=session.canonical_communication_state,
        reasoning_decision=session.reasoning_decision,
        execution_state=session.execution_state,
        interaction=opening_interaction,
        communication_analysis=opening_analysis,
        reasoning_invoked=False,
        reasoning_status=session.reasoning_status,
        reasoning_run_count=session.reasoning_run_count,
        reasoning_reason=session.reasoning_reason,
        reasoning_error=session.reasoning_error,
        assistant_message=latest_prompt,
        assistant_question=latest_prompt,
        guidance_steps=_current_guidance_steps_for_response(session, opening_analysis),
        quick_replies=opening_analysis.quick_replies,
        assessment=session.latest_assessment,
        execution_updates=session.execution_updates,
        action_states=session.action_states,
        transcript_append=[ConversationMessage(role="assistant", text=latest_prompt)],
        reasoning_runs=session.reasoning_runs,
    )


def _build_default_opening_interaction() -> InteractionSummary:
    return InteractionSummary(
        communication_target="patient",
        responder_mode="patient_only",
        guidance_style="calm_question",
        interaction_mode="opening_check",
        rationale="A detected fall always starts with a patient-first opening check.",
        reasoning_refresh=ReasoningRefreshSummary(
            required=False,
            reason="The opening check happens before the first reasoning trigger.",
        ),
        testing_assume_bystander=False,
    )


def _is_affirmative(message: str) -> bool:
    normalized = " ".join((message or "").strip().lower().split())
    return normalized in {
        "yes",
        "yes.",
        "yeah",
        "yeah.",
        "yep",
        "yep.",
        "i am here",
        "i'm here",
        "here",
        "conscious",
        "awake",
        "breathing normally",
        "breathing okay",
        "breathing fine",
    }


def _is_negative(message: str) -> bool:
    normalized = " ".join((message or "").strip().lower().split())
    return normalized in {
        "no",
        "no.",
        "no one nearby",
        "nobody nearby",
        "not conscious",
        "unconscious",
        "not breathing",
        "breathing strangely",
        "breathing abnormal",
    }


def _next_canonical_state_from_analysis(
    *,
    current_state: SessionState | None,
    latest_message: str,
    analysis: CommunicationAgentAnalysis,
    previous_state: CommunicationState | None = None,
) -> tuple[SessionState, str, dict[str, object]]:
    """Pick the next canonical state from the latest analyzed responder turn."""

    if current_state in {
        SessionState.REASONING_IN_PROGRESS,
        SessionState.AWAITING_DISPATCH_CONFIRMATION,
        SessionState.EXECUTION_IN_PROGRESS,
        SessionState.COMPLETED,
    }:
        existing_prompt = (
            previous_state.latest_prompt
            if previous_state is not None and previous_state.latest_prompt
            else (analysis.followup_text or "")
        )
        return current_state, existing_prompt, {}

    if current_state in {SessionState.OPENING_CHECK, SessionState.AWAITING_OPENING_RESPONSE, None}:
        conscious_state = True if (analysis.patient_responded or _is_affirmative(latest_message)) else None
        return SessionState.BYSTANDER_CHECK, "Is anyone nearby who can assist?", {"conscious": conscious_state}

    if current_state == SessionState.BYSTANDER_CHECK:
        if _is_affirmative(latest_message) or analysis.bystander_present:
            # If we already confirmed patient is conscious from turn 1, skip to breathing.
            if previous_state and previous_state.conscious:
                return SessionState.BREATHING_CHECK, "Is the patient breathing normally?", {
                    "bystander_present": True,
                    "mode": "bystander",
                }
            return SessionState.CONSCIOUSNESS_CHECK, "Is the patient conscious?", {
                "bystander_present": True,
                "mode": "bystander",
            }
        # No bystander present.
        if previous_state and previous_state.conscious:
            return SessionState.BREATHING_CHECK, "Are you breathing normally?", {
                "bystander_present": False,
                "mode": "patient_only",
            }
        return SessionState.READY_FOR_REASONING, "No one is nearby to help. Checking the situation.", {
            "bystander_present": False,
            "mode": "no_response",
        }

    if current_state == SessionState.CONSCIOUSNESS_CHECK:
        conscious_value = None
        if _is_affirmative(latest_message):
            conscious_value = True
        elif _is_negative(latest_message):
            conscious_value = False
        return SessionState.BREATHING_CHECK, "Is the patient breathing normally?", {
            "conscious": conscious_value,
        }

    if current_state == SessionState.BREATHING_CHECK:
        breathing_value = None
        if _is_affirmative(latest_message):
            breathing_value = True
        elif _is_negative(latest_message) or any(
            fact in {"abnormal_breathing", "not_breathing"} for fact in analysis.extracted_facts
        ):
            breathing_value = False
        
        is_bystander = (previous_state and previous_state.mode == "bystander") or analysis.responder_role == "bystander"
        prompt = "Is the patient bleeding, in pain, or unable to move?" if is_bystander else "Are you bleeding, in pain, or unable to move?"
        
        return SessionState.OPTIONAL_FLAGS_CHECK, prompt, {
            "breathing_normal": breathing_value,
        }

    if current_state == SessionState.OPTIONAL_FLAGS_CHECK:
        return SessionState.READY_FOR_REASONING, analysis.followup_text or "", {}

    if analysis.reasoning_needed:
        return SessionState.READY_FOR_REASONING, analysis.followup_text or "", {}

    return current_state or SessionState.AWAITING_OPENING_RESPONSE, analysis.followup_text or "", {}


def _store_canonical_transition_from_analysis(
    *,
    session_id: str,
    session,
    request: CommunicationTurnRequest,
    analysis: CommunicationAgentAnalysis,
) -> None:
    """Update the additive canonical state model from the latest analyzed reply."""

    current_state = session.state if getattr(session, "state", None) is not None else None
    previous_communication_state = session.canonical_communication_state
    next_state, next_prompt, state_updates = _next_canonical_state_from_analysis(
        current_state=current_state,
        latest_message=request.latest_responder_message,
        analysis=analysis,
        previous_state=previous_communication_state,
    )
    latest_message = " ".join((request.latest_responder_message or "").strip().lower().split())
    normalized_flags: list[str] = []
    if "severe_bleeding" in analysis.extracted_facts or "bleeding" in latest_message:
        normalized_flags.append("bleeding")
    if any(
        fact in {"pain_present", "mild_pain", "chest_pain"} for fact in analysis.extracted_facts
    ) or "pain" in latest_message or "hurts" in latest_message:
        normalized_flags.append("pain")
    if "cannot_stand" in analysis.extracted_facts or any(
        phrase in latest_message for phrase in ["unable to move", "cannot move", "can't move", "cannot stand", "can't stand"]
    ):
        normalized_flags.append("mobility")
    merged_flags = sorted(
        {
            *(previous_communication_state.flags if previous_communication_state is not None else []),
            *normalized_flags,
        }
    )
    mode = str(state_updates.get("mode") or (
        previous_communication_state.mode if previous_communication_state is not None else "patient_only"
    ))
    bystander_present = bool(state_updates.get("bystander_present")) or bool(
        previous_communication_state.bystander_present if previous_communication_state is not None else False
    )
    conscious = (
        state_updates["conscious"]
        if "conscious" in state_updates
        else (previous_communication_state.conscious if previous_communication_state is not None else None)
    )
    breathing_normal = (
        state_updates["breathing_normal"]
        if "breathing_normal" in state_updates
        else (previous_communication_state.breathing_normal if previous_communication_state is not None else None)
    )
    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        state=next_state,
        communication_state=CommunicationState(
            session_id=session_id,
            state=next_state,
            mode=mode,
            responder_role=analysis.responder_role,
            patient_responded=analysis.patient_responded,
            bystander_present=bystander_present,
            conscious=conscious,
            breathing_normal=breathing_normal,
            flags=merged_flags,
            latest_prompt=next_prompt,
            latest_message=request.latest_responder_message.strip(),
            reasoning_call_count=session.reasoning_run_count,
        ),
        execution_state=session.execution_state or ExecutionState(),
    )


def _apply_canonical_prompt_override(
    *,
    session,
    analysis: CommunicationAgentAnalysis,
) -> CommunicationAgentAnalysis:
    """Force early-stage prompts to follow the canonical finite-state flow.

    For the first refactor pass, we only override the communication output for
    the tightly controlled early states. Later execution and post-reasoning
    stages still use the legacy reply composition until those layers are
    migrated as well.
    """

    communication_state = getattr(session, "canonical_communication_state", None)
    if communication_state is None:
        return analysis

    is_bystander = (communication_state.mode == "bystander")
    
    prompt_by_state = {
        SessionState.AWAITING_OPENING_RESPONSE: "A fall is detected, are you okay?",
        SessionState.BYSTANDER_CHECK: "Is anyone nearby who can assist?",
        SessionState.CONSCIOUSNESS_CHECK: "Is the patient conscious?",
        SessionState.BREATHING_CHECK: "Is the patient breathing normally?" if is_bystander else "Are you breathing normally?",
        SessionState.OPTIONAL_FLAGS_CHECK: "Is the patient bleeding, in pain, or unable to move?" if is_bystander else "Are you bleeding, in pain, or unable to move?",
        SessionState.REASONING_IN_PROGRESS: "Analyzing the situation now.",
    }
    prompt = prompt_by_state.get(communication_state.state)
    if not prompt:
        return analysis

    quick_replies_by_state = {
        SessionState.AWAITING_OPENING_RESPONSE: ["Yes", "No", "I need help"],
        SessionState.BYSTANDER_CHECK: ["Yes, someone is here", "No one nearby"],
        SessionState.CONSCIOUSNESS_CHECK: ["Yes", "No", "Not sure", "Can't tell"],
        SessionState.BREATHING_CHECK: ["Yes", "Breathing strangely", "Not really"],
        SessionState.OPTIONAL_FLAGS_CHECK: analysis.quick_replies,
        SessionState.REASONING_IN_PROGRESS: [],
    }
    next_focus_by_state = {
        SessionState.AWAITING_OPENING_RESPONSE: "opening_check",
        SessionState.BYSTANDER_CHECK: "bystander_check",
        SessionState.CONSCIOUSNESS_CHECK: "consciousness",
        SessionState.BREATHING_CHECK: "breathing",
        SessionState.OPTIONAL_FLAGS_CHECK: analysis.next_focus,
        SessionState.REASONING_IN_PROGRESS: "reasoning",
    }

    return analysis.model_copy(
        update={
            "followup_text": prompt,
            "guidance_intent": "question",
            "next_focus": next_focus_by_state.get(communication_state.state, analysis.next_focus),
            "immediate_step": None,
            "quick_replies": quick_replies_by_state.get(communication_state.state, analysis.quick_replies),
        }
    )


def _build_reasoning_decision_from_assessment(session, assessment: FallAssessment) -> ReasoningDecision:
    """Map the canonical structured intake state into the final decision model.

    During the refactor, the legacy assessment pipeline still runs underneath,
    but the final scenario mapping should follow the new canonical structured
    state first so the product behavior matches the final plan.
    """

    communication_state = getattr(session, "canonical_communication_state", None)
    flags_used = list(communication_state.flags) if communication_state is not None else []

    if communication_state is not None:
        if not communication_state.patient_responded and not communication_state.bystander_present:
            return ReasoningDecision(
                scenario="no_response",
                severity="critical",
                action="call_ambulance",
                reason="No response after fall detection timeout.",
                instructions="Emergency help should be dispatched while monitoring continues.",
                confidence=0.93,
                flags_used=flags_used,
            )

        if (
            communication_state.bystander_present
            and communication_state.conscious is False
            and communication_state.breathing_normal is False
        ):
            return ReasoningDecision(
                scenario="CPR",
                severity="critical",
                action="call_ambulance",
                reason="Patient is unconscious and not breathing normally with a bystander present.",
                instructions="Start CPR immediately.",
                confidence=0.95,
                flags_used=flags_used,
            )

        if (
            communication_state.conscious is True
            and communication_state.breathing_normal is True
        ):
            return ReasoningDecision(
                scenario="non_critical",
                severity="low",
                action="contact_family",
                reason="Patient is conscious and breathing normally.",
                instructions="Advise rest, keep monitoring, and notify family for support.",
                confidence=0.9,
                flags_used=flags_used,
            )

    action = assessment.action.recommended
    scenario = "non_critical"
    final_action = "monitor"
    if action in {"dispatch_pending_confirmation", "emergency_dispatch"}:
        scenario = "critical_response"
        final_action = "call_ambulance"
    elif action == "contact_family":
        final_action = "contact_family"

    confidence = assessment.clinical_assessment.action_confidence_score
    if not confidence:
        confidence = assessment.clinical_assessment.clinical_confidence_score

    instructions = (
        assessment.protocol_guidance.communication_message
        or assessment.guidance.primary_message
        or assessment.clinical_assessment.reasoning_summary
    )

    return ReasoningDecision(
        scenario=scenario,
        severity=assessment.clinical_assessment.severity,
        action=final_action,
        reason=assessment.clinical_assessment.reasoning_summary,
        instructions=instructions,
        confidence=confidence,
        flags_used=flags_used,
    )


def _store_canonical_reasoning_started(*, session_id: str, session) -> None:
    """Mark the canonical state model as reasoning in progress."""

    previous_state = session.canonical_communication_state
    reasoning_call_count = (
        (previous_state.reasoning_call_count if previous_state is not None else 0) + 1
    )
    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        state=SessionState.REASONING_IN_PROGRESS,
        communication_state=CommunicationState(
            session_id=session_id,
            state=SessionState.REASONING_IN_PROGRESS,
            mode=previous_state.mode if previous_state is not None else "patient_only",
            responder_role=previous_state.responder_role if previous_state is not None else "unknown",
            patient_responded=previous_state.patient_responded if previous_state is not None else False,
            bystander_present=previous_state.bystander_present if previous_state is not None else False,
            conscious=previous_state.conscious if previous_state is not None else None,
            breathing_normal=previous_state.breathing_normal if previous_state is not None else None,
            flags=list(previous_state.flags) if previous_state is not None else [],
            latest_prompt="Analyzing the situation now.",
            latest_message=previous_state.latest_message if previous_state is not None else "",
            reasoning_call_count=reasoning_call_count,
        ),
        execution_state=session.execution_state or ExecutionState(phase="idle"),
    )


def _store_canonical_reasoning_completed(
    *,
    session_id: str,
    session,
    assessment: FallAssessment,
) -> None:
    """Store the canonical decision model and next state after reasoning completes."""

    decision = _build_reasoning_decision_from_assessment(session, assessment)
    previous_state = session.canonical_communication_state
    next_state = (
        SessionState.AWAITING_DISPATCH_CONFIRMATION
        if decision.action == "call_ambulance"
        else SessionState.EXECUTION_IN_PROGRESS
    )
    dispatch_status = (
        DispatchStatus.PENDING_CONFIRMATION
        if decision.action == "call_ambulance"
        else DispatchStatus.NOT_REQUESTED
    )
    next_prompt = (
        "Emergency help is preparing to be dispatched."
        if next_state == SessionState.AWAITING_DISPATCH_CONFIRMATION
        else decision.instructions
    )
    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        state=next_state,
        communication_state=CommunicationState(
            session_id=session_id,
            state=next_state,
            mode=previous_state.mode if previous_state is not None else "patient_only",
            responder_role=previous_state.responder_role if previous_state is not None else "unknown",
            patient_responded=previous_state.patient_responded if previous_state is not None else False,
            bystander_present=previous_state.bystander_present if previous_state is not None else False,
            conscious=previous_state.conscious if previous_state is not None else None,
            breathing_normal=previous_state.breathing_normal if previous_state is not None else None,
            flags=list(previous_state.flags) if previous_state is not None else [],
            latest_prompt=next_prompt,
            latest_message=previous_state.latest_message if previous_state is not None else "",
            reasoning_call_count=previous_state.reasoning_call_count if previous_state is not None else 1,
        ),
        reasoning_decision=decision,
        execution_state=ExecutionState(
            phase="dispatch_countdown" if next_state == SessionState.AWAITING_DISPATCH_CONFIRMATION else "guidance",
            countdown_seconds=15 if next_state == SessionState.AWAITING_DISPATCH_CONFIRMATION else None,
            family_notified_initial=True,
            family_notified_update=False,
            dispatch_status=dispatch_status,
            guidance_protocol=assessment.protocol_guidance.protocol_key,
            guidance_step_index=0,
        ),
    )


def _build_passive_turn_response(
    *,
    session,
    assessment,
) -> CommunicationTurnResponse:
    """Return current session state without running a new communication turn.

    Existing sessions should remain in a listening state until a new responder
    message arrives. Frontend polling or accidental empty submissions should
    not trigger another communication-agent pass.
    """

    latest_analysis = session.latest_analysis or CommunicationAgentAnalysis(
        followup_text=(
            session.canonical_communication_state.latest_prompt
            if session.canonical_communication_state is not None
            else ""
        ),
        responder_role="unknown",
        communication_target="unknown",
        patient_responded=False,
        bystander_present=False,
        bystander_can_help=False,
        extracted_facts=[],
        resolved_fact_keys=[],
        open_question_key=None,
        open_question_resolved=False,
        conversation_state_summary="",
        reasoning_needed=False,
        reasoning_reason="",
        should_surface_execution_update=False,
        guidance_intent="question",
        next_focus="general_check",
        immediate_step=None,
        quick_replies=[],
    )

    return CommunicationTurnResponse(
        session_id=session.session_id,
        state=session.state,
        canonical_communication_state=session.canonical_communication_state,
        reasoning_decision=session.reasoning_decision,
        execution_state=session.execution_state,
        interaction=session.interaction_summary or _build_default_opening_interaction(),
        communication_analysis=latest_analysis,
        reasoning_invoked=False,
        reasoning_status=session.reasoning_status,
        reasoning_run_count=session.reasoning_run_count,
        reasoning_reason=session.reasoning_reason,
        reasoning_error=session.reasoning_error,
        assistant_message=(
            session.canonical_communication_state.latest_prompt
            if session.canonical_communication_state is not None
            else ""
        ),
        assistant_question=(
            session.canonical_communication_state.latest_prompt
            if session.canonical_communication_state is not None
            and session.canonical_communication_state.latest_prompt
            else None
        ),
        guidance_steps=[],
        quick_replies=latest_analysis.quick_replies,
        assessment=assessment,
        execution_updates=session.execution_updates,
        action_states=session.action_states,
        transcript_append=[],
        reasoning_runs=session.reasoning_runs,
    )


async def start_fall_conversation_session(
    request: CommunicationSessionStartRequest,
) -> CommunicationTurnResponse:
    """Create a canonical fall session and return the deterministic opening prompt."""

    session = fall_session_store.create_session(
        event=request.event,
        vitals=request.vitals,
        interaction_input=request.interaction,
    )
    _bootstrap_canonical_opening_state(session_id=session.session_id)
    session = fall_session_store.get_session(session.session_id) or session
    logger.info(
        "[Session %s] Started via session-start | user=%s motion=%s",
        _short_session_id(session.session_id),
        request.event.user_id,
        request.event.motion_state,
    )
    return _build_opening_turn_response(session=session)


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


def _rehydrate_session_from_incident(incident, session_id: str) -> FallSessionRecord:
    """Map a persistent Incident record back into the in-memory FallSessionRecord.

    This allows the backend to recover session state across multiple workers or
    after a process restart, provided the incident record was already created.
    """
    trigger = incident.simulation_trigger or {}
    event = FallEvent(
        user_id=incident.patient_id,
        motion_state=trigger.get("motion_state", "stable"),
        confidence=trigger.get("confidence", 0.0),
        vitals_snapshot=trigger.get("vitals_snapshot"),
        detection_summary=trigger.get("detection_summary"),
        video_metadata=incident.video_metadata,
    )

    interaction = InteractionInput(
        patient_id=incident.patient_id,
        bystander_present=trigger.get("interaction", {}).get("bystander_present", False),
    )

    # Map status to session state (they share similar values but are different enums)
    try:
        session_state = SessionState(incident.status.value)
    except (ValueError, AttributeError):
        session_state = SessionState.IDLE

    return FallSessionRecord(
        session_id=session_id,
        event=event,
        state=session_state,
        canonical_communication_state=(
            CommunicationState.model_validate(incident.canonical_communication_state)
            if incident.canonical_communication_state
            else None
        ),
        reasoning_decision=(
            ReasoningDecision.model_validate(incident.reasoning_decision)
            if incident.reasoning_decision
            else None
        ),
        execution_state=(
            ExecutionState.model_validate(incident.execution_state)
            if incident.execution_state
            else None
        ),
        interaction_input=interaction,
        conversation_history=[
            ConversationMessage.model_validate(m) for m in incident.conversation_history
        ],
        execution_updates=[
            ExecutionUpdate.model_validate(u) for u in incident.execution_updates
        ],
        action_states=[
            ActionStateSummary.model_validate(s) for s in incident.action_states
        ],
        reasoning_runs=[
            ReasoningRunSummary.model_validate(r) for r in incident.reasoning_runs
        ],
        version=1,
    )

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
    if session is None and request.session_id:
        incident = get_incident_by_realtime_session_id(request.session_id)
        if incident:
            logger.info(
                "[Session %s] Not in memory but found incident %s | Rehydrating",
                _short_session_id(request.session_id),
                incident.incident_id,
            )
            hydrated_record = _rehydrate_session_from_incident(incident, request.session_id)
            session = fall_session_store.upsert_session_record(hydrated_record)

    if session is None:
        session = fall_session_store.create_session(
            event=request.event,
            vitals=request.vitals,
            interaction_input=request.interaction,
        )
        _bootstrap_canonical_opening_state(session_id=session.session_id)
        session = fall_session_store.get_session(session.session_id) or session
        logger.info(
            "[Session %s] Started | user=%s motion=%s",
            _short_session_id(session.session_id),
            request.event.user_id,
            request.event.motion_state,
        )
        if not request.latest_responder_message.strip():
            logger.info(
                "[Session %s] Returning canonical opening prompt",
                _short_session_id(session.session_id),
            )
            return _build_opening_turn_response(session=session)
    else:
        updated_session = fall_session_store.update_context(
            session_id=session.session_id,
            event=request.event,
            vitals=request.vitals,
            interaction_input=request.interaction,
        )
        session = updated_session or session

    if request.session_id and not request.latest_responder_message.strip():
        logger.info(
            "[Session %s] Passive turn received | returning current state without running communication",
            _short_session_id(session.session_id),
        )
        current_session = fall_session_store.get_session(session.session_id) or session
        existing_assessment = current_session.latest_assessment or request.previous_assessment
        return _build_passive_turn_response(
            session=current_session,
            assessment=existing_assessment,
        )

    existing_assessment = session.latest_assessment or request.previous_assessment
    conversation_history = session.conversation_history or request.conversation_history

    if _is_no_response_message(request.latest_responder_message):
        logger.info(
            "[Session %s] No-response timeout detected | triggering hardcoded dispatch flow",
            _short_session_id(session.session_id),
        )
        fallback_analysis = session.latest_analysis or CommunicationAgentAnalysis(
            followup_text=(
                "Patient appears to be unconscious. "
                "I am skipping further communication checks, dispatching emergency support, "
                "and notifying the family now."
            ),
            responder_role="no_response",
            communication_target="bystander",
            patient_responded=False,
            bystander_present=False,
            bystander_can_help=False,
            extracted_facts=["no_response", "possible_unconsciousness"],
            guidance_intent="instruction",
            next_focus="emergency_dispatch",
            reasoning_needed=False,
            reasoning_reason="No response timeout triggered the unconsciousness safety path.",
            quick_replies=[],
        )
        responder_reasoning_version = session.reasoning_input_version
        user_message = ConversationMessage(
            role="no_response",
            text=request.latest_responder_message.strip(),
            reasoning_input_version=responder_reasoning_version,
            comm_reasoning_required=False,
            comm_reasoning_reason="No response timeout triggered the unconsciousness safety path.",
        )
        fall_session_store.append_messages(session.session_id, [user_message])

        final_analysis = fallback_analysis.model_copy(
            update={
                "followup_text": (
                    "Patient appears to be unconscious. "
                    "I am skipping further communication checks, dispatching emergency support, "
                    "and notifying the family now."
                ),
                "responder_role": "no_response",
                "communication_target": "bystander",
                "patient_responded": False,
                "guidance_intent": "instruction",
                "next_focus": "emergency_dispatch",
                "reasoning_needed": False,
                "reasoning_reason": "No response timeout triggered the unconsciousness safety path.",
                "quick_replies": [],
            }
        )
        enriched_interaction = request.interaction.model_copy(
            update={
                "patient_response_status": "no_response",
                "bystander_available": True,
                "message_text": request.latest_responder_message,
                "new_fact_keys": ["no_response", "possible_unconsciousness"],
                "responder_mode_hint": "no_response",
                "no_response_timeout": True,
            }
        )
        fall_session_store.update_context(
            session_id=session.session_id,
            event=request.event,
            vitals=request.vitals,
            interaction_input=enriched_interaction,
            bump_reasoning_version=False,
        )
        interaction = build_interaction_summary(
            interaction=enriched_interaction,
            patient_answers=_answers_from_turn_message(request.latest_responder_message, "patient"),
            recommended_action=existing_assessment.action.recommended if existing_assessment else None,
        )
        assistant_message = ConversationMessage(
            role="assistant",
            text=final_analysis.followup_text,
            reasoning_input_version=responder_reasoning_version,
        )
        fall_session_store.append_messages(session.session_id, [assistant_message])
        fall_session_store.store_turn_state(
            session_id=session.session_id,
            interaction_summary=interaction,
            latest_analysis=final_analysis,
        )
        request_emergency_dispatch_confirmation(
            session.session_id,
            reason="No response was detected after the communication agent waited for a reply.",
            detail="Emergency dispatch is pending confirmation because the patient appears unconscious.",
        )
        request_contact_family_action(
            session.session_id,
            reason="The patient appears unconscious and emergency support is being escalated.",
            detail="Family contact was triggered because the patient appears unconscious.",
            message_text="Emergency escalation update: the patient appears unconscious and emergency help is being dispatched.",
        )
        latest_session = fall_session_store.get_session(session.session_id) or session
        return CommunicationTurnResponse(
            session_id=session.session_id,
            state=latest_session.state,
            canonical_communication_state=latest_session.canonical_communication_state,
            reasoning_decision=latest_session.reasoning_decision,
            execution_state=latest_session.execution_state,
            interaction=interaction,
            communication_analysis=final_analysis,
            reasoning_invoked=False,
            reasoning_status=latest_session.reasoning_status,
            reasoning_run_count=latest_session.reasoning_run_count,
            reasoning_reason=latest_session.reasoning_reason,
            reasoning_error=latest_session.reasoning_error,
            assistant_message=final_analysis.followup_text,
            assistant_question=None,
            guidance_steps=[],
            quick_replies=[],
            assessment=latest_session.latest_assessment or existing_assessment,
            execution_updates=latest_session.execution_updates,
            action_states=latest_session.action_states,
            transcript_append=[assistant_message],
            reasoning_runs=latest_session.reasoning_runs,
        )

    # Consume pending context from background reasoning (cleared after read)
    pending_reasoning_context = fall_session_store.consume_pending_context(
        session.session_id
    )

    patient_profile = load_user_profile(request.event.user_id)
    runtime = get_fall_agent_runtime()
    analysis = await runtime.analyze_communication_turn(
        event=request.event,
        vitals=request.vitals,
        patient_profile=patient_profile,
        conversation_history=conversation_history,
        latest_message=request.latest_responder_message,
        previous_assessment=existing_assessment,
        previous_analysis=session.latest_analysis,
        pending_reasoning_context=pending_reasoning_context,
        execution_updates=session.execution_updates,
        acknowledged_reasoning_triggers=session.reasoning_triggered_fact_keys,
    )
    logger.info(
        "[Session %s] Communication analyzed | role=%s target=%s reasoning_needed=%s execution_signal=%s message=\"%s\"",
        _short_session_id(session.session_id),
        analysis.responder_role,
        analysis.communication_target,
        analysis.reasoning_needed,
        analysis.execution_signal or "none",
        _clip_message(request.latest_responder_message or "<session start>"),
    )
    signal = (analysis.execution_signal or "none").strip().lower()
    if signal in CPR_JOIN_SIGNALS and session.reasoning_status == "pending" and not _has_ready_cpr_guidance(session):
        logger.info(
            "[Session %s] Waiting briefly for CPR guidance | signal=%s timeout=%.1fs",
            _short_session_id(session.session_id),
            signal,
            CPR_GUIDANCE_JOIN_TIMEOUT_SECONDS,
        )
        await _wait_for_cpr_guidance_ready(
            session.session_id,
            timeout_seconds=CPR_GUIDANCE_JOIN_TIMEOUT_SECONDS,
        )
        session = fall_session_store.get_session(session.session_id) or session

    _advance_execution_guidance_if_needed(
        session_id=session.session_id,
        session=session,
        analysis=analysis,
        latest_message=request.latest_responder_message,
    )
    session = fall_session_store.get_session(session.session_id) or session
    _store_canonical_transition_from_analysis(
        session_id=session.session_id,
        session=session,
        request=request,
        analysis=analysis,
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

    final_analysis = analysis.model_copy(
        update={
            "reasoning_needed": analysis.reasoning_needed,
            "reasoning_reason": analysis.reasoning_reason,
        }
    )
    current_session = fall_session_store.get_session(session.session_id) or session
    final_analysis, announced_execution_types = _apply_execution_status_override(
        analysis=final_analysis,
        execution_updates=current_session.execution_updates,
        announced_execution_types=current_session.announced_execution_types,
        assessment=current_session.latest_assessment or existing_assessment,
    )
    final_analysis = _apply_canonical_prompt_override(
        session=current_session,
        analysis=final_analysis,
    )
    final_analysis = _apply_execution_guidance_prompt(
        session=current_session,
        analysis=final_analysis,
    )
    final_analysis = _apply_cpr_guidance_hold_if_needed(
        session=current_session,
        analysis=final_analysis,
    )

    reasoning_needed = final_analysis.reasoning_needed
    is_duplicate_human_turn = (
        bool(request.latest_responder_message.strip())
        and _normalized_message_key(request.latest_responder_message) == _latest_human_message_key(conversation_history)
    )
    canonical_reasoning_ready = current_session.state == SessionState.READY_FOR_REASONING
    reasoning_requested = canonical_reasoning_ready and not is_duplicate_human_turn
    if reasoning_requested:
        final_analysis = final_analysis.model_copy(
            update={
                "followup_text": "Analyzing the situation now.",
                "guidance_intent": "instruction",
                "next_focus": "reasoning",
                "immediate_step": None,
                "quick_replies": [],
            }
        )
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
            reason=final_analysis.reasoning_reason or interaction.reasoning_refresh.reason or "Canonical intake is complete.",
        )
        logger.info(
            "[Session %s] Reasoning %s | reason=%s",
            _short_session_id(session.session_id),
            "queued" if should_start_now else "already pending",
            final_analysis.reasoning_reason or interaction.reasoning_refresh.reason or "none",
        )
        _store_canonical_reasoning_started(
            session_id=session.session_id,
            session=current_session,
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
    latest_assessment = latest_session.latest_assessment or existing_assessment
    latest_interaction = latest_session.interaction_summary or interaction
    logger.info(
        "[Session %s] Response snapshot | state=%s protocol=%s phase=%s step_index=%s guidance_steps=%d current_guidance=%s",
        _short_session_id(session.session_id),
        latest_session.state.value if hasattr(latest_session.state, "value") else latest_session.state,
        (
            latest_assessment.protocol_guidance.protocol_key
            if latest_assessment is not None and latest_assessment.protocol_guidance is not None
            else "none"
        ),
        latest_session.execution_state.phase if latest_session.execution_state is not None else "none",
        (
            latest_session.execution_state.guidance_step_index
            if latest_session.execution_state is not None
            else "none"
        ),
        len(_execution_guidance_steps(latest_session)),
        _current_guidance_steps_for_response(latest_session, final_analysis),
    )

    return CommunicationTurnResponse(
        session_id=session.session_id,
        state=latest_session.state,
        canonical_communication_state=latest_session.canonical_communication_state,
        reasoning_decision=latest_session.reasoning_decision,
        execution_state=latest_session.execution_state,
        interaction=latest_interaction,
        communication_analysis=final_analysis,
        reasoning_invoked=reasoning_requested,
        reasoning_status=latest_session.reasoning_status,
        reasoning_run_count=latest_session.reasoning_run_count,
        reasoning_reason=latest_session.reasoning_reason,
        reasoning_error=latest_session.reasoning_error,
        assistant_message=final_analysis.followup_text,
        assistant_question=None,
        guidance_steps=_current_guidance_steps_for_response(latest_session, final_analysis),
        quick_replies=final_analysis.quick_replies,
        assessment=latest_assessment,
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
            communication_state=session.canonical_communication_state,
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

        # Summarize reasoning for the communication agent's next turn
        pending_context = _summarize_for_comm_agent(assessment)

        should_rerun = fall_session_store.complete_reasoning(
            session_id=session_id,
            processed_version=session.reasoning_active_version,
            assessment=assessment,
            assistant_message=None,
            execution_updates=execution_updates,
            pending_reasoning_context=pending_context,
        )
        refreshed_session = fall_session_store.get_session(session_id)
        if refreshed_session is not None:
            _store_canonical_reasoning_completed(
                session_id=session_id,
                session=refreshed_session,
                assessment=assessment,
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
        runtime = get_fall_agent_runtime()
        if runtime.requires_execution_grounding(
            action=assessment.action.recommended,
            bystander_actions=bystander_actions,
        ):
            logger.info(
                "[Session %s] Phase 2: Execution agent starting | action=%s",
                _short_session_id(session_id),
                assessment.action.recommended,
            )
            patient_profile = load_user_profile(session.event.user_id)
            execution_guidance = await runtime.run_execution_grounding(
                action=assessment.action.recommended,
                clinical_assessment=assessment.clinical_assessment,
                patient_profile=patient_profile,
                patient_answers=patient_answers,
            )
            refreshed_session = fall_session_store.get_session(session_id)
            if refreshed_session is not None:
                _store_execution_guidance_assessment(
                    session_id=session_id,
                    session=refreshed_session,
                    guidance=execution_guidance,
                )
                refreshed_session = fall_session_store.get_session(session_id) or refreshed_session
                _store_execution_guidance_state(
                    session_id=session_id,
                    session=refreshed_session,
                    guidance=execution_guidance,
                )
            execution_context = _summarize_execution_guidance(execution_guidance)
            if execution_context:
                fall_session_store.store_pending_context(
                    session_id=session_id,
                    context=(
                        f"{pending_context} | {execution_context}"
                        if pending_context
                        else execution_context
                    ),
                )
            logger.info(
                "[Session %s] Phase 2 complete | scenario=%s protocol=%s",
                _short_session_id(session_id),
                execution_guidance.scenario or "none",
                execution_guidance.protocol_key or "none",
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
        state=session.state,
        canonical_communication_state=session.canonical_communication_state,
        reasoning_decision=session.reasoning_decision,
        execution_state=session.execution_state,
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

