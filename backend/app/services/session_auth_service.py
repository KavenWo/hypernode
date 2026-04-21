"""Session bootstrap and Firebase token verification helpers."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

from fastapi import Header, HTTPException
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pydantic import BaseModel, Field

# Persistent request object to cache Google certificates
HTTP_REQUEST = Request()

from db.firebase_client import (
    get_or_create_anonymous_session,
    list_session_patient_profiles,
    load_frontend_patient_profile,
    preview_default_session_patients,
    save_frontend_patient_profile,
    seed_default_session_patients,
)
from db.models import AnonymousSession, FrontendPatientProfile

logger = logging.getLogger(__name__)


def _resolve_session_patient_id(
    requested_patient_id: str | None,
    seeded_profiles: list[FrontendPatientProfile],
    session: AnonymousSession,
    session_uid: str,
) -> str:
    if requested_patient_id:
        return requested_patient_id
    if session.active_patient_id:
        return session.active_patient_id
    if seeded_profiles:
        return seeded_profiles[0].patient_id
    if session.patient_ids:
        return session.patient_ids[0]
    return ""


class SessionBootstrapRequest(BaseModel):
    id_token: str
    patient_id: str | None = None
    create_profile: bool = True


class SessionBootstrapResponse(BaseModel):
    session: AnonymousSession
    patient_id: str
    profile: FrontendPatientProfile | None = None
    patients: list[FrontendPatientProfile] = Field(default_factory=list)
    verified: bool = True
    auth_provider: str = "firebase_anonymous"
    bootstrapped_at: datetime = Field(default_factory=datetime.utcnow)


class SessionMeResponse(BaseModel):
    session: AnonymousSession
    patient_id: str
    verified: bool = True


def _firebase_project_id() -> str:
    return os.getenv("FIREBASE_PROJECT_ID") or os.getenv("FIRESTORE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Authorization header must use Bearer token")
    token = authorization[len(prefix) :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def _token_subject(token_payload: dict) -> str:
    subject = token_payload.get("uid") or token_payload.get("sub") or token_payload.get("user_id")
    if not subject:
        raise HTTPException(status_code=401, detail="Firebase token did not include a user identifier")
    return str(subject)


def verify_firebase_id_token(raw_token: str) -> dict:
    project_id = _firebase_project_id()
    if not project_id:
        raise HTTPException(
            status_code=500,
            detail="Firebase project is not configured on the backend",
        )

    try:
        # Reusing HTTP_REQUEST for certificate caching
        token_payload = id_token.verify_firebase_token(raw_token, HTTP_REQUEST, audience=project_id)
    except Exception as exc:  # pragma: no cover - exact Google exception types vary
        raise HTTPException(status_code=401, detail=f"Invalid Firebase ID token: {exc}") from exc

    if not token_payload:
        raise HTTPException(status_code=401, detail="Unable to verify Firebase ID token")

    _token_subject(token_payload)

    return token_payload


def bootstrap_anonymous_session(
    request: SessionBootstrapRequest, defer_seeding: bool = False
) -> SessionBootstrapResponse:
    t0 = time.time()
    token_payload = verify_firebase_id_token(request.id_token)
    t1 = time.time()
    session_uid = _token_subject(token_payload)
    patient_id = request.patient_id

    session = get_or_create_anonymous_session(session_uid=session_uid, patient_id=patient_id)
    t2 = time.time()
    
    seeded_profiles = []
    profile = None

    if not defer_seeding:
        seeded_profiles = (
            seed_default_session_patients(session_uid)
            if not session.default_patient_seeded
            else list_session_patient_profiles(session_uid)
        )
        t3 = time.time()
        patient_id = _resolve_session_patient_id(request.patient_id, seeded_profiles, session, session_uid)
        session = get_or_create_anonymous_session(session_uid=session_uid, patient_id=patient_id)

        if request.create_profile:
            existing_profile = load_frontend_patient_profile(patient_id=patient_id, session_uid=session_uid)
            profile = existing_profile.model_copy(update={"session_uid": session_uid, "updated_at": datetime.utcnow()})
            save_frontend_patient_profile(profile)
        t4 = time.time()
        logger.info(f"Bootstrap timing: auth={t1-t0:.3f}s, session={t2-t1:.3f}s, seeding={t3-t2:.3f}s, profile={t4-t3:.3f}s")
    else:
        seeded_profiles = preview_default_session_patients(session_uid)
        patient_id = _resolve_session_patient_id(request.patient_id, seeded_profiles, session, session_uid)
        logger.info(f"Light bootstrap timing: auth={t1-t0:.3f}s, session={t2-t1:.3f}s")

    return SessionBootstrapResponse(
        session=session,
        patient_id=patient_id,
        profile=profile,
        patients=seeded_profiles,
        verified=True,
    )


def background_bootstrap_tasks(session_uid: str, patient_id: str, create_profile: bool) -> None:
    """Perform heavy Firestore seeding and profile setup in the background."""
    seeded_profiles = seed_default_session_patients(session_uid)
    resolved_patient_id = patient_id or (seeded_profiles[0].patient_id if seeded_profiles else "")
    get_or_create_anonymous_session(session_uid=session_uid, patient_id=resolved_patient_id)
    if create_profile:
        existing_profile = load_frontend_patient_profile(patient_id=resolved_patient_id, session_uid=session_uid)
        profile = existing_profile.model_copy(update={"session_uid": session_uid, "updated_at": datetime.utcnow()})
        save_frontend_patient_profile(profile)


def resolve_session_from_authorization(authorization: str | None) -> SessionMeResponse:
    token = _extract_bearer_token(authorization)
    token_payload = verify_firebase_id_token(token)
    session_uid = _token_subject(token_payload)
    session = get_or_create_anonymous_session(session_uid=session_uid)
    patient_id = _resolve_session_patient_id(None, [], session, session_uid)
    if session.default_patient_seeded and patient_id != session.active_patient_id:
        session = get_or_create_anonymous_session(session_uid=session_uid, patient_id=patient_id)
    return SessionMeResponse(
        session=session,
        patient_id=patient_id,
    )


__all__ = [
    "SessionBootstrapRequest",
    "SessionBootstrapResponse",
    "SessionMeResponse",
    "_token_subject",
    "bootstrap_anonymous_session",
    "resolve_session_from_authorization",
    "verify_firebase_id_token",
]
