from agents.shared.schemas import (
    FallEvent,
    PatientAnswer,
    UserMedicalProfile,
    VisionAssessment,
    VitalAssessment,
)


def build_clinical_reasoning_prompt(
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    vision_assessment: VisionAssessment,
    vital_assessment: VitalAssessment | None,
    grounded_medical_guidance: list[str],
    patient_answers: list[PatientAnswer] | None = None,
) -> str:
    vitals_context = (
        f"Vital assessment: {vital_assessment.reasoning} Severity hint: {vital_assessment.severity_hint}."
        if vital_assessment
        else "No vital-sign assessment is available yet."
    )
    guidance_context = "\n".join(f"- {item}" for item in grounded_medical_guidance) or "- No external medical guidance retrieved."
    answer_context = (
        "\n".join(f"- {answer.question_id}: {answer.answer}" for answer in (patient_answers or []))
        or "- No patient answers were collected."
    )

    return f"""
    You are the Clinical Reasoning Agent for an emergency response workflow.

    You must return structured JSON that follows the provided schema exactly.
    Use only these severity values: low, medium, critical.
    Use only these action values: monitor, contact_family, dispatch_pending_confirmation, emergency_dispatch.
    Use only these confidence bands: low, medium, high.

    Normalize red flags into these vocabulary keys when supported by the evidence:
    - unresponsive
    - loss_of_consciousness
    - not_breathing
    - abnormal_breathing
    - severe_bleeding
    - chest_pain
    - seizure_activity
    - head_strike
    - vomiting_after_head_injury
    - confusion_after_fall
    - sudden_collapse
    - cannot_stand
    - severe_pain
    - severe_hip_pain
    - severe_back_pain
    - severe_neck_pain
    - suspected_fracture
    - suspected_spinal_injury
    - blood_thinner_use
    - older_adult
    - known_heart_disease
    - known_neurological_disease
    - mobility_support_user
    - recurrent_falls

    Separate observed facts, reported facts, grounded medical support, and uncertainty.
    Do not use fall detection confidence as a synonym for medical severity.
    Keep reasoning_summary short and operational.

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
    - Patient or bystander answers:
    {answer_context}
    - Grounded medical guidance:
    {guidance_context}

    Decision rules:
    - If rapid_descent or no_movement occurs with confidence above 0.85, bias toward critical severity.
    - If both motion evidence and vitals suggest danger, bias toward critical.
    - If the patient reports trouble breathing, heavy bleeding, head strike on blood thinners, loss of consciousness, or inability to move safely, bias toward critical severity.
    - Elderly patients, blood thinners, or concerning fall red flags should increase caution.
    - If explicit life-threatening red flags are present, prefer emergency_dispatch unless a brief confirmation window is clearly safer and still appropriate.
    - If the case is concerning but not clearly life-threatening, prefer contact_family.
    - If the case appears stable with limited evidence of danger, prefer monitor.

    Return a structured clinical assessment.
    """
