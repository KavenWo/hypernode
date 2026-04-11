"""Vision agent: interprets fall-motion signals and outputs the initial fall likelihood and severity hint."""

from agents.shared.schemas import FallEvent, VisionAssessment

from .prompts import build_vision_reasoning_prompt


async def inspect_fall_event(event: FallEvent) -> VisionAssessment:
    prompt = build_vision_reasoning_prompt(event.motion_state, event.confidence_score)
    del prompt

    high_risk_state = event.motion_state in {"rapid_descent", "no_movement"}
    fall_detected = high_risk_state or event.confidence_score >= 0.9

    if event.motion_state == "rapid_descent" and event.confidence_score > 0.85:
        severity_hint = "critical"
    elif high_risk_state and event.confidence_score > 0.7:
        severity_hint = "high"
    elif event.confidence_score > 0.5:
        severity_hint = "medium"
    else:
        severity_hint = "low"

    reasoning = (
        f"Motion state '{event.motion_state}' with confidence {event.confidence_score:.2f} "
        f"suggests an initial {severity_hint} risk profile."
    )
    return VisionAssessment(
        fall_detected=fall_detected,
        severity_hint=severity_hint,
        reasoning=reasoning,
    )
