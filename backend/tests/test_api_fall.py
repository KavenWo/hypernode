"""Exercise the FastAPI fall endpoints the frontend will call."""

import time

from fastapi.testclient import TestClient

from app.main import app


def test_api_fall_flow() -> None:
    client = TestClient(app)

    demo_videos_response = client.get("/api/v1/events/fall/demo-videos")
    demo_videos_response.raise_for_status()
    demo_videos_payload = demo_videos_response.json()
    assert demo_videos_payload["videos"], demo_videos_payload
    assert any(video["id"] == "clip1" for video in demo_videos_payload["videos"]), demo_videos_payload

    demo_video_file_response = client.get("/api/v1/events/fall/demo-videos/clip1/file")
    demo_video_file_response.raise_for_status()
    assert demo_video_file_response.headers["content-type"].startswith("video/mp4"), demo_video_file_response.headers

    session_turn_response = client.post(
        "/api/v1/events/fall/session-turn",
        json={
            "event": {
                "user_id": "user_001",
                "timestamp": "2024-04-10T12:00:00Z",
                "motion_state": "rapid_descent",
                "confidence_score": 0.98,
                "video_id": "clip1",
                "video_source": "local_demo_video",
                "video_summary": "Person fell and is motionless",
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
