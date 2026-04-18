const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function readJson(response, fallbackMessage) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.detail || fallbackMessage || `Request failed (${response.status})`);
  }
  return payload;
}

export async function createIncident({ sessionUid, patientId, eventType = "simulation", simulationTrigger = {}, videoMetadata = null }) {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_uid: sessionUid,
      patient_id: patientId,
      event_type: eventType,
      simulation_trigger: simulationTrigger,
      video_metadata: videoMetadata,
    }),
  });

  return readJson(response, `Failed to create incident (${response.status})`);
}

export async function updateIncidentStatus(incidentId, { state, summary = null }) {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, summary }),
  });

  return readJson(response, `Failed to update incident status (${response.status})`);
}

export async function submitIncidentAnswers(incidentId, payload) {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return readJson(response, `Failed to save incident reasoning (${response.status})`);
}

export async function executeIncidentAction(incidentId, action) {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });

  return readJson(response, `Failed to execute incident action (${response.status})`);
}
