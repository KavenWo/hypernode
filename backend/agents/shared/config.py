import os
import logging

from google import genai

if not os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_GENAI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_GENAI_API_KEY"]

REASONING_PRIMARY_MODEL = "gemini-3-pro-preview"
REASONING_FALLBACK_MODELS = ("gemini-pro-latest", "gemini-2.5-pro", "gemini-2.5-flash")

COMMUNICATION_PRIMARY_MODEL = "gemini-3-flash-preview"
COMMUNICATION_FALLBACK_MODELS = ("gemini-flash-latest", "gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite")

logger = logging.getLogger(__name__)


def _use_vertex_ai_adc() -> bool:
    return os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in {"1", "true", "yes", "on"}


def get_genai_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        logger.info(
            "Gemini client initialized. Reasoning model: %s | Communication model: %s",
            REASONING_PRIMARY_MODEL,
            COMMUNICATION_PRIMARY_MODEL,
        )
        return genai.Client(api_key=api_key)

    if _use_vertex_ai_adc():
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not project:
            logger.warning("GOOGLE_CLOUD_PROJECT is not set. The backend will use fallback reasoning.")
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set for Vertex AI ADC mode.")
        logger.info(
            "Gemini client initialized with Vertex AI ADC. Reasoning model: %s | Communication model: %s | project=%s | location=%s",
            REASONING_PRIMARY_MODEL,
            COMMUNICATION_PRIMARY_MODEL,
            project,
            location,
        )
        return genai.Client(vertexai=True, project=project, location=location)

    logger.info(
        "No Gemini API key or Vertex AI ADC configuration found. The backend will use fallback reasoning."
    )
    raise RuntimeError("No Gemini API key or Vertex AI ADC configuration found.")
