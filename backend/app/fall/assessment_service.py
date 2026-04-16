"""Deterministic fall assessment service.

This module now owns the single-pass retrieval + reasoning path used for both
direct evaluation and conversation-session refreshes.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import BackgroundTasks

from agents.bystander.guidance_normalizer import normalize_guidance_from_buckets
from agents.bystander.retrieval_engine import run_phase2_retrieval
from agents.bystander.retrieval_policy import build_phase2_retrieval_plan
from agents.communication.interaction_policy import (
    InteractionContext,
    choose_interaction_target,
    should_refresh_reasoning,
)
from agents.reasoning.clinical_agent import assess_clinical_severity
from agents.sentinel.vital_agent import inspect_vitals
from agents.sentinel.vision_agent import inspect_fall_event
from agents.shared.config import get_genai_client
from agents.triage.question_agent import generate_triage_questions
from app.fall.contracts import (
    ActionSummary,
    AuditSummary,
    ClinicalAssessmentSummary,
    DetectionSummary,
    FallAssessment,
    FallEvent,
    GroundingSummary,
    GuidanceSummary,
    InteractionInput,
    InteractionSummary,
    PatientAnswer,
    ReasoningRefreshSummary,
    TriageQuestionSet,
    UserMedicalProfile,
    VitalSigns,
)
from app.fall.execution_service import SeverityLevel as EmergencySeverityLevel
from app.fall.execution_service import trigger_emergency
from db.firebase_client import load_patient_profile

logger = logging.getLogger(__name__)

FALLBACK_REASONING_PREFIX = "Fallback assessment used because the live reasoning model was unavailable."


def load_user_profile(user_id: str) -> UserMedicalProfile:
    """Load the patient profile once and normalize it to the shared schema."""
    return UserMedicalProfile.model_validate(load_patient_profile(user_id).model_dump())


def _confidence_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


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


def build_interaction_summary(
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


def build_fall_questions(
    event: FallEvent,
    vitals: VitalSigns | None = None,
    interaction: InteractionInput | None = None,
) -> TriageQuestionSet:
    """Return the current deterministic question set for a fall incident."""
    patient_profile = load_user_profile(event.user_id)
    interaction_summary = build_interaction_summary(
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
    return action == "emergency_dispatch"


def _event_validity(event: FallEvent, vision_assessment) -> str:
    if vision_assessment.fall_detected and event.confidence_score >= 0.75:
        return "likely_true"
    if event.confidence_score >= 0.4:
        return "uncertain"
    return "weak_signal"


def _status_for_action(action: str) -> str:
    if action == "dispatch_pending_confirmation":
        return "dispatch_pending_confirmation"
    if action == "emergency_dispatch":
        return "dispatch_confirmed"
    if action == "contact_family":
        return "triage_in_progress"
    return "guidance_active"


def _map_assessment_severity_to_dispatch(severity: str) -> EmergencySeverityLevel:
    normalized = severity.lower().strip()
    if normalized in {"critical", "high"}:
        return EmergencySeverityLevel.RED
    if normalized == "medium":
        return EmergencySeverityLevel.AMBER
    return EmergencySeverityLevel.YELLOW


def _build_dispatch_ai_summary(
    *,
    assessment: FallAssessment,
    patient_answers: list[PatientAnswer],
    patient_profile: UserMedicalProfile,
) -> dict:
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
                    "rationale": "Generated from the centralized fall reasoning flow.",
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
    if vitals is None:
        return {}

    return {
        "heart_rate": vitals.heart_rate,
        "spo2": vitals.blood_oxygen_sp02,
        "systolic_bp": vitals.blood_pressure_systolic,
        "diastolic_bp": vitals.blood_pressure_diastolic,
    }


async def run_fall_assessment(
    event: FallEvent,
    vitals: VitalSigns | None = None,
    patient_answers: list[PatientAnswer] | None = None,
    interaction: InteractionInput | None = None,
    *,
    trigger_dispatch: bool = False,
    background_tasks: Optional[BackgroundTasks] = None,
) -> FallAssessment:
    """Run the full single-pass fall assessment and optionally bridge to dispatch."""
    logger.info(
        "[Reasoning] Starting assessment | user=%s motion=%s confidence=%.2f answers=%d",
        event.user_id,
        event.motion_state,
        event.confidence_score,
        len(patient_answers or []),
    )
    try:
        client = get_genai_client()
    except RuntimeError:
        client = None

    patient_profile = load_user_profile(event.user_id)
    vision_assessment = await inspect_fall_event(event)
    vital_assessment = await inspect_vitals(vitals)
    answers = patient_answers or []
    initial_interaction = build_interaction_summary(
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
    interaction_summary = build_interaction_summary(
        interaction=interaction,
        patient_answers=answers,
        recommended_action=next_action,
    )

    assessment = FallAssessment(
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

