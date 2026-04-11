"""Run a direct Vertex AI Search app query using backend/.env."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.api_core.client_options import ClientOptions
from google.auth import default as google_auth_default
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import discoveryengine_v1 as discoveryengine

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def _build_serving_config(project_id: str, location: str, engine_id: str) -> str:
    return (
        f"projects/{project_id}/locations/{location}/collections/default_collection/"
        f"engines/{engine_id}/servingConfigs/default_config"
    )


def _to_plain_value(value):
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
    plain = _to_plain_value(value or {})
    return plain if isinstance(plain, dict) else {}


def _as_plain_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [_to_plain_value(item) for item in value]
    try:
        return [_to_plain_value(item) for item in list(value)]
    except Exception:
        return []


def _pick_display_title(document: object) -> str | None:
    struct_data = _as_plain_mapping(getattr(document, "struct_data", None))
    derived_struct_data = _as_plain_mapping(getattr(document, "derived_struct_data", None))

    candidate_fields = [
        "title",
        "name",
        "file_name",
        "filename",
        "document_title",
        "display_name",
        "source",
        "uri",
        "link",
    ]

    for field in candidate_fields:
        value = struct_data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for field in candidate_fields:
        value = derived_struct_data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    document_name = getattr(document, "name", None)
    if isinstance(document_name, str) and document_name.strip():
        return document_name.strip()

    return None


def _print_source_metadata(document: object) -> None:
    struct_data = _as_plain_mapping(getattr(document, "struct_data", None))
    derived_struct_data = _as_plain_mapping(getattr(document, "derived_struct_data", None))

    source_fields = [
        "uri",
        "link",
        "source",
        "file_name",
        "filename",
        "title",
        "document_title",
        "display_name",
    ]

    printed = False
    for field in source_fields:
        value = struct_data.get(field)
        if isinstance(value, str) and value.strip():
            print(f"{field}: {value.strip()}")
            printed = True

    if not printed:
        for field in source_fields:
            value = derived_struct_data.get(field)
            if isinstance(value, str) and value.strip():
                print(f"{field}: {value.strip()}")
                printed = True

    if not printed:
        struct_keys = sorted(struct_data.keys())
        derived_keys = sorted(derived_struct_data.keys())
        if struct_keys:
            print(f"Struct data keys: {', '.join(struct_keys[:10])}")
        if derived_keys:
            print(f"Derived data keys: {', '.join(derived_keys[:10])}")


def main() -> int:
    query = " ".join(sys.argv[1:]).strip() or "retrieve what to do if unconscious"

    project_id = os.getenv("VERTEX_AI_SEARCH_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("VERTEX_AI_SEARCH_LOCATION", "global")
    engine_id = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID")

    print("Vertex AI Search test")
    print(f"Project ID: {project_id or '<missing>'}")
    print(f"Location: {location}")
    print(f"Engine ID: {engine_id or '<missing>'}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS set: {bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))}")
    print(f"Query: {query}")

    if not project_id or not engine_id:
        print(
            "\nMissing required env vars. Expected "
            "VERTEX_AI_SEARCH_PROJECT_ID and VERTEX_AI_SEARCH_ENGINE_ID."
        )
        return 1

    try:
        credentials, detected_project = google_auth_default()
        print(f"ADC resolved successfully. Detected project: {detected_project or '<none>'}")
    except DefaultCredentialsError as exc:
        print("\nADC not configured.")
        print(f"Reason: {exc}")
        print(
            "Next step: either run `gcloud auth application-default login` or set "
            "`GOOGLE_APPLICATION_CREDENTIALS` to a service-account JSON file."
        )
        return 1

    client_options = (
        ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
        if location != "global"
        else None
    )
    serving_config = _build_serving_config(project_id, location, engine_id)

    print(f"Serving config: {serving_config}")

    try:
        client = discoveryengine.SearchServiceClient(
            credentials=credentials,
            client_options=client_options,
        )
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=3,
            content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                    return_snippet=True,
                ),
                extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                    max_extractive_answer_count=1,
                    max_extractive_segment_count=3,
                ),
            ),
        )
        response = client.search(request=request)
    except Exception as exc:
        print("\nVertex AI Search request failed.")
        print(f"Error type: {type(exc).__name__}")
        print(f"Details: {exc}")
        return 1

    results = list(response.results)
    print(f"\nSearch succeeded. Result count: {len(results)}")

    if not results:
        print("The request worked, but no results were returned.")
        return 0

    for index, result in enumerate(results, start=1):
        document = result.document
        print(f"\nResult {index}")
        title = _pick_display_title(document)
        if title:
            print(f"Title: {title}")
        print(f"Document ID: {getattr(document, 'id', '<none>')}")
        print(f"Document Name: {getattr(document, 'name', '<none>')}")
        _print_source_metadata(document)

        derived_struct_data = _as_plain_mapping(getattr(document, "derived_struct_data", None))
        extractive_segments = _as_plain_list(derived_struct_data.get("extractive_segments"))
        extractive_answers = _as_plain_list(derived_struct_data.get("extractive_answers"))
        snippets = _as_plain_list(derived_struct_data.get("snippets"))

        if extractive_answers:
            for answer_index, answer in enumerate(extractive_answers[:2], start=1):
                answer_map = _as_plain_mapping(answer)
                content = str(answer_map.get("content", "")).strip()
                page_number = answer_map.get("pageNumber") or answer_map.get("page_number")
                if content:
                    suffix = f" (page {page_number})" if page_number else ""
                    print(f"Extractive Answer {answer_index}{suffix}: {content[:400]}")
        if extractive_segments:
            for segment_index, segment in enumerate(extractive_segments[:2], start=1):
                segment_map = _as_plain_mapping(segment)
                content = str(segment_map.get("content", "")).strip()
                if content:
                    print(f"Segment {segment_index}: {content[:400]}")
        if snippets:
            for snippet_index, snippet in enumerate(snippets[:2], start=1):
                snippet_map = _as_plain_mapping(snippet)
                snippet_text = str(snippet_map.get("snippet", "")).strip()
                if snippet_text:
                    print(f"Snippet {snippet_index}: {snippet_text[:400]}")
        elif getattr(document, "struct_data", None):
            print(f"Struct data: {_as_plain_mapping(getattr(document, 'struct_data', None))}")
        else:
            print("No extractive segment or struct data in this result.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
