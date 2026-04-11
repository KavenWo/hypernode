"""Dispatcher agent: converts the clinical assessment into a structured response decision for the backend."""

from agents.reasoning.clinical_agent import _generate_json_response
from agents.shared.schemas import ClinicalAssessment, DispatchDecision, FallEvent, VisionAssessment

from .prompts import build_dispatch_prompt


async def decide_dispatch(
    *,
    client,
    event: FallEvent,
    vision_assessment: VisionAssessment,
    clinical_assessment: ClinicalAssessment,
) -> DispatchDecision:
    prompt = build_dispatch_prompt(
        event=event,
        vision_assessment=vision_assessment,
        clinical_assessment=clinical_assessment,
    )
    response = await _generate_json_response(
        client=client,
        prompt=prompt,
        schema=DispatchDecision,
    )
    decision = response.parsed
    if decision is None:
        decision = DispatchDecision.model_validate_json(response.text or "{}")
    return decision
