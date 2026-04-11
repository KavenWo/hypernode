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

import logging
from typing import Optional
import os

from fastapi import BackgroundTasks

from agents.bystander.knowledge_base import retrieve_medical_guidance_with_source
from agents.bystander.rag_agent import build_first_aid_instructions_from_guidance
from agents.reasoning.clinical_agent import assess_clinical_severity
from agents.sentinel.vital_agent import inspect_vitals
from agents.sentinel.vision_agent import inspect_fall_event
from agents.shared.config import get_genai_client
from agents.shared.schemas import (
    FallEvent,
    MvpAssessment,
    PatientAnswer,
    TriageQuestionSet,
    UserMedicalProfile,
    VitalSigns,
)
from agents.triage.question_agent import generate_triage_questions
from db.firebase_client import load_patient_profile
from app.api.routes.emergency import SeverityLevel as EmergencySeverityLevel
from app.api.routes.emergency import trigger_emergency

logger = logging.getLogger(__name__)

FALLBACK_REASONING_PREFIX = "Fallback assessment used because the live reasoning model was unavailable."


def load_user_profile(user_id: str) -> UserMedicalProfile:
    """Load the patient profile once and normalize it to the shared schema."""
    return UserMedicalProfile.model_validate(load_patient_profile(user_id).model_dump())


def build_guidance_query(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> str:
    """Choose a focused first-aid retrieval query based on risk signals."""
    answer_text = " ".join(answer.answer.lower() for answer in patient_answers)

    if "not breathing" in answer_text or "cpr" in answer_text:
        return "cpr first aid guidance for elderly fall patient"
    if (
        patient_profile.blood_thinners
        or "head" in answer_text
        or "bleeding" in answer_text
        or "confusion" in answer_text
        or "unconscious" in answer_text
    ):
        return "fall red flags for elderly patient on blood thinners"
    return "fall first aid guidance for elderly patient"


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
) -> TriageQuestionSet:
    """Return the 2-3 questions the frontend should ask before reasoning."""
    patient_profile = load_user_profile(event.user_id)
    return generate_triage_questions(
        event=event,
        patient_profile=patient_profile,
        vitals=vitals,
    )


def _should_trigger_dispatch(action: str) -> bool:
    """Only the emergency action path should fan out into dispatch stubs."""
    return action == "emergency_dispatch"


def _map_assessment_severity_to_dispatch(severity: str) -> EmergencySeverityLevel:
    """Bridge the reasoning severity labels to the dispatch layer labels."""
    normalized = severity.lower().strip()
    if normalized in {"critical", "high"}:
        return EmergencySeverityLevel.RED
    if normalized == "medium":
        return EmergencySeverityLevel.AMBER
    return EmergencySeverityLevel.YELLOW


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

    return {
        "suspected_conditions": [
            {
                "condition": "Fall-related injury",
                "confidence": assessment.severity,
                "reasoning": assessment.reasoning,
            }
        ],
        "self_help_actions": [
            {
                "action": assessment.action,
                "priority": 1,
                "rationale": "Generated from the centralized MVP reasoning flow.",
            }
        ],
        "suggested_department": "Trauma" if "head" in answer_text.lower() else "General ED",
        "key_alerts": key_alerts,
        "recommended_prep": ["Prepare fall-injury intake", "Review patient profile on arrival"],
        "contact_priority": ["999", "next_of_kin"],
        "summary": assessment.reasoning,
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
    *,
    trigger_dispatch: bool = False,
    background_tasks: Optional[BackgroundTasks] = None,
) -> MvpAssessment:
    """Run the full MVP reasoning step once and optionally bridge to dispatch."""
    logger.info(
        "Starting MVP assessment for user %s. Motion=%s Confidence=%.2f",
        event.user_id,
        event.motion_state,
        event.confidence_score,
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

    guidance_query = build_guidance_query(
        patient_profile=patient_profile,
        patient_answers=answers,
    )
    guidance_bundle = retrieve_medical_guidance_with_source(guidance_query)
    grounded_medical_guidance = guidance_bundle["snippets"]
    logger.info(
        "Grounded guidance source for user %s: %s",
        event.user_id,
        guidance_bundle["source"],
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

    assessment = MvpAssessment(
        severity=clinical_assessment.severity,
        action=clinical_assessment.recommended_action,
        instructions=build_first_aid_instructions_from_guidance(grounded_medical_guidance).steps,
        reasoning=clinical_assessment.reasoning,
        ai_status=(
            "fallback"
            if clinical_assessment.reasoning.startswith(FALLBACK_REASONING_PREFIX)
            else "live_model"
        ),
        guidance_source=guidance_bundle["source"],
        guidance_preview=grounded_medical_guidance[:3],
        guidance_references=guidance_bundle.get("references", []),
    )
    logger.info(
        "MVP assessment completed for user %s. Severity=%s Action=%s AI=%s Guidance=%s",
        event.user_id,
        assessment.severity,
        assessment.action,
        assessment.ai_status,
        assessment.guidance_source,
    )

    if not trigger_dispatch or not _should_trigger_dispatch(assessment.action):
        return assessment

    incident_id = await trigger_emergency(
        patient_id=event.user_id,
        severity=_map_assessment_severity_to_dispatch(assessment.severity),
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
        "Emergency dispatch triggered for user %s with incident %s.",
        event.user_id,
        incident_id,
    )

    return assessment.model_copy(
        update={
            "dispatch_triggered": True,
            "incident_id": incident_id,
        }
    )
