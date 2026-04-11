"""
emergency.py — Emergency Dispatch Router
Golden Hour AI Platform | Backend (FastAPI)

The nerve centre of the golden hour pipeline. When vitals.py or
the AI triage agent flags a critical event, this module:

  1. Creates an incident record (Firebase)
  2. Fetches patient profile for context
  3. Dispatches THREE actions in parallel (asyncio.gather):
     a) Twilio  → call 999 + emergency contacts
     b) Maps    → find nearest capable hospital by ETA
     c) GPS     → confirm patient location
  4. Assembles a pre-alert payload
  5. Fires the hospital webhook
  6. Enters continuous monitoring mode

Routes:
  POST /emergency/trigger          → manual/internal trigger
  GET  /emergency/{incident_id}    → get incident status
  GET  /emergency/active           → list active incidents
  POST /emergency/{incident_id}/resolve → close an incident
"""

import asyncio
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, BackgroundTasks # type: ignore
from pydantic import BaseModel, Field # type: ignore
from enum import Enum

# -- Internal imports (uncomment as you wire up each module) --
# from db.firebase_client import db
# from integrations.twilio_caller import dispatch_emergency_calls
# from integrations.maps_router import find_nearest_hospitals
# from integrations.hospital_webhook import send_pre_alert

router = APIRouter(prefix="/emergency", tags=["Emergency"])


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class SeverityLevel(str, Enum):
    YELLOW = "yellow"
    AMBER = "amber"
    RED = "red"


class IncidentStatus(str, Enum):
    TRIGGERED = "triggered"         # initial state
    DISPATCHING = "dispatching"     # parallel actions running
    HOSPITAL_ALERTED = "alerted"    # webhook sent
    MONITORING = "monitoring"       # continuous vitals streaming
    RESOLVED = "resolved"          # patient arrived / incident closed


class Location(BaseModel):
    lat: float
    lng: float


class VitalsSnapshot(BaseModel):
    """Frozen vitals at the moment of emergency trigger."""
    heart_rate: Optional[float] = None
    spo2: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    body_temp: Optional[float] = None


class AIDecisionSummary(BaseModel):
    """Subset of TriageDecision passed from the AI agent."""
    suspected_conditions: list[dict] = []
    self_help_actions: list[dict] = []
    suggested_department: str = "General ED"
    key_alerts: list[str] = []
    recommended_prep: list[str] = []
    contact_priority: list[str] = ["999"]
    summary: str = ""


class EmergencyTriggerRequest(BaseModel):
    """Payload to trigger an emergency (from vitals.py or manual)."""
    patient_id: str
    severity: SeverityLevel
    vitals: VitalsSnapshot
    location: Optional[Location] = None
    flags: list[str] = []
    ai_decision: Optional[AIDecisionSummary] = None


# ──────────────────────────────────────────────
# Incident record
# ──────────────────────────────────────────────

class Incident(BaseModel):
    """Full incident record — single source of truth."""
    incident_id: str
    patient_id: str
    severity: SeverityLevel
    status: IncidentStatus
    triggered_at: datetime
    vitals_snapshot: VitalsSnapshot
    location: Optional[Location] = None
    flags: list[str] = []

    # Enriched after profile lookup
    patient_name: str = ""
    blood_type: str = ""
    allergies: list[str] = []
    medications: list[str] = []
    chronic_conditions: list[str] = []
    emergency_contacts: list[dict] = []

    # AI triage context (if available)
    ai_decision: Optional[AIDecisionSummary] = None

    # Dispatch results (populated after parallel actions)
    twilio_call_sids: list[str] = []
    twilio_status: str = "pending"
    nearest_hospitals: list[dict] = []
    selected_hospital: Optional[dict] = None
    hospital_eta_minutes: Optional[float] = None
    webhook_sent: bool = False
    webhook_response_code: Optional[int] = None

    # Timeline
    profile_fetched_at: Optional[datetime] = None
    dispatch_started_at: Optional[datetime] = None
    dispatch_completed_at: Optional[datetime] = None
    hospital_alerted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    # Elapsed time tracking
    total_elapsed_seconds: Optional[float] = None


# In-memory store (swap for Firebase in production)
_incidents: dict[str, Incident] = {}


# ──────────────────────────────────────────────
# Patient profile fetch (stub — replace with Firebase)
# ──────────────────────────────────────────────

