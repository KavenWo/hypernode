"""Patient profile, incident lifecycle, and history helpers for the app layer.

This service is the consolidation point for frontend support APIs that were
previously exposed through the standalone ``backend/emergency.py`` module.
Keeping the stateful logic here lets the live FastAPI app import from one
stable location under ``app/...`` while we continue migrating toward a fuller
Firestore-backed implementation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from db.firebase_client import (
    FrontendPatientProfile,
    HistoryLogEntry,
    IncidentRecord,
    append_history_log,
    load_incident_record,
    list_history_logs,
    list_session_patient_profiles,
    load_frontend_patient_profile,
    save_frontend_patient_profile,
    save_incident_record,
)


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
    MONITORING = "monitoring"
    RESOLVED = "resolved"


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


class SmsRequest(BaseModel):
    to: str
    message: str
    incident_id: str | None = None


class SmsResult(BaseModel):
    to: str
    status: str
    provider: str = "simulation"
    simulated: bool = True
    message_id: str | None = None
    error: str | None = None


class HistoryEntry(BaseModel):
    history_id: str
    incident_id: str
    session_uid: str
    patient_id: str
    patient_name: str | None = None
    event_type: str
    severity: str | None = None
    action_taken: str | None = None
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Incident(BaseModel):
    incident_id: str
    patient_id: str
    session_uid: str
    event_type: str = "simulation"
    status: IncidentStatus
    severity: SeverityLevel = SeverityLevel.YELLOW
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    simulation_trigger: dict = Field(default_factory=dict)
    video_metadata: dict | None = None
    triage_answers: list[dict] = Field(default_factory=list)
    ai_result: dict | None = None
    final_action: str | None = None
    action_taken: dict | None = None
    execution_locked: bool = False
    execution_count: int = 0
    history_logged: bool = False
    resolved_at: datetime | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


_patients: dict[str, PatientProfile] = {}
_incidents: dict[str, Incident] = {}
_history: dict[str, HistoryEntry] = {}


def _persist_incident(incident: Incident) -> Incident:
    save_incident_record(
        IncidentRecord(
            incident_id=incident.incident_id,
            session_uid=incident.session_uid,
            patient_id=incident.patient_id,
            event_type=incident.event_type,
            status=incident.status.value,
            severity=incident.severity.value,
            simulation_trigger=incident.simulation_trigger,
            video_metadata=incident.video_metadata,
            triage_answers=incident.triage_answers,
            ai_result=incident.ai_result,
            action_execution={
                "final_action": incident.final_action,
                "action_taken": incident.action_taken,
                "execution_locked": incident.execution_locked,
                "execution_count": incident.execution_count,
                "executed_at": incident.updated_at if incident.action_taken else None,
            },
            created_at=incident.triggered_at,
            updated_at=incident.updated_at,
            resolved_at=incident.resolved_at,
        )
    )
    return incident


def _incident_from_record(record: IncidentRecord) -> Incident:
    action_execution = record.action_execution
    return Incident(
        incident_id=record.incident_id,
        patient_id=record.patient_id,
        session_uid=record.session_uid,
        event_type=record.event_type,
        status=IncidentStatus(record.status.value if hasattr(record.status, "value") else record.status),
        severity=SeverityLevel(record.severity.value if hasattr(record.severity, "value") else record.severity),
        triggered_at=record.created_at,
        simulation_trigger=record.simulation_trigger,
        video_metadata=record.video_metadata,
        triage_answers=record.triage_answers,
        ai_result=record.ai_result,
        final_action=(
            action_execution.final_action.value
            if getattr(action_execution.final_action, "value", None)
            else action_execution.final_action
        ),
        action_taken=action_execution.action_taken,
        execution_locked=action_execution.execution_locked,
        execution_count=action_execution.execution_count,
        history_logged=False,
        resolved_at=record.resolved_at,
        updated_at=record.updated_at,
    )


def _app_contacts(contacts: list[object]) -> list[EmergencyContact]:
    normalized: list[EmergencyContact] = []
    for contact in contacts:
        if isinstance(contact, EmergencyContact):
            normalized.append(contact)
            continue
        if hasattr(contact, "model_dump"):
            normalized.append(EmergencyContact.model_validate(contact.model_dump(mode="python")))
            continue
        normalized.append(EmergencyContact.model_validate(contact))
    return normalized


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


def _coerce_severity(value: str | None) -> SeverityLevel:
    normalized = (value or "").strip().lower()
    if normalized in {"critical", "red", "high"}:
        return SeverityLevel.RED
    if normalized in {"amber", "moderate", "medium"}:
        return SeverityLevel.AMBER
    return SeverityLevel.YELLOW


def load_patient_profile(patient_id: str, session_uid: str | None = None) -> PatientProfile:
    if session_uid:
        firestore_profile = load_frontend_patient_profile(patient_id, session_uid)
        return PatientProfile(
            patient_id=firestore_profile.patient_id,
            session_uid=firestore_profile.session_uid,
            full_name=firestore_profile.full_name,
            age=firestore_profile.age,
            blood_type=firestore_profile.medical_profile.blood_type,
            allergies=firestore_profile.medical_profile.allergies,
            medications=firestore_profile.medical_profile.medications,
            chronic_conditions=firestore_profile.medical_profile.chronic_conditions,
            emergency_contacts=_app_contacts(firestore_profile.emergency_contacts),
            notes=firestore_profile.medical_profile.notes,
            updated_at=firestore_profile.updated_at,
        )

    profile = _patients.get(patient_id)
    if profile is None:
        profile = _default_patient_profile(patient_id, session_uid)
        _patients[patient_id] = profile
    elif session_uid and not profile.session_uid:
        profile.session_uid = session_uid
        profile.updated_at = datetime.utcnow()
    return profile


def update_patient_profile(patient_id: str, updates: dict) -> PatientProfile:
    existing = load_patient_profile(patient_id, updates.get("session_uid"))
    merged = existing.model_dump(mode="python")
    merged.update({key: value for key, value in updates.items() if value is not None})
    profile = PatientProfile.model_validate(merged)
    profile.updated_at = datetime.utcnow()
    _patients[patient_id] = profile
    if profile.session_uid:
        serialized_contacts = [
            contact.model_dump(mode="python") if isinstance(contact, EmergencyContact) else contact
            for contact in profile.emergency_contacts
        ]
        save_frontend_patient_profile(
            FrontendPatientProfile(
                patient_id=profile.patient_id,
                session_uid=profile.session_uid,
                full_name=profile.full_name,
                age=profile.age,
                medical_profile={
                    "blood_type": profile.blood_type,
                    "allergies": profile.allergies,
                    "medications": profile.medications,
                    "chronic_conditions": profile.chronic_conditions,
                    "notes": profile.notes,
                },
                emergency_contacts=serialized_contacts,
                updated_at=profile.updated_at,
            )
        )
    return profile


def create_incident(request: StartIncidentRequest) -> Incident:
    load_patient_profile(request.patient_id, request.session_uid)
    incident = Incident(
        incident_id=f"INC-{uuid4().hex[:12].upper()}",
        patient_id=request.patient_id,
        session_uid=request.session_uid,
        status=IncidentStatus.ANALYZING,
        event_type=request.event_type,
        simulation_trigger=request.simulation_trigger,
        video_metadata=request.video_metadata,
    )
    _incidents[incident.incident_id] = incident
    _persist_incident(incident)
    return incident


def get_incident_record(incident_id: str) -> Incident:
    incident = _incidents.get(incident_id)
    if incident is not None:
        return incident

    for session_incident in _incidents.values():
        if session_incident.incident_id == incident_id:
            return session_incident

    for session_uid in {entry.session_uid for entry in _history.values()}:
        record = load_incident_record(session_uid, incident_id)
        if record is not None:
            incident = _incident_from_record(record)
            _incidents[incident.incident_id] = incident
            return incident

    raise HTTPException(status_code=404, detail="Incident not found")


def _history_summary(incident: Incident, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    if incident.action_taken and incident.action_taken.get("message"):
        return str(incident.action_taken["message"])[:240]
    if incident.ai_result and incident.ai_result.get("reasoning"):
        return str(incident.ai_result["reasoning"])[:240]
    return f"{incident.event_type} incident completed with action {incident.final_action or 'none'}."


def append_history(incident: Incident, summary: str | None = None) -> HistoryEntry:
    profile = load_patient_profile(incident.patient_id, incident.session_uid)
    entry = HistoryEntry(
        history_id=incident.incident_id,
        incident_id=incident.incident_id,
        session_uid=incident.session_uid,
        patient_id=incident.patient_id,
        patient_name=profile.full_name,
        event_type=incident.event_type,
        severity=incident.severity.value,
        action_taken=incident.final_action,
        summary=_history_summary(incident, summary),
    )
    _history[entry.history_id] = entry
    incident.history_logged = True
    incident.updated_at = datetime.utcnow()
    _incidents[incident.incident_id] = incident
    _persist_incident(incident)
    append_history_log(
        HistoryLogEntry(
            history_id=entry.history_id,
            incident_id=entry.incident_id,
            session_uid=entry.session_uid,
            patient_id=entry.patient_id,
            patient_name=entry.patient_name,
            event_type=entry.event_type,
            severity=entry.severity,
            action_taken=entry.action_taken,
            summary=entry.summary,
            created_at=entry.created_at,
        )
    )
    return entry


def update_incident_status(incident_id: str, request: IncidentStatusUpdate) -> Incident:
    incident = get_incident_record(incident_id)
    incident.status = request.state
    incident.updated_at = datetime.utcnow()
    if request.state == IncidentStatus.RESOLVED:
        incident.resolved_at = datetime.utcnow()
        if not incident.history_logged:
            append_history(incident, request.summary)
    _incidents[incident_id] = incident
    _persist_incident(incident)
    return incident


def submit_incident_answers(incident_id: str, request: SubmitAnswersRequest) -> Incident:
    incident = get_incident_record(incident_id)
    incident.status = IncidentStatus.REASONING
    incident.triage_answers = request.triage_answers
    incident.ai_result = request.ai_decision
    incident.severity = _coerce_severity(request.severity)
    incident.final_action = _normalize_action(request.final_action or (request.ai_decision or {}).get("action"))
    incident.updated_at = datetime.utcnow()
    _incidents[incident_id] = incident
    _persist_incident(incident)
    return incident


def _simulate_action(action: str, incident: Incident) -> dict:
    if action == "monitor":
        return {
            "action": action,
            "executed": True,
            "message": "Monitoring continued. No external notification sent.",
        }
    if action == "call_family":
        profile = load_patient_profile(incident.patient_id, incident.session_uid)
        sms_results = [
            send_sms_message(
                SmsRequest(
                    to=contact.phone,
                    message=f"Hypernode alert for incident {incident.incident_id}. Action: {action}.",
                    incident_id=incident.incident_id,
                )
            ).model_dump(mode="json")
            for contact in profile.emergency_contacts
        ]
        return {
            "action": action,
            "executed": True,
            "message": "Simulated family notification sent.",
            "contacts": [contact.model_dump(mode='json') for contact in profile.emergency_contacts],
            "sms_results": sms_results,
        }
    if action == "call_ambulance":
        profile = load_patient_profile(incident.patient_id, incident.session_uid)
        return {
            "action": action,
            "executed": True,
            "message": f"Simulated ambulance call created for incident {incident.incident_id}.",
            "emergency_number": "999",
            "sms_results": [
                send_sms_message(
                    SmsRequest(
                        to=contact.phone,
                        message=f"Hypernode alert for incident {incident.incident_id}. Action: {action}.",
                        incident_id=incident.incident_id,
                    )
                ).model_dump(mode="json")
                for contact in profile.emergency_contacts
            ],
        }
    return {
        "action": action,
        "executed": True,
        "message": f"Recorded action {action}.",
    }


def execute_incident_action_once(incident_id: str, action: str | None = None) -> Incident:
    incident = get_incident_record(incident_id)
    if incident.execution_locked or incident.action_taken:
        return incident

    normalized_action = _normalize_action(action or incident.final_action)
    incident.final_action = normalized_action
    incident.action_taken = _simulate_action(normalized_action, incident)
    incident.execution_locked = True
    incident.execution_count += 1
    incident.status = IncidentStatus.MONITORING if normalized_action == "monitor" else IncidentStatus.ACTION_TAKEN
    incident.updated_at = datetime.utcnow()
    _incidents[incident_id] = incident
    _persist_incident(incident)

    if not incident.history_logged:
        append_history(incident)

    return incident


def list_history_entries(
    *,
    session_uid: str | None = None,
    patient_id: str | None = None,
    limit: int = 25,
) -> list[HistoryEntry]:
    if session_uid:
        firestore_entries = list_history_logs(session_uid=session_uid, patient_id=patient_id, limit=limit)
        if firestore_entries:
            return [
                HistoryEntry(
                    history_id=entry.history_id,
                    incident_id=entry.incident_id,
                    session_uid=entry.session_uid,
                    patient_id=entry.patient_id,
                    patient_name=entry.patient_name,
                    event_type=entry.event_type,
                    severity=entry.severity,
                    action_taken=entry.action_taken,
                    summary=entry.summary,
                    created_at=entry.created_at,
                )
                for entry in firestore_entries
            ]

    entries = list(_history.values())
    if session_uid:
        entries = [entry for entry in entries if entry.session_uid == session_uid]
    if patient_id:
        entries = [entry for entry in entries if entry.patient_id == patient_id]
    entries.sort(key=lambda entry: entry.created_at, reverse=True)
    return entries[:limit]


def list_patient_profiles(session_uid: str) -> list[PatientProfile]:
    profiles = list_session_patient_profiles(session_uid)
    return [
        PatientProfile(
            patient_id=profile.patient_id,
            session_uid=profile.session_uid,
            full_name=profile.full_name,
            age=profile.age,
            blood_type=profile.medical_profile.blood_type,
            allergies=profile.medical_profile.allergies,
            medications=profile.medical_profile.medications,
            chronic_conditions=profile.medical_profile.chronic_conditions,
            emergency_contacts=_app_contacts(profile.emergency_contacts),
            notes=profile.medical_profile.notes,
            updated_at=profile.updated_at,
        )
        for profile in profiles
    ]


def send_sms_message(request: SmsRequest) -> SmsResult:
    if not request.to:
        return SmsResult(to=request.to, status="skipped", error="Missing recipient phone number")
    return SmsResult(
        to=request.to,
        status="simulated",
        message_id=f"SIM-{uuid4().hex[:12].upper()}",
    )


__all__ = [
    "ExecuteActionRequest",
    "HistoryEntry",
    "Incident",
    "IncidentStatus",
    "IncidentStatusUpdate",
    "PatientProfile",
    "PatientProfileUpdate",
    "SmsRequest",
    "SmsResult",
    "StartIncidentRequest",
    "SubmitAnswersRequest",
    "create_incident",
    "execute_incident_action_once",
    "get_incident_record",
    "list_history_entries",
    "list_patient_profiles",
    "load_patient_profile",
    "send_sms_message",
    "submit_incident_answers",
    "update_incident_status",
    "update_patient_profile",
]
