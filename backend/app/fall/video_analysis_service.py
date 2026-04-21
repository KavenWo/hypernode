"""Gemini-backed analysis for controlled dashboard demo videos."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import HTTPException
from google.genai import types
from pydantic import BaseModel, Field

from app.fall.demo_video_registry import get_demo_video, get_demo_video_path
from app.fall.contracts import DemoVideoAnalysisResponse
from app.fall.adk_video_analysis import analyze_video_with_adk

ADK_VISION_MODEL = os.getenv("ADK_VISION_MODEL", "gemini-2.5-flash")


# Replaced by analyze_video_with_adk


async def analyze_demo_video(video_id: str) -> DemoVideoAnalysisResponse:
    """Run ADK video analysis for a preset local demo clip."""

    video_metadata = get_demo_video(video_id)
    if video_metadata is None:
        raise HTTPException(status_code=404, detail="Demo video not found")

    video_path = get_demo_video_path(video_id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Demo video file is missing")

    try:
        analysis = await analyze_video_with_adk(video_path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Video analysis failed: {exc}") from exc

    return DemoVideoAnalysisResponse(
        video_id=str(video_metadata["id"]),
        video_label=str(video_metadata["label"]),
        video_source=str(video_metadata["source_type"]),
        fall_detected=analysis.fall_detected,
        summary=analysis.summary,
        motion_state="rapid_descent" if analysis.fall_detected else "stumble",
        confidence_score=analysis.confidence if analysis.confidence > 0 else (0.98 if analysis.fall_detected else 0.2),
        analysis_model=ADK_VISION_MODEL,
    )
