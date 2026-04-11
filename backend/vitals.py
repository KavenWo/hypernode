"""
vitals.py — Vital Signs Ingestion & Anomaly Detection Router
Golden Hour AI Platform | Backend (FastAPI)

Handles:
- POST /vitals/        → Receive vitals from wearable/IoT gateway
- GET  /vitals/{id}    → Fetch latest vitals for a patient
- GET  /vitals/{id}/history → Fetch vitals history (for trend analysis)

Anomaly detection uses a threshold + rate-of-change approach:
1. Absolute thresholds   → immediate critical flag
2. Rolling delta check   → detects rapid deterioration
3. Compound assessment   → multiple borderline signs = escalate
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks # type: ignore
from pydantic import BaseModel, Field # type: ignore
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum

# -- Internal imports (adjust paths to your project structure) --
# from db.firebase_client import db
# from routers.emergency import trigger_emergency

router = APIRouter(prefix="/vitals", tags=["Vitals"])


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class Location(BaseModel):
    lat: float
    lng: float


class VitalsPayload(BaseModel):
    """Payload received from wearable / IoT gateway."""
    patient_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    heart_rate: Optional[float] = None          # bpm
    spo2: Optional[float] = None                # percentage (0-100)
    systolic_bp: Optional[float] = None         # mmHg
    diastolic_bp: Optional[float] = None        # mmHg
    body_temp: Optional[float] = None           # °C
    location: Optional[Location] = None


class SeverityLevel(str, Enum):
    NORMAL = "normal"
    YELLOW = "yellow"      # mild concern — log + monitor
    AMBER = "amber"        # moderate — alert contacts
    RED = "red"            # critical — full emergency chain


class VitalsAssessment(BaseModel):
    """Result of anomaly detection on incoming vitals."""
    severity: SeverityLevel
    flags: list[str]                            # human-readable reasons
    vitals: VitalsPayload
    assessed_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Thresholds (configurable per deployment)
# ──────────────────────────────────────────────

THRESHOLDS = {
    "heart_rate": {
        "critical_high": 150,
        "critical_low": 40,
        "warning_high": 120,
        "warning_low": 50,
        "delta_limit": 40,          # bpm change in rolling window
    },
    "spo2": {
        "critical_low": 90,
        "warning_low": 94,
    },
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

# Rolling window size for rate-of-change detection (seconds)
ROLLING_WINDOW_SEC = 30


# ──────────────────────────────────────────────
# In-memory rolling buffer (swap for Redis/Firebase in prod)
# ──────────────────────────────────────────────

# { patient_id: [ { "timestamp": ..., "heart_rate": ..., "spo2": ... }, ... ] }
_vitals_buffer: dict[str, list[dict]] = {}

MAX_BUFFER_SIZE = 50  # keep last N readings per patient


def _push_to_buffer(patient_id: str, reading: dict):
    """Append reading to rolling buffer, trim old entries."""
    if patient_id not in _vitals_buffer:
        _vitals_buffer[patient_id] = []
    buf = _vitals_buffer[patient_id]
    buf.append(reading)
    if len(buf) > MAX_BUFFER_SIZE:
        _vitals_buffer[patient_id] = buf[-MAX_BUFFER_SIZE:]


def _get_recent_readings(patient_id: str, window_sec: int = ROLLING_WINDOW_SEC) -> list[dict]:
    """Return readings within the rolling window."""
    buf = _vitals_buffer.get(patient_id, [])
    cutoff = datetime.utcnow() - timedelta(seconds=window_sec)
    return [r for r in buf if r["timestamp"] >= cutoff]


# ──────────────────────────────────────────────
# Anomaly Detection Engine
# ──────────────────────────────────────────────

def assess_vitals(payload: VitalsPayload) -> VitalsAssessment:
    """
    Three-layer anomaly detection:
      1. Absolute threshold check
      2. Rate-of-change (delta) check
      3. Compound flag escalation
    """
    flags: list[str] = []
    severity = SeverityLevel.NORMAL

    # --- Layer 1: Absolute thresholds ---

    if payload.heart_rate is not None:
        hr = payload.heart_rate
        t = THRESHOLDS["heart_rate"]
        if hr >= t["critical_high"] or hr <= t["critical_low"]:
            flags.append(f"CRITICAL HR: {hr} bpm")
            severity = SeverityLevel.RED
        elif hr >= t["warning_high"] or hr <= t["warning_low"]:
            flags.append(f"Elevated HR: {hr} bpm")
            severity = max(severity, SeverityLevel.YELLOW, key=_severity_rank)

    if payload.spo2 is not None:
        spo2 = payload.spo2
        t = THRESHOLDS["spo2"]
        if spo2 <= t["critical_low"]:
            flags.append(f"CRITICAL SpO₂: {spo2}%")
            severity = SeverityLevel.RED
        elif spo2 <= t["warning_low"]:
            flags.append(f"Low SpO₂: {spo2}%")
            severity = max(severity, SeverityLevel.YELLOW, key=_severity_rank)

    if payload.systolic_bp is not None:
        sbp = payload.systolic_bp
        t = THRESHOLDS["systolic_bp"]
        if sbp >= t["critical_high"] or sbp <= t["critical_low"]:
            flags.append(f"CRITICAL BP: {sbp} mmHg")
            severity = SeverityLevel.RED
        elif sbp >= t["warning_high"] or sbp <= t["warning_low"]:
            flags.append(f"Abnormal BP: {sbp} mmHg")
            severity = max(severity, SeverityLevel.YELLOW, key=_severity_rank)

    if payload.body_temp is not None:
        temp = payload.body_temp
        t = THRESHOLDS["body_temp"]
        if temp >= t["critical_high"] or temp <= t["critical_low"]:
            flags.append(f"CRITICAL temp: {temp}°C")
            severity = SeverityLevel.RED
        elif temp >= t["warning_high"] or temp <= t["warning_low"]:
            flags.append(f"Abnormal temp: {temp}°C")
            severity = max(severity, SeverityLevel.YELLOW, key=_severity_rank)

    # --- Layer 2: Rate-of-change (delta) detection ---

    recent = _get_recent_readings(payload.patient_id)
    if recent and payload.heart_rate is not None:
        oldest_hr = next((r["heart_rate"] for r in recent if r.get("heart_rate") is not None), None)
        if oldest_hr is not None:
            delta = abs(payload.heart_rate - oldest_hr)
            if delta >= THRESHOLDS["heart_rate"]["delta_limit"]:
                flags.append(f"Rapid HR change: Δ{delta:.0f} bpm in {ROLLING_WINDOW_SEC}s")
                severity = max(severity, SeverityLevel.AMBER, key=_severity_rank)

    # --- Layer 3: Compound escalation ---
    # Multiple yellow flags → escalate to amber
    # Any amber + any yellow → escalate to red

    yellow_count = sum(1 for f in flags if not f.startswith("CRITICAL") and not f.startswith("Rapid"))
    amber_count = sum(1 for f in flags if f.startswith("Rapid"))

    if severity == SeverityLevel.YELLOW and yellow_count >= 2:
        severity = SeverityLevel.AMBER
        flags.append("COMPOUND: Multiple abnormal vitals")

    if severity == SeverityLevel.AMBER and yellow_count >= 1 and amber_count >= 1:
        severity = SeverityLevel.RED
        flags.append("COMPOUND: Rapid change + abnormal vitals → escalated to RED")

    return VitalsAssessment(
        severity=severity,
        flags=flags,
        vitals=payload,
    )


def _severity_rank(s: SeverityLevel) -> int:
    """Numeric rank for severity comparison."""
    return {
        SeverityLevel.NORMAL: 0,
        SeverityLevel.YELLOW: 1,
        SeverityLevel.AMBER: 2,
        SeverityLevel.RED: 3,
    }[s]


# ──────────────────────────────────────────────
# Background task: persist + trigger emergency
# ──────────────────────────────────────────────

async def _process_vitals(assessment: VitalsAssessment):
    """
    Runs after response is sent to wearable gateway.
    1. Persist vitals to Firebase
    2. If severity >= AMBER, trigger emergency pipeline
    """
    payload = assessment.vitals

    # -- Persist to Firebase --
    # vitals_doc = {
    #     "patient_id": payload.patient_id,
    #     "timestamp": payload.timestamp.isoformat(),
    #     "heart_rate": payload.heart_rate,
    #     "spo2": payload.spo2,
    #     "systolic_bp": payload.systolic_bp,
    #     "diastolic_bp": payload.diastolic_bp,
    #     "body_temp": payload.body_temp,
    #     "location": payload.location.dict() if payload.location else None,
    #     "severity": assessment.severity.value,
    #     "flags": assessment.flags,
    # }
    # db.collection("vitals").add(vitals_doc)

    # -- Trigger emergency chain if critical --
    if assessment.severity in (SeverityLevel.AMBER, SeverityLevel.RED):
        # trigger_emergency(
        #     patient_id=payload.patient_id,
        #     severity=assessment.severity,
        #     vitals=payload,
        #     flags=assessment.flags,
        # )
        print(f"🚨 EMERGENCY TRIGGERED for {payload.patient_id} — {assessment.severity.value}")
        print(f"   Flags: {assessment.flags}")
    else:
        print(f"✅ Vitals OK for {payload.patient_id} — {assessment.severity.value}")


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@router.post("/", response_model=VitalsAssessment)
async def ingest_vitals(payload: VitalsPayload, background_tasks: BackgroundTasks):
    """
    Receive vitals from wearable/IoT gateway.

    Flow:
      1. Push to rolling buffer
      2. Run anomaly detection
      3. Return assessment immediately (low latency for gateway)
      4. Background: persist to Firebase + trigger emergency if needed
    """
    # Push to rolling buffer for delta detection
    _push_to_buffer(payload.patient_id, {
        "timestamp": payload.timestamp,
        "heart_rate": payload.heart_rate,
        "spo2": payload.spo2,
        "systolic_bp": payload.systolic_bp,
        "body_temp": payload.body_temp,
    })

    # Assess
    assessment = assess_vitals(payload)

    # Fire-and-forget: persist + emergency trigger
    background_tasks.add_task(_process_vitals, assessment)

    return assessment


@router.get("/{patient_id}/latest")
async def get_latest_vitals(patient_id: str):
    """Return the most recent reading from the rolling buffer."""
    buf = _vitals_buffer.get(patient_id)
    if not buf:
        raise HTTPException(status_code=404, detail="No vitals found for this patient")
    return buf[-1]


@router.get("/{patient_id}/history")
async def get_vitals_history(patient_id: str, limit: int = 20):
    """
    Return recent vitals from the rolling buffer.
    In production, query Firebase for full history.
    """
    buf = _vitals_buffer.get(patient_id, [])
    return buf[-limit:]
