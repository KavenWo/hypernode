"""Primary API routes for the fall-triage flow.

These routes are intentionally thin. They delegate the business flow to the
fall-domain service boundary under ``app.fall`` so the API can stay stable while
the underlying implementation is cleaned up.
"""

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse

from app.fall.assessment_service import get_runtime_status
from app.fall.action_runtime_service import apply_session_action_decision
from app.fall.conversation_service import (
    get_fall_conversation_session_state,
    reset_fall_conversation_session,
    start_fall_conversation_session,
    run_fall_conversation_turn,
)
from app.fall.contracts import (
    CommunicationSessionStateResponse,
    CommunicationSessionStartRequest,
    CommunicationTurnRequest,
    CommunicationTurnResponse,
    DemoVideoAnalysisRequest,
    DemoVideoAnalysisResponse,
    SessionActionRequest,
    SessionActionResponse,
)
from app.fall.demo_video_registry import get_demo_video_path, list_demo_videos
from app.fall.video_analysis_service import analyze_demo_video
from db.firebase_client import list_sample_patient_profiles

router = APIRouter(prefix="/api/v1/events/fall", tags=["Fall Flow"])


def _encode_sse(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


@router.get("/status")
async def get_fall_status() -> dict:
    """Frontend-friendly backend/runtime status for fall-flow testing."""
    return get_runtime_status()


@router.get("/patients")
async def get_sample_patients() -> dict:
    """Return sample patient profiles so the MVP test UI can offer a dropdown."""
    profiles = list_sample_patient_profiles()
    return {
        "patients": [
            {
                "user_id": profile.user_id,
                "full_name": profile.full_name,
                "age": profile.age,
                "blood_thinners": profile.blood_thinners,
                "mobility_support": profile.mobility_support,
                "pre_existing_conditions": profile.pre_existing_conditions,
            }
            for profile in profiles
        ]
    }


@router.get("/demo-videos")
async def get_demo_videos() -> dict:
    """Return the preset demo videos available for the controlled dashboard flow."""

    return {"videos": list_demo_videos()}


@router.post("/demo-videos/analyze", response_model=DemoVideoAnalysisResponse)
async def analyze_selected_demo_video(
    request: DemoVideoAnalysisRequest,
) -> DemoVideoAnalysisResponse:
    """Run Gemini vision analysis on a selected preset dashboard clip."""

    return await analyze_demo_video(request.video_id)


@router.get("/demo-videos/{video_id}/file")
async def get_demo_video_file(video_id: str) -> FileResponse:
    """Serve a local preset demo video asset for dashboard preview."""

    video_path = get_demo_video_path(video_id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Demo video not found")
    return FileResponse(video_path, media_type="video/mp4", filename=video_path.name)


@router.post("/session-start", response_model=CommunicationTurnResponse)
async def start_session(
    request: CommunicationSessionStartRequest,
) -> CommunicationTurnResponse:
    """Create a canonical fall-response session and return the opening prompt."""

    return await start_fall_conversation_session(request)


@router.post("/session-turn", response_model=CommunicationTurnResponse)
async def run_session_turn(
    request: CommunicationTurnRequest,
    background_tasks: BackgroundTasks,
) -> CommunicationTurnResponse:
    """Run one turn in the canonical fall-response finite-state session flow."""
    # The HTTP response returns the immediate turn result, while heavier
    # reasoning/execution refresh work can continue in the background and reach
    # the dashboard through session-state polling or SSE updates.
    return await run_fall_conversation_turn(
        request,
        background_tasks=background_tasks,
    )


@router.get("/session-state/{session_id}", response_model=CommunicationSessionStateResponse)
async def get_session_state(session_id: str) -> CommunicationSessionStateResponse:
    """Return the latest backend-held state for the canonical session flow."""
    session_state = get_fall_conversation_session_state(session_id)
    if session_state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_state


@router.post("/session-reset/{session_id}")
async def reset_session_state(session_id: str) -> dict:
    """Immediately stop active backend work for a session and clear its state."""
    reset_result = reset_fall_conversation_session(session_id)
    if not reset_result["reset"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return reset_result


@router.post("/session-stop/{session_id}")
async def stop_session_log(session_id: str) -> dict:
    """Log when a user explicitly stops a session from the frontend dashboard."""
    from app.fall.conversation_service import logger
    logger.info(f"[Session {session_id}] WORKFLOW_STOPPED | User explicitly halted the session from the dashboard.")
    return {"status": "ok", "session_id": session_id}


@router.post("/session-action/{session_id}", response_model=SessionActionResponse)
async def control_session_action(
    session_id: str,
    request: SessionActionRequest,
) -> SessionActionResponse:
    """Apply an explicit user control decision to a session action track."""
    try:
        response = await apply_session_action_decision(
            session_id,
            action_type=request.action_type,
            decision=request.decision,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return response


@router.get("/session-events/{session_id}")
async def stream_session_events(session_id: str, request: Request) -> StreamingResponse:
    """Stream canonical session updates over Server-Sent Events."""
    session_state = get_fall_conversation_session_state(session_id)
    if session_state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream():
        # SSE gives the dashboard a push-based mirror of the canonical session.
        # We only emit when the version changes, plus occasional keepalives so
        # the browser connection stays warm during quiet periods.
        last_version = -1
        keepalive_ticks = 0
        while True:
            if await request.is_disconnected():
                break

            state = get_fall_conversation_session_state(session_id)
            if state is None:
                yield _encode_sse("session_closed", {"session_id": session_id})
                break

            if state.version != last_version:
                last_version = state.version
                keepalive_ticks = 0
                yield _encode_sse("session_state", state.model_dump(mode="json"))
            else:
                keepalive_ticks += 1
                if keepalive_ticks >= 20:
                    keepalive_ticks = 0
                    yield ": keepalive\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
