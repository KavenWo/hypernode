"""Emergency dispatch API routes.

The execution logic lives under ``app.fall.execution_service`` so these routes
can stay thin and HTTP-focused.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app.fall.execution_service import (
    EmergencyTriggerRequest,
    get_incident,
    list_active_incidents,
    resolve_incident,
    trigger_emergency,
)

router = APIRouter(prefix="/emergency", tags=["Emergency"])


@router.post("/trigger")
async def trigger_emergency_route(
    req: EmergencyTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """Manual route for demoing the dispatch layer in isolation."""
    incident_id = await trigger_emergency(
        patient_id=req.patient_id,
        severity=req.severity,
        vitals=req.vitals.model_dump(),
        flags=req.flags,
        ai_decision=req.ai_decision,
        location=req.location.model_dump() if req.location else None,
        background_tasks=background_tasks,
    )

    return {
        "incident_id": incident_id,
        "status": "triggered",
        "message": f"Emergency dispatch initiated for patient {req.patient_id}",
    }


@router.get("/")
async def list_active_incidents_route():
    """List all incidents that are not resolved yet."""
    return list_active_incidents()


@router.get("/active")
async def list_active_incidents_alias():
    """Alias that matches the teammate module's original route documentation."""
    return list_active_incidents()


@router.get("/{incident_id}")
async def get_incident_route(incident_id: str):
    """Return the full in-memory incident record."""
    return get_incident(incident_id)


@router.post("/{incident_id}/resolve")
async def resolve_incident_route(incident_id: str):
    """Resolve an incident so the demo dashboard can close it out cleanly."""
    return resolve_incident(incident_id)
