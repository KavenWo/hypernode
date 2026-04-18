"""Shared database and persistence models used by the backend.

The existing fall-flow runtime still depends on the legacy ``PatientProfile``
shape loaded from ``data/sample_patient.json``. Newer frontend-support and
Firestore-backed work should use the richer models defined below alongside that
legacy profile type.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PatientProfile(BaseModel):
    """Legacy sample-profile schema used by the active fall runtime."""

    user_id: str
    full_name: str
    age: int
    pre_existing_conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    emergency_contacts: list[str] = Field(default_factory=list)
    blood_thinners: bool = False
    mobility_support: bool = False
    primary_language: str = "en"
    address: str | None = None


class IncidentState(BaseModel):
    """Legacy fall-state snapshot retained for current agent runtime usage."""

    user_id: str
    bystander_present: bool = False
    responded_within_30s: bool = False
    user_requested_ambulance: bool = False
    bleeding_observed: bool = False
    breathing_status: str = "unknown"
    dispatch_status: str = "pending"


class IncidentLifecycleStatus(str, Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    TRIAGE = "triage"
    REASONING = "reasoning"
    ACTION_TAKEN = "action_taken"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class IncidentSeverity(str, Enum):
    YELLOW = "yellow"
    AMBER = "amber"
    RED = "red"


class IncidentActionType(str, Enum):
    MONITOR = "monitor"
    CALL_FAMILY = "call_family"
    CALL_AMBULANCE = "call_ambulance"


class AnonymousSession(BaseModel):
    session_uid: str
    auth_provider: str = "firebase_anonymous"
    patient_ids: list[str] = Field(default_factory=list)
    default_patient_seeded: bool = False
    active_patient_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    active_incident_id: str | None = None


class EmergencyContact(BaseModel):
    contact_id: str
    name: str
    phone: str
    relationship: str = "emergency_contact"
    priority: int = 1


class MedicalProfile(BaseModel):
    blood_type: str | None = None
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    chronic_conditions: list[str] = Field(default_factory=list)
    blood_thinners: bool = False
    mobility_support: bool = False
    notes: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FrontendPatientProfile(BaseModel):
    patient_id: str
    session_uid: str | None = None
    full_name: str = ""
    age: int | None = None
    primary_language: str = "en"
    address: str | None = None
    medical_profile: MedicalProfile = Field(default_factory=MedicalProfile)
    emergency_contacts: list[EmergencyContact] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ActionExecutionState(BaseModel):
    final_action: IncidentActionType | None = None
    action_taken: dict | None = None
    execution_locked: bool = False
    execution_count: int = 0
    executed_at: datetime | None = None


class IncidentRecord(BaseModel):
    incident_id: str
    session_uid: str
    patient_id: str
    event_type: str = "simulation"
    status: IncidentLifecycleStatus = IncidentLifecycleStatus.ANALYZING
    severity: IncidentSeverity = IncidentSeverity.YELLOW
    simulation_trigger: dict = Field(default_factory=dict)
    video_metadata: dict | None = None
    triage_answers: list[dict] = Field(default_factory=list)
    ai_result: dict | None = None
    action_execution: ActionExecutionState = Field(default_factory=ActionExecutionState)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None


class HistoryLogEntry(BaseModel):
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
