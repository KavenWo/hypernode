from pydantic import BaseModel, Field


class PatientProfile(BaseModel):
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
    user_id: str
    bystander_present: bool = False
    responded_within_30s: bool = False
    user_requested_ambulance: bool = False
    bleeding_observed: bool = False
    breathing_status: str = "unknown"
    dispatch_status: str = "pending"
"""Shared backend data models.

The standalone backend currently keeps the canonical model definitions in
`emergency.py`. This module restores the conventional `db.models` import path
and re-exports those models for other backend files.
"""

from emergency import (  # noqa: F401
    AIDecisionSummary,
    EmergencyContact,
    ExecuteActionRequest,
    HistoryEntry,
    Incident,
    IncidentStatus,
    IncidentStatusUpdate,
    Location,
    PatientProfile,
    PatientProfileUpdate,
    SeverityLevel,
    SmsRequest,
    SmsResult,
    StartIncidentRequest,
    SubmitAnswersRequest,
    VitalsSnapshot,
)
