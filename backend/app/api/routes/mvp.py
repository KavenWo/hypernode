"""Primary API routes for the fall-triage MVP.

These routes are intentionally thin. They delegate the business flow to
``app.services.mvp_flow`` so both the backend team and frontend team have one
place to understand the prototype behavior.
"""

from fastapi import APIRouter, BackgroundTasks

from agents.shared.schemas import (
    FallAssessmentRequest,
    FallEvent,
    FallQuestionsRequest,
    MvpAssessment,
    TriageQuestionSet,
)
from app.services.mvp_flow import get_mvp_fall_questions, get_runtime_status, run_mvp_fall_assessment
from db.firebase_client import list_sample_patient_profiles

router = APIRouter(prefix="/api/v1/events/fall", tags=["MVP Fall Flow"])


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


@router.post("/questions", response_model=TriageQuestionSet)
async def get_questions(request: FallQuestionsRequest) -> TriageQuestionSet:
    """Step 2 of the MVP: ask 2-3 questions before running reasoning."""
    return get_mvp_fall_questions(request.event, request.vitals)


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
        trigger_dispatch=True,
        background_tasks=background_tasks,
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
