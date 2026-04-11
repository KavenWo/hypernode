"""Clinical agent: combines event data, patient profile, and grounded guidance to assess medical severity."""

import asyncio

from google.genai import errors, types

from agents.shared.config import FALLBACK_MODELS
from agents.shared.schemas import (
    ClinicalAssessment,
    FallEvent,
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
) -> ClinicalAssessment:
    prompt = build_clinical_reasoning_prompt(
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance,
    )

    response = await _generate_json_response(
        client=client,
        prompt=prompt,
        schema=ClinicalAssessment,
    )
    assessment = response.parsed
    if assessment is None:
        assessment = ClinicalAssessment.model_validate_json(response.text or "{}")
    return assessment


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
