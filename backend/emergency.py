"""Emergency dispatch router for the standalone backend prototype."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

try:
    from google.cloud import firestore  # type: ignore
except ImportError:  # pragma: no cover - Firestore is optional for local demos
    firestore = None


router = APIRouter(prefix="/emergency", tags=["Emergency"])
api_router = APIRouter(prefix="/api/v1", tags=["Frontend API"])


class SeverityLevel(str, Enum):
    YELLOW = "yellow"
    AMBER = "amber"
    RED = "red"


class IncidentStatus(str, Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    TRIAGE = "triage"
    REASONING = "reasoning"
    ACTION_TAKEN = "action_taken"
    TRIGGERED = "triggered"
    DISPATCHING = "dispatching"
    HOSPITAL_ALERTED = "alerted"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class Location(BaseModel):
    lat: float
    lng: float


class VitalsSnapshot(BaseModel):
    heart_rate: Optional[float] = None
    spo2: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    body_temp: Optional[float] = None


class AIDecisionSummary(BaseModel):
    suspected_conditions: list[dict] = Field(default_factory=list)
    self_help_actions: list[dict] = Field(default_factory=list)
    suggested_department: str = "General ED"
    key_alerts: list[str] = Field(default_factory=list)
    recommended_prep: list[str] = Field(default_factory=lambda: ["Standard emergency intake"])
    contact_priority: list[str] = Field(default_factory=lambda: ["999"])
    summary: str = ""


class EmergencyTriggerRequest(BaseModel):
    patient_id: str
    severity: SeverityLevel
    vitals: VitalsSnapshot
    location: Optional[Location] = None
    flags: list[str] = Field(default_factory=list)
    ai_decision: Optional[AIDecisionSummary] = None


class EmergencyContact(BaseModel):
    contact_id: str = Field(default_factory=lambda: f"contact_{uuid4().hex[:8]}")
    name: str
    phone: str
    relationship: str = "emergency_contact"
    priority: int = 1


class PatientProfile(BaseModel):
    patient_id: str
    session_uid: str | None = None
    full_name: str = ""
    age: int | None = None
    blood_type: str | None = None
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    chronic_conditions: list[str] = Field(default_factory=list)
    emergency_contacts: list[EmergencyContact] = Field(default_factory=list)
    notes: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PatientProfileUpdate(BaseModel):
    session_uid: str | None = None
    full_name: str | None = None
    age: int | None = None
    blood_type: str | None = None
    allergies: list[str] | None = None
    medications: list[str] | None = None
    chronic_conditions: list[str] | None = None
    emergency_contacts: list[EmergencyContact] | None = None
    notes: str | None = None


class StartIncidentRequest(BaseModel):
    session_uid: str
    patient_id: str
    event_type: str = "simulation"
    simulation_trigger: dict = Field(default_factory=dict)
    video_metadata: dict | None = None


class IncidentStatusUpdate(BaseModel):
    state: IncidentStatus
    summary: str | None = None


class SubmitAnswersRequest(BaseModel):
    triage_answers: list[dict] = Field(default_factory=list)
    ai_decision: dict | None = None
    severity: str | None = None
    final_action: str | None = None


class ExecuteActionRequest(BaseModel):
    action: str | None = None


class HistoryEntry(BaseModel):
    history_id: str
    incident_id: str
    session_uid: str
    patient_id: str
    event_type: str
    severity: str | None = None
    action_taken: str | None = None
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Incident(BaseModel):
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

    session_uid: str | None = None
    event_type: str = "emergency"
    simulation_trigger: dict = Field(default_factory=dict)
    video_metadata: dict | None = None
    triage_answers: list[dict] = Field(default_factory=list)
    ai_result: dict | None = None
    final_action: str | None = None
    action_taken: dict | None = None
    execution_locked: bool = False
    execution_count: int = 0
    history_logged: bool = False
    updated_at: datetime = Field(default_factory=datetime.utcnow)


_incidents: dict[str, Incident] = {}
_patients: dict[str, PatientProfile] = {}
_history: dict[str, HistoryEntry] = {}


def _get_firestore_client():
    project_id = os.getenv("FIRESTORE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if firestore is None or not project_id:
        return None
    return firestore.Client(project=project_id)


def _strip_none(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value is not None}


def _model_payload(model: BaseModel) -> dict:
    return _strip_none(model.model_dump(mode="json"))


def _default_patient_profile(patient_id: str, session_uid: str | None = None) -> PatientProfile:
    return PatientProfile(
        patient_id=patient_id,
        session_uid=session_uid,
        full_name="Ahmad bin Ibrahim",
        age=62,
        blood_type="O+",
        allergies=["Penicillin"],
        medications=["Warfarin 5mg", "Metformin 500mg"],
        chronic_conditions=["Type 2 Diabetes", "Atrial Fibrillation"],
        emergency_contacts=[
            EmergencyContact(
                contact_id="contact_1",
                name="Siti binti Ahmad",
                phone="+60123456789",
                relationship="Wife",
                priority=1,
            ),
            EmergencyContact(
                contact_id="contact_2",
                name="Dr. Lee Wei Ming",
                phone="+60198765432",
                relationship="Family Doctor",
                priority=2,
            ),
        ],
    )


def _save_patient_profile(profile: PatientProfile) -> PatientProfile:
    profile.updated_at = datetime.utcnow()
    _patients[profile.patient_id] = profile

    client = _get_firestore_client()
    if client is None:
        return profile

    patient_ref = client.collection("patients").document(profile.patient_id)
    patient_ref.set(_model_payload(profile), merge=True)
    patient_ref.collection("medical_profile").document("current").set(_model_payload(profile), merge=True)
    for contact in profile.emergency_contacts:
        patient_ref.collection("emergency_contacts").document(contact.contact_id).set(
            _model_payload(contact),
            merge=True,
        )
    return profile


def _load_patient_profile(patient_id: str, session_uid: str | None = None) -> PatientProfile:
    if patient_id in _patients:
        return _patients[patient_id]

    client = _get_firestore_client()
    if client is not None:
        document = client.collection("patients").document(patient_id).get()
        if document.exists:
            profile = PatientProfile.model_validate(document.to_dict())
            _patients[patient_id] = profile
            return profile

    profile = _default_patient_profile(patient_id, session_uid)
    _patients[patient_id] = profile
    return profile


def _update_patient_profile(patient_id: str, updates: dict) -> PatientProfile:
    profile = _load_patient_profile(patient_id, updates.get("session_uid"))
    clean_updates = {key: value for key, value in updates.items() if value is not None}
    updated = profile.model_copy(update=clean_updates)
    return _save_patient_profile(updated)


def _save_incident(incident: Incident) -> Incident:
    incident.updated_at = datetime.utcnow()
    _incidents[incident.incident_id] = incident

    client = _get_firestore_client()
    if client is None:
        return incident

    payload = _model_payload(incident)
    client.collection("incidents").document(incident.incident_id).set(payload, merge=True)
    if incident.session_uid:
        (
            client.collection("sessions")
            .document(incident.session_uid)
            .collection("incidents")
            .document(incident.incident_id)
            .set(payload, merge=True)
        )
    return incident


def _load_incident(incident_id: str) -> Incident | None:
    if incident_id in _incidents:
        return _incidents[incident_id]

    client = _get_firestore_client()
    if client is None:
        return None

    document = client.collection("incidents").document(incident_id).get()
    if not document.exists:
        return None
    incident = Incident.model_validate(document.to_dict())
    _incidents[incident_id] = incident
    return incident


def _incident_or_404(incident_id: str) -> Incident:
    incident = _load_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def _normalize_action(action: str | None) -> str:
    normalized = (action or "monitor").strip().lower()
    aliases = {
        "monitoring": "monitor",
        "contact_family": "call_family",
        "notify_family": "call_family",
        "emergency_dispatch": "call_ambulance",
        "dispatch": "call_ambulance",
        "ambulance": "call_ambulance",
    }
    return aliases.get(normalized, normalized)


def _history_summary(incident: Incident) -> str:
    if incident.action_taken and incident.action_taken.get("message"):
        return str(incident.action_taken["message"])[:240]
    if incident.ai_result and incident.ai_result.get("reasoning"):
        return str(incident.ai_result["reasoning"])[:240]
    if incident.ai_decision and incident.ai_decision.summary:
        return incident.ai_decision.summary[:240]
    return f"{incident.event_type} incident completed with action {incident.final_action or 'none'}."


def _append_history(incident: Incident, summary: str | None = None) -> HistoryEntry:
    session_uid = incident.session_uid or "unknown_session"
    entry = HistoryEntry(
        history_id=incident.incident_id,
        incident_id=incident.incident_id,
        session_uid=session_uid,
        patient_id=incident.patient_id,
        event_type=incident.event_type,
        severity=incident.severity.value if isinstance(incident.severity, SeverityLevel) else str(incident.severity),
        action_taken=incident.final_action,
        summary=summary or _history_summary(incident),
    )
    _history[entry.history_id] = entry
    incident.history_logged = True

    client = _get_firestore_client()
    if client is not None:
        payload = _model_payload(entry)
        client.collection("history").document(entry.history_id).set(payload, merge=True)
        (
            client.collection("sessions")
            .document(session_uid)
            .collection("history")
            .document(entry.history_id)
            .set(payload, merge=True)
        )
        (
            client.collection("patients")
            .document(incident.patient_id)
            .collection("history")
            .document(entry.history_id)
            .set(payload, merge=True)
        )
    _save_incident(incident)
    return entry


async def _fetch_patient_profile(patient_id: str) -> dict:
    profile = _load_patient_profile(patient_id)
    return {
        "name": profile.full_name,
        "age": profile.age,
        "blood_type": profile.blood_type,
        "allergies": profile.allergies,
        "medications": profile.medications,
        "chronic_conditions": profile.chronic_conditions,
        "emergency_contacts": [
            {
                "name": contact.name,
                "phone": contact.phone,
                "relation": contact.relationship,
            }
            for contact in profile.emergency_contacts
        ],
    }


def _value_from_source(source: object, key: str, default):
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


async def _dispatch_twilio(incident: Incident) -> dict:
    contact_priority = ["999"]
    if incident.ai_decision:
        contact_priority = incident.ai_decision.contact_priority
    elif incident.emergency_contacts:
        contact_priority = ["999"] + [contact["phone"] for contact in incident.emergency_contacts]

    return {
        "call_sids": [f"CA{uuid4().hex[:16]}" for _ in contact_priority],
        "status": "calls_initiated",
        "numbers_called": contact_priority,
    }


async def _dispatch_maps(incident: Incident) -> dict:
    if not incident.location:
        return {"hospitals": [], "selected": None, "eta_minutes": None}

    required_dept = incident.ai_decision.suggested_department if incident.ai_decision else "General ED"
    hospitals = [
        {
            "name": "Hospital Kuala Lumpur",
            "lat": 3.1714,
            "lng": 101.7004,
            "eta_minutes": 8.2,
            "distance_km": 4.1,
            "departments": ["General ED", "Cardiology", "Trauma"],
        },
        {
            "name": "Institut Jantung Negara",
            "lat": 3.1630,
            "lng": 101.6962,
            "eta_minutes": 10.5,
            "distance_km": 5.3,
            "departments": ["Cardiology", "Cardiac Surgery"],
        },
    ]
    matched = [hospital for hospital in hospitals if required_dept in hospital["departments"]]
    selected = sorted(matched or hospitals, key=lambda hospital: hospital["eta_minutes"])[0]
    return {"hospitals": hospitals, "selected": selected, "eta_minutes": selected["eta_minutes"]}


async def _confirm_location(incident: Incident) -> dict:
    if incident.location:
        return {"lat": incident.location.lat, "lng": incident.location.lng}
    return {"lat": 3.1390, "lng": 101.6869}


async def _fire_hospital_webhook(incident: Incident) -> dict:
    if not incident.selected_hospital:
        return {"sent": False, "status_code": None}
    return {
        "sent": True,
        "status_code": 200,
        "payload": {
            "incident_id": incident.incident_id,
            "severity": incident.severity.value,
            "eta_minutes": incident.hospital_eta_minutes,
            "patient_name": incident.patient_name,
            "vitals": incident.vitals_snapshot.model_dump(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


async def _run_dispatch(incident_id: str) -> None:
    incident = _load_incident(incident_id)
    if not incident:
        return

    try:
        incident.status = IncidentStatus.DISPATCHING
        _save_incident(incident)
        profile = await _fetch_patient_profile(incident.patient_id)
        incident.patient_name = profile.get("name", "Unknown")
        incident.blood_type = profile.get("blood_type", "Unknown")
        incident.allergies = profile.get("allergies", [])
        incident.medications = profile.get("medications", [])
        incident.chronic_conditions = profile.get("chronic_conditions", [])
        incident.emergency_contacts = profile.get("emergency_contacts", [])
        incident.profile_fetched_at = datetime.utcnow()
        _save_incident(incident)

        incident.dispatch_started_at = datetime.utcnow()
        twilio_result, maps_result, location_result = await asyncio.gather(
            _dispatch_twilio(incident),
            _dispatch_maps(incident),
            _confirm_location(incident),
        )

        incident.twilio_call_sids = twilio_result.get("call_sids", [])
        incident.twilio_status = twilio_result.get("status", "unknown")
        incident.nearest_hospitals = maps_result.get("hospitals", [])
        incident.selected_hospital = maps_result.get("selected")
        incident.hospital_eta_minutes = maps_result.get("eta_minutes")
        incident.location = Location(lat=location_result["lat"], lng=location_result["lng"])
        incident.dispatch_completed_at = datetime.utcnow()

        webhook_result = await _fire_hospital_webhook(incident)
        incident.webhook_sent = webhook_result.get("sent", False)
        incident.webhook_response_code = webhook_result.get("status_code")
        incident.hospital_alerted_at = datetime.utcnow()
        incident.total_elapsed_seconds = round(
            (incident.hospital_alerted_at - incident.triggered_at).total_seconds(),
            2,
        )
        incident.status = IncidentStatus.MONITORING
        incident.action_taken = {
            "action": incident.final_action or "call_ambulance",
            "executed": True,
            "message": "Emergency dispatch simulation completed.",
            "twilio_status": incident.twilio_status,
            "hospital": incident.selected_hospital.get("name") if incident.selected_hospital else None,
        }
        incident.execution_locked = True
        incident.execution_count = max(incident.execution_count, 1)
        _save_incident(incident)
        _append_history(incident)
    except Exception:
        incident.status = IncidentStatus.TRIGGERED
        _save_incident(incident)


async def trigger_emergency(
    patient_id: str,
    severity: SeverityLevel,
    vitals: dict,
    flags: list[str],
    ai_decision: Optional[object] = None,
    location: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> str:
    incident_id = f"INC-{uuid4().hex[:12].upper()}"
    hospital_context = _value_from_source(ai_decision, "hospital_context", None)
    ai_summary = (
        AIDecisionSummary(
            suspected_conditions=_value_from_source(ai_decision, "suspected_conditions", []),
            self_help_actions=_value_from_source(ai_decision, "self_help_actions", []),
            suggested_department=_value_from_source(
                hospital_context,
                "suggested_department",
                _value_from_source(ai_decision, "suggested_department", "General ED"),
            ),
            key_alerts=_value_from_source(hospital_context, "key_alerts", []),
            recommended_prep=_value_from_source(hospital_context, "recommended_prep", []),
            contact_priority=_value_from_source(ai_decision, "contact_priority", ["999"]),
            summary=_value_from_source(ai_decision, "summary", ""),
        )
        if ai_decision
        else None
    )

    incident = Incident(
        incident_id=incident_id,
        patient_id=patient_id,
        severity=severity,
        status=IncidentStatus.TRIGGERED,
        triggered_at=datetime.utcnow(),
        vitals_snapshot=VitalsSnapshot(**vitals) if isinstance(vitals, dict) else vitals,
        location=Location(**location) if location and isinstance(location, dict) else location,
        flags=flags,
        ai_decision=ai_summary,
        final_action="call_ambulance" if severity == SeverityLevel.RED else "call_family",
    )
    _save_incident(incident)

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
    incident_id = await trigger_emergency(
        patient_id=req.patient_id,
        severity=req.severity,
        vitals=req.vitals.model_dump(),
        flags=req.flags,
        ai_decision=req.ai_decision,
        location=req.location.model_dump() if req.location else None,
        background_tasks=background_tasks,
    )
    return {"incident_id": incident_id, "status": "triggered"}


@router.get("/")
async def list_active_incidents():
    active = [
        incident
        for incident in _incidents.values()
        if incident.status != IncidentStatus.RESOLVED
    ]
    return {"active_count": len(active), "incidents": active}


@router.get("/active")
async def list_active_incidents_alias():
    return await list_active_incidents()


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    incident = _incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str):
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
    }


def _create_lifecycle_incident(request: StartIncidentRequest) -> Incident:
    _load_patient_profile(request.patient_id, request.session_uid)
    incident = Incident(
        incident_id=f"INC-{uuid4().hex[:12].upper()}",
        patient_id=request.patient_id,
        session_uid=request.session_uid,
        severity=SeverityLevel.YELLOW,
        status=IncidentStatus.ANALYZING,
        triggered_at=datetime.utcnow(),
        vitals_snapshot=VitalsSnapshot(),
        event_type=request.event_type,
        simulation_trigger=request.simulation_trigger,
        video_metadata=request.video_metadata,
    )
    return _save_incident(incident)


def _simulate_action(action: str, incident: Incident) -> dict:
    if action == "monitor":
        return {
            "action": action,
            "executed": True,
            "message": "Monitoring continued. No external notification sent.",
        }
    if action == "call_family":
        profile = _load_patient_profile(incident.patient_id, incident.session_uid)
        contacts = [contact.model_dump(mode="json") for contact in profile.emergency_contacts]
        return {
            "action": action,
            "executed": True,
            "message": "Simulated family notification sent.",
            "contacts": contacts,
        }
    if action == "call_ambulance":
        return {
            "action": action,
            "executed": True,
            "message": f"Simulated ambulance call created for incident {incident.incident_id}.",
            "emergency_number": "999",
        }
    return {
        "action": action,
        "executed": True,
        "message": f"Recorded action {action}.",
    }


@api_router.get("/patients/{patient_id}/profile", response_model=PatientProfile)
async def get_current_profile(
    patient_id: str,
    session_uid: str | None = Query(default=None),
) -> PatientProfile:
    """Read the current patient profile."""
    return _load_patient_profile(patient_id, session_uid)


@api_router.patch("/patients/{patient_id}/profile", response_model=PatientProfile)
async def update_current_profile(
    patient_id: str,
    request: PatientProfileUpdate,
) -> PatientProfile:
    """Update patient details and emergency contacts."""
    return _update_patient_profile(patient_id, request.model_dump(exclude_unset=True))


@api_router.post("/incidents", response_model=Incident)
async def start_incident(request: StartIncidentRequest) -> Incident:
    """Create a new simulation incident and attach it to the session/user."""
    return _create_lifecycle_incident(request)


@api_router.get("/incidents/{incident_id}", response_model=Incident)
async def get_lifecycle_incident(incident_id: str) -> Incident:
    """Return the stored incident lifecycle record."""
    return _incident_or_404(incident_id)


@api_router.get("/incidents/{incident_id}/result", response_model=Incident)
async def get_incident_result(incident_id: str) -> Incident:
    """Return the incident result, including AI decision and final action."""
    return _incident_or_404(incident_id)


@api_router.patch("/incidents/{incident_id}/status", response_model=Incident)
async def update_lifecycle_status(
    incident_id: str,
    request: IncidentStatusUpdate,
) -> Incident:
    """Update incident status and log resolved runs to history."""
    incident = _incident_or_404(incident_id)
    incident.status = request.state
    if request.state == IncidentStatus.RESOLVED:
        incident.resolved_at = datetime.utcnow()
    _save_incident(incident)
    if request.state == IncidentStatus.RESOLVED and not incident.history_logged:
        _append_history(incident, request.summary)
    return incident


@api_router.post("/incidents/{incident_id}/answers", response_model=Incident)
async def submit_triage_answers(
    incident_id: str,
    request: SubmitAnswersRequest,
) -> Incident:
    """Store triage answers, AI result, severity, and final recommended action."""
    incident = _incident_or_404(incident_id)
    incident.status = IncidentStatus.REASONING
    incident.triage_answers = request.triage_answers
    incident.ai_result = request.ai_decision
    if request.ai_decision:
        incident.ai_decision = AIDecisionSummary(
            suspected_conditions=request.ai_decision.get("suspected_conditions", []),
            self_help_actions=request.ai_decision.get("self_help_actions", []),
            suggested_department=request.ai_decision.get("suggested_department", "General ED"),
            key_alerts=request.ai_decision.get("key_alerts", []),
            recommended_prep=request.ai_decision.get("recommended_prep", ["Standard emergency intake"]),
            contact_priority=request.ai_decision.get("contact_priority", ["999"]),
            summary=request.ai_decision.get("summary", request.ai_decision.get("reasoning", "")),
        )
    if request.severity:
        incident.severity = SeverityLevel.RED if request.severity in {"critical", "red", "high"} else SeverityLevel.AMBER
    incident.final_action = _normalize_action(request.final_action or (request.ai_decision or {}).get("action"))
    return _save_incident(incident)


@api_router.post("/incidents/{incident_id}/triage", response_model=Incident)
async def submit_triage_answers_alias(
    incident_id: str,
    request: SubmitAnswersRequest,
) -> Incident:
    """Alias for the frontend triage-answer submission step."""
    return await submit_triage_answers(incident_id, request)


@api_router.post("/incidents/{incident_id}/execute", response_model=Incident)
async def execute_incident_action(
    incident_id: str,
    request: ExecuteActionRequest,
) -> Incident:
    """Execute the final action once. Repeated calls return the locked record."""
    incident = _incident_or_404(incident_id)
    if incident.execution_locked or incident.action_taken:
        return incident

    action = _normalize_action(request.action or incident.final_action)
    incident.final_action = action
    incident.action_taken = _simulate_action(action, incident)
    incident.execution_locked = True
    incident.execution_count += 1
    incident.status = IncidentStatus.MONITORING if action == "monitor" else IncidentStatus.ACTION_TAKEN
    _save_incident(incident)
    if not incident.history_logged:
        _append_history(incident)
    return incident


@api_router.get("/history", response_model=list[HistoryEntry])
async def fetch_history(
    session_uid: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[HistoryEntry]:
    """Fetch previous emergency runs for the History view."""
    client = _get_firestore_client()
    if client is not None:
        query = client.collection("history")
        if session_uid:
            query = query.where("session_uid", "==", session_uid)
        if patient_id:
            query = query.where("patient_id", "==", patient_id)
        entries = [HistoryEntry.model_validate(document.to_dict()) for document in query.limit(limit).stream()]
    else:
        entries = list(_history.values())
        if session_uid:
            entries = [entry for entry in entries if entry.session_uid == session_uid]
        if patient_id:
            entries = [entry for entry in entries if entry.patient_id == patient_id]

    entries.sort(key=lambda entry: entry.created_at, reverse=True)
    return entries[:limit]
