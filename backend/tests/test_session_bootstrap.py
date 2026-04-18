from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_session_bootstrap_creates_session_and_profile(monkeypatch):
    monkeypatch.setattr(
        "app.services.session_auth_service.verify_firebase_id_token",
        lambda token: {"uid": "anon_uid_123", "firebase": {"sign_in_provider": "anonymous"}},
    )

    response = client.post(
        "/api/v1/session/bootstrap",
        json={
            "id_token": "fake-token",
            "create_profile": True,
        },
    )

    response.raise_for_status()
    payload = response.json()
    assert payload["session"]["session_uid"] == "anon_uid_123"
    assert payload["patient_id"] == "anon_uid_123"
    assert payload["profile"]["patient_id"] == "anon_uid_123"
    assert payload["profile"]["session_uid"] == "anon_uid_123"


def test_session_me_resolves_bearer_token(monkeypatch):
    monkeypatch.setattr(
        "app.services.session_auth_service.verify_firebase_id_token",
        lambda token: {"uid": "anon_uid_me"},
    )

    response = client.get(
        "/api/v1/session/me",
        headers={"Authorization": "Bearer fake-token"},
    )

    response.raise_for_status()
    payload = response.json()
    assert payload["session"]["session_uid"] == "anon_uid_me"
    assert payload["patient_id"] == "anon_uid_me"


def test_session_bootstrap_accepts_sub_claim(monkeypatch):
    monkeypatch.setattr(
        "app.services.session_auth_service.verify_firebase_id_token",
        lambda token: {"sub": "anon_uid_sub", "firebase": {"sign_in_provider": "anonymous"}},
    )

    response = client.post(
        "/api/v1/session/bootstrap",
        json={
            "id_token": "fake-token",
            "create_profile": True,
        },
    )

    response.raise_for_status()
    payload = response.json()
    assert payload["session"]["session_uid"] == "anon_uid_sub"
    assert payload["patient_id"] == "anon_uid_sub"
