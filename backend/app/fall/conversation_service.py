"""Session-based fall conversation service."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import BackgroundTasks

from agents.communication.session_agent import analyze_communication_turn
from agents.shared.config import get_genai_client
from app.fall.assessment_service import build_interaction_summary, load_user_profile, run_fall_assessment
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


def _short_session_id(session_id: str | None) -> str:
    if not session_id:
        return "unknown"
    return session_id.replace("phase4-", "")[:8]


def _clip_message(text: str, limit: int = 80) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _answers_from_turn_message(message_text: str, target: str) -> list[PatientAnswer]:
    normalized_text = (message_text or "").strip()
    if not normalized_text:
        return []
    question_id = "bystander_turn" if target == "bystander" else "patient_turn"
    return [PatientAnswer(question_id=question_id, answer=normalized_text)]


def _answers_from_conversation_history(conversation_history: list[ConversationMessage]) -> list[PatientAnswer]:
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
    if assessment is None:
        return analysis

    immediate_step = analysis.immediate_step
    if immediate_step is None and assessment.guidance.steps:
        immediate_step = assessment.guidance.steps[0]

    if analysis.followup_text.strip():
        return analysis.model_copy(update={"immediate_step": immediate_step})

    primary_message = (assessment.guidance.primary_message or "").strip()
    if primary_message:
        return analysis.model_copy(
            update={
                "followup_text": primary_message,
                "immediate_step": immediate_step,
            }
        )
    return analysis.model_copy(update={"immediate_step": immediate_step})


def _apply_assessment_handoff_to_analysis(
    *,
    analysis: CommunicationAgentAnalysis,
    assessment: FallAssessment | None,
) -> CommunicationAgentAnalysis:
    if assessment is None:
        return analysis

    handoff = assessment.communication_handoff
    if not handoff.primary_message and not handoff.next_question and not handoff.immediate_step:
        return analysis

    followup_parts: list[str] = []
    if handoff.primary_message:
        followup_parts.append(handoff.primary_message.strip())
    if handoff.ask_followup and handoff.next_question:
        followup_parts.append(handoff.next_question.strip())

    guidance_intent = {
        "urgent_instruction": "instruction",
        "status_update": "reassure",
        "instruction": "instruction",
        "reassure": "reassure",
        "question": "question",
    }.get(handoff.mode, analysis.guidance_intent)

    immediate_step = handoff.immediate_step or analysis.immediate_step
    followup_text = " ".join(part for part in followup_parts if part).strip() or analysis.followup_text

    return analysis.model_copy(
        update={
            "followup_text": followup_text,
            "guidance_intent": guidance_intent,
            "next_focus": handoff.next_focus or analysis.next_focus,
            "immediate_step": immediate_step,
            "quick_replies": handoff.quick_replies or analysis.quick_replies,
        }
    )


def build_execution_updates(assessment: FallAssessment) -> list[ExecutionUpdate]:
    updates: list[ExecutionUpdate] = []

    if assessment.action.recommended == "emergency_dispatch":
        updates.append(
            ExecutionUpdate(
                type="emergency_dispatch",
                status="completed",
                detail="Emergency dispatch was triggered for this incident.",
            )
        )
    elif assessment.action.recommended == "dispatch_pending_confirmation":
        updates.append(
            ExecutionUpdate(
                type="emergency_dispatch",
                status="pending_confirmation",
                detail="Emergency dispatch is being prepared and is waiting on confirmation signals.",
            )
        )

    for action in assessment.response_plan.notification_actions:
        if action.type == "inform_family":
            updates.append(
                ExecutionUpdate(
                    type="inform_family",
                    status="queued",
                    detail="Family notification was queued in the MVP flow for support.",
                )
            )

    if not updates and assessment.action.recommended == "monitor":
        updates.append(
            ExecutionUpdate(
                type="monitor",
                status="active",
                detail="The session remains in monitoring mode with no external escalation yet.",
            )
        )

    return updates


def _apply_execution_context_to_reply(
    *,
    session_id: str,
    analysis: CommunicationAgentAnalysis,
    execution_updates: list[ExecutionUpdate],
    assessment: FallAssessment | None = None,
    conversation_history: list[ConversationMessage] | None = None,
) -> CommunicationAgentAnalysis:
    effective_updates = [item.model_copy(deep=True) for item in execution_updates]

    if assessment is not None:
        has_family_update = any(item.type == "inform_family" for item in effective_updates)
        if not has_family_update:
            for action in assessment.response_plan.notification_actions:
                if action.type == "inform_family":
                    effective_updates.append(
                        ExecutionUpdate(
                            type="inform_family",
                            status="queued",
                            detail="Family notification was queued in the MVP flow for support.",
                        )
                    )
                    break

    if not effective_updates:
        return analysis

    updated_analysis = analysis
    announced_types: list[str] = []
    recent_assistant_mentions_family = any(
        message.role == "assistant" and "family" in message.text.lower()
        for message in (conversation_history or [])[-4:]
    )

    for update in effective_updates:
        if update.type != "inform_family" or update.status not in {"queued", "completed"}:
            continue

        target_key = analysis.communication_target if analysis.communication_target in {"patient", "bystander"} else "general"
        announcement_key = f"{update.type}:{target_key}"
        if recent_assistant_mentions_family:
            continue

        if updated_analysis.communication_target == "patient":
            followup = "I have informed your family. Tell me if your pain or breathing changes."
        elif updated_analysis.communication_target == "bystander":
            followup = "I have informed the family. Stay with them and tell me if anything changes."
        else:
            followup = "I have informed the family for support. Tell me if anything changes."

        updated_analysis = updated_analysis.model_copy(
            update={
                "followup_text": followup,
                "guidance_intent": "reassure",
            }
        )
        announced_types.append(announcement_key)
        break

    for execution_type in announced_types:
        fall_session_store.mark_execution_announced(
            session_id=session_id,
            execution_type=execution_type,
        )

    return updated_analysis


async def run_fall_conversation_turn(
    request: CommunicationTurnRequest,
    *,
    background_tasks: Optional[BackgroundTasks] = None,
) -> CommunicationTurnResponse:
    """Run one session-based communication turn for an active fall incident."""
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
            "reasoning_needed": analysis.reasoning_needed or interaction.reasoning_refresh.required,
            "reasoning_reason": analysis.reasoning_reason if analysis.reasoning_reason else interaction.reasoning_refresh.reason,
        }
    )
    final_analysis = _apply_assessment_handoff_to_analysis(
        analysis=final_analysis,
        assessment=existing_assessment,
    )
    current_session = fall_session_store.get_session(session.session_id) or session
    final_analysis = _apply_execution_context_to_reply(
        session_id=session.session_id,
        analysis=final_analysis,
        execution_updates=current_session.execution_updates,
        assessment=current_session.latest_assessment or existing_assessment,
        conversation_history=current_session.conversation_history,
    )

    responder_messages: list[ConversationMessage] = []
    if request.latest_responder_message.strip():
        responder_messages.append(
            ConversationMessage(
                role=_message_role_from_analysis(analysis),
                text=request.latest_responder_message.strip(),
            )
        )
    if responder_messages:
        fall_session_store.append_messages(session.session_id, responder_messages)

    assistant_message = ConversationMessage(role="assistant", text=final_analysis.followup_text)
    if assistant_message.text.strip():
        fall_session_store.append_messages(session.session_id, [assistant_message])
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

    reasoning_needed = final_analysis.reasoning_needed
    should_bootstrap_reasoning = existing_assessment is None
    reasoning_requested = reasoning_needed or should_bootstrap_reasoning

    if reasoning_requested:
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
                asyncio.create_task(_run_session_reasoning_refresh(session.session_id))
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
        reasoning_reason=latest_session.reasoning_reason,
        reasoning_error=latest_session.reasoning_error,
        assistant_message=final_analysis.followup_text,
        assistant_question=None,
        guidance_steps=[final_analysis.immediate_step] if final_analysis.immediate_step else [],
        quick_replies=final_analysis.quick_replies,
        assessment=existing_assessment,
        execution_updates=latest_session.execution_updates,
        transcript_append=[assistant_message] if assistant_message.text.strip() else [],
    )


async def _run_session_reasoning_refresh(session_id: str) -> None:
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
        assessment = await run_fall_assessment(
            event=session.event,
            vitals=session.vitals,
            patient_answers=patient_answers,
            interaction=session.interaction_input,
            trigger_dispatch=True,
            background_tasks=None,
        )
        should_rerun = fall_session_store.complete_reasoning(
            session_id=session_id,
            processed_version=session.reasoning_active_version,
            assessment=assessment,
            execution_updates=build_execution_updates(assessment),
        )
        logger.info(
            "[Session %s] Background reasoning complete | severity=%s action=%s processed_version=%s rerun=%s",
            _short_session_id(session_id),
            assessment.clinical_assessment.severity,
            assessment.action.recommended,
            session.reasoning_active_version,
            should_rerun,
        )
        if should_rerun:
            asyncio.create_task(_run_session_reasoning_refresh(session_id))
    except Exception as exc:
        logger.exception("[Session %s] Background reasoning failed", _short_session_id(session_id))
        should_retry = fall_session_store.fail_reasoning(
            session_id=session_id,
            error_message=str(exc),
        )
        if should_retry:
            asyncio.create_task(_run_session_reasoning_refresh(session_id))


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
        reasoning_reason=session.reasoning_reason,
        reasoning_error=session.reasoning_error,
        interaction=session.interaction_summary,
        latest_analysis=session.latest_analysis,
        assessment=session.latest_assessment,
        execution_updates=session.execution_updates,
        conversation_history=session.conversation_history,
    )

