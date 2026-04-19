"""Gemini-backed analysis for controlled dashboard demo videos."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import HTTPException
from google.genai import types
from pydantic import BaseModel, Field

from agents.shared.config import get_genai_client
from app.fall.demo_video_registry import get_demo_video, get_demo_video_path
from app.fall.contracts import DemoVideoAnalysisResponse

VISION_ANALYSIS_MODEL = "gemini-2.5-flash"


class _GeminiVideoAnalysis(BaseModel):
    fall_detected: bool = Field(..., description="Whether a fall occurs in the clip.")
    summary: str = Field(..., description="One short sentence describing the observed event.")


def _normalize_motion_state(fall_detected: bool) -> str:
    return "rapid_descent" if fall_detected else "stumble"


def _normalize_confidence_score(fall_detected: bool) -> float:
    return 0.98 if fall_detected else 0.2


def _analyze_video_sync(video_path: Path) -> _GeminiVideoAnalysis:
    client = get_genai_client()
    video_bytes = video_path.read_bytes()
    response = client.models.generate_content(
        model=VISION_ANALYSIS_MODEL,
        contents=[
            types.Part.from_bytes(data=video_bytes, mime_type="video/mp4"),
            (
                "Analyze this safety-monitoring clip. Return JSON only. "
                "Determine whether a person actually falls in the video. "
                "Set fall_detected to true only if a real fall is visible. "
                "If the person falls and ends up down or motionless, mention that in the summary. "
                "If there is no real fall, set fall_detected to false. "
                "Keep summary to one short sentence grounded in the visible video."
            ),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_GeminiVideoAnalysis,
            temperature=0,
        ),
    )
    parsed = response.parsed
    if parsed is None:
        raise RuntimeError("Gemini video analysis returned no structured response.")
    return parsed


async def analyze_demo_video(video_id: str) -> DemoVideoAnalysisResponse:
    """Run Gemini video analysis for a preset local demo clip."""

    video_metadata = get_demo_video(video_id)
    if video_metadata is None:
        raise HTTPException(status_code=404, detail="Demo video not found")

    video_path = get_demo_video_path(video_id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Demo video file is missing")

    try:
        analysis = await asyncio.to_thread(_analyze_video_sync, video_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Video analysis failed: {exc}") from exc

    return DemoVideoAnalysisResponse(
        video_id=str(video_metadata["id"]),
        video_label=str(video_metadata["label"]),
        video_source=str(video_metadata["source_type"]),
        fall_detected=analysis.fall_detected,
        summary=analysis.summary,
        motion_state=_normalize_motion_state(analysis.fall_detected),
        confidence_score=_normalize_confidence_score(analysis.fall_detected),
        analysis_model=VISION_ANALYSIS_MODEL,
    )
