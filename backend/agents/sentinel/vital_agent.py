"""Vital agent: checks incoming vital signs for anomalies and returns a basic urgency hint."""

from agents.shared.schemas import VitalAssessment, VitalSigns


async def inspect_vitals(vitals: VitalSigns | None) -> VitalAssessment | None:
    if vitals is None:
        return None

    anomaly_detected = (
        vitals.heart_rate < 45
        or vitals.heart_rate > 130
        or vitals.blood_oxygen_sp02 < 92
    )
    severity_hint = "high" if anomaly_detected else "low"
    reasoning = (
        "Abnormal vital signs detected." if anomaly_detected else "Vital signs are within the expected MVP range."
    )

    return VitalAssessment(
        anomaly_detected=anomaly_detected,
        severity_hint=severity_hint,
        reasoning=reasoning,
    )
