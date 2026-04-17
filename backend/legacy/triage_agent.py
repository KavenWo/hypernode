"""Standalone triage agent compatibility module.

This file keeps the original `run_triage_agent` entrypoint available for older
prototype code while using conservative, deterministic fallbacks when no live
LLM key is configured.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from enum import Enum
from typing import Any

import httpx  # type: ignore
from pydantic import BaseModel, Field  # type: ignore


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-pro:generateContent"
)
MAX_TOKENS = 1024


class SeverityLevel(str, Enum):
    NORMAL = "normal"
    YELLOW = "yellow"
    AMBER = "amber"
    RED = "red"


class SuspectedCondition(BaseModel):
    """What the AI agent thinks might be happening."""

    condition: str
    confidence: str = "low"
    reasoning: str = ""


class SelfHelpAction(BaseModel):
    """Immediate action the patient or bystander should take."""

    action: str
    priority: int = 1
    rationale: str = ""


class HospitalContext(BaseModel):
    """What the emergency team needs to know for this case."""

    suggested_department: str = "General ED"
    key_alerts: list[str] = Field(default_factory=list)
    recommended_prep: list[str] = Field(default_factory=lambda: ["Standard emergency intake"])


class TriageDecision(BaseModel):
    """Complete output of the agentic triage engine."""

    final_severity: SeverityLevel
    escalated: bool
    escalation_reason: str | None = None
    suspected_conditions: list[SuspectedCondition] = Field(default_factory=list)
    self_help_actions: list[SelfHelpAction] = Field(default_factory=list)
    hospital_context: HospitalContext = Field(default_factory=HospitalContext)
    contact_priority: list[str] = Field(default_factory=lambda: ["999"])
    summary: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PatientProfile(BaseModel):
    patient_id: str
    name: str = ""
    age: int | None = None
    sex: str | None = None
    blood_type: str | None = None
    chronic_conditions: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    emergency_contacts: list[dict] = Field(default_factory=list)
    notes: str = ""


SYSTEM_PROMPT = """You are an emergency medical triage decision engine.
Return only JSON with final_severity, escalated, escalation_reason,
suspected_conditions, self_help_actions, hospital_context, contact_priority,
and summary. Err on the side of patient safety."""


def _severity_rank(severity: SeverityLevel) -> int:
    return {
        SeverityLevel.NORMAL: 0,
        SeverityLevel.YELLOW: 1,
        SeverityLevel.AMBER: 2,
        SeverityLevel.RED: 3,
    }[severity]


def _coerce_severity(value: Any, default: SeverityLevel = SeverityLevel.YELLOW) -> SeverityLevel:
    try:
        return SeverityLevel(str(value).lower())
    except ValueError:
        return default


def _build_user_prompt(
    vitals: dict,
    profile: PatientProfile,
    recent_history: list[dict],
    rule_severity: SeverityLevel,
) -> str:
    trend_lines = []
    for reading in recent_history[-10:]:
        timestamp = reading.get("timestamp", "?")
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        trend_lines.append(
            json.dumps(
                {
                    "timestamp": timestamp,
                    "heart_rate": reading.get("heart_rate"),
                    "spo2": reading.get("spo2"),
                    "systolic_bp": reading.get("systolic_bp"),
                    "body_temp": reading.get("body_temp"),
                },
                default=str,
            )
        )

    return json.dumps(
        {
            "current_vitals": vitals,
            "rule_based_severity": rule_severity.value,
            "patient_profile": profile.model_dump(),
            "recent_history": trend_lines,
        },
        default=str,
    )


async def _call_llm(system: str, user_msg: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system}\n\n{user_msg}"}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": MAX_TOKENS,
        },
    }
    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()
        payload = response.json()

    candidates = payload.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "\n".join(part.get("text", "") for part in parts).strip()


def _parse_decision(raw: str) -> TriageDecision:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        data["final_severity"] = _coerce_severity(data.get("final_severity")).value
        return TriageDecision.model_validate(data)
    except Exception as exc:
        return _fallback_decision(f"LLM output could not be parsed: {exc}")


def _fallback_decision(reason: str, rule_severity: SeverityLevel = SeverityLevel.AMBER) -> TriageDecision:
    final_severity = SeverityLevel.RED if rule_severity in {SeverityLevel.AMBER, SeverityLevel.RED} else rule_severity
    return TriageDecision(
        final_severity=final_severity,
        escalated=_severity_rank(final_severity) > _severity_rank(rule_severity),
        escalation_reason=f"Fallback triage used: {reason}",
        suspected_conditions=[
            SuspectedCondition(
                condition="Potential acute deterioration",
                confidence="medium",
                reasoning="Rule-based vitals require caution while live AI reasoning is unavailable.",
            )
        ],
        self_help_actions=[
            SelfHelpAction(
                action="Stay still, keep airway clear, and wait for help",
                priority=1,
                rationale="Reduces fall and breathing risk while responders are contacted.",
            )
        ],
        hospital_context=HospitalContext(
            suggested_department="General ED",
            key_alerts=["AI fallback used", f"Rule severity: {rule_severity.value}"],
            recommended_prep=["Manual clinical assessment on arrival"],
        ),
        contact_priority=["999", "next_of_kin"],
        summary=f"Fallback triage result: {final_severity.value}",
    )


async def run_triage_agent(
    vitals: dict,
    patient_profile: PatientProfile | dict,
    recent_history: list[dict],
    rule_severity: SeverityLevel,
) -> TriageDecision:
    """Run contextual triage and return a structured decision."""
    profile = (
        patient_profile
        if isinstance(patient_profile, PatientProfile)
        else PatientProfile.model_validate(patient_profile)
    )

    try:
        raw_response = await _call_llm(
            SYSTEM_PROMPT,
            _build_user_prompt(vitals, profile, recent_history, rule_severity),
        )
        decision = _parse_decision(raw_response)
    except Exception as exc:
        decision = _fallback_decision(str(exc), rule_severity)

    if rule_severity == SeverityLevel.RED and decision.final_severity != SeverityLevel.RED:
        decision.final_severity = SeverityLevel.RED
        decision.escalated = True
        decision.escalation_reason = "Rule-based RED severity cannot be downgraded."

    return decision
