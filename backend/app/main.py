from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Project 2030 Vital Signs Agentic Flow")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Vital Signs Agentic Backend is running"}

# Import the flow so it can be discovered by Genkit
from app.agents.flows import vital_signs_emergency_workflow
