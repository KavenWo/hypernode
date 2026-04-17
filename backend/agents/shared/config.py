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


def get_genai_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. The backend will use fallback reasoning.")
        raise RuntimeError("GEMINI_API_KEY is not set.")
    logger.info(
        "Gemini client initialized. Reasoning model: %s | Communication model: %s",
        REASONING_PRIMARY_MODEL,
        COMMUNICATION_PRIMARY_MODEL,
    )
    return genai.Client(api_key=api_key)
