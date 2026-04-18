from app.fall.assessment_service import get_runtime_status


def test_runtime_status_reports_storage_and_agent_backends(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "hypernode-492511")
    monkeypatch.setenv(
        "ADK_VERTEX_SEARCH_ENGINE_ID",
        "projects/848039689147/locations/us/collections/default_collection/engines/hypernode_1776448189581",
    )
    monkeypatch.setenv("AGENT_BACKEND_REASONING", "adk")
    monkeypatch.setenv("AGENT_BACKEND_COMMUNICATION", "adk")
    monkeypatch.setenv("AGENT_BACKEND_EXECUTION", "adk")
    monkeypatch.delenv("AGENT_BACKEND_VISION", raising=False)
    monkeypatch.delenv("AGENT_BACKEND_VITALS", raising=False)

    status = get_runtime_status()

    assert status["backend_ok"] is True
    assert status["vertex_search_configured"] is True
    assert status["storage"]["storage_mode"] in {"firestore_preferred", "local_sample_only"}
    assert status["agent_backends"]["reasoning"] == "adk"
    assert status["agent_backends"]["communication"] == "adk"
    assert status["agent_backends"]["execution"] == "adk"
    assert "reasoning" in status["adk_enabled_roles"]


def test_runtime_status_reports_local_sample_storage_when_firestore_unconfigured(monkeypatch):
    monkeypatch.delenv("FIRESTORE_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    status = get_runtime_status()

    assert status["storage"]["storage_mode"] == "local_sample_only"
    assert status["storage"]["firestore_configured"] is False
    assert status["storage"]["demo_ready"] is True
