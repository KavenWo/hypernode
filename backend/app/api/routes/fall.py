"""Primary API routes for the fall-triage flow.

These routes are intentionally thin. They delegate the business flow to the
fall-domain service boundary under ``app.fall`` so the API can stay stable while
the underlying implementation is cleaned up.
"""

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.fall.assessment_service import build_fall_questions, get_runtime_status, run_fall_assessment
from app.fall.conversation_service import (
    apply_session_action_decision,
    get_fall_conversation_session_state,
    reset_fall_conversation_session,
    run_fall_conversation_turn,
)
from app.fall.contracts import (
    CommunicationSessionStateResponse,
    CommunicationTurnRequest,
    CommunicationTurnResponse,
    FallAssessment,
    FallAssessmentRequest,
    FallEvent,
    FallQuestionsRequest,
    SessionActionRequest,
    SessionActionResponse,
    TriageQuestionSet,
)
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


@router.post("/questions", response_model=TriageQuestionSet)
async def get_questions(request: FallQuestionsRequest) -> TriageQuestionSet:
    """Step 2 of the MVP: ask 2-3 questions before running reasoning."""
    return build_fall_questions(request.event, request.vitals, request.interaction)


@router.post("/assess", response_model=FallAssessment)
async def assess_after_answers(
    request: FallAssessmentRequest,
    background_tasks: BackgroundTasks,
) -> FallAssessment:
    """Step 4-5 of the MVP: run reasoning once and optionally dispatch."""
    return await run_fall_assessment(
        event=request.event,
        vitals=request.vitals,
        patient_answers=request.patient_answers,
        interaction=request.interaction,
        trigger_dispatch=True,
        background_tasks=background_tasks,
    )


@router.post("/session-turn", response_model=CommunicationTurnResponse)
async def run_session_turn(
    request: CommunicationTurnRequest,
    background_tasks: BackgroundTasks,
) -> CommunicationTurnResponse:
    """Run one communication-agent turn for the Phase 4 text session loop."""
    return await run_fall_conversation_turn(
        request,
        background_tasks=background_tasks,
    )


@router.get("/session-state/{session_id}", response_model=CommunicationSessionStateResponse)
async def get_session_state(session_id: str) -> CommunicationSessionStateResponse:
    """Return the latest backend-held state for a Phase 4 communication session."""
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
    """Stream Phase 4 session updates over Server-Sent Events."""
    session_state = get_fall_conversation_session_state(session_id)
    if session_state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream():
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


@router.post("/", response_model=FallAssessment)
async def assess_without_questions(
    event: FallEvent,
    background_tasks: BackgroundTasks,
) -> FallAssessment:
    """Legacy shortcut route for direct testing without the question stage."""
    return await run_fall_assessment(
        event=event,
        vitals=None,
        patient_answers=[],
        trigger_dispatch=True,
        background_tasks=background_tasks,
    )
