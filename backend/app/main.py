"""FastAPI entrypoint for the prototype backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.emergency import router as emergency_router
from app.api.routes.mvp import router as mvp_router
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
    """Simple health endpoint plus a hint for the main MVP route sequence."""
    return {
        "status": "ok",
        "message": "Vital Signs Agentic Backend is running",
        "mvp_flow": "POST /api/v1/events/fall/questions -> POST /api/v1/events/fall/assess",
    }


app.include_router(mvp_router)
app.include_router(emergency_router)
