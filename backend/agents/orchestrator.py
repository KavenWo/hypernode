"""Orchestrator: coordinates all agents in sequence and bridges their decisions to execution steps."""

import json

from agents.bystander.knowledge_base import retrieve_medical_guidance
from agents.bystander.rag_agent import retrieve_first_aid_instructions
from agents.coordinator.dispatcher_agent import decide_dispatch
from agents.execution.emergency_actions import dispatch_ambulance
from agents.reasoning.clinical_agent import assess_clinical_severity
from agents.sentinel.vital_agent import inspect_vitals
from agents.sentinel.vision_agent import inspect_fall_event
from agents.shared.config import get_genai_client
from agents.shared.schemas import (
    DispatchDecision,
    FallEvent,
    MvpAssessment,
    PatientAnswer,
    TriageQuestionSet,
    UserMedicalProfile,
    VitalSigns,
)
from agents.triage.question_agent import generate_triage_questions
from db.firebase_client import load_patient_profile


def _load_user_profile(user_id: str) -> UserMedicalProfile:
    return UserMedicalProfile.model_validate(load_patient_profile(user_id).model_dump())


def _build_guidance_query(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> str:
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


def get_fall_triage_questions(
    event: FallEvent,
    vitals: VitalSigns | None = None,
) -> TriageQuestionSet:
    patient_profile = _load_user_profile(event.user_id)
    return generate_triage_questions(
        event=event,
        patient_profile=patient_profile,
        vitals=vitals,
    )


async def run_mvp_fall_assessment(
    event: FallEvent,
    vitals: VitalSigns | None = None,
    patient_answers: list[PatientAnswer] | None = None,
) -> MvpAssessment:
    print(f"Running MVP fall assessment for User: {event.user_id} with Confidence {event.confidence_score}")

    client = get_genai_client()
    patient_profile = _load_user_profile(event.user_id)
    vision_assessment = await inspect_fall_event(event)
    vital_assessment = await inspect_vitals(vitals)
    answers = patient_answers or []
    grounded_medical_guidance = retrieve_medical_guidance(
        _build_guidance_query(
            patient_profile=patient_profile,
            patient_answers=answers,
        )
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

    instructions = retrieve_first_aid_instructions("fall").steps
    return MvpAssessment(
        severity=clinical_assessment.severity,
        action=clinical_assessment.recommended_action,
        instructions=instructions,
        reasoning=clinical_assessment.reasoning,
    )


async def vital_signs_emergency_workflow(
    event: FallEvent,
    vitals: VitalSigns | None = None,
) -> DispatchDecision:
    print(f"Received Fall Event for User: {event.user_id} with Confidence {event.confidence_score}")

    client = get_genai_client()
    patient_profile = _load_user_profile(event.user_id)
    vision_assessment = await inspect_fall_event(event)
    vital_assessment = await inspect_vitals(vitals)
    grounded_medical_guidance = retrieve_medical_guidance(
        "fall red flags for elderly patient on blood thinners"
    )
    clinical_assessment = await assess_clinical_severity(
        client=client,
        event=event,
        patient_profile=patient_profile,
        vision_assessment=vision_assessment,
        vital_assessment=vital_assessment,
        grounded_medical_guidance=grounded_medical_guidance,
        patient_answers=[],
    )
    print(f"Clinical Assessment: [{clinical_assessment.severity.upper()}] - {clinical_assessment.reasoning}")

    decision = await decide_dispatch(
        client=client,
        event=event,
        vision_assessment=vision_assessment,
        clinical_assessment=clinical_assessment,
    )

    if decision.call_emergency_services:
        dispatch_summary = dispatch_ambulance(
            lat=1.4927,
            lon=103.7414,
            contact_number="+60123456789",
            message="Emergency: probable severe fall detected. Ambulance dispatch requested.",
        )
        print(json.dumps({"dispatch_summary": dispatch_summary}))

    if decision.first_aid_instructions_needed:
        instructions = retrieve_first_aid_instructions("fall")
        print(json.dumps({"bystander_instruction": instructions.model_dump()}))

    print(f"Final Decision: {decision}")
    return decision
