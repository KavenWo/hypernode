"""Shared database models used by the active fall backend.

These models back the current sample-patient and Firestore profile loading used
by the ADK-enabled fall flow. The standalone emergency prototype keeps its own
models in ``backend/emergency.py`` and should import from there directly.
"""

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
