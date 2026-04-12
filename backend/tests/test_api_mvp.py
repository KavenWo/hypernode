"""Exercise the FastAPI MVP endpoints the frontend will call."""

from pathlib import Path
import sys

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from app.main import app


def main() -> None:
    client = TestClient(app)

    questions_response = client.post(
        "/api/v1/events/fall/questions",
        json={
            "event": {
                "user_id": "user_001",
                "timestamp": "2024-04-10T12:00:00Z",
                "motion_state": "rapid_descent",
                "confidence_score": 0.98,
            },
            "vitals": {
                "user_id": "user_001",
                "heart_rate": 118,
                "blood_pressure_systolic": 92,
                "blood_pressure_diastolic": 58,
                "blood_oxygen_sp02": 91.0,
            },
        },
    )
    questions_response.raise_for_status()
    questions = questions_response.json()["questions"]
    assert len(questions) == 3, questions

    assess_response = client.post(
        "/api/v1/events/fall/assess",
        json={
            "event": {
                "user_id": "user_001",
                "timestamp": "2024-04-10T12:00:00Z",
                "motion_state": "rapid_descent",
                "confidence_score": 0.98,
            },
            "vitals": {
                "user_id": "user_001",
                "heart_rate": 118,
                "blood_pressure_systolic": 92,
                "blood_pressure_diastolic": 58,
                "blood_oxygen_sp02": 91.0,
            },
            "patient_answers": [
                {"question_id": "consciousness", "answer": "Yes, but I feel dizzy and slow to respond."},
                {"question_id": "pain_mobility", "answer": "I have strong pain in my hip and cannot stand up."},
                {"question_id": "head_injury_blood_thinner", "answer": "I hit my head and I take blood thinners."},
            ],
        },
    )
    assess_response.raise_for_status()
    assessment = assess_response.json()

    assert assessment["clinical_assessment"]["severity"] == "critical", assessment
    assert assessment["action"]["recommended"] in {"dispatch_pending_confirmation", "emergency_dispatch"}, assessment
    assert assessment["clinical_assessment"]["red_flags"], assessment
    assert assessment["detection"]["fall_detection_confidence_band"] == "high", assessment
    assert assessment["grounding"]["source"] in {"vertex_ai_search", "fallback_file"}, assessment
    assert assessment["audit"]["dispatch_triggered"] == (assessment["action"]["recommended"] == "emergency_dispatch"), assessment
    if assessment["action"]["recommended"] == "emergency_dispatch":
        assert assessment["incident_id"], assessment
    else:
        assert assessment["incident_id"] in {None, ""}, assessment

    print("MVP API flow verified.")


if __name__ == "__main__":
    main()
