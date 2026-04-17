"""Firestore and local fallback helpers for patient, incident, and history data.

This file restores the `db.firebase_client` import path while delegating to the
single storage implementation in `emergency.py`, so all routes share the same
state and Firestore writes.
"""

from __future__ import annotations

from emergency import (  # noqa: F401
    HistoryEntry,
    Incident,
    PatientProfile,
    SmsResult,
    StartIncidentRequest,
    _append_history,
    _create_lifecycle_incident,
    _get_firestore_client,
    _incident_or_404,
    _load_incident,
    _load_patient_profile,
    _save_incident,
    _save_patient_profile,
    _send_sms,
    _update_patient_profile,
)


def get_firestore_client():
    return _get_firestore_client()


def load_patient_profile(patient_id: str, session_uid: str | None = None) -> PatientProfile:
    return _load_patient_profile(patient_id, session_uid)


def save_patient_profile(profile: PatientProfile) -> PatientProfile:
    return _save_patient_profile(profile)


def update_patient_profile(patient_id: str, updates: dict) -> PatientProfile:
    return _update_patient_profile(patient_id, updates)


def create_incident_record(
    *,
    session_uid: str,
    patient_id: str,
    event_type: str = "simulation",
    simulation_trigger: dict | None = None,
    video_metadata: dict | None = None,
) -> Incident:
    return _create_lifecycle_incident(
        StartIncidentRequest(
            session_uid=session_uid,
            patient_id=patient_id,
            event_type=event_type,
            simulation_trigger=simulation_trigger or {},
            video_metadata=video_metadata,
        )
    )


def get_incident_record(incident_id: str) -> Incident | None:
    return _load_incident(incident_id)


def require_incident_record(incident_id: str) -> Incident:
    return _incident_or_404(incident_id)


def save_incident_record(incident: Incident) -> Incident:
    return _save_incident(incident)


def append_history_entry(incident: Incident, summary: str | None = None) -> HistoryEntry:
    return _append_history(incident, summary)


async def send_sms(to: str, message: str, incident_id: str | None = None) -> SmsResult:
    return await _send_sms(to=to, message=message, incident_id=incident_id)