async def _fetch_patient_profile(patient_id: str) -> dict:
    """
    Fetch patient profile from Firebase.
    Replace this stub with actual Firebase lookup.
    """
    # Simulated profile for demo
    # In production:
    # doc = db.collection("patients").document(patient_id).get()
    # return doc.to_dict()
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


# ──────────────────────────────────────────────
# Parallel dispatch actions
# ──────────────────────────────────────────────

async def _dispatch_twilio(incident: Incident) -> dict:
    """
    Call 999 and emergency contacts via Twilio.
    Returns call SIDs and status.
    """
    # Build TTS message for 999
    tts_message = (
        f"Emergency medical alert. "
        f"Patient {incident.patient_name}, age {62}, "
        f"is experiencing a medical emergency. "
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

    # Determine call order from AI decision or default
    contact_priority = ["999"]
    if incident.ai_decision:
        contact_priority = incident.ai_decision.contact_priority
    elif incident.emergency_contacts:
        contact_priority = ["999"] + [c["phone"] for c in incident.emergency_contacts]

    # -- Actual Twilio calls (uncomment when wired) --
    # call_sids = await dispatch_emergency_calls(
    #     numbers=contact_priority,
    #     tts_message=tts_message,
    #     patient_id=incident.patient_id,
    # )

    # Simulated response for demo
    call_sids = [f"CA{uuid4().hex[:16]}" for _ in contact_priority]

    print(f"   📞 Twilio: calling {contact_priority}")
    print(f"   📞 TTS: {tts_message[:80]}...")

    return {
        "call_sids": call_sids,
        "status": "calls_initiated",
        "numbers_called": contact_priority,
    }


async def _dispatch_maps(incident: Incident) -> dict:
    """
    Find nearest hospitals by drive-time ETA.
    Filters by capability if AI suggests a department.
    """
    if not incident.location:
        return {"hospitals": [], "error": "No patient location available"}

    # Determine required capability from AI decision
    required_dept = "General ED"
    if incident.ai_decision:
        required_dept = incident.ai_decision.suggested_department

    # -- Actual Maps API call (uncomment when wired) --
    # hospitals = await find_nearest_hospitals(
    #     lat=incident.location.lat,
    #     lng=incident.location.lng,
    #     required_department=required_dept,
    #     max_results=5,
    # )

    # Simulated response for demo (KL area hospitals)
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

    # Select best hospital: match department, then sort by ETA
    matched = [h for h in hospitals if required_dept in h.get("departments", [])]
    if not matched:
        matched = hospitals  # fall back to all if no match
    best = sorted(matched, key=lambda h: h["eta_minutes"])[0]

    print(f"   🗺️  Maps: {len(hospitals)} hospitals found, best = {best['name']} ({best['eta_minutes']} min)")

    return {
        "hospitals": hospitals,
        "selected": best,
        "eta_minutes": best["eta_minutes"],
        "required_department": required_dept,
    }


async def _confirm_location(incident: Incident) -> dict:
    """
    Confirm patient GPS coordinates.
    In production, this would check the latest wearable reading
    and fall back to last known location if GPS is stale.
    """
    if incident.location:
        # Check staleness (in production, compare timestamp)
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


# ──────────────────────────────────────────────
# Hospital webhook
# ──────────────────────────────────────────────

async def _fire_hospital_webhook(incident: Incident) -> dict:
    """
    Send pre-alert payload to the selected hospital's system.
    """
    if not incident.selected_hospital:
        return {"sent": False, "error": "No hospital selected"}

    # Build the pre-alert payload the ER team will see
    pre_alert = {
        "incident_id": incident.incident_id,
        "severity": incident.severity.value,
        "eta_minutes": incident.hospital_eta_minutes,

        # Patient identity
        "patient_name": incident.patient_name,
        "blood_type": incident.blood_type,

        # Medical context
        "allergies": incident.allergies,
        "medications": incident.medications,
        "chronic_conditions": incident.chronic_conditions,

        # Current vitals
        "vitals": {
            "heart_rate": incident.vitals_snapshot.heart_rate,
            "spo2": incident.vitals_snapshot.spo2,
            "systolic_bp": incident.vitals_snapshot.systolic_bp,
            "body_temp": incident.vitals_snapshot.body_temp,
        },

        # AI-enriched context
        "suspected_conditions": (
            incident.ai_decision.suspected_conditions
            if incident.ai_decision else []
        ),
        "suggested_department": (
            incident.ai_decision.suggested_department
            if incident.ai_decision else "General ED"
        ),
        "recommended_prep": (
            incident.ai_decision.recommended_prep
            if incident.ai_decision else ["Standard emergency intake"]
        ),
        "key_alerts": (
            incident.ai_decision.key_alerts
            if incident.ai_decision else []
        ),

        # Location
        "patient_location": (
            {"lat": incident.location.lat, "lng": incident.location.lng}
            if incident.location else None
        ),

        "timestamp": datetime.utcnow().isoformat(),
    }

    # -- Actual webhook call (uncomment when wired) --
    # response = await send_pre_alert(
    #     hospital_endpoint=incident.selected_hospital.get("webhook_url"),
    #     payload=pre_alert,
    # )
    # return {"sent": True, "status_code": response.status_code}

    print(f"   🏥 Webhook → {incident.selected_hospital['name']}")
    print(f"   🏥 Payload keys: {list(pre_alert.keys())}")

    return {"sent": True, "status_code": 200, "payload": pre_alert}


# ──────────────────────────────────────────────
# Main dispatch orchestrator
# ──────────────────────────────────────────────

async def _run_dispatch(incident_id: str):
    """
    Full emergency dispatch pipeline.
    Runs as a background task after the trigger endpoint responds.

    Timeline:
      t=0s   Incident created
      t≈0.2s Patient profile fetched
      t≈2s   Parallel dispatch (Twilio + Maps + GPS) — asyncio.gather
      t≈4s   Hospital selected, pre-alert payload assembled
      t≈5s   Hospital webhook fired
      t≈6s   Monitoring mode active
    """
    incident = _incidents.get(incident_id)
    if not incident:
        return

    try:
        # ── Step 1: Fetch patient profile ──
        incident.status = IncidentStatus.DISPATCHING
        profile = await _fetch_patient_profile(incident.patient_id)

        incident.patient_name = profile.get("name", "Unknown")
        incident.blood_type = profile.get("blood_type", "Unknown")
        incident.allergies = profile.get("allergies", [])
        incident.medications = profile.get("medications", [])
        incident.chronic_conditions = profile.get("chronic_conditions", [])
        incident.emergency_contacts = profile.get("emergency_contacts", [])
        incident.profile_fetched_at = datetime.utcnow()

        print(f"\n{'='*60}")
        print(f"🚨 EMERGENCY DISPATCH — Incident {incident_id[:8]}...")
        print(f"   Patient: {incident.patient_name}")
        print(f"   Severity: {incident.severity.value}")
        print(f"   Flags: {incident.flags}")
        if incident.ai_decision:
            print(f"   AI summary: {incident.ai_decision.summary}")
        print(f"{'='*60}")

        # ── Step 2: Parallel dispatch ──
        incident.dispatch_started_at = datetime.utcnow()

        twilio_result, maps_result, location_result = await asyncio.gather(
            _dispatch_twilio(incident),
            _dispatch_maps(incident),
            _confirm_location(incident),
            return_exceptions=True,
        )

        # Process Twilio result
        if isinstance(twilio_result, Exception):
            print(f"   ❌ Twilio error: {twilio_result}")
            incident.twilio_status = "error"
        else:
            incident.twilio_call_sids = twilio_result.get("call_sids", [])
            incident.twilio_status = twilio_result.get("status", "unknown")

        # Process Maps result
        if isinstance(maps_result, Exception):
            print(f"   ❌ Maps error: {maps_result}")
        else:
            incident.nearest_hospitals = maps_result.get("hospitals", [])
            incident.selected_hospital = maps_result.get("selected")
            incident.hospital_eta_minutes = maps_result.get("eta_minutes")

        # Process location confirmation
        if isinstance(location_result, Exception):
            print(f"   ❌ Location error: {location_result}")
        else:
            incident.location = Location(
                lat=location_result["lat"],
                lng=location_result["lng"],
            )

        incident.dispatch_completed_at = datetime.utcnow()

        # ── Step 3: Fire hospital webhook ──
        webhook_result = await _fire_hospital_webhook(incident)
        incident.webhook_sent = webhook_result.get("sent", False)
        incident.webhook_response_code = webhook_result.get("status_code")
        incident.hospital_alerted_at = datetime.utcnow()
        incident.status = IncidentStatus.HOSPITAL_ALERTED

        # Calculate total elapsed time
        elapsed = (incident.hospital_alerted_at - incident.triggered_at).total_seconds()
        incident.total_elapsed_seconds = round(elapsed, 2)

        print(f"\n   ✅ DISPATCH COMPLETE in {elapsed:.1f}s")
        print(f"   🏥 Hospital: {incident.selected_hospital['name'] if incident.selected_hospital else 'None'}")
        print(f"   ⏱️  ETA: {incident.hospital_eta_minutes} minutes")
        print(f"{'='*60}\n")

        # ── Step 4: Enter monitoring mode ──
        incident.status = IncidentStatus.MONITORING

        # In production: start streaming live vitals to hospital
        # await _start_vitals_stream(incident)

        # Persist to Firebase
        # db.collection("incidents").document(incident_id).set(incident.dict())

    except Exception as e:
        print(f"   ❌ DISPATCH FAILED: {e}")
        incident.status = IncidentStatus.TRIGGERED  # allow retry


# ──────────────────────────────────────────────
# Public API: trigger_emergency (called by vitals.py)
# ──────────────────────────────────────────────

async def trigger_emergency(
    patient_id: str,
    severity: SeverityLevel,
    vitals: dict,
    flags: list[str],
    ai_decision: Optional[dict] = None,
    location: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> str:
    """
    Entry point called by vitals.py or the AI triage agent.
    Creates an incident and kicks off the dispatch pipeline.

    Returns the incident_id for tracking.
    """
    incident_id = f"INC-{uuid4().hex[:12].upper()}"
    now = datetime.utcnow()

    # Build AI decision summary if provided
    ai_summary = None
    if ai_decision:
        ai_summary = AIDecisionSummary(
            suspected_conditions=getattr(ai_decision, "suspected_conditions", []),
            self_help_actions=getattr(ai_decision, "self_help_actions", []),
            suggested_department=getattr(
                getattr(ai_decision, "hospital_context", None),
                "suggested_department", "General ED"
            ),
            key_alerts=getattr(
                getattr(ai_decision, "hospital_context", None),
                "key_alerts", []
            ),
            recommended_prep=getattr(
                getattr(ai_decision, "hospital_context", None),
                "recommended_prep", []
            ),
            contact_priority=getattr(ai_decision, "contact_priority", ["999"]),
            summary=getattr(ai_decision, "summary", ""),
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

    # Fire dispatch as background task
    if background_tasks:
        background_tasks.add_task(_run_dispatch, incident_id)
    else:
        # Direct call (from simulator or internal trigger)
        asyncio.create_task(_run_dispatch(incident_id))

    return incident_id


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@router.post("/trigger")
async def trigger_emergency_route(
    req: EmergencyTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Manually trigger an emergency (for testing / demo).
    In production, this is called internally by vitals.py.
    """
    incident_id = await trigger_emergency(
        patient_id=req.patient_id,
        severity=req.severity,
        vitals=req.vitals.dict(),
        flags=req.flags,
        ai_decision=req.ai_decision,
        location=req.location.dict() if req.location else None,
        background_tasks=background_tasks,
    )

    return {
        "incident_id": incident_id,
        "status": "triggered",
        "message": f"Emergency dispatch initiated for patient {req.patient_id}",
    }


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    """Get full incident details and current status."""
    incident = _incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/")
async def list_active_incidents():
    """List all active (non-resolved) incidents."""
    active = {
        iid: inc for iid, inc in _incidents.items()
        if inc.status != IncidentStatus.RESOLVED
    }
    return {
        "active_count": len(active),
        "incidents": [
            {
                "incident_id": inc.incident_id,
                "patient_id": inc.patient_id,
                "severity": inc.severity.value,
                "status": inc.status.value,
                "triggered_at": inc.triggered_at.isoformat(),
                "hospital": inc.selected_hospital.get("name") if inc.selected_hospital else None,
                "eta_minutes": inc.hospital_eta_minutes,
                "elapsed_seconds": inc.total_elapsed_seconds,
            }
            for inc in active.values()
        ],
    }


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str):
    """Mark an incident as resolved (patient arrived / false alarm)."""
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