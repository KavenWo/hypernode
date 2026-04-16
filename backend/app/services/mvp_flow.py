"""Centralized MVP backend flow for fall triage.

This module is the single place to follow the hackathon MVP path:

1. Detect a fall event.
2. Ask 2-3 triage questions.
3. Collect patient or bystander answers.
4. Run clinical reasoning once.
5. Return severity, action, and instructions.
6. If needed, trigger the emergency dispatch stub layer.

Older modules still exist in the repo, but this service is the primary path
the API should use so the prototype remains easy to understand.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from fastapi import BackgroundTasks

from agents.communication.interaction_policy import (
    InteractionContext,
    choose_interaction_target,
    should_refresh_reasoning,
)
from agents.communication.session_agent import analyze_communication_turn
from agents.bystander.retrieval_engine import run_phase2_retrieval
from agents.bystander.retrieval_policy import build_phase2_retrieval_plan
from agents.bystander.guidance_normalizer import normalize_guidance_from_buckets
from agents.reasoning.clinical_agent import assess_clinical_severity
from agents.sentinel.vital_agent import inspect_vitals
from agents.sentinel.vision_agent import inspect_fall_event
from agents.shared.config import get_genai_client
from agents.shared.schemas import (
    ActionSummary,
    AuditSummary,
    ClinicalAssessmentSummary,
    CommunicationAgentAnalysis,
    CommunicationSessionStateResponse,
    CommunicationTurnRequest,
    CommunicationTurnResponse,
    ConversationMessage,
    DetectionSummary,
    ExecutionUpdate,
    FallEvent,
    GroundingSummary,
    GuidanceSummary,
    InteractionInput,
    InteractionSummary,
    MvpAssessment,
    PatientAnswer,
    ReasoningRefreshSummary,
    TriageQuestionSet,
    UserMedicalProfile,
    VitalSigns,
)
from agents.triage.question_agent import generate_triage_questions
from app.services.session_store import mvp_session_store
from db.firebase_client import load_patient_profile
from app.api.routes.emergency import SeverityLevel as EmergencySeverityLevel
from app.api.routes.emergency import trigger_emergency

logger = logging.getLogger(__name__)

FALLBACK_REASONING_PREFIX = "Fallback assessment used because the live reasoning model was unavailable."


def _short_session_id(session_id: str | None) -> str:
    if not session_id:
        return "unknown"
    return session_id.replace("phase4-", "")[:8]


def _clip_message(text: str, limit: int = 80) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def load_user_profile(user_id: str) -> UserMedicalProfile:
    """Load the patient profile once and normalize it to the shared schema."""
    return UserMedicalProfile.model_validate(load_patient_profile(user_id).model_dump())


def _confidence_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def build_guidance_query(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    severity_hint: str | None = None,
) -> str:
    """Choose the primary query from the lightweight Phase 2 retrieval policy."""
    retrieval_plan = build_phase2_retrieval_plan(
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        severity_hint=severity_hint,
    )
    return retrieval_plan["primary_query"]


def get_runtime_status() -> dict:
    """Expose lightweight runtime state for the frontend MVP tester."""
    vertex_project = os.getenv("VERTEX_AI_SEARCH_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    vertex_engine = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")

    return {
        "backend_ok": True,
        "gemini_configured": bool(gemini_key and gemini_key != "your_api_key_here"),
        "vertex_search_configured": bool(vertex_project and vertex_engine),
        "vertex_project": vertex_project or "",
        "vertex_engine": vertex_engine or "",
    }


def get_mvp_fall_questions(
    event: FallEvent,
    vitals: VitalSigns | None = None,
    interaction: InteractionInput | None = None,
) -> TriageQuestionSet:
    """Return the 2-3 questions the frontend should ask before reasoning."""
    patient_profile = load_user_profile(event.user_id)
    interaction_summary = _build_interaction_summary(
        interaction=interaction,
        patient_answers=[],
        recommended_action=None,
    )
    return generate_triage_questions(
        event=event,
        patient_profile=patient_profile,
        vitals=vitals,
        interaction=interaction_summary,
    )


def _should_trigger_dispatch(action: str) -> bool:
    """Only the emergency action path should fan out into dispatch stubs."""
    return action == "emergency_dispatch"


def _event_validity(event: FallEvent, vision_assessment) -> str:
    if vision_assessment.fall_detected and event.confidence_score >= 0.75:
        return "likely_true"
    if event.confidence_score >= 0.4:
        return "uncertain"
    return "weak_signal"


def _responder_mode(patient_answers: list[PatientAnswer]) -> str:
    answer_text = " ".join(answer.answer.lower() for answer in patient_answers)
    if not patient_answers:
        return "no_response"
    if "bystander" in answer_text or "he is" in answer_text or "she is" in answer_text or "the patient" in answer_text:
        return "bystander"
    return "patient"


def _serious_action_required(recommended_action: str | None) -> bool:
    return recommended_action in {
        "dispatch_pending_confirmation",
        "emergency_dispatch",
        "contact_family",
        "urgent_monitoring",
    }


def _extract_fact_keys_from_answers(patient_answers: list[PatientAnswer]) -> list[str]:
    answer_text = " ".join(answer.answer.lower() for answer in patient_answers)
    facts: list[str] = []
    signal_map = {
        "abnormal_breathing": ["breathing strangely", "abnormal breathing", "gasping"],
        "not_breathing": ["not breathing", "stopped breathing"],
        "severe_bleeding": ["heavy bleeding", "severe bleeding", "bleeding a lot"],
        "unresponsive": ["not responding", "unresponsive", "won't wake up"],
        "lost_consciousness": ["lost consciousness", "passed out", "blacked out"],
        "head_strike": ["hit my head", "hit their head", "head injury"],
        "chest_pain": ["chest pain"],
        "new_confusion": ["confused", "new confusion"],
    }
    for fact_key, keywords in signal_map.items():
        if any(keyword in answer_text for keyword in keywords):
            facts.append(fact_key)
    return facts


def _build_interaction_summary(
    *,
    interaction: InteractionInput | None,
    patient_answers: list[PatientAnswer],
    recommended_action: str | None,
) -> InteractionSummary:
    responder_mode_hint = interaction.responder_mode_hint if interaction else None
    inferred_mode = responder_mode_hint or _responder_mode(patient_answers)
    context = InteractionContext(
        patient_response_status=(interaction.patient_response_status if interaction else "unknown"),
        bystander_available=bool(interaction and interaction.bystander_available),
        bystander_can_help=bool(interaction and interaction.bystander_can_help),
        serious_action_required=_serious_action_required(recommended_action),
        testing_assume_bystander=bool(interaction and interaction.testing_assume_bystander),
        active_execution_action=interaction.active_execution_action if interaction else None,
        responder_mode_hint=responder_mode_hint,
    )
    interaction_decision = choose_interaction_target(context)

    fact_keys = (
        interaction.new_fact_keys
        if interaction and interaction.new_fact_keys
        else _extract_fact_keys_from_answers(patient_answers)
    )
    message_text = interaction.message_text if interaction and interaction.message_text else " ".join(
        answer.answer for answer in patient_answers
    )
    refresh_decision = should_refresh_reasoning(
        message_text=message_text,
        new_fact_keys=fact_keys,
        previous_action=recommended_action,
        responder_mode_changed=bool(interaction and interaction.responder_mode_changed),
        contradiction_detected=bool(interaction and interaction.contradiction_detected),
        no_response_timeout=bool(interaction and interaction.no_response_timeout),
        active_execution_action=interaction.active_execution_action if interaction else None,
    )

    if inferred_mode == "no_response" and interaction_decision.communication_target == "patient":
        interaction_decision = choose_interaction_target(
            context.model_copy(update={"patient_response_status": "no_response"})
        )

    return InteractionSummary(
        communication_target=interaction_decision.communication_target,
        responder_mode=interaction_decision.responder_mode,
        guidance_style=interaction_decision.guidance_style,
        interaction_mode=interaction_decision.interaction_mode,
        rationale=interaction_decision.rationale,
        reasoning_refresh=ReasoningRefreshSummary(
            required=refresh_decision.refresh_required,
            reason=refresh_decision.reason,
            priority=refresh_decision.priority,
        ),
        testing_assume_bystander=bool(interaction and interaction.testing_assume_bystander),
    )


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
    assessment: MvpAssessment | None,
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


def _apply_execution_context_to_reply(
    *,
    session_id: str,
    analysis: CommunicationAgentAnalysis,
    execution_updates: list[ExecutionUpdate],
    assessment: MvpAssessment | None = None,
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
        mvp_session_store.mark_execution_announced(
            session_id=session_id,
            execution_type=execution_type,
        )

    return updated_analysis


def _status_for_action(action: str) -> str:
    if action == "dispatch_pending_confirmation":
        return "dispatch_pending_confirmation"
    if action == "emergency_dispatch":
        return "dispatch_confirmed"
    if action == "contact_family":
        return "triage_in_progress"
    return "guidance_active"


def _map_assessment_severity_to_dispatch(severity: str) -> EmergencySeverityLevel:
    """Bridge the reasoning severity labels to the dispatch layer labels."""
    normalized = severity.lower().strip()
    if normalized in {"critical", "high"}:
        return EmergencySeverityLevel.RED
    if normalized == "medium":
        return EmergencySeverityLevel.AMBER
    return EmergencySeverityLevel.YELLOW


def _build_execution_updates(assessment: MvpAssessment) -> list[ExecutionUpdate]:
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


def _build_dispatch_ai_summary(
    *,
    assessment: MvpAssessment,
    patient_answers: list[PatientAnswer],
    patient_profile: UserMedicalProfile,
) -> dict:
    """Create the lightweight AI payload consumed by the dispatch layer."""
    answer_text = " ".join(answer.answer for answer in patient_answers).strip()
    key_alerts: list[str] = []

    if patient_profile.blood_thinners:
        key_alerts.append("Patient uses blood thinners")
    if "head" in answer_text.lower():
        key_alerts.append("Possible head injury reported")

    plan_actions = [
        *assessment.response_plan.bystander_actions,
        *assessment.response_plan.followup_actions,
        *assessment.response_plan.notification_actions,
    ]

    return {
        "suspected_conditions": [
            {
                "condition": "Fall-related injury",
                "confidence": assessment.clinical_assessment.action_confidence_band,
                "reasoning": assessment.clinical_assessment.reasoning_summary,
            }
        ],
        "self_help_actions": (
            [
                {
                    "action": item.type,
                    "priority": index + 1,
                    "rationale": item.reason or "Generated from the Phase 3 response plan.",
                }
                for index, item in enumerate(plan_actions[:4])
            ]
            or [
                {
                    "action": assessment.action.recommended,
                    "priority": 1,
                    "rationale": "Generated from the centralized MVP reasoning flow.",
                }
            ]
        ),
        "suggested_department": "Trauma" if "head" in answer_text.lower() else "General ED",
        "key_alerts": key_alerts,
        "recommended_prep": ["Prepare fall-injury intake", "Review patient profile on arrival"],
        "contact_priority": ["999", "next_of_kin"],
        "summary": assessment.clinical_assessment.reasoning_summary,
    }


def _vitals_to_dispatch_payload(vitals: VitalSigns | None) -> dict:
    """Normalize optional vitals into the shape expected by emergency.py."""
    if vitals is None:
        return {}

    return {
        "heart_rate": vitals.heart_rate,
        "spo2": vitals.blood_oxygen_sp02,
        "systolic_bp": vitals.blood_pressure_systolic,
        "diastolic_bp": vitals.blood_pressure_diastolic,
    }


async def run_mvp_fall_assessment(
    event: FallEvent,
    vitals: VitalSigns | None = None,
    patient_answers: list[PatientAnswer] | None = None,
    interaction: InteractionInput | None = None,
    *,
    trigger_dispatch: bool = False,
    background_tasks: Optional[BackgroundTasks] = None,
) -> MvpAssessment:
    """Run the full MVP reasoning step once and optionally bridge to dispatch."""
    logger.info(
        "[Reasoning] Starting assessment | user=%s motion=%s confidence=%.2f answers=%d",
        event.user_id,
        event.motion_state,
        event.confidence_score,
        len(patient_answers or []),
    )
    # Local MVP tests should still work even when the live model key is absent.
    try:
        client = get_genai_client()
    except RuntimeError:
        client = None

    patient_profile = load_user_profile(event.user_id)
    vision_assessment = await inspect_fall_event(event)
    vital_assessment = await inspect_vitals(vitals)
    answers = patient_answers or []
    initial_interaction = _build_interaction_summary(
        interaction=interaction,
        patient_answers=answers,
        recommended_action=None,
    )

    retrieval_plan = build_phase2_retrieval_plan(
        patient_profile=patient_profile,
        patient_answers=answers,
        severity_hint=vision_assessment.severity_hint,
    )
    retrieval_result = run_phase2_retrieval(
        patient_profile=patient_profile,
        patient_answers=answers,
        severity_hint=vision_assessment.severity_hint,
    )
    grounded_medical_guidance = retrieval_result["guidance_snippets"]
    logger.info(
        "[Reasoning] Retrieval ready | user=%s source=%s intents=%s",
        event.user_id,
        retrieval_result["retrieval_source"],
        ", ".join(retrieval_plan["selected_intents"][:3]) or "none",
    )

    clinical_assessment = await assess_clinical_severity(
        client=client,
        event=event,
        patient_profile=patient_profile,
        vision_assessment=vision_assessment,
        vital_assessment=vital_assessment,
        grounded_medical_guidance=grounded_medical_guidance,
        patient_answers=answers,
    )
    next_action = clinical_assessment.recommended_action
    normalized_guidance = normalize_guidance_from_buckets(
        buckets=retrieval_result["bucketed_snippets"],
        action=next_action,
    )
    interaction_summary = _build_interaction_summary(
        interaction=interaction,
        patient_answers=answers,
        recommended_action=next_action,
    )

    assessment = MvpAssessment(
        incident_id=None,
        status=_status_for_action(next_action),
        responder_mode=interaction_summary.responder_mode,
        interaction=interaction_summary,
        detection=DetectionSummary(
            motion_state=event.motion_state,
            fall_detection_confidence_score=event.confidence_score,
            fall_detection_confidence_band=_confidence_band(event.confidence_score),
            event_validity=_event_validity(event, vision_assessment),
        ),
        clinical_assessment=ClinicalAssessmentSummary(
            severity=clinical_assessment.severity,
            clinical_confidence_score=clinical_assessment.clinical_confidence_score,
            clinical_confidence_band=clinical_assessment.clinical_confidence_band,
            action_confidence_score=clinical_assessment.action_confidence_score,
            action_confidence_band=clinical_assessment.action_confidence_band,
            red_flags=clinical_assessment.red_flags,
            protective_signals=clinical_assessment.protective_signals,
            suspected_risks=clinical_assessment.suspected_risks,
            vulnerability_modifiers=clinical_assessment.vulnerability_modifiers,
            missing_facts=clinical_assessment.missing_facts,
            contradictions=clinical_assessment.contradictions,
            uncertainty=clinical_assessment.uncertainty,
            hard_emergency_triggered=clinical_assessment.hard_emergency_triggered,
            blocking_uncertainties=clinical_assessment.blocking_uncertainties,
            override_policy=clinical_assessment.override_policy,
            reasoning_summary=clinical_assessment.reasoning_summary,
            response_plan=clinical_assessment.response_plan,
            reasoning_trace=clinical_assessment.reasoning_trace,
        ),
        action=ActionSummary(
            recommended=next_action,
            requires_confirmation=(next_action == "dispatch_pending_confirmation"),
            cancel_allowed=(next_action in {"dispatch_pending_confirmation", "emergency_dispatch"}),
            countdown_seconds=30 if next_action == "dispatch_pending_confirmation" else None,
        ),
        response_plan=clinical_assessment.response_plan,
        guidance=GuidanceSummary(
            primary_message=normalized_guidance.primary_message,
            steps=normalized_guidance.steps,
            warnings=normalized_guidance.warnings,
            escalation_triggers=normalized_guidance.escalation_triggers,
        ),
        grounding=GroundingSummary(
            source=retrieval_result["retrieval_source"],
            references=retrieval_result.get("references", []),
            preview=grounded_medical_guidance[:3],
            retrieval_intents=retrieval_plan["selected_intents"],
            queries=retrieval_plan["queries"],
            buckets=retrieval_result["bucketed_snippets"],
            queries_by_bucket=retrieval_result.get("queries_by_bucket", {}),
            references_by_bucket=retrieval_result.get("references_by_bucket", {}),
            bucket_sources=retrieval_result.get("bucket_sources", {}),
        ),
        audit=AuditSummary(
            fallback_used=clinical_assessment.reasoning_summary.startswith(FALLBACK_REASONING_PREFIX),
            policy_version=f"{retrieval_plan['policy_version']}+phase3_reasoning_v1",
            dispatch_triggered=False,
        ),
    )
    logger.info(
        "[Reasoning] Assessment complete | user=%s severity=%s action=%s target=%s fallback=%s",
        event.user_id,
        assessment.clinical_assessment.severity,
        assessment.action.recommended,
        assessment.interaction.communication_target if assessment.interaction else initial_interaction.communication_target,
        assessment.audit.fallback_used,
    )

    if not trigger_dispatch or not _should_trigger_dispatch(assessment.action.recommended):
        return assessment

    incident_id = await trigger_emergency(
        patient_id=event.user_id,
        severity=_map_assessment_severity_to_dispatch(assessment.clinical_assessment.severity),
        vitals=_vitals_to_dispatch_payload(vitals),
        flags=["fall_detected", f"motion_state:{event.motion_state}"],
        ai_decision=_build_dispatch_ai_summary(
            assessment=assessment,
            patient_answers=answers,
            patient_profile=patient_profile,
        ),
        background_tasks=background_tasks,
    )
    logger.info(
        "[Reasoning] Emergency dispatch triggered | user=%s incident=%s",
        event.user_id,
        incident_id,
    )

    return assessment.model_copy(
        update={
            "incident_id": incident_id,
            "status": "dispatch_confirmed",
            "audit": assessment.audit.model_copy(update={"dispatch_triggered": True}),
        }
    )


async def run_mvp_conversation_turn(
    request: CommunicationTurnRequest,
    *,
    background_tasks: Optional[BackgroundTasks] = None,
) -> CommunicationTurnResponse:
    """Run one communication-agent turn.

    The communication agent decides whether to continue the session directly or
    invoke the reasoning layer for a refreshed assessment.
    """

    session = (
        mvp_session_store.get_session(request.session_id)
        if request.session_id
        else None
    )
    if session is None:
        session = mvp_session_store.create_session(
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
        updated_session = mvp_session_store.update_context(
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

    mvp_session_store.update_context(
        session_id=session.session_id,
        event=request.event,
        vitals=request.vitals,
        interaction_input=enriched_interaction,
    )

    answers = _answers_from_turn_message(
        request.latest_responder_message,
        analysis.communication_target if analysis.communication_target != "unknown" else "patient",
    )
    interaction = _build_interaction_summary(
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
            "reasoning_reason": (
                analysis.reasoning_reason
                if analysis.reasoning_reason
                else interaction.reasoning_refresh.reason
            ),
        }
    )
    current_session = mvp_session_store.get_session(session.session_id) or session
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
        mvp_session_store.append_messages(session.session_id, responder_messages)

    assistant_message = ConversationMessage(
        role="assistant",
        text=final_analysis.followup_text,
    )
    if assistant_message.text.strip():
        mvp_session_store.append_messages(session.session_id, [assistant_message])
    logger.info(
        "[Session %s] Assistant reply | target=%s text=\"%s\"",
        _short_session_id(session.session_id),
        interaction.communication_target,
        _clip_message(final_analysis.followup_text),
    )

    mvp_session_store.store_turn_state(
        session_id=session.session_id,
        interaction_summary=interaction,
        latest_analysis=final_analysis,
    )

    reasoning_needed = final_analysis.reasoning_needed
    should_bootstrap_reasoning = existing_assessment is None
    reasoning_requested = reasoning_needed or should_bootstrap_reasoning

    if reasoning_requested:
        should_start_now = mvp_session_store.request_reasoning(
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

    latest_session = mvp_session_store.get_session(session.session_id) or session

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
    session = mvp_session_store.get_session(session_id)
    if session is None:
        return

    try:
        logger.info(
            "[Session %s] Background reasoning started",
            _short_session_id(session_id),
        )
        patient_answers = _answers_from_conversation_history(session.conversation_history)
        assessment = await run_mvp_fall_assessment(
            event=session.event,
            vitals=session.vitals,
            patient_answers=patient_answers,
            interaction=session.interaction_input,
            trigger_dispatch=True,
            background_tasks=None,
        )
        should_rerun = mvp_session_store.complete_reasoning(
            session_id=session_id,
            assessment=assessment,
            execution_updates=_build_execution_updates(assessment),
        )
        logger.info(
            "[Session %s] Background reasoning complete | severity=%s action=%s rerun=%s context_updated=true",
            _short_session_id(session_id),
            assessment.clinical_assessment.severity,
            assessment.action.recommended,
            should_rerun,
        )
        if should_rerun:
            asyncio.create_task(_run_session_reasoning_refresh(session_id))
    except Exception as exc:
        logger.exception(
            "[Session %s] Background reasoning failed",
            _short_session_id(session_id),
        )
        should_retry = mvp_session_store.fail_reasoning(
            session_id=session_id,
            error_message=str(exc),
        )
        if should_retry:
            asyncio.create_task(_run_session_reasoning_refresh(session_id))


def get_mvp_conversation_session_state(session_id: str) -> CommunicationSessionStateResponse | None:
    session = mvp_session_store.get_session(session_id)
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
