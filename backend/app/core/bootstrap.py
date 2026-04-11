"""Application bootstrap helpers.

This keeps environment loading and logging setup out of ``app.main`` so the
entrypoint stays focused on route registration.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]


def configure_runtime() -> None:
    """Load local environment values and apply the shared log format."""
    load_dotenv(BACKEND_DIR / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
