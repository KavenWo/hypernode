import json
import os
from pathlib import Path

from db.models import PatientProfile

try:
    from google.cloud import firestore
except ImportError:  # pragma: no cover - optional during early local setup
    firestore = None


BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PATIENT_PATH = BACKEND_DIR / "data" / "sample_patient.json"


def get_firestore_client():
    project_id = os.getenv("FIRESTORE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if firestore is None or not project_id:
        return None
    return firestore.Client(project=project_id)


def load_patient_profile(user_id: str) -> PatientProfile:
    client = get_firestore_client()
    if client is not None:
        document = client.collection("patients").document(user_id).get()
        if document.exists:
            return PatientProfile.model_validate(document.to_dict())

    with SAMPLE_PATIENT_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    sample_profile = PatientProfile.model_validate(payload)
    if sample_profile.user_id == user_id:
        return sample_profile

    return sample_profile.model_copy(update={"user_id": user_id})


def seed_sample_patient() -> PatientProfile:
    with SAMPLE_PATIENT_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    profile = PatientProfile.model_validate(payload)
    client = get_firestore_client()
    if client is not None:
        client.collection("patients").document(profile.user_id).set(profile.model_dump())
    return profile
