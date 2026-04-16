"""Primary API routes for the fall-triage MVP.

These routes are intentionally thin. They delegate the business flow to
``app.services.mvp_flow`` so both the backend team and frontend team have one
place to understand the prototype behavior.
"""

import json
from pathlib import Path
import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse

from agents.shared.schemas import (
    CommunicationSessionStateResponse,
    CommunicationTurnRequest,
    CommunicationTurnResponse,
    FallAssessmentRequest,
    FallEvent,
    FallQuestionsRequest,
    MvpAssessment,
    TriageQuestionSet,
)
from app.services.mvp_flow import (
    get_mvp_conversation_session_state,
    get_mvp_fall_questions,
    get_runtime_status,
    run_mvp_conversation_turn,
    run_mvp_fall_assessment,
)
from db.firebase_client import list_sample_patient_profiles

router = APIRouter(prefix="/api/v1/events/fall", tags=["MVP Fall Flow"])
SCENARIO_PACK_PATH = Path(__file__).resolve().parents[3] / "data" / "phase2_test_scenarios.json"
PHASE3_SCENARIO_PACK_PATH = Path(__file__).resolve().parents[3] / "data" / "phase3_test_scenarios.json"
PHASE4_SCENARIO_PACK_PATH = Path(__file__).resolve().parents[3] / "data" / "phase4_interaction_scenarios.json"


def _encode_sse(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


@router.get("/status")
async def get_mvp_status() -> dict:
    """Frontend-friendly backend/runtime status for MVP testing."""
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


@router.get("/phase2-scenarios")
async def get_phase2_scenarios() -> dict:
    """Return a small scenario pack so the MVP can test retrieval behavior quickly."""
    with SCENARIO_PACK_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


@router.get("/phase3-scenarios")
async def get_phase3_scenarios() -> dict:
    """Return the Phase 3 reasoning scenario pack for staged MVP testing."""
    with PHASE3_SCENARIO_PACK_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


@router.get("/phase4-scenarios")
async def get_phase4_scenarios() -> dict:
    """Return the Phase 4 interaction scenario pack for communication-flow testing."""
    with PHASE4_SCENARIO_PACK_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


@router.post("/questions", response_model=TriageQuestionSet)
async def get_questions(request: FallQuestionsRequest) -> TriageQuestionSet:
    """Step 2 of the MVP: ask 2-3 questions before running reasoning."""
    return get_mvp_fall_questions(request.event, request.vitals, request.interaction)


@router.post("/assess", response_model=MvpAssessment)
async def assess_after_answers(
    request: FallAssessmentRequest,
    background_tasks: BackgroundTasks,
) -> MvpAssessment:
    """Step 4-5 of the MVP: run reasoning once and optionally dispatch."""
    return await run_mvp_fall_assessment(
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
    return await run_mvp_conversation_turn(
        request,
        background_tasks=background_tasks,
    )


@router.get("/session-state/{session_id}", response_model=CommunicationSessionStateResponse)
async def get_session_state(session_id: str) -> CommunicationSessionStateResponse:
    """Return the latest backend-held state for a Phase 4 communication session."""
    session_state = get_mvp_conversation_session_state(session_id)
    if session_state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_state


@router.get("/session-events/{session_id}")
async def stream_session_events(session_id: str, request: Request) -> StreamingResponse:
    """Stream Phase 4 session updates over Server-Sent Events."""
    session_state = get_mvp_conversation_session_state(session_id)
    if session_state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream():
        last_version = -1
        keepalive_ticks = 0
        while True:
            if await request.is_disconnected():
                break

            state = get_mvp_conversation_session_state(session_id)
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


@router.post("/", response_model=MvpAssessment)
async def assess_without_questions(
    event: FallEvent,
    background_tasks: BackgroundTasks,
) -> MvpAssessment:
    """Legacy shortcut route for direct testing without the question stage."""
    return await run_mvp_fall_assessment(
        event=event,
        vitals=None,
        patient_answers=[],
        trigger_dispatch=True,
        background_tasks=background_tasks,
    )
