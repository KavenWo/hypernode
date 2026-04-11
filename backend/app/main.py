from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agents.orchestrator import get_fall_triage_questions, run_mvp_fall_assessment, vital_signs_emergency_workflow
from agents.shared.schemas import (
    DispatchDecision,
    FallAssessmentRequest,
    FallEvent,
    FallQuestionsRequest,
    MvpAssessment,
    TriageQuestionSet,
)

app = FastAPI(title="Project 2030 Vital Signs Agentic Flow")

# Allow CORS for easy hackathon integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Vital Signs Agentic Backend is running"}

@app.post("/api/v1/events/fall", response_model=DispatchDecision)
async def handle_fall_event(event: FallEvent):
    """
    Endpoint for hardware or frontend to submit a fall event.
    This triggers the orchestrated backend agent workflow.
    """
    decision = await vital_signs_emergency_workflow(event)
    return decision


@app.post("/api/v1/events/fall/questions", response_model=TriageQuestionSet)
async def handle_fall_questions(request: FallQuestionsRequest):
    """
    Endpoint for the MVP intake step.
    Returns 2-3 targeted follow-up questions before reasoning is run.
    """
    return get_fall_triage_questions(request.event, request.vitals)


@app.post("/api/v1/events/fall/assess", response_model=MvpAssessment)
async def handle_fall_assessment(request: FallAssessmentRequest):
    """
    Endpoint for the MVP flow after patient or bystander answers have been collected.
    Runs the reasoning agent once and returns severity, action, and instructions.
    """
    return await run_mvp_fall_assessment(
        event=request.event,
        vitals=request.vitals,
        patient_answers=request.patient_answers,
    )
