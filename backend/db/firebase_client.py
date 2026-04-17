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
