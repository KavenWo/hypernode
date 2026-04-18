"""Session bootstrap and Firebase token verification helpers."""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import Header, HTTPException
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pydantic import BaseModel, Field

from db.firebase_client import (
    get_or_create_anonymous_session,
    list_session_patient_profiles,
    load_frontend_patient_profile,
    save_frontend_patient_profile,
    seed_default_session_patients,
)
from db.models import AnonymousSession, FrontendPatientProfile


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
        token_payload = id_token.verify_firebase_token(raw_token, Request(), audience=project_id)
    except Exception as exc:  # pragma: no cover - exact Google exception types vary
        raise HTTPException(status_code=401, detail=f"Invalid Firebase ID token: {exc}") from exc

    if not token_payload:
        raise HTTPException(status_code=401, detail="Unable to verify Firebase ID token")

    _token_subject(token_payload)

    return token_payload


def bootstrap_anonymous_session(request: SessionBootstrapRequest) -> SessionBootstrapResponse:
    token_payload = verify_firebase_id_token(request.id_token)
    session_uid = _token_subject(token_payload)
    patient_id = request.patient_id or session_uid

    session = get_or_create_anonymous_session(session_uid=session_uid, patient_id=patient_id)
    seeded_profiles = seed_default_session_patients(session_uid) if not session.default_patient_seeded else list_session_patient_profiles(session_uid)
    session = get_or_create_anonymous_session(session_uid=session_uid, patient_id=patient_id)

    profile = None
    if request.create_profile:
        existing_profile = load_frontend_patient_profile(patient_id=patient_id, session_uid=session_uid)
        profile = existing_profile.model_copy(update={"session_uid": session_uid, "updated_at": datetime.utcnow()})
        save_frontend_patient_profile(profile)

    return SessionBootstrapResponse(
        session=session,
        patient_id=patient_id,
        profile=profile,
        patients=seeded_profiles,
    )


def resolve_session_from_authorization(authorization: str | None) -> SessionMeResponse:
    token = _extract_bearer_token(authorization)
    token_payload = verify_firebase_id_token(token)
    session_uid = _token_subject(token_payload)
    patient_id = session_uid
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
