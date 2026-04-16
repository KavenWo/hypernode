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

from .phase3_reasoning import apply_phase3_defaults, render_phase3_context, run_phase3_reasoning
from .prompts import build_clinical_reasoning_prompt

logger = logging.getLogger(__name__)


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
    stage_outcome = run_phase3_reasoning(
        event=event,
        patient_profile=patient_profile,
        vision_assessment=vision_assessment,
        vital_assessment=vital_assessment,
        patient_answers=patient_answers or [],
    )
    prompt = build_clinical_reasoning_prompt(
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance,
        render_phase3_context(stage_outcome),
        patient_answers,
    )

    if client is None:
        logger.warning(
            "Live reasoning model unavailable. Using fallback clinical assessment for user %s.",
            event.user_id,
        )
        return _fallback_clinical_assessment(
            stage_outcome=stage_outcome,
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
        return apply_phase3_defaults(assessment=assessment, outcome=stage_outcome)
    except Exception as exc:
        logger.warning(
            "Live clinical reasoning failed for user %s. Falling back to heuristic assessment. Error: %s",
            event.user_id,
            exc,
        )
        return _fallback_clinical_assessment(
            stage_outcome=stage_outcome,
        )


async def _generate_json_response(*, client, prompt: str, schema):
    last_error = None

    for model_name in FALLBACK_MODELS:
        for attempt in range(2):
            try:
                logger.debug(
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
    stage_outcome,
) -> ClinicalAssessment:
    assessment = stage_outcome.to_clinical_assessment().model_copy(
        update={
            "reasoning_summary": (
                "Fallback assessment used because the live reasoning model was unavailable. "
                f"{stage_outcome.reasoning_summary}"
            )
        }
    )
    logger.info(
        "Fallback clinical assessment generated. Severity=%s Action=%s Reasons=%s",
        assessment.severity,
        assessment.recommended_action,
        stage_outcome.severity_reason,
    )
    return assessment
