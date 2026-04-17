"""Exercise the frontend incident lifecycle API."""

from pathlib import Path
import os
import sys

from fastapi.testclient import TestClient  # type: ignore

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))


def main() -> None:
    os.environ["FIRESTORE_PROJECT_ID"] = ""
    os.environ["GOOGLE_CLOUD_PROJECT"] = ""

    from main import app

    client = TestClient(app)
    session_uid = "test_session_001"

    profile_response = client.get("/api/v1/patients/user_001/profile")
    profile_response.raise_for_status()
    assert profile_response.json()["patient_id"] == "user_001"

    update_response = client.patch(
        "/api/v1/patients/user_001/profile",
        json={
            "session_uid": session_uid,
            "full_name": "Demo Patient",
            "emergency_contacts": [
                {
                    "contact_id": "family_1",
                    "name": "Demo Family",
                    "phone": "+60123456789",
                    "relationship": "Family",
                    "priority": 1,
                }
            ],
        },
    )
    update_response.raise_for_status()
    assert update_response.json()["full_name"] == "Demo Patient"

    start_response = client.post(
        "/api/v1/incidents",
        json={
            "session_uid": session_uid,
            "patient_id": "user_001",
            "event_type": "fall",
            "simulation_trigger": {"source": "test", "motion_state": "rapid_descent"},
            "video_metadata": {"filename": "fall-demo.mp4", "duration_seconds": 8},
        },
    )
    start_response.raise_for_status()
    incident = start_response.json()
    incident_id = incident["incident_id"]
    assert incident["session_uid"] == session_uid
    assert incident["status"] == "analyzing"

    triage_response = client.post(
        f"/api/v1/incidents/{incident_id}/triage",
        json={
            "triage_answers": [
                {"question_id": "consciousness", "answer": "Dizzy but awake"},
                {"question_id": "pain", "answer": "Hip pain and cannot stand"},
            ],
            "ai_decision": {
                "summary": "High-risk fall with possible injury.",
                "reasoning": "Fall plus inability to stand.",
                "action": "call_family",
            },
            "severity": "high",
            "final_action": "call_family",
        },
    )
    triage_response.raise_for_status()
    assert triage_response.json()["status"] == "reasoning"
    assert triage_response.json()["final_action"] == "call_family"

    result_response = client.get(f"/api/v1/incidents/{incident_id}/result")
    result_response.raise_for_status()
    assert result_response.json()["ai_result"]

    execute_response = client.post(f"/api/v1/incidents/{incident_id}/execute", json={})
    execute_response.raise_for_status()
    executed = execute_response.json()
    assert executed["execution_locked"] is True
    assert executed["execution_count"] == 1
    assert executed["action_taken"]["sms_results"]
    assert executed["action_taken"]["sms_results"][0]["status"] == "simulated"

    duplicate_response = client.post(f"/api/v1/incidents/{incident_id}/execute", json={})
    duplicate_response.raise_for_status()
    assert duplicate_response.json()["execution_count"] == 1

    history_response = client.get(f"/api/v1/history?session_uid={session_uid}")
    history_response.raise_for_status()
    history = history_response.json()
    assert history
    assert history[0]["incident_id"] == incident_id

    sms_response = client.post(
        "/api/v1/sms/send",
        json={
            "to": "+60123456789",
            "message": "Standalone SMS smoke test",
            "incident_id": incident_id,
        },
    )
    sms_response.raise_for_status()
    assert sms_response.json()["status"] == "simulated"

    print("Incident lifecycle API verified.")


if __name__ == "__main__":
    main()
