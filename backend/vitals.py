"""Vital-sign ingestion and anomaly detection compatibility router."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, BackgroundTasks, HTTPException  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

try:
    from emergency import SeverityLevel as EmergencySeverityLevel
    from emergency import trigger_emergency
except Exception:  # pragma: no cover - keeps standalone imports safe
    EmergencySeverityLevel = None
    trigger_emergency = None


router = APIRouter(prefix="/vitals", tags=["Vitals"])


class Location(BaseModel):
    lat: float
    lng: float


class VitalsPayload(BaseModel):
    patient_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    heart_rate: float | None = None
    spo2: float | None = None
    systolic_bp: float | None = None
    diastolic_bp: float | None = None
    body_temp: float | None = None
    location: Location | None = None


class SeverityLevel(str, Enum):
    NORMAL = "normal"
    YELLOW = "yellow"
    AMBER = "amber"
    RED = "red"


class VitalsAssessment(BaseModel):
    severity: SeverityLevel
    flags: list[str] = Field(default_factory=list)
    vitals: VitalsPayload
    assessed_at: datetime = Field(default_factory=datetime.utcnow)


THRESHOLDS = {
    "heart_rate": {
        "critical_high": 150,
        "critical_low": 40,
        "warning_high": 120,
        "warning_low": 50,
        "delta_limit": 40,
    },
    "spo2": {"critical_low": 90, "warning_low": 94},
    "systolic_bp": {
        "critical_high": 180,
        "critical_low": 90,
        "warning_high": 160,
        "warning_low": 100,
    },
    "body_temp": {
        "critical_high": 40.0,
        "critical_low": 35.0,
        "warning_high": 38.5,
        "warning_low": 35.5,
    },
}

ROLLING_WINDOW_SEC = 30
MAX_BUFFER_SIZE = 50
_vitals_buffer: dict[str, list[dict]] = {}


def _severity_rank(severity: SeverityLevel) -> int:
    return {
        SeverityLevel.NORMAL: 0,
        SeverityLevel.YELLOW: 1,
        SeverityLevel.AMBER: 2,
        SeverityLevel.RED: 3,
    }[severity]


def _max_severity(current: SeverityLevel, candidate: SeverityLevel) -> SeverityLevel:
    return max(current, candidate, key=_severity_rank)


def _push_to_buffer(patient_id: str, reading: dict) -> None:
    buffer = _vitals_buffer.setdefault(patient_id, [])
    buffer.append(reading)
    if len(buffer) > MAX_BUFFER_SIZE:
        _vitals_buffer[patient_id] = buffer[-MAX_BUFFER_SIZE:]


def _get_recent_readings(patient_id: str, window_sec: int = ROLLING_WINDOW_SEC) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(seconds=window_sec)
    return [
        reading
        for reading in _vitals_buffer.get(patient_id, [])
        if reading.get("timestamp") and reading["timestamp"] >= cutoff
    ]


def assess_vitals(payload: VitalsPayload) -> VitalsAssessment:
    flags: list[str] = []
    severity = SeverityLevel.NORMAL

    if payload.heart_rate is not None:
        heart_rate = payload.heart_rate
        threshold = THRESHOLDS["heart_rate"]
        if heart_rate >= threshold["critical_high"] or heart_rate <= threshold["critical_low"]:
            flags.append(f"CRITICAL HR: {heart_rate} bpm")
            severity = SeverityLevel.RED
        elif heart_rate >= threshold["warning_high"] or heart_rate <= threshold["warning_low"]:
            flags.append(f"Abnormal HR: {heart_rate} bpm")
            severity = _max_severity(severity, SeverityLevel.YELLOW)

    if payload.spo2 is not None:
        spo2 = payload.spo2
        threshold = THRESHOLDS["spo2"]
        if spo2 <= threshold["critical_low"]:
            flags.append(f"CRITICAL SpO2: {spo2}%")
            severity = SeverityLevel.RED
        elif spo2 <= threshold["warning_low"]:
            flags.append(f"Low SpO2: {spo2}%")
            severity = _max_severity(severity, SeverityLevel.YELLOW)

    if payload.systolic_bp is not None:
        systolic_bp = payload.systolic_bp
        threshold = THRESHOLDS["systolic_bp"]
        if systolic_bp >= threshold["critical_high"] or systolic_bp <= threshold["critical_low"]:
            flags.append(f"CRITICAL BP: {systolic_bp} mmHg")
            severity = SeverityLevel.RED
        elif systolic_bp >= threshold["warning_high"] or systolic_bp <= threshold["warning_low"]:
            flags.append(f"Abnormal BP: {systolic_bp} mmHg")
            severity = _max_severity(severity, SeverityLevel.YELLOW)

    if payload.body_temp is not None:
        body_temp = payload.body_temp
        threshold = THRESHOLDS["body_temp"]
        if body_temp >= threshold["critical_high"] or body_temp <= threshold["critical_low"]:
            flags.append(f"CRITICAL temp: {body_temp} C")
            severity = SeverityLevel.RED
        elif body_temp >= threshold["warning_high"] or body_temp <= threshold["warning_low"]:
            flags.append(f"Abnormal temp: {body_temp} C")
            severity = _max_severity(severity, SeverityLevel.YELLOW)

    recent = _get_recent_readings(payload.patient_id)
    if recent and payload.heart_rate is not None:
        oldest_hr = next(
            (reading.get("heart_rate") for reading in recent if reading.get("heart_rate") is not None),
            None,
        )
        if oldest_hr is not None:
            delta = abs(payload.heart_rate - oldest_hr)
            if delta >= THRESHOLDS["heart_rate"]["delta_limit"]:
                flags.append(f"Rapid HR change: delta {delta:.0f} bpm in {ROLLING_WINDOW_SEC}s")
                severity = _max_severity(severity, SeverityLevel.AMBER)

    yellow_count = sum(1 for flag in flags if not flag.startswith("CRITICAL") and not flag.startswith("Rapid"))
    amber_count = sum(1 for flag in flags if flag.startswith("Rapid"))

    if severity == SeverityLevel.YELLOW and yellow_count >= 2:
        flags.append("COMPOUND: multiple abnormal vitals")
        severity = SeverityLevel.AMBER
    if severity == SeverityLevel.AMBER and yellow_count >= 1 and amber_count >= 1:
        flags.append("COMPOUND: rapid change plus abnormal vitals")
        severity = SeverityLevel.RED

    return VitalsAssessment(severity=severity, flags=flags, vitals=payload)


def _dispatch_severity(severity: SeverityLevel):
    if EmergencySeverityLevel is None:
        return severity
    if severity == SeverityLevel.RED:
        return EmergencySeverityLevel.RED
    if severity == SeverityLevel.AMBER:
        return EmergencySeverityLevel.AMBER
    return EmergencySeverityLevel.YELLOW


async def _process_vitals(assessment: VitalsAssessment) -> None:
    payload = assessment.vitals
    if assessment.severity not in {SeverityLevel.AMBER, SeverityLevel.RED}:
        return
    if trigger_emergency is None:
        return

    await trigger_emergency(
        patient_id=payload.patient_id,
        severity=_dispatch_severity(assessment.severity),
        vitals={
            "heart_rate": payload.heart_rate,
            "spo2": payload.spo2,
            "systolic_bp": payload.systolic_bp,
            "diastolic_bp": payload.diastolic_bp,
            "body_temp": payload.body_temp,
        },
        flags=assessment.flags,
        location=payload.location.model_dump() if payload.location else None,
    )


@router.post("/", response_model=VitalsAssessment)
async def ingest_vitals(payload: VitalsPayload, background_tasks: BackgroundTasks) -> VitalsAssessment:
    _push_to_buffer(
        payload.patient_id,
        {
            "timestamp": payload.timestamp,
            "heart_rate": payload.heart_rate,
            "spo2": payload.spo2,
            "systolic_bp": payload.systolic_bp,
            "body_temp": payload.body_temp,
            "location": payload.location.model_dump() if payload.location else None,
        },
    )
    assessment = assess_vitals(payload)
    background_tasks.add_task(_process_vitals, assessment)
    return assessment


@router.get("/{patient_id}/latest")
async def get_latest_vitals(patient_id: str) -> dict:
    buffer = _vitals_buffer.get(patient_id)
    if not buffer:
        raise HTTPException(status_code=404, detail="No vitals found for this patient")
    return buffer[-1]


@router.get("/{patient_id}/history")
async def get_vitals_history(patient_id: str, limit: int = 20) -> list[dict]:
    return _vitals_buffer.get(patient_id, [])[-limit:]
