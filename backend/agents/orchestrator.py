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
from agents.shared.schemas import DispatchDecision, FallEvent, UserMedicalProfile, VitalSigns
from db.firebase_client import load_patient_profile


async def vital_signs_emergency_workflow(
    event: FallEvent,
    vitals: VitalSigns | None = None,
) -> DispatchDecision:
    print(f"Received Fall Event for User: {event.user_id} with Confidence {event.confidence_score}")

    client = get_genai_client()
    patient_profile = UserMedicalProfile.model_validate(load_patient_profile(event.user_id).model_dump())
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
