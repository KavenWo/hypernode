"""Exercise the FastAPI fall endpoints the frontend will call."""

import time

from fastapi.testclient import TestClient

from app.main import app


def test_api_fall_flow() -> None:
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
            "interaction": {
                "patient_response_status": "unknown",
                "bystander_available": True,
                "bystander_can_help": True,
                "testing_assume_bystander": True,
                "message_text": "I am next to the patient and can help.",
                "new_fact_keys": [],
            },
        },
    )
    questions_response.raise_for_status()
    questions_payload = questions_response.json()
    questions = questions_payload["questions"]
    assert len(questions) == 3, questions
    assert questions_payload["interaction"]["communication_target"] == "bystander", questions_payload

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
                {"question_id": "patient_responsiveness", "answer": "He responds slowly and seems confused."},
                {"question_id": "breathing_observation", "answer": "He is breathing strangely and cannot stand up."},
                {"question_id": "head_strike_and_risk", "answer": "He hit his head and takes blood thinners."},
            ],
            "interaction": {
                "patient_response_status": "confused",
                "bystander_available": True,
                "bystander_can_help": True,
                "testing_assume_bystander": True,
                "message_text": "He is breathing strangely now.",
                "new_fact_keys": ["abnormal_breathing", "head_strike"],
            },
        },
    )
    assess_response.raise_for_status()
    assessment = assess_response.json()

    assert assessment["clinical_assessment"]["severity"] == "critical", assessment
    assert assessment["action"]["recommended"] in {"dispatch_pending_confirmation", "emergency_dispatch"}, assessment
    assert assessment["interaction"]["communication_target"] == "bystander", assessment
    assert assessment["interaction"]["reasoning_refresh"]["required"] is True, assessment
    assert assessment["clinical_assessment"]["red_flags"], assessment
    assert "reasoning_trace" in assessment["clinical_assessment"], assessment
    assert "response_plan" in assessment, assessment
    assert "escalation_action" in assessment["response_plan"], assessment
    assert "communication_handoff" in assessment, assessment
    assert "protocol_guidance" in assessment, assessment
    assert assessment["communication_handoff"]["mode"] in {"question", "instruction", "status_update", "urgent_instruction", "reassure"}, assessment
    assert "recommended_context_bits" in assessment["communication_handoff"], assessment
    assert "should_surface_execution_update" in assessment["communication_handoff"], assessment
    assert assessment["detection"]["fall_detection_confidence_band"] == "high", assessment
    assert assessment["grounding"]["source"] in {"vertex_ai_search", "fallback_file"}, assessment
    assert assessment["audit"]["dispatch_triggered"] == (assessment["action"]["recommended"] == "emergency_dispatch"), assessment
    if assessment["action"]["recommended"] == "emergency_dispatch":
        assert assessment["incident_id"], assessment
    else:
        assert assessment["incident_id"] in {None, ""}, assessment

    session_turn_response = client.post(
        "/api/v1/events/fall/session-turn",
        json={
            "event": {
                "user_id": "user_001",
                "timestamp": "2024-04-10T12:00:00Z",
                "motion_state": "rapid_descent",
                "confidence_score": 0.98,
            },
            "interaction": {
                "patient_response_status": "confused",
                "bystander_available": True,
                "bystander_can_help": True,
                "testing_assume_bystander": True,
                "new_fact_keys": ["abnormal_breathing"],
            },
            "latest_responder_message": "He is breathing strangely now.",
        },
    )
    session_turn_response.raise_for_status()
    session_turn_payload = session_turn_response.json()
    assert session_turn_payload["session_id"], session_turn_payload
    assert session_turn_payload["reasoning_invoked"] is True, session_turn_payload
    assert session_turn_payload["reasoning_status"] == "pending", session_turn_payload
    assert session_turn_payload["reasoning_run_count"] == 0, session_turn_payload
    assert session_turn_payload["interaction"]["communication_target"] == "bystander", session_turn_payload
    assert session_turn_payload["assistant_message"], session_turn_payload

    session_state_payload = None
    for _ in range(20):
        session_state_response = client.get(
            f"/api/v1/events/fall/session-state/{session_turn_payload['session_id']}"
        )
        session_state_response.raise_for_status()
        session_state_payload = session_state_response.json()
        if session_state_payload["reasoning_status"] == "completed":
            break
        time.sleep(0.15)

    assert session_state_payload is not None, session_turn_payload
    assert session_state_payload["conversation_history"], session_state_payload
    assert session_state_payload["assessment"] is not None, session_state_payload
    assert session_state_payload["reasoning_run_count"] >= 1, session_state_payload

    assert session_state_payload["assessment"] is not None, session_state_payload

    reset_response = client.post(
        f"/api/v1/events/fall/session-reset/{session_turn_payload['session_id']}"
    )
    reset_response.raise_for_status()
    reset_payload = reset_response.json()
    assert reset_payload["reset"] is True, reset_payload

    missing_state_response = client.get(
        f"/api/v1/events/fall/session-state/{session_turn_payload['session_id']}"
    )
    assert missing_state_response.status_code == 404, missing_state_response.text
