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
    IncidentRecord,
    find_incident_record,
    load_incident_record,
    list_session_incidents,
    list_session_patient_profiles,
    load_frontend_patient_profile,
    save_frontend_patient_profile,
    save_incident_record,
    find_incident_by_realtime_session_id,
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
    gender: str | None = None
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    chronic_conditions: list[str] = Field(default_factory=list)
    emergency_contacts: list[EmergencyContact] = Field(default_factory=list)
    blood_thinners: bool = False
    mobility_support: bool = False
    primary_language: str = "en"
    address: str = ""
    notes: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PatientProfileUpdate(BaseModel):
    session_uid: str | None = None
    full_name: str | None = None
    age: int | None = None
    blood_type: str | None = None
    gender: str | None = None
    allergies: list[str] | None = None
    medications: list[str] | None = None
    chronic_conditions: list[str] | None = None
    emergency_contacts: list[EmergencyContact] | None = None
    blood_thinners: bool | None = None
    mobility_support: bool | None = None
    primary_language: str | None = None
    address: str | None = None
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


class IncidentContextUpdate(BaseModel):
    conversation_history: list[dict] | None = None
    canonical_communication_state: dict | None = None
    reasoning_decision: dict | None = None
    execution_state: dict | None = None
    protocol_guidance: dict | None = None
    guidance_steps: list[str] | None = None
    reasoning_runs: list[dict] | None = None
    execution_updates: list[dict] | None = None
    action_states: list[dict] | None = None


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


class IncidentSummary(BaseModel):
    incident_id: str
    session_uid: str
    patient_id: str
    patient_name: str | None = None
    event_type: str
    severity: str | None = None
    action_taken: str | None = None
    status: str
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
    conversation_history: list[dict] = Field(default_factory=list)
    canonical_communication_state: dict | None = None
    reasoning_decision: dict | None = None
    execution_state: dict | None = None
    protocol_guidance: dict | None = None
    guidance_steps: list[str] = Field(default_factory=list)
    reasoning_runs: list[dict] = Field(default_factory=list)
    execution_updates: list[dict] = Field(default_factory=list)
    action_states: list[dict] = Field(default_factory=list)
    final_action: str | None = None
    action_taken: dict | None = None
    execution_locked: bool = False
    execution_count: int = 0
    history_logged: bool = False
    resolved_at: datetime | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


