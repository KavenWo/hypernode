"""Clinical agent: combines event data, patient profile, and grounded guidance to assess medical severity."""

import asyncio
import logging

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

logger = logging.getLogger(__name__)


def _confidence_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def _normalized_answer_text(patient_answers: list[PatientAnswer]) -> str:
    return " ".join(answer.answer.lower() for answer in patient_answers)


def _extract_red_flags(
    *,
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    vital_assessment: VitalAssessment | None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    answer_text = _normalized_answer_text(patient_answers)
    red_flags: list[str] = []
    protective_signals: list[str] = []
    suspected_risks: list[str] = []
    uncertainty: list[str] = []

    def add_unique(target: list[str], value: str) -> None:
        if value not in target:
            target.append(value)

    if event.motion_state in {"rapid_descent", "no_movement"} and event.confidence_score >= 0.75:
        add_unique(suspected_risks, "high_impact_fall")

    checks = [
        (["unresponsive", "not responding"], "unresponsive", "airway_compromise"),
        (["lost consciousness", "loss of consciousness", "passed out", "blacked out"], "loss_of_consciousness", "head_injury"),
        (["not breathing"], "not_breathing", "airway_compromise"),
        (["abnormal breathing", "trouble breathing", "difficulty breathing"], "abnormal_breathing", "respiratory_distress"),
        (["heavy bleeding", "severe bleeding", "bleeding heavily"], "severe_bleeding", "hemorrhage_risk"),
        (["chest pain"], "chest_pain", "cardiac_event"),
        (["seizure", "convuls"], "seizure_activity", "neurological_event"),
        (["hit my head", "hit their head", "head strike", "head injury"], "head_strike", "head_injury"),
        (["vomiting"], "vomiting_after_head_injury", "head_injury"),
        (["confusion", "confused", "disoriented"], "confusion_after_fall", "head_injury"),
        (["sudden collapse", "collapsed suddenly"], "sudden_collapse", "medical_collapse"),
        (["cannot stand", "can't stand", "unable to get up", "unable to stand"], "cannot_stand", "fracture_risk"),
        (["severe pain", "strong pain"], "severe_pain", "serious_injury"),
        (["hip pain"], "severe_hip_pain", "fracture_risk"),
        (["back pain"], "severe_back_pain", "spinal_injury"),
        (["neck pain"], "severe_neck_pain", "spinal_injury"),
        (["fracture", "broken"], "suspected_fracture", "fracture_risk"),
        (["spinal", "spine"], "suspected_spinal_injury", "spinal_injury"),
    ]

    for phrases, red_flag, risk in checks:
        if any(phrase in answer_text for phrase in phrases):
            add_unique(red_flags, red_flag)
            add_unique(suspected_risks, risk)

    if "awake" in answer_text or "speaking clearly" in answer_text or "responding clearly" in answer_text:
        add_unique(protective_signals, "awake_and_answering")
    if "breathing normally" in answer_text:
        add_unique(protective_signals, "breathing_normally")

    if patient_profile.blood_thinners:
        add_unique(red_flags, "blood_thinner_use")
    if patient_profile.age >= 65:
        add_unique(red_flags, "older_adult")
    for condition in patient_profile.pre_existing_conditions:
        lowered = condition.lower()
        if any(term in lowered for term in ["heart", "atrial", "cardiac"]):
            add_unique(red_flags, "known_heart_disease")
        if any(term in lowered for term in ["neuro", "stroke", "seizure", "parkinson"]):
            add_unique(red_flags, "known_neurological_disease")
    if patient_profile.mobility_support:
        add_unique(red_flags, "mobility_support_user")
    if any("recurrent fall" in condition.lower() for condition in patient_profile.pre_existing_conditions):
        add_unique(red_flags, "recurrent_falls")

    if vital_assessment and vital_assessment.anomaly_detected:
        add_unique(suspected_risks, "physiologic_instability")
        if vital_assessment.severity_hint == "critical":
            add_unique(uncertainty, "Vital instability suggests urgent reassessment if symptoms are unclear")

    if patient_answers and not any(flag in red_flags for flag in ["severe_bleeding", "not_breathing", "abnormal_breathing"]):
        add_unique(uncertainty, "Breathing and bleeding status may need confirmation")

    return red_flags, protective_signals, suspected_risks, uncertainty


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

    if client is None:
        logger.warning(
            "Live reasoning model unavailable before request. Using fallback clinical assessment for user %s.",
            event.user_id,
        )
        return _fallback_clinical_assessment(
            event=event,
            patient_profile=patient_profile,
            vision_assessment=vision_assessment,
            vital_assessment=vital_assessment,
            patient_answers=patient_answers or [],
        )

    try:
        logger.info(
            "Starting live clinical reasoning for user %s with %d grounded guidance snippet(s).",
            event.user_id,
            len(grounded_medical_guidance),
        )
        response = await _generate_json_response(
            client=client,
            prompt=prompt,
            schema=ClinicalAssessment,
        )
        assessment = response.parsed
        if assessment is None:
            assessment = ClinicalAssessment.model_validate_json(response.text or "{}")
        logger.info(
            "Live clinical reasoning succeeded for user %s. Severity=%s Action=%s",
            event.user_id,
            assessment.severity,
            assessment.recommended_action,
        )
        return assessment
    except Exception as exc:
        logger.warning(
            "Live clinical reasoning failed for user %s. Falling back to heuristic assessment. Error: %s",
            event.user_id,
            exc,
        )
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
                logger.info(
                    "Attempting live model call with %s (attempt %d/%d).",
                    model_name,
                    attempt + 1,
                    2,
                )
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
                logger.warning(
                    "Model call failed for %s on attempt %d/%d with code %s: %s",
                    model_name,
                    attempt + 1,
                    2,
                    exc.code,
                    exc,
                )
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
    red_flags, protective_signals, suspected_risks, uncertainty = _extract_red_flags(
        event=event,
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        vital_assessment=vital_assessment,
    )
    score = 0
    reasons: list[str] = []

    immediate_flags = {
        "unresponsive",
        "loss_of_consciousness",
        "not_breathing",
        "abnormal_breathing",
        "severe_bleeding",
        "chest_pain",
        "seizure_activity",
    }
    high_risk_flags = {
        "head_strike",
        "vomiting_after_head_injury",
        "confusion_after_fall",
        "sudden_collapse",
        "cannot_stand",
        "severe_pain",
        "severe_hip_pain",
        "severe_back_pain",
        "severe_neck_pain",
        "suspected_fracture",
        "suspected_spinal_injury",
    }

    if vision_assessment.severity_hint == "critical":
        score += 2
        reasons.append("motion pattern looks critical")
    elif vision_assessment.severity_hint == "medium":
        score += 1
        reasons.append("motion pattern looks concerning")

    if vital_assessment and vital_assessment.anomaly_detected:
        score += 1 if vital_assessment.severity_hint == "medium" else 2
        reasons.append("vitals are abnormal")

    immediate_present = [flag for flag in red_flags if flag in immediate_flags]
    high_risk_present = [flag for flag in red_flags if flag in high_risk_flags]
    modifiers_present = [flag for flag in red_flags if flag not in immediate_flags and flag not in high_risk_flags]

    if immediate_present:
        score += 4
        reasons.append("immediate emergency red flags are present")
    if high_risk_present:
        score += 2
        reasons.append("high-risk fall symptoms are present")
    if modifiers_present:
        score += 1
        reasons.append("vulnerability modifiers increase caution")

    if event.motion_state == "rapid_descent" and event.confidence_score >= 0.9:
        score += 1
    elif event.motion_state == "no_movement" and event.confidence_score >= 0.85:
        score += 1

    if immediate_present or ({"head_strike", "blood_thinner_use"} <= set(red_flags)):
        severity = "critical"
        action = "emergency_dispatch" if {"not_breathing", "abnormal_breathing", "unresponsive"} & set(red_flags) else "dispatch_pending_confirmation"
        clinical_confidence_score = 0.83
        action_confidence_score = 0.9 if action == "emergency_dispatch" else 0.8
    elif score >= 3:
        severity = "medium"
        action = "contact_family"
        clinical_confidence_score = 0.67
        action_confidence_score = 0.62
    else:
        severity = "low"
        action = "monitor"
        clinical_confidence_score = 0.79
        action_confidence_score = 0.76

    if severity == "critical" and not immediate_present and uncertainty:
        clinical_confidence_score = min(clinical_confidence_score, 0.73)

    reasoning_summary = (
        "Fallback assessment used because the live reasoning model was unavailable. "
        + (", ".join(reasons) if reasons else "Limited high-risk signals were detected.")
        + "."
    )
    assessment = ClinicalAssessment(
        severity=severity,
        clinical_confidence_score=clinical_confidence_score,
        clinical_confidence_band=_confidence_band(clinical_confidence_score),
        action_confidence_score=action_confidence_score,
        action_confidence_band=_confidence_band(action_confidence_score),
        red_flags=red_flags,
        protective_signals=protective_signals,
        suspected_risks=suspected_risks[:5],
        uncertainty=uncertainty[:3],
        reasoning_summary=reasoning_summary,
        recommended_action=action,
    )
    logger.info(
        "Fallback clinical assessment generated. Severity=%s Action=%s Reasons=%s",
        assessment.severity,
        assessment.recommended_action,
        ", ".join(reasons) if reasons else "limited signals",
    )
    return assessment
