"""ADK-backed video analysis agent for the fall-response backend.

This migrates the legacy Gemini vision analysis to the ADK framework, allowing
multimodal video assessment using an ADK Runner.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ADK_VISION_MODEL = os.getenv("ADK_VISION_MODEL", "gemini-2.5-flash")
ADK_VISION_APP_NAME = "fall-vision-adk"

class AdkVideoAnalysis(BaseModel):
    """Structured output for the vision-based fall detection agent."""
    fall_detected: bool = Field(description="True if a definitive human fall was observed.")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0.")
    summary: str = Field(description="Short clinical summary of the observed motion.")

VIDEO_ANALYSIS_INSTRUCTION = """
You are a Clinical Vision Assistant specializing in emergency fall detection.

Return structured JSON only.

Your job is to analyze the provided video clip and determine if a human fall has occurred.
Focus on:
1. Posture: Is the subject upright, leaning, or on the floor?
2. Movement: Was there a sudden loss of balance or rapid downward acceleration?
3. Final State: Is the subject remaining on the floor after the event?

Return JSON with these fields:
- fall_detected (boolean)
- confidence (float, 0.0 to 1.0)
- summary (string, max 20 words)
""".strip()

def _extract_json_block(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("ADK vision response was empty.")
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)
    brace_match = re.search(r"(\{.*\})", stripped, re.DOTALL)
    if brace_match:
        return brace_match.group(1)
    raise ValueError("ADK vision response did not contain a JSON object.")

def _build_vision_agent():
    from google.adk.agents import llm_agent

    return llm_agent.LlmAgent(
        name="VisionAgent",
        model=ADK_VISION_MODEL,
        description="Analyzes video clips for human fall detection.",
        instruction=VIDEO_ANALYSIS_INSTRUCTION,
    )

async def _run_video_agent_prompt(video_bytes: bytes) -> str:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    user_id = "fall-vision-system"
    session_id = f"vision-{abs(hash(video_bytes)) % 10_000_000}"
    session_service = InMemorySessionService()
    runner = Runner(
        agent=_build_vision_agent(),
        app_name=ADK_VISION_APP_NAME,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name=ADK_VISION_APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )

    # Construct multimodal parts
    video_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
    text_part = types.Part(text="Analyze this clip for potential falls.")

    final_text_parts: list[str] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[video_part, text_part]),
    ):
        content = getattr(event, "content", None)
        if content and getattr(content, "parts", None) and event.is_final_response():
            for part in content.parts:
                text = getattr(part, "text", None)
                if text:
                    final_text_parts.append(text)

    return "\n".join(final_text_parts).strip()

async def analyze_video_with_adk(video_path: Path) -> AdkVideoAnalysis:
    """Analyze a video clip using the ADK-backed Vision Agent."""
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    logger.info("[AdkVision] Starting video analysis for: %s", video_path.name)
    video_bytes = video_path.read_bytes()

    try:
        response_text = await _run_video_agent_prompt(video_bytes)
        json_text = _extract_json_block(response_text)
        payload = json.loads(json_text)
        
        analysis = AdkVideoAnalysis.model_validate(payload)
        
        logger.info(
            "[AdkVision] Analysis complete | fall_detected=%s confidence=%.2f",
            analysis.fall_detected,
            analysis.confidence,
        )
        return analysis
    except Exception as exc:
        logger.exception("[AdkVision] Agent failed during video analysis")
        # Deterministic fallback if the AI fails
        return AdkVideoAnalysis(
            fall_detected=False,
            confidence=0.0,
            summary=f"Analysis failed: {str(exc)[:50]}",
        )
