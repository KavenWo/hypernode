import json
import logging
import os
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.auth import default as google_auth_default
from google.auth.exceptions import DefaultCredentialsError

BACKEND_DIR = Path(__file__).resolve().parents[2]
FALLBACK_GUIDANCE_PATH = BACKEND_DIR / "data" / "medical_guidance_fallback.json"

try:
    from google.cloud import discoveryengine_v1 as discoveryengine
except ImportError:  # pragma: no cover - optional during early local setup
    discoveryengine = None

logger = logging.getLogger(__name__)


def _to_plain_value(value):
    """Best-effort conversion from protobuf wrapper values to plain Python values."""
    if isinstance(value, dict):
        return {key: _to_plain_value(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_to_plain_value(item) for item in value]
    if hasattr(value, "items"):
        try:
            return {key: _to_plain_value(inner) for key, inner in value.items()}
        except Exception:
            pass
    return value


def _as_plain_mapping(value) -> dict:
    """Convert Discovery Engine struct-like values into a normal dict."""
    plain = _to_plain_value(value or {})
    return plain if isinstance(plain, dict) else {}


def _as_plain_list(value) -> list:
    """Convert repeated protobuf collections into a normal Python list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [_to_plain_value(item) for item in value]
    try:
        return [_to_plain_value(item) for item in list(value)]
    except Exception:
        return []


def retrieve_medical_guidance(query: str, max_results: int = 3) -> list[str]:
    return retrieve_medical_guidance_with_source(query, max_results=max_results)["snippets"]


def retrieve_medical_guidance_with_source(query: str, max_results: int = 3) -> dict:
    """Return grounded guidance plus the source used to retrieve it."""
    logger.info("Retrieving grounded medical guidance for query: %s", query)
    vertex_result = _query_vertex_ai_search(query, max_results=max_results)
    results = vertex_result["snippets"]
    if results:
        logger.info(
            "Vertex AI Search returned %d snippet(s) and %d reference(s).",
            len(results),
            len(vertex_result["references"]),
        )
        for index, snippet in enumerate(results, start=1):
            logger.info("Vertex snippet %d: %s", index, snippet[:500])
        for index, reference in enumerate(vertex_result["references"], start=1):
            logger.info("Vertex reference %d: %s", index, json.dumps(reference))
        return {
            "snippets": results,
            "source": "vertex_ai_search",
            "references": vertex_result["references"],
        }
    if vertex_result["status"] == "no_results":
        logger.warning("Vertex AI Search returned zero usable snippets for query: %s", query)
    elif vertex_result["status"] == "error":
        logger.warning("Vertex AI Search failed for query: %s", query)
    fallback = _load_fallback_guidance(query)
    logger.info("Using fallback medical guidance file with %d snippet(s).", len(fallback))
    for index, snippet in enumerate(fallback, start=1):
        logger.info("Fallback snippet %d: %s", index, snippet[:500])
    return {
        "snippets": fallback,
        "source": "fallback_file",
        "references": [],
    }


def _pick_reference_fields(document: object) -> dict:
    """Extract lightweight document reference metadata for logs and UI."""
    struct_data = _as_plain_mapping(getattr(document, "struct_data", None))
    derived_struct_data = _as_plain_mapping(getattr(document, "derived_struct_data", None))

    reference: dict[str, str] = {}
    for field in [
        "title",
        "name",
        "file_name",
        "filename",
        "document_title",
        "display_name",
        "source",
        "uri",
        "link",
    ]:
        value = struct_data.get(field)
        if isinstance(value, str) and value.strip():
            reference[field] = value.strip()

    for field in [
        "title",
        "name",
        "file_name",
        "filename",
        "document_title",
        "display_name",
        "source",
        "uri",
        "link",
    ]:
        value = derived_struct_data.get(field)
        if isinstance(value, str) and value.strip() and field not in reference:
            reference[field] = value.strip()

    document_id = getattr(document, "id", None)
    if isinstance(document_id, str) and document_id.strip():
        reference["document_id"] = document_id.strip()

    document_name = getattr(document, "name", None)
    if isinstance(document_name, str) and document_name.strip():
        reference["document_name"] = document_name.strip()

    return reference


def _query_vertex_ai_search(query: str, max_results: int) -> dict:
    project_id = os.getenv("VERTEX_AI_SEARCH_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("VERTEX_AI_SEARCH_LOCATION", "global")
    engine_id = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID")

    if discoveryengine is None or not project_id or not engine_id:
        logger.warning(
            "Vertex AI Search not configured or library unavailable. discoveryengine=%s project_id=%s engine_id=%s",
            discoveryengine is not None,
            bool(project_id),
            bool(engine_id),
        )
        return {"snippets": [], "references": [], "status": "not_configured"}

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
        credentials, detected_project = google_auth_default()
        logger.info("ADC resolved for Vertex AI Search. Detected project: %s", detected_project or "<none>")
        logger.info("Calling Vertex AI Search serving config: %s", serving_config)
        client = discoveryengine.SearchServiceClient(
            credentials=credentials,
            client_options=client_options,
        )
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=max_results,
            content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                    return_snippet=True,
                ),
                extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                    max_extractive_answer_count=1,
                    max_extractive_segment_count=max_results,
                ),
            ),
        )
        response = client.search(request=request)
    except DefaultCredentialsError as exc:
        logger.warning("Vertex AI Search credentials are unavailable: %s", exc)
        return {"snippets": [], "references": [], "status": "error"}
    except Exception as exc:  # pragma: no cover - network/auth depends on runtime environment
        logger.warning(
            "Vertex AI Search request failed for serving config %s: %s",
            serving_config,
            exc,
        )
        return {"snippets": [], "references": [], "status": "error"}

    snippets: list[str] = []
    references: list[dict] = []
    for result in response.results:
        document = result.document
        references.append(_pick_reference_fields(document))
        derived_struct_data = _as_plain_mapping(getattr(document, "derived_struct_data", None))
        extractive_segments = _as_plain_list(derived_struct_data.get("extractive_segments"))
        for segment in extractive_segments:
            segment_map = _as_plain_mapping(segment)
            content = segment_map.get("content")
            if content:
                snippets.append(content)
        extractive_answers = _as_plain_list(derived_struct_data.get("extractive_answers"))
        for answer in extractive_answers:
            answer_map = _as_plain_mapping(answer)
            content = answer_map.get("content")
            if content:
                snippets.append(content)
        raw_snippets = _as_plain_list(derived_struct_data.get("snippets"))
        for snippet in raw_snippets:
            snippet_map = _as_plain_mapping(snippet)
            snippet_text = snippet_map.get("snippet")
            if snippet_text:
                snippets.append(snippet_text)
        if not snippets and getattr(document, "struct_data", None):
            snippets.append(json.dumps(_as_plain_mapping(getattr(document, "struct_data", None))))
    return {
        "snippets": snippets[:max_results],
        "references": references,
        "status": "success" if snippets else "no_results",
    }


def _load_fallback_guidance(query: str) -> list[str]:
    logger.info("Loading fallback guidance from %s for query: %s", FALLBACK_GUIDANCE_PATH, query)
    with FALLBACK_GUIDANCE_PATH.open("r", encoding="utf-8") as handle:
        guidance = json.load(handle)

    lowered = query.lower()
    if "cpr" in lowered or "not breathing" in lowered:
        return guidance["cpr"]
    if "red flag" in lowered or "high risk" in lowered or "blood thinner" in lowered:
        return guidance["fall_red_flags"]
    return guidance["first_aid_fall"]
