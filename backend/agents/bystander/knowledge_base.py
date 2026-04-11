import json
import logging
import os
from pathlib import Path

from google.api_core.client_options import ClientOptions

BACKEND_DIR = Path(__file__).resolve().parents[2]
FALLBACK_GUIDANCE_PATH = BACKEND_DIR / "data" / "medical_guidance_fallback.json"

try:
    from google.cloud import discoveryengine_v1 as discoveryengine
except ImportError:  # pragma: no cover - optional during early local setup
    discoveryengine = None

logger = logging.getLogger(__name__)


def retrieve_medical_guidance(query: str, max_results: int = 3) -> list[str]:
    results = _query_vertex_ai_search(query, max_results=max_results)
    if results:
        return results
    return _load_fallback_guidance(query)


def _query_vertex_ai_search(query: str, max_results: int) -> list[str]:
    project_id = os.getenv("VERTEX_AI_SEARCH_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("VERTEX_AI_SEARCH_LOCATION", "global")
    engine_id = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID")

    if discoveryengine is None or not project_id or not engine_id:
        return []

    client_options = (
        ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
        if location != "global"
        else None
    )
    serving_config = (
        f"projects/{project_id}/locations/{location}/collections/default_collection/"
        f"engines/{engine_id}/servingConfigs/default_config"
    )

    try:
        client = discoveryengine.SearchServiceClient(client_options=client_options)
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=max_results,
        )
        response = client.search(request=request)
    except Exception:  # pragma: no cover - network/auth depends on runtime environment
        logger.exception("Vertex AI Search request failed for serving config %s", serving_config)
        return []

    snippets: list[str] = []
    for result in response.results:
        document = result.document
        derived_struct_data = getattr(document, "derived_struct_data", None) or {}
        extractive_segments = derived_struct_data.get("extractive_segments", [])
        for segment in extractive_segments:
            content = segment.get("content")
            if content:
                snippets.append(content)
        if not snippets and getattr(document, "struct_data", None):
            snippets.append(json.dumps(document.struct_data))
    return snippets[:max_results]


def _load_fallback_guidance(query: str) -> list[str]:
    with FALLBACK_GUIDANCE_PATH.open("r", encoding="utf-8") as handle:
        guidance = json.load(handle)

    lowered = query.lower()
    if "cpr" in lowered or "not breathing" in lowered:
        return guidance["cpr"]
    if "red flag" in lowered or "high risk" in lowered or "blood thinner" in lowered:
        return guidance["fall_red_flags"]
    return guidance["first_aid_fall"]