_patients: dict[str, PatientProfile] = {}
_incidents: dict[str, Incident] = {}


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
            conversation_history=incident.conversation_history,
            canonical_communication_state=incident.canonical_communication_state,
            reasoning_decision=incident.reasoning_decision,
            execution_state=incident.execution_state,
            protocol_guidance=incident.protocol_guidance,
            guidance_steps=incident.guidance_steps,
            reasoning_runs=incident.reasoning_runs,
            execution_updates=incident.execution_updates,
            action_states=incident.action_states,
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
        conversation_history=record.conversation_history,
        canonical_communication_state=record.canonical_communication_state,
        reasoning_decision=record.reasoning_decision,
        execution_state=record.execution_state,
        protocol_guidance=record.protocol_guidance,
        guidance_steps=record.guidance_steps,
        reasoning_runs=record.reasoning_runs,
        execution_updates=record.execution_updates,
        action_states=record.action_states,
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
        gender="Male",
        primary_language="en",
        address="Kuala Lumpur, Malaysia",
        blood_thinners=True,
        mobility_support=True,
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
            gender=firestore_profile.gender,
            primary_language=firestore_profile.primary_language,
            address=firestore_profile.address or "",
            blood_thinners=firestore_profile.medical_profile.blood_thinners,
            mobility_support=firestore_profile.medical_profile.mobility_support,
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
                gender=profile.gender,
                primary_language=profile.primary_language,
                address=profile.address,
                medical_profile={
                    "blood_type": profile.blood_type,
                    "blood_thinners": profile.blood_thinners,
                    "mobility_support": profile.mobility_support,
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


def get_incident_record(incident_id: str, session_uid: str | None = None) -> Incident:
    incident = _incidents.get(incident_id)
    if incident is not None:
        return incident

    for session_incident in _incidents.values():
        if session_incident.incident_id == incident_id:
            return session_incident

    if session_uid:
        record = load_incident_record(session_uid, incident_id)
        if record is not None:
            incident = _incident_from_record(record)
            _incidents[incident.incident_id] = incident
            return incident

    record = find_incident_record(incident_id)
    if record is not None:
        incident = _incident_from_record(record)
        _incidents[incident.incident_id] = incident
        return incident

    raise HTTPException(status_code=404, detail="Incident not found")


def get_incident_by_realtime_session_id(session_id: str) -> Incident | None:
    # 1. Check local in-memory cache
    for incident in _incidents.values():
        if incident.simulation_trigger.get("realtime_session_id") == session_id:
            return incident

    # 2. Check Firestore globally via collectionGroup
    record = find_incident_by_realtime_session_id(session_id)
    if record:
        incident = _incident_from_record(record)
        _incidents[incident.incident_id] = incident  # Cache locally for future turns
        return incident

    # 3. Fallback to summary list (last resort)
    for summary in list_incident_summaries(limit=100):
        incident = get_incident_record(summary.incident_id, summary.session_uid)
        if incident.simulation_trigger.get("realtime_session_id") == session_id:
            return incident

    return None


def _generate_incident_summary(incident: Incident, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    if incident.action_taken and incident.action_taken.get("message"):
        return str(incident.action_taken["message"])[:240]
    if incident.ai_result and incident.ai_result.get("reasoning"):
        return str(incident.ai_result["reasoning"])[:240]
    if incident.status.value in {"analyzing", "triage", "reasoning"}:
        return f"{incident.event_type} incident is currently in {incident.status.value} phase."
    return f"{incident.event_type} incident completed with action {incident.final_action or 'none'}."


def update_incident_status(incident_id: str, request: IncidentStatusUpdate) -> Incident:
    incident = get_incident_record(incident_id)
    incident.status = request.state
    incident.updated_at = datetime.utcnow()
    if request.state == IncidentStatus.RESOLVED:
        incident.resolved_at = datetime.utcnow()
    elif request.state != IncidentStatus.ACTION_TAKEN:
        incident.resolved_at = None
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


def update_incident_context(incident_id: str, request: IncidentContextUpdate) -> Incident:
    incident = get_incident_record(incident_id)
    payload = request.model_dump(exclude_unset=True)

    for field_name, value in payload.items():
        setattr(incident, field_name, value)

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

    return incident


def list_incident_summaries(
    *,
    session_uid: str | None = None,
    patient_id: str | None = None,
    limit: int = 25,
) -> list[IncidentSummary]:
    summaries: dict[str, IncidentSummary] = {}
    profile_cache: dict[tuple[str, str], PatientProfile] = {}

    def get_profile_for_incident(incident: Incident) -> PatientProfile:
        cache_key = (incident.session_uid, incident.patient_id)
        cached = profile_cache.get(cache_key)
        if cached is not None:
            return cached
        profile = load_patient_profile(incident.patient_id, incident.session_uid)
        profile_cache[cache_key] = profile
        return profile

    if session_uid:
        firestore_incidents = list_session_incidents(session_uid=session_uid)
        for record in firestore_incidents:
            if patient_id and record.patient_id != patient_id:
                continue
            incident = _incident_from_record(record)
            profile = get_profile_for_incident(incident)
            summaries[incident.incident_id] = IncidentSummary(
                incident_id=incident.incident_id,
                session_uid=incident.session_uid,
                patient_id=incident.patient_id,
                patient_name=profile.full_name,
                event_type=incident.event_type,
                severity=incident.severity.value,
                action_taken=incident.final_action,
                status=incident.status.value,
                summary=_generate_incident_summary(incident),
                created_at=incident.triggered_at,
            )

    for incident in _incidents.values():
        if session_uid and incident.session_uid != session_uid:
            continue
        if patient_id and incident.patient_id != patient_id:
            continue
        profile = get_profile_for_incident(incident)
        summaries[incident.incident_id] = IncidentSummary(
            incident_id=incident.incident_id,
            session_uid=incident.session_uid,
            patient_id=incident.patient_id,
            patient_name=profile.full_name,
            event_type=incident.event_type,
            severity=incident.severity.value,
            action_taken=incident.final_action,
            status=incident.status.value,
            summary=_generate_incident_summary(incident),
            created_at=incident.triggered_at,
        )

    entries = list(summaries.values())
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
            gender=profile.gender,
            primary_language=profile.primary_language,
            address=profile.address or "",
            blood_thinners=profile.medical_profile.blood_thinners,
            mobility_support=profile.medical_profile.mobility_support,
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
    "IncidentSummary",
    "Incident",
    "IncidentContextUpdate",
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
    "get_incident_by_realtime_session_id",
    "get_incident_record",
    "list_incident_summaries",
    "list_patient_profiles",
    "load_patient_profile",
    "send_sms_message",
    "submit_incident_answers",
    "update_incident_context",
    "update_incident_status",
    "update_patient_profile",
]
