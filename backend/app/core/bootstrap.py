"""Application bootstrap helpers.

This keeps environment loading and logging setup out of ``app.main`` so the
entrypoint stays focused on route registration.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _configure_third_party_logging() -> None:
    """Reduce noise from verbose SDK internals while preserving app logs."""

    quiet_level_name = os.getenv("THIRD_PARTY_LOG_LEVEL", "WARNING").upper()
    quiet_level = getattr(logging, quiet_level_name, logging.WARNING)

    noisy_loggers = [
        "google_adk",
        "google.adk",
        "google.genai",
        "httpx",
        "httpcore",
        "urllib3",
    ]

    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(quiet_level)
        logger.propagate = True


def configure_runtime() -> None:
    """Load local environment values and apply the shared log format."""
    load_dotenv(BACKEND_DIR / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    _configure_third_party_logging()
