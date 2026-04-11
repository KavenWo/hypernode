from agents.shared.schemas import FallEvent, UserMedicalProfile, VisionAssessment, VitalAssessment


def build_clinical_reasoning_prompt(
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    vision_assessment: VisionAssessment,
    vital_assessment: VitalAssessment | None,
    grounded_medical_guidance: list[str],
) -> str:
    vitals_context = (
        f"Vital assessment: {vital_assessment.reasoning} Severity hint: {vital_assessment.severity_hint}."
        if vital_assessment
        else "No vital-sign assessment is available yet."
    )
    guidance_context = "\n".join(f"- {item}" for item in grounded_medical_guidance) or "- No external medical guidance retrieved."

    return f"""
    You are the Clinical Reasoning Agent for an emergency response workflow.

    Event details:
    - Motion State: {event.motion_state}
    - Confidence Score: {event.confidence_score}
    - Patient Age: {patient_profile.age}
    - Blood Thinners: {patient_profile.blood_thinners}
    - Pre-existing Conditions: {", ".join(patient_profile.pre_existing_conditions) or "None listed"}
    - Medications: {", ".join(patient_profile.medications) or "None listed"}
    - Vision Sentinel: fall_detected={vision_assessment.fall_detected}, severity_hint={vision_assessment.severity_hint}
    - Vision Reasoning: {vision_assessment.reasoning}
    - {vitals_context}
    - Grounded medical guidance:
    {guidance_context}

    Decision rules:
    - If rapid_descent or no_movement occurs with confidence above 0.85, bias toward high or critical severity.
    - If both motion evidence and vitals suggest danger, bias toward critical.
    - Elderly patients, blood thinners, or concerning fall red flags should increase caution.
    - Keep the recommended action to one of: monitor, contact_family, emergency_dispatch.

    Return a structured clinical assessment.
    """
