"""Emergency dispatch router and in-memory incident tracker.

This module is still a stubbed execution layer for the hackathon prototype:

1. Create an incident.
2. Enrich it with patient context.
3. Run mock Twilio, Maps, and location confirmation in parallel.
4. Build a hospital pre-alert payload.
5. Expose incident status for demos and frontend testing.

The main MVP reasoning now lives in ``app.services.mvp_flow``. This file is the
execution boundary that gets called only after the assessment decides to
escalate.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

router = APIRouter(prefix="/emergency", tags=["Emergency"])


class SeverityLevel(str, Enum):
    YELLOW = "yellow"
    AMBER = "amber"
    RED = "red"


class IncidentStatus(str, Enum):
    TRIGGERED = "triggered"
    DISPATCHING = "dispatching"
    HOSPITAL_ALERTED = "alerted"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class Location(BaseModel):
    lat: float
    lng: float


class VitalsSnapshot(BaseModel):
    """Frozen vitals at the moment the incident starts."""

    heart_rate: Optional[float] = None
    spo2: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    body_temp: Optional[float] = None


class AIDecisionSummary(BaseModel):
    """Compact AI context passed into the dispatch layer."""

    suspected_conditions: list[dict] = Field(default_factory=list)
    self_help_actions: list[dict] = Field(default_factory=list)
    suggested_department: str = "General ED"
    key_alerts: list[str] = Field(default_factory=list)
    recommended_prep: list[str] = Field(default_factory=list)
    contact_priority: list[str] = Field(default_factory=lambda: ["999"])
    summary: str = ""


class EmergencyTriggerRequest(BaseModel):
    """Payload for manual or internal emergency dispatch."""

    patient_id: str
    severity: SeverityLevel
    vitals: VitalsSnapshot
    location: Optional[Location] = None
    flags: list[str] = Field(default_factory=list)
    ai_decision: Optional[AIDecisionSummary] = None


class Incident(BaseModel):
    """Single source of truth for a mock emergency dispatch run."""

    incident_id: str
    patient_id: str
    severity: SeverityLevel
    status: IncidentStatus
    triggered_at: datetime
    vitals_snapshot: VitalsSnapshot
    location: Optional[Location] = None
    flags: list[str] = Field(default_factory=list)

    patient_name: str = ""
    blood_type: str = ""
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    chronic_conditions: list[str] = Field(default_factory=list)
    emergency_contacts: list[dict] = Field(default_factory=list)

    ai_decision: Optional[AIDecisionSummary] = None

    twilio_call_sids: list[str] = Field(default_factory=list)
    twilio_status: str = "pending"
    nearest_hospitals: list[dict] = Field(default_factory=list)
    selected_hospital: Optional[dict] = None
    hospital_eta_minutes: Optional[float] = None
    webhook_sent: bool = False
    webhook_response_code: Optional[int] = None

    profile_fetched_at: Optional[datetime] = None
    dispatch_started_at: Optional[datetime] = None
    dispatch_completed_at: Optional[datetime] = None
    hospital_alerted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    total_elapsed_seconds: Optional[float] = None


_incidents: dict[str, Incident] = {}


async def _fetch_patient_profile(patient_id: str) -> dict:
    """Stub profile lookup until Firebase is wired into the dispatch side."""
    return {
        "name": "Ahmad bin Ibrahim",
        "age": 62,
        "sex": "Male",
        "blood_type": "O+",
        "allergies": ["Penicillin"],
        "medications": ["Warfarin 5mg", "Metformin 500mg"],
        "chronic_conditions": ["Type 2 Diabetes", "Atrial Fibrillation"],
        "emergency_contacts": [
            {"name": "Siti binti Ahmad", "phone": "+60123456789", "relation": "Wife"},
            {"name": "Dr. Lee Wei Ming", "phone": "+60198765432", "relation": "Family Doctor"},
        ],
    }


def _value_from_source(source: object, key: str, default):
    """Support both dict payloads and object models from older modules."""
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


async def _dispatch_twilio(incident: Incident) -> dict:
    """Mock Twilio call fan-out using the AI-selected priority order."""
    tts_message = (
        f"Emergency medical alert. "
        f"Patient {incident.patient_name}. "
        f"Severity: {incident.severity.value}. "
    )

    if incident.ai_decision and incident.ai_decision.suspected_conditions:
        condition = incident.ai_decision.suspected_conditions[0].get("condition", "Unknown")
        tts_message += f"Suspected condition: {condition}. "

    if incident.location:
        tts_message += (
            f"Patient location: latitude {incident.location.lat:.4f}, "
            f"longitude {incident.location.lng:.4f}. "
        )

    tts_message += "Please dispatch ambulance immediately."

    contact_priority = ["999"]
    if incident.ai_decision:
        contact_priority = incident.ai_decision.contact_priority
    elif incident.emergency_contacts:
        contact_priority = ["999"] + [c["phone"] for c in incident.emergency_contacts]

    call_sids = [f"CA{uuid4().hex[:16]}" for _ in contact_priority]

    print(f"   [Twilio] Calling {contact_priority}")
    print(f"   [Twilio] TTS: {tts_message[:80]}...")

    return {
        "call_sids": call_sids,
        "status": "calls_initiated",
        "numbers_called": contact_priority,
    }


async def _dispatch_maps(incident: Incident) -> dict:
    """Mock nearest-hospital routing using a small in-memory list."""
    if not incident.location:
        return {"hospitals": [], "error": "No patient location available"}

    required_dept = "General ED"
    if incident.ai_decision:
        required_dept = incident.ai_decision.suggested_department

    hospitals = [
        {
            "name": "Hospital Kuala Lumpur",
            "lat": 3.1714,
            "lng": 101.7004,
            "eta_minutes": 8.2,
            "distance_km": 4.1,
            "departments": ["General ED", "Cardiology", "Trauma"],
            "has_cath_lab": True,
        },
        {
            "name": "Institut Jantung Negara",
            "lat": 3.1630,
            "lng": 101.6962,
            "eta_minutes": 10.5,
            "distance_km": 5.3,
            "departments": ["Cardiology", "Cardiac Surgery"],
            "has_cath_lab": True,
        },
        {
            "name": "Hospital Universiti Kebangsaan Malaysia",
            "lat": 3.0896,
            "lng": 101.7250,
            "eta_minutes": 14.1,
            "distance_km": 8.7,
            "departments": ["General ED", "Neurology", "Trauma"],
            "has_cath_lab": False,
        },
    ]

    matched = [hospital for hospital in hospitals if required_dept in hospital.get("departments", [])]
    if not matched:
        matched = hospitals
    best = sorted(matched, key=lambda hospital: hospital["eta_minutes"])[0]

    print(f"   [Maps] {len(hospitals)} hospitals found, best = {best['name']} ({best['eta_minutes']} min)")

    return {
        "hospitals": hospitals,
        "selected": best,
        "eta_minutes": best["eta_minutes"],
        "required_department": required_dept,
    }


async def _confirm_location(incident: Incident) -> dict:
    """Confirm live location or fall back to the last known coordinate."""
    if incident.location:
        return {
            "lat": incident.location.lat,
            "lng": incident.location.lng,
            "source": "latest_wearable_payload",
            "stale": False,
        }

    return {
        "lat": 3.1390,
        "lng": 101.6869,
        "source": "last_known_location",
        "stale": True,
    }


async def _fire_hospital_webhook(incident: Incident) -> dict:
    """Build the pre-alert payload that would be sent to a hospital system."""
    if not incident.selected_hospital:
        return {"sent": False, "error": "No hospital selected"}

    pre_alert = {
        "incident_id": incident.incident_id,
        "severity": incident.severity.value,
        "eta_minutes": incident.hospital_eta_minutes,
        "patient_name": incident.patient_name,
        "blood_type": incident.blood_type,
        "allergies": incident.allergies,
        "medications": incident.medications,
        "chronic_conditions": incident.chronic_conditions,
        "vitals": {
            "heart_rate": incident.vitals_snapshot.heart_rate,
            "spo2": incident.vitals_snapshot.spo2,
            "systolic_bp": incident.vitals_snapshot.systolic_bp,
            "body_temp": incident.vitals_snapshot.body_temp,
        },
        "suspected_conditions": incident.ai_decision.suspected_conditions if incident.ai_decision else [],
        "suggested_department": incident.ai_decision.suggested_department if incident.ai_decision else "General ED",
        "recommended_prep": (
            incident.ai_decision.recommended_prep if incident.ai_decision else ["Standard emergency intake"]
        ),
        "key_alerts": incident.ai_decision.key_alerts if incident.ai_decision else [],
        "patient_location": (
            {"lat": incident.location.lat, "lng": incident.location.lng} if incident.location else None
        ),
        "timestamp": datetime.utcnow().isoformat(),
    }

    print(f"   [Webhook] -> {incident.selected_hospital['name']}")
    print(f"   [Webhook] Payload keys: {list(pre_alert.keys())}")

    return {"sent": True, "status_code": 200, "payload": pre_alert}


async def _run_dispatch(incident_id: str):
    """Run the end-to-end mock dispatch pipeline in the background."""
    incident = _incidents.get(incident_id)
    if not incident:
        return

    try:
        incident.status = IncidentStatus.DISPATCHING
        profile = await _fetch_patient_profile(incident.patient_id)

        incident.patient_name = profile.get("name", "Unknown")
        incident.blood_type = profile.get("blood_type", "Unknown")
        incident.allergies = profile.get("allergies", [])
        incident.medications = profile.get("medications", [])
        incident.chronic_conditions = profile.get("chronic_conditions", [])
        incident.emergency_contacts = profile.get("emergency_contacts", [])
        incident.profile_fetched_at = datetime.utcnow()

        print(f"\n{'=' * 60}")
        print(f"[Emergency Dispatch] Incident {incident_id[:8]}...")
        print(f"   Patient: {incident.patient_name}")
        print(f"   Severity: {incident.severity.value}")
        print(f"   Flags: {incident.flags}")
        if incident.ai_decision:
            print(f"   AI summary: {incident.ai_decision.summary}")
        print(f"{'=' * 60}")

        incident.dispatch_started_at = datetime.utcnow()
        twilio_result, maps_result, location_result = await asyncio.gather(
            _dispatch_twilio(incident),
            _dispatch_maps(incident),
            _confirm_location(incident),
            return_exceptions=True,
        )

        if isinstance(twilio_result, Exception):
            print(f"   [Error] Twilio: {twilio_result}")
            incident.twilio_status = "error"
        else:
            incident.twilio_call_sids = twilio_result.get("call_sids", [])
            incident.twilio_status = twilio_result.get("status", "unknown")

        if isinstance(maps_result, Exception):
            print(f"   [Error] Maps: {maps_result}")
        else:
            incident.nearest_hospitals = maps_result.get("hospitals", [])
            incident.selected_hospital = maps_result.get("selected")
            incident.hospital_eta_minutes = maps_result.get("eta_minutes")

        if isinstance(location_result, Exception):
            print(f"   [Error] Location: {location_result}")
        else:
            incident.location = Location(
                lat=location_result["lat"],
                lng=location_result["lng"],
            )

        incident.dispatch_completed_at = datetime.utcnow()

        webhook_result = await _fire_hospital_webhook(incident)
        incident.webhook_sent = webhook_result.get("sent", False)
        incident.webhook_response_code = webhook_result.get("status_code")
        incident.hospital_alerted_at = datetime.utcnow()
        incident.status = IncidentStatus.HOSPITAL_ALERTED

        elapsed = (incident.hospital_alerted_at - incident.triggered_at).total_seconds()
        incident.total_elapsed_seconds = round(elapsed, 2)

        print(f"\n   [Done] Dispatch complete in {elapsed:.1f}s")
        print(f"   Hospital: {incident.selected_hospital['name'] if incident.selected_hospital else 'None'}")
        print(f"   ETA: {incident.hospital_eta_minutes} minutes")
        print(f"{'=' * 60}\n")

        incident.status = IncidentStatus.MONITORING
    except Exception as exc:
        print(f"   [Error] Dispatch failed: {exc}")
        incident.status = IncidentStatus.TRIGGERED


async def trigger_emergency(
    patient_id: str,
    severity: SeverityLevel,
    vitals: dict,
    flags: list[str],
    ai_decision: Optional[object] = None,
    location: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> str:
    """Create a mock incident and start the dispatch pipeline."""
    incident_id = f"INC-{uuid4().hex[:12].upper()}"
    now = datetime.utcnow()

    ai_summary = None
    if ai_decision:
        hospital_context = _value_from_source(ai_decision, "hospital_context", None)
        ai_summary = AIDecisionSummary(
            suspected_conditions=_value_from_source(ai_decision, "suspected_conditions", []),
            self_help_actions=_value_from_source(ai_decision, "self_help_actions", []),
            suggested_department=_value_from_source(
                hospital_context,
                "suggested_department",
                _value_from_source(ai_decision, "suggested_department", "General ED"),
            ),
            key_alerts=_value_from_source(
                hospital_context,
                "key_alerts",
                _value_from_source(ai_decision, "key_alerts", []),
            ),
            recommended_prep=_value_from_source(
                hospital_context,
                "recommended_prep",
                _value_from_source(ai_decision, "recommended_prep", []),
            ),
            contact_priority=_value_from_source(ai_decision, "contact_priority", ["999"]),
            summary=_value_from_source(ai_decision, "summary", ""),
        )

    incident = Incident(
        incident_id=incident_id,
        patient_id=patient_id,
        severity=severity,
        status=IncidentStatus.TRIGGERED,
        triggered_at=now,
        vitals_snapshot=VitalsSnapshot(**vitals) if isinstance(vitals, dict) else vitals,
        location=Location(**location) if location and isinstance(location, dict) else location,
        flags=flags,
        ai_decision=ai_summary,
    )

    _incidents[incident_id] = incident

    if background_tasks:
        background_tasks.add_task(_run_dispatch, incident_id)
    else:
        asyncio.create_task(_run_dispatch(incident_id))

    return incident_id


@router.post("/trigger")
async def trigger_emergency_route(
    req: EmergencyTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """Manual route for demoing the dispatch layer in isolation."""
    incident_id = await trigger_emergency(
        patient_id=req.patient_id,
        severity=req.severity,
        vitals=req.vitals.model_dump(),
        flags=req.flags,
        ai_decision=req.ai_decision,
        location=req.location.model_dump() if req.location else None,
        background_tasks=background_tasks,
    )

    return {
        "incident_id": incident_id,
        "status": "triggered",
        "message": f"Emergency dispatch initiated for patient {req.patient_id}",
    }


@router.get("/")
async def list_active_incidents():
    """List all incidents that are not resolved yet."""
    active = {
        incident_id: incident
        for incident_id, incident in _incidents.items()
        if incident.status != IncidentStatus.RESOLVED
    }
    return {
        "active_count": len(active),
        "incidents": [
            {
                "incident_id": incident.incident_id,
                "patient_id": incident.patient_id,
                "severity": incident.severity.value,
                "status": incident.status.value,
                "triggered_at": incident.triggered_at.isoformat(),
                "hospital": incident.selected_hospital.get("name") if incident.selected_hospital else None,
                "eta_minutes": incident.hospital_eta_minutes,
                "elapsed_seconds": incident.total_elapsed_seconds,
            }
            for incident in active.values()
        ],
    }


@router.get("/active")
async def list_active_incidents_alias():
    """Alias that matches the teammate module's original route documentation."""
    return await list_active_incidents()


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    """Return the full in-memory incident record."""
    incident = _incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str):
    """Resolve an incident so the demo dashboard can close it out cleanly."""
    incident = _incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = datetime.utcnow()

    total = (incident.resolved_at - incident.triggered_at).total_seconds()

    return {
        "incident_id": incident_id,
        "status": "resolved",
        "total_golden_hour_seconds": round(total, 1),
        "golden_hour_remaining_minutes": round((3600 - total) / 60, 1),
    }
