"""Authentication and anonymous-session bootstrap routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, BackgroundTasks

from app.services.session_auth_service import (
    SessionBootstrapRequest,
    SessionBootstrapResponse,
    SessionMeResponse,
    bootstrap_anonymous_session,
    background_bootstrap_tasks,
    resolve_session_from_authorization,
)

router = APIRouter(prefix="/api/v1/session", tags=["Session"])


@router.post("/bootstrap", response_model=SessionBootstrapResponse)
async def bootstrap_session(
    request: SessionBootstrapRequest, background_tasks: BackgroundTasks
) -> SessionBootstrapResponse:
    # Perform a light bootstrap first to return quickly
    response = bootstrap_anonymous_session(request, defer_seeding=True)
    
    # Schedule heavy tasks in the background
    background_tasks.add_task(
        background_bootstrap_tasks,
        session_uid=response.session.session_uid,
        patient_id=response.patient_id,
        create_profile=request.create_profile,
    )
    
    return response


@router.get("/me", response_model=SessionMeResponse)
async def get_current_session(authorization: str | None = Header(default=None)) -> SessionMeResponse:
    return resolve_session_from_authorization(authorization)
