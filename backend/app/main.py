"""FastAPI entrypoint for the prototype backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.fall import router as fall_router
from app.api.routes.patient_data import router as patient_data_router
from app.core.bootstrap import configure_runtime

configure_runtime()

app = FastAPI(title="Project 2030 Vital Signs Agentic Flow")

# Allow CORS for easy hackathon integration while the frontend is still local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Simple health endpoint plus hints for the canonical fall-flow sequence."""
    # This doubles as a lightweight discovery endpoint during the hackathon so
    # anyone hitting the backend directly can see the main session-oriented API
    # contract without opening the source first.
    return {
        "status": "ok",
        "message": "Vital Signs Agentic Backend is running",
        "canonical_flow": {
            "start_session": "POST /api/v1/events/fall/session-start",
            "continue_session": "POST /api/v1/events/fall/session-turn",
            "read_session_state": "GET /api/v1/events/fall/session-state/{session_id}",
            "stream_session_events": "GET /api/v1/events/fall/session-events/{session_id}",
            "control_session_action": "POST /api/v1/events/fall/session-action/{session_id}",
        },
    }


app.include_router(fall_router)
app.include_router(patient_data_router)
app.include_router(auth_router)
