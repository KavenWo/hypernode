from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agents.orchestrator import vital_signs_emergency_workflow
from agents.shared.schemas import DispatchDecision, FallEvent

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
