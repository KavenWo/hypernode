import os
import logging

from google import genai

if not os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_GENAI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_GENAI_API_KEY"]

PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash")

logger = logging.getLogger(__name__)


def get_genai_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. The backend will use fallback reasoning.")
        raise RuntimeError("GEMINI_API_KEY is not set.")
    logger.info("Gemini client initialized. Primary model: %s | fallback chain: %s", PRIMARY_MODEL, ", ".join(FALLBACK_MODELS))
    return genai.Client(api_key=api_key)
