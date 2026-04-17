import json
import logging
import os
from pathlib import Path

from db.models import PatientProfile

try:
    from google.cloud import firestore
except ImportError:  # pragma: no cover - optional during early local setup
    firestore = None


BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PATIENT_PATH = BACKEND_DIR / "data" / "sample_patient.json"
logger = logging.getLogger(__name__)


def _load_sample_profiles_payload() -> tuple[PatientProfile, list[PatientProfile]]:
    """Support both the older single-profile file and the newer multi-profile file."""
    with SAMPLE_PATIENT_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if "default_profile" in payload:
        default_profile = PatientProfile.model_validate(payload["default_profile"])
        profiles = [
            PatientProfile.model_validate(profile_payload)
            for profile_payload in payload.get("profiles", [])
        ]
        return default_profile, profiles

    legacy_profile = PatientProfile.model_validate(payload)
    return legacy_profile, [legacy_profile]


def get_firestore_client():
    project_id = os.getenv("FIRESTORE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if firestore is None or not project_id:
        return None
    return firestore.Client(project=project_id)


def load_patient_profile(user_id: str) -> PatientProfile:
    client = get_firestore_client()
    if client is not None:
        try:
            document = client.collection("patients").document(user_id).get()
            if document.exists:
                return PatientProfile.model_validate(document.to_dict())
        except Exception as exc:
            logger.warning(
                "Firestore profile lookup failed for user %s; falling back to local sample profiles. Error: %s",
                user_id,
                exc,
            )

    default_profile, profiles = _load_sample_profiles_payload()

    for profile in profiles:
        if profile.user_id == user_id:
            return profile

    return default_profile.model_copy(update={"user_id": user_id})


def list_sample_patient_profiles() -> list[PatientProfile]:
    """Return all locally configured sample patient profiles for UI selection."""
    _, profiles = _load_sample_profiles_payload()
    return profiles


def seed_sample_patient() -> PatientProfile:
    profile, _ = _load_sample_profiles_payload()
    client = get_firestore_client()
    if client is not None:
        try:
            client.collection("patients").document(profile.user_id).set(profile.model_dump())
        except Exception as exc:
            logger.warning(
                "Firestore seed failed; local sample profile remains available. Error: %s",
                exc,
            )
    return profile
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
