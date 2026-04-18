"""Authentication and anonymous-session bootstrap routes."""

from __future__ import annotations

from fastapi import APIRouter, Header

from app.services.session_auth_service import (
    SessionBootstrapRequest,
    SessionBootstrapResponse,
    SessionMeResponse,
    bootstrap_anonymous_session,
    resolve_session_from_authorization,
)

router = APIRouter(prefix="/api/v1/session", tags=["Session"])


@router.post("/bootstrap", response_model=SessionBootstrapResponse)
async def bootstrap_session(request: SessionBootstrapRequest) -> SessionBootstrapResponse:
    return bootstrap_anonymous_session(request)


@router.get("/me", response_model=SessionMeResponse)
async def get_current_session(authorization: str | None = Header(default=None)) -> SessionMeResponse:
    return resolve_session_from_authorization(authorization)
