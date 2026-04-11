"""Clinical agent: combines event data, patient profile, and grounded guidance to assess medical severity."""

import asyncio

from google.genai import errors, types

from agents.shared.config import FALLBACK_MODELS
from agents.shared.schemas import (
    ClinicalAssessment,
    FallEvent,
    PatientAnswer,
    UserMedicalProfile,
    VisionAssessment,
    VitalAssessment,
)

from .prompts import build_clinical_reasoning_prompt


async def assess_clinical_severity(
    *,
    client,
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    vision_assessment: VisionAssessment,
    vital_assessment: VitalAssessment | None,
    grounded_medical_guidance: list[str],
    patient_answers: list[PatientAnswer] | None = None,
) -> ClinicalAssessment:
    prompt = build_clinical_reasoning_prompt(
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance,
        patient_answers,
    )

    try:
        response = await _generate_json_response(
            client=client,
            prompt=prompt,
            schema=ClinicalAssessment,
        )
        assessment = response.parsed
        if assessment is None:
            assessment = ClinicalAssessment.model_validate_json(response.text or "{}")
        return assessment
    except Exception:
        return _fallback_clinical_assessment(
            event=event,
            patient_profile=patient_profile,
            vision_assessment=vision_assessment,
            vital_assessment=vital_assessment,
            patient_answers=patient_answers or [],
        )


async def _generate_json_response(*, client, prompt: str, schema):
    last_error = None

    for model_name in FALLBACK_MODELS:
        for attempt in range(2):
            try:
                return await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
            except errors.APIError as exc:
                last_error = exc
                is_retryable = exc.code in {429, 500, 503}
                is_last_attempt = attempt == 1 and model_name == FALLBACK_MODELS[-1]
                if not is_retryable or is_last_attempt:
                    raise
                await asyncio.sleep(1 + attempt)

    if last_error is not None:
        raise last_error

    raise RuntimeError("No model response was produced.")


def _fallback_clinical_assessment(
    *,
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    vision_assessment: VisionAssessment,
    vital_assessment: VitalAssessment | None,
    patient_answers: list[PatientAnswer],
) -> ClinicalAssessment:
    answer_text = " ".join(answer.answer.lower() for answer in patient_answers)
    score = 0
    reasons: list[str] = []

    if vision_assessment.severity_hint == "critical":
        score += 4
        reasons.append("motion pattern looks critical")
    elif vision_assessment.severity_hint == "high":
        score += 3
        reasons.append("motion pattern looks high risk")
    elif vision_assessment.severity_hint == "medium":
        score += 1

    if vital_assessment and vital_assessment.anomaly_detected:
        score += 3
        reasons.append("vitals are abnormal")

    if patient_profile.age >= 75:
        score += 1
        reasons.append("older adult patient")
    if patient_profile.blood_thinners:
        score += 2
        reasons.append("patient is on blood thinners")

    critical_terms = [
        "not breathing",
        "trouble breathing",
        "heavy bleeding",
        "chest pain",
        "unconscious",
        "confusion",
    ]
    high_risk_terms = [
        "hit my head",
        "head",
        "cannot stand",
        "can't stand",
        "unable to get up",
        "severe pain",
        "hip",
        "back",
        "neck",
        "dizzy",
    ]

    if any(term in answer_text for term in critical_terms):
        score += 4
        reasons.append("answers describe immediate danger signs")
    elif any(term in answer_text for term in high_risk_terms):
        score += 2
        reasons.append("answers describe high-risk fall symptoms")

    if event.motion_state == "rapid_descent" and event.confidence_score >= 0.9:
        score += 2
    elif event.motion_state == "no_movement" and event.confidence_score >= 0.85:
        score += 2

    if score >= 7:
        severity = "critical"
        action = "emergency_dispatch"
    elif score >= 4:
        severity = "high"
        action = "emergency_dispatch"
    elif score >= 2:
        severity = "medium"
        action = "contact_family"
    else:
        severity = "low"
        action = "monitor"

    reasoning = (
        "Fallback assessment used because the live reasoning model was unavailable. "
        + (", ".join(reasons) if reasons else "Limited high-risk signals were detected.")
        + "."
    )
    return ClinicalAssessment(
        severity=severity,
        reasoning=reasoning,
        recommended_action=action,
    )
