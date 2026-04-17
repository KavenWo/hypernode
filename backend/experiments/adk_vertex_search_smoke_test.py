"""Minimal ADK smoke test for Vertex AI Search grounding.

This keeps the test intentionally small so we can answer one question first:
can ADK call Vertex AI Search successfully from code?
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    load_dotenv(backend_root / ".env", override=False)
    load_dotenv(backend_root / "local.env", override=True)


def _resource_from_env() -> tuple[str, str]:
    datastore_id = os.getenv("ADK_VERTEX_DATASTORE_ID", "").strip()
    search_engine_id = os.getenv("ADK_VERTEX_SEARCH_ENGINE_ID", "").strip()
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    search_location = os.getenv("VERTEX_AI_SEARCH_LOCATION", "").strip() or "global"
    collection = os.getenv("ADK_VERTEX_COLLECTION_ID", "").strip() or "default_collection"
    legacy_engine_id = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID", "").strip()

    if datastore_id and search_engine_id:
        raise RuntimeError(
            "Set only one of ADK_VERTEX_DATASTORE_ID or ADK_VERTEX_SEARCH_ENGINE_ID for the smoke test."
        )
    if datastore_id:
        return "datastore", datastore_id
    if search_engine_id:
        return "engine", search_engine_id
    if project and legacy_engine_id:
        return (
            "engine",
            f"projects/{project}/locations/{search_location}/collections/{collection}/engines/{legacy_engine_id}",
        )

    raise RuntimeError(
        "Missing ADK search resource. Set ADK_VERTEX_DATASTORE_ID or ADK_VERTEX_SEARCH_ENGINE_ID in backend/.env or backend/local.env."
    )


def _build_agent():
    from google.adk.agents import llm_agent
    from google.adk.tools import VertexAiSearchTool

    resource_kind, resource_id = _resource_from_env()
    tool_kwargs = (
        {"data_store_id": resource_id}
        if resource_kind == "datastore"
        else {"search_engine_id": resource_id}
    )

    return llm_agent.LlmAgent(
        name="VertexSearchSmokeTest",
        model=os.getenv("ADK_VERTEX_MODEL", "gemini-2.5-flash"),
        description="Small smoke test for Vertex AI Search grounding through ADK.",
        sub_agents=[],
        instruction=(
            "Use the VertexAiSearchTool first. "
            "Return only grounded information from retrieved results. "
            "If no relevant result is found, say that no grounded result was found. "
            "Include short references to retrieved sources when available."
        ),
        tools=[VertexAiSearchTool(**tool_kwargs)],
    )


async def main() -> None:
    _load_env()

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    app_name = "vertex-search-smoke-test"
    user_id = os.getenv("ADK_TEST_USER_ID", "codex-smoke-test")
    session_id = "session-001"
    prompt = os.getenv(
        "ADK_TEST_QUERY",
        (
            "Search the connected datastore for CPR guidance for an unresponsive patient after a fall. "
            "Tell me whether grounded results were found, summarize the top grounded facts, "
            "and mention any source titles or document identifiers if available."
        ),
    )

    agent = _build_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)

    print("=== ADK Vertex Search Smoke Test ===")
    print(f"Project: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
    print(f"Location: {os.getenv('GOOGLE_CLOUD_LOCATION')}")
    resource_kind, resource_id = _resource_from_env()
    print(f"Search resource kind: {resource_kind}")
    print(f"Search resource id: {resource_id}")
    print(f"Model: {os.getenv('ADK_VERTEX_MODEL', 'gemini-2.5-flash')}")
    print(f"Prompt: {prompt}")
    print()

    final_text_parts: list[str] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        print(f"[event] author={getattr(event, 'author', 'unknown')} final={event.is_final_response()}")
        content = getattr(event, "content", None)
        if content and getattr(content, "parts", None):
            for part in content.parts:
                text = getattr(part, "text", None)
                if text:
                    print(text)
                    if event.is_final_response():
                        final_text_parts.append(text)
        grounding_metadata = getattr(event, "grounding_metadata", None)
        if grounding_metadata:
            print("[grounding_metadata]", grounding_metadata)
        print("---")

    final_text = "\n".join(final_text_parts).strip()
    print("=== FINAL RESPONSE ===")
    print(final_text or "(no final text)")


if __name__ == "__main__":
    asyncio.run(main())
