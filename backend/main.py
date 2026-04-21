"""Compatibility entrypoint for older scripts that still import ``main``.

The real FastAPI application now lives in ``app.main``. This module simply
re-exports that app so existing smoke tests and local launch commands keep
working while the backend is consolidated.
"""

from app.main import app
