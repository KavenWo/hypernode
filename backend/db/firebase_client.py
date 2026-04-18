"""Firestore and local sample-profile helpers for the active backend."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from db.models import (
    AnonymousSession,
    FrontendPatientProfile,
    HistoryLogEntry,
    IncidentRecord,
    EmergencyContact,
    MedicalProfile,
    PatientProfile,
)

try:
    from google.cloud import firestore
except ImportError:  # pragma: no cover - optional during early local setup
    firestore = None


BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PATIENT_PATH = BACKEND_DIR / "data" / "sample_patient.json"
logger = logging.getLogger(__name__)


def _configured_project_id() -> str:
    return (
        os.getenv("FIREBASE_PROJECT_ID")
        or os.getenv("FIRESTORE_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or ""
    )


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


def _firestore_required() -> bool:
    return os.getenv("FIRESTORE_REQUIRED", "").strip().lower() in {"1", "true", "yes", "on"}


def get_storage_runtime_status() -> dict:
    project_id = _configured_project_id()
    firestore_configured = firestore is not None and bool(project_id)
    sample_profiles_available = SAMPLE_PATIENT_PATH.exists()

    if firestore_configured:
        storage_mode = "firestore_preferred"
    elif sample_profiles_available:
        storage_mode = "local_sample_only"
    else:
        storage_mode = "unconfigured"

    return {
        "storage_mode": storage_mode,
        "firestore_configured": firestore_configured,
        "firestore_required": _firestore_required(),
        "firestore_project": project_id,
        "sample_profiles_available": sample_profiles_available,
        "demo_ready": sample_profiles_available,
    }


def get_firestore_client():
    project_id = _configured_project_id()
    if firestore is None or not project_id:
        return None
    return firestore.Client(project=project_id)


def _model_payload(model) -> dict:
    return model.model_dump(mode="json")


def _session_document(session_uid: str):
    client = get_firestore_client()
    if client is None:
        return None
    return client.collection("sessions").document(session_uid)


def _frontend_profile_from_sample(sample: PatientProfile, session_uid: str) -> FrontendPatientProfile:
    return FrontendPatientProfile(
        patient_id=sample.user_id,
        session_uid=session_uid,
        full_name=sample.full_name,
        age=sample.age,
        primary_language=sample.primary_language,
        address=sample.address,
        medical_profile=MedicalProfile(
            allergies=sample.allergies,
            medications=sample.medications,
            chronic_conditions=sample.pre_existing_conditions,
            blood_thinners=sample.blood_thinners,
            mobility_support=sample.mobility_support,
            notes="Seeded default patient profile for this anonymous session.",
        ),
        emergency_contacts=[
            EmergencyContact(
                contact_id=f"contact_{index + 1}",
                name=f"Emergency Contact {index + 1}",
                phone=phone,
                relationship="emergency_contact",
                priority=index + 1,
            )
            for index, phone in enumerate(sample.emergency_contacts)
        ],
    )


def _seeded_frontend_profiles(session_uid: str) -> list[FrontendPatientProfile]:
    _, sample_profiles = _load_sample_profiles_payload()
    return [_frontend_profile_from_sample(sample, session_uid) for sample in sample_profiles]


def _write_session_patient_profile(profile: FrontendPatientProfile) -> FrontendPatientProfile:
    session_ref = _session_document(profile.session_uid or "")
    if session_ref is None:
        return profile

    patient_ref = session_ref.collection("patients").document(profile.patient_id)
    base_payload = profile.model_dump(mode="json")
    base_payload.pop("medical_profile", None)
    base_payload.pop("emergency_contacts", None)
    patient_ref.set(base_payload, merge=True)
    patient_ref.collection("medical_profile").document("current").set(
        _model_payload(profile.medical_profile),
        merge=True,
    )
    for contact in profile.emergency_contacts:
        patient_ref.collection("emergency_contacts").document(contact.contact_id).set(
            _model_payload(contact),
            merge=True,
        )
    return profile


def _load_session_patient_profile(session_uid: str, patient_id: str) -> FrontendPatientProfile | None:
    session_ref = _session_document(session_uid)
    if session_ref is None:
        return None

    patient_document = session_ref.collection("patients").document(patient_id).get()
    if not patient_document.exists:
        return None

    payload = patient_document.to_dict()
    medical_document = (
        session_ref.collection("patients")
        .document(patient_id)
        .collection("medical_profile")
        .document("current")
        .get()
    )
    contacts = [
        contact.to_dict()
        for contact in (
            session_ref.collection("patients")
            .document(patient_id)
            .collection("emergency_contacts")
            .stream()
        )
    ]
    payload["medical_profile"] = medical_document.to_dict() if medical_document.exists else {}
    payload["emergency_contacts"] = contacts
    return FrontendPatientProfile.model_validate(payload)


def load_patient_profile(user_id: str) -> PatientProfile:
    client = get_firestore_client()
    if client is not None:
        try:
            document = client.collection("patients").document(user_id).get()
            if document.exists:
                return PatientProfile.model_validate(document.to_dict())
        except Exception as exc:
            log_message = (
                "Firestore profile lookup failed for user %s; falling back to local sample profiles. Error: %s"
            )
            if _firestore_required():
                logger.warning(log_message, user_id, exc)
            else:
                logger.info(log_message, user_id, exc)

    default_profile, profiles = _load_sample_profiles_payload()

    for profile in profiles:
        if profile.user_id == user_id:
            return profile

    return default_profile.model_copy(update={"user_id": user_id})


def load_frontend_patient_profile(patient_id: str, session_uid: str | None = None) -> FrontendPatientProfile:
    client = get_firestore_client()
    if client is not None and session_uid:
        try:
            seeded_session = get_or_create_anonymous_session(session_uid=session_uid)
            if not seeded_session.default_patient_seeded:
                seed_default_session_patients(session_uid)
            profile = _load_session_patient_profile(session_uid, patient_id)
            if profile is not None:
                return profile
        except Exception as exc:
            logger.info(
                "Firestore frontend profile lookup failed for patient %s; falling back to local sample profile. Error: %s",
                patient_id,
                exc,
            )

    legacy_profile = load_patient_profile(patient_id)
    return FrontendPatientProfile(
        patient_id=patient_id,
        session_uid=session_uid,
        full_name=legacy_profile.full_name,
        age=legacy_profile.age,
        primary_language=legacy_profile.primary_language,
        address=legacy_profile.address,
        medical_profile=MedicalProfile(
            allergies=legacy_profile.allergies,
            medications=legacy_profile.medications,
            chronic_conditions=legacy_profile.pre_existing_conditions,
            blood_thinners=legacy_profile.blood_thinners,
            mobility_support=legacy_profile.mobility_support,
        ),
        emergency_contacts=[
            EmergencyContact(
                contact_id=f"contact_{index + 1}",
                name=f"Emergency Contact {index + 1}",
                phone=phone,
                relationship="emergency_contact",
                priority=index + 1,
            )
            for index, phone in enumerate(legacy_profile.emergency_contacts)
        ],
    )


def save_frontend_patient_profile(profile: FrontendPatientProfile) -> FrontendPatientProfile:
    if not profile.session_uid:
        return profile
    return _write_session_patient_profile(profile)


def get_or_create_anonymous_session(session_uid: str, patient_id: str | None = None) -> AnonymousSession:
    client = get_firestore_client()
    if client is not None:
        try:
            session_ref = client.collection("sessions").document(session_uid)
            document = session_ref.get()
            if document.exists:
                session = AnonymousSession.model_validate(document.to_dict())
            else:
                session = AnonymousSession(session_uid=session_uid)
            if patient_id and patient_id not in session.patient_ids:
                session.patient_ids.append(patient_id)
            if patient_id and not session.active_patient_id:
                session.active_patient_id = patient_id
            session.last_seen_at = datetime.utcnow()
            session_ref.set(_model_payload(session), merge=True)
            return session
        except Exception as exc:
            logger.info("Firestore session bootstrap failed for %s. Error: %s", session_uid, exc)

    session = AnonymousSession(session_uid=session_uid)
    if patient_id:
        session.patient_ids.append(patient_id)
        session.active_patient_id = patient_id
    return session


def seed_default_session_patients(session_uid: str) -> list[FrontendPatientProfile]:
    session = get_or_create_anonymous_session(session_uid=session_uid)
    profiles = _seeded_frontend_profiles(session_uid)

    for profile in profiles:
        _write_session_patient_profile(profile)

    session.patient_ids = [profile.patient_id for profile in profiles]
    session.default_patient_seeded = True
    if not session.active_patient_id and session.patient_ids:
        session.active_patient_id = session.patient_ids[0]

    session_ref = _session_document(session_uid)
    if session_ref is not None:
        session.last_seen_at = datetime.utcnow()
        session_ref.set(_model_payload(session), merge=True)

    return profiles


def list_session_patient_profiles(session_uid: str) -> list[FrontendPatientProfile]:
    client = get_firestore_client()
    if client is not None:
        try:
            session = get_or_create_anonymous_session(session_uid)
            if not session.default_patient_seeded:
                return seed_default_session_patients(session_uid)

            session_ref = _session_document(session_uid)
            if session_ref is not None:
                profiles = []
                for patient_doc in session_ref.collection("patients").stream():
                    profile = _load_session_patient_profile(session_uid, patient_doc.id)
                    if profile is not None:
                        profiles.append(profile)
                if profiles:
                    return profiles
        except Exception as exc:
            logger.info("Firestore session patient list failed for %s. Error: %s", session_uid, exc)

    return _seeded_frontend_profiles(session_uid)


def save_incident_record(incident: IncidentRecord) -> IncidentRecord:
    session_ref = _session_document(incident.session_uid)
    if session_ref is None:
        logger.info(
            "Skipping incident persistence because Firestore session document is unavailable | session_uid=%s incident_id=%s",
            incident.session_uid,
            incident.incident_id,
        )
        return incident
    session_ref.collection("incidents").document(incident.incident_id).set(_model_payload(incident), merge=True)
    session_ref.set(
        {
            "active_incident_id": incident.incident_id,
            "last_seen_at": datetime.utcnow().isoformat(),
        },
        merge=True,
    )
    logger.info(
        "Persisted incident record to Firestore | session_uid=%s incident_id=%s status=%s",
        incident.session_uid,
        incident.incident_id,
        incident.status,
    )
    return incident


def load_incident_record(session_uid: str, incident_id: str) -> IncidentRecord | None:
    session_ref = _session_document(session_uid)
    if session_ref is None:
        return None

    document = session_ref.collection("incidents").document(incident_id).get()
    if not document.exists:
        return None

    return IncidentRecord.model_validate(document.to_dict())


def append_history_log(entry: HistoryLogEntry) -> HistoryLogEntry:
    session_ref = _session_document(entry.session_uid)
    if session_ref is None:
        return entry
    payload = _model_payload(entry)
    session_ref.collection("history").document(entry.history_id).set(payload, merge=True)
    session_ref.collection("patients").document(entry.patient_id).collection("history").document(entry.history_id).set(
        payload,
        merge=True,
    )
    return entry


def list_history_logs(session_uid: str, patient_id: str | None = None, limit: int = 25) -> list[HistoryLogEntry]:
    session_ref = _session_document(session_uid)
    if session_ref is None:
        return []

    entries: list[HistoryLogEntry] = []
    documents = session_ref.collection("history").stream()
    for document in documents:
        entry = HistoryLogEntry.model_validate(document.to_dict())
        if patient_id and entry.patient_id != patient_id:
            continue
        entries.append(entry)

    entries.sort(key=lambda entry: entry.created_at, reverse=True)
    return entries[:limit]


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
            log_message = "Firestore seed failed; local sample profile remains available. Error: %s"
            if _firestore_required():
                logger.warning(log_message, exc)
            else:
                logger.info(log_message, exc)
    return profile
