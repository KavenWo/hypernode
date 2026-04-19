"""Focused checks for the controlled demo-video API surface."""

from fastapi.testclient import TestClient

from app.main import app


def test_demo_video_registry_and_file_routes() -> None:
    client = TestClient(app)

    registry_response = client.get("/api/v1/events/fall/demo-videos")
    registry_response.raise_for_status()
    registry_payload = registry_response.json()

    assert registry_payload["videos"], registry_payload
    video_ids = {item["id"] for item in registry_payload["videos"]}
    assert {"clip1", "clip2"}.issubset(video_ids), registry_payload

    demo_video = next((item for item in registry_payload["videos"] if item["id"] == "clip1"), None)
    assert demo_video is not None, registry_payload
    assert demo_video["summary"] == "Gemini will analyze this clip at session start.", demo_video
    assert demo_video["available"] is True, demo_video

    file_response = client.get("/api/v1/events/fall/demo-videos/clip1/file")
    file_response.raise_for_status()
    assert file_response.headers["content-type"].startswith("video/mp4"), file_response.headers


def test_demo_video_analysis_route_uses_ai_result(monkeypatch) -> None:
    client = TestClient(app)

    async def fake_analyze_demo_video(video_id: str):
        return {
            "video_id": video_id,
            "video_label": "Clip 1",
            "video_source": "local_demo_video",
            "fall_detected": True,
            "summary": "Person fell and is motionless",
            "motion_state": "rapid_descent",
            "confidence_score": 0.98,
            "analysis_model": "gemini-2.5-flash",
        }

    monkeypatch.setattr("app.api.routes.fall.analyze_demo_video", fake_analyze_demo_video)

    response = client.post(
        "/api/v1/events/fall/demo-videos/analyze",
        json={
            "user_id": "user_001",
            "video_id": "clip1",
        },
    )
    response.raise_for_status()
    payload = response.json()

    assert payload["video_id"] == "clip1", payload
    assert payload["fall_detected"] is True, payload
    assert payload["summary"] == "Person fell and is motionless", payload
    assert payload["motion_state"] == "rapid_descent", payload
