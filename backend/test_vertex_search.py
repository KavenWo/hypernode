"""Run a direct Vertex AI Search app query using backend/.env."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.api_core.client_options import ClientOptions
from google.auth import default as google_auth_default
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import discoveryengine_v1 as discoveryengine

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")


def _build_serving_config(project_id: str, location: str, engine_id: str) -> str:
    return (
        f"projects/{project_id}/locations/{location}/collections/default_collection/"
        f"engines/{engine_id}/servingConfigs/default_config"
    )


def _pick_display_title(document: object) -> str | None:
    struct_data = getattr(document, "struct_data", None) or {}
    derived_struct_data = getattr(document, "derived_struct_data", None) or {}

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
    struct_data = getattr(document, "struct_data", None) or {}
    derived_struct_data = getattr(document, "derived_struct_data", None) or {}

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

        derived_struct_data = getattr(document, "derived_struct_data", None) or {}
        extractive_segments = derived_struct_data.get("extractive_segments", [])
        if extractive_segments:
            for segment_index, segment in enumerate(extractive_segments[:2], start=1):
                content = segment.get("content", "").strip()
                if content:
                    print(f"Segment {segment_index}: {content[:400]}")
        elif getattr(document, "struct_data", None):
            print(f"Struct data: {document.struct_data}")
        else:
            print("No extractive segment or struct data in this result.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
