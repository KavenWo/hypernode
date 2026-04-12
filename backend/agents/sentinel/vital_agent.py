"""Vital agent: checks incoming vital signs for anomalies and returns a basic urgency hint."""

from agents.shared.schemas import VitalAssessment, VitalSigns


async def inspect_vitals(vitals: VitalSigns | None) -> VitalAssessment | None:
    if vitals is None:
        return None

    critical_abnormality = (
        vitals.heart_rate < 40
        or vitals.heart_rate > 140
        or vitals.blood_oxygen_sp02 < 90
        or vitals.blood_pressure_systolic < 90
    )
    anomaly_detected = critical_abnormality or (
        vitals.heart_rate < 45
        or vitals.heart_rate > 130
        or vitals.blood_oxygen_sp02 < 92
    )
    severity_hint = "critical" if critical_abnormality else "medium" if anomaly_detected else "low"
    reasoning = (
        "Critical abnormal vital signs detected."
        if critical_abnormality
        else "Abnormal vital signs detected."
        if anomaly_detected
        else "Vital signs are within the expected MVP range."
    )

    return VitalAssessment(
        anomaly_detected=anomaly_detected,
        severity_hint=severity_hint,
        reasoning=reasoning,
    )
