"""
triage_agent.py — Agentic AI Triage Engine
Golden Hour AI Platform | Backend
 
Two-stage emergency decision system:
  Stage 1 (in vitals.py): Rule-based threshold gate — instant, deterministic
  Stage 2 (this module):  LLM contextual triage — reasons over patient
                          history, trends, and medical context
 
The agent doesn't just classify — it decides:
  • Whether to escalate or hold
  • What the suspected condition is
  • What self-help steps the patient should take NOW
  • What info the hospital needs for THIS specific case
  • Which contacts to prioritise
 
Usage:
    from ai.triage_agent import run_triage_agent
 
    decision = await run_triage_agent(
        vitals=current_vitals,
        patient_profile=profile,
        recent_history=last_20_readings,
        rule_severity=SeverityLevel.AMBER,
    )
"""

import os
import json
import httpx # type: ignore
from datetime import datetime
from pydantic import BaseModel, Field # type: ignore
from typing import Optional
from enum import Enum

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = str("https://generativelanguage.googleapis.com/v1beta2/models/gemini-1.5-pro:generateContent")
MODEL = "gemini-3.1-pro"
MAX_TOKENS = 1024

# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class SeverityLevel(str, Enum):
    NORMAL = "normal"
    YELLOW = "yellow"
    AMBER = "amber"

class SuspectedCondition(str, Enum):
    """What the AI agent thinks might be happening."""
    condition: str      # e.g. "Acute myocardial infarction"
    confidence: str     # e.g. "high", "medium", "low"
    reasoning: str      # e.g. "Based on the combination of chest pain, elevated heart rate, and ST elevation on ECG, this pattern is highly indicative of an acute myocardial infarction."

class SelfHelpAction(BaseModel):
    """Immediate action the patient/bystander shoudl take."""
    action: str         # e.g. "Call emergency services immediately"
    priority: str       # e.g. "Given the severity of the symptoms and the high suspicion for a life-threatening condition, it is critical to seek emergency medical care without delay."
    rationale: str      # e.g. "The patient's symptoms and vital signs suggest a potentially life-threatening condition that requires urgent medical attention. Delaying care could lead to worsening of the condition and increase the risk of complications or death."

class HospitalContext(BaseModel):
    """What the ER team needs to know for THIS case."""
    suggested_department: str               # e.g. "Cardiology", "Trauma", "General ED"
    key_alerts: list[str]                   # e.g. ["Patient on warfarin", "Penicillin allergy"]
    recommended_prep: list[str]             # e.g. ["ECG on arrival", "Prepare cath lab"]


class TriageDecision(BaseModel):
    """Complete output of the agentic triage engine."""
    final_severity: SeverityLevel
    escalated: bool                         # did AI change the severity from rule-based?
    escalation_reason: Optional[str] = None
    suspected_conditions: list[SuspectedCondition]
    self_help_actions: list[SelfHelpAction]
    hospital_context: HospitalContext
    contact_priority: list[str]             # ordered list: ["999", "next_of_kin", "family_doctor"]
    summary: str                            # one-line for logs/dashboard
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ──────────────────────────────────────────────
# Patient profile type (mirrors profile.py)
# ──────────────────────────────────────────────

class PatientProfile(BaseModel):
    patient_id: str
    name: str = ""
    age: Optional[int] = None
    sex: Optional[str] = None
    blood_type: Optional[str] = None
    chronic_conditions: list[str] = []      # e.g. ["COPD", "Type 2 Diabetes"]
    current_medications: list[str] = []     # e.g. ["Metformin 500mg", "Warfarin 5mg"]
    allergies: list[str] = []               # e.g. ["Penicillin", "Latex"]
    emergency_contacts: list[dict] = []     # [{"name": "...", "phone": "...", "relation": "..."}]
    notes: str = ""

# ──────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an emergency medical triage AI agent deployed in Malaysia as part of \
a "Golden Hour" rapid-response system. Your job is to assess a patient's \
vital signs in context and make autonomous decisions about emergency response.

You are NOT a chatbot. You are a decision engine. Your output must be \
structured JSON that the system acts on immediately.

CRITICAL RULES:
1. You CANNOT diagnose — you assess SUSPECTED conditions with confidence levels.
2. Err on the side of caution. A false alarm is better than a missed emergency.
3. Consider the patient's medical history, medications, and chronic conditions.
4. Factor in vital sign TRENDS, not just the current snapshot.
5. Account for Malaysian context: 999 is the emergency number, \
   hospitals may vary in capability.
6. Self-help actions must be safe for a layperson to perform.
7. Never recommend stopping prescribed medications.

OUTPUT FORMAT — respond with ONLY this JSON, no markdown, no preamble:
{
    "final_severity": "normal|yellow|amber|red",
    "escalated": true/false,
    "escalation_reason": "string or null",
    "suspected_conditions": [
        {"condition": "...", "confidence": "high|moderate|low", "reasoning": "..."}
    ],
    "self_help_actions": [
        {"action": "...", "priority": 1, "rationale": "..."}
    ],
    "hospital_context": {
        "suggested_department": "...",
        "key_alerts": ["..."],
        "recommended_prep": ["..."]
    },
    "contact_priority": ["999", "next_of_kin", ...],
    "summary": "One-line summary of the situation"
}
"""

def _build_user_prompt(
    vitals: dict,
    profile: PatientProfile,
    recent_history: list[dict],
    rule_severity: SeverityLevel,
) -> str:
    """Construct the contextual prompt for the LLM."""

    # Format recent vitals trend
    trend_lines = []
    for r in recent_history[-10:]:  # last 10 readings
        ts = r.get("timestamp", "?")
        if isinstance(ts, datetime):
            ts = ts.strftime("%H:%M:%S")
        parts = []
        if r.get("heart_rate") is not None:
            parts.append(f"HR={r['heart_rate']}")
        if r.get("spo2") is not None:
            parts.append(f"SpO₂={r['spo2']}")
        if r.get("systolic_bp") is not None:
            parts.append(f"SBP={r['systolic_bp']}")
        if r.get("body_temp") is not None:
            parts.append(f"Temp={r['body_temp']}")
        if parts:
            trend_lines.append(f"  [{ts}] {', '.join(parts)}")

    trend_str = "\n".join(trend_lines) if trend_lines else "  No prior readings available."

    return f"""\
CURRENT VITALS (just received):
  Heart rate:    {vitals.get('heart_rate', 'N/A')} bpm
  SpO₂:         {vitals.get('spo2', 'N/A')}%
  Systolic BP:   {vitals.get('systolic_bp', 'N/A')} mmHg
  Diastolic BP:  {vitals.get('diastolic_bp', 'N/A')} mmHg
  Body temp:     {vitals.get('body_temp', 'N/A')}°C
  Time:          {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

RULE-BASED ASSESSMENT: {rule_severity.value}
(Your job is to confirm, escalate, or de-escalate this based on context below.)

PATIENT PROFILE:
  Name:          {profile.name}
  Age:           {profile.age or 'Unknown'}
  Sex:           {profile.sex or 'Unknown'}
  Blood type:    {profile.blood_type or 'Unknown'}
  Conditions:    {', '.join(profile.chronic_conditions) or 'None known'}
  Medications:   {', '.join(profile.current_medications) or 'None known'}
  Allergies:     {', '.join(profile.allergies) or 'None known'}
  Notes:         {profile.notes or 'None'}

RECENT VITALS TREND (oldest → newest):
{trend_str}

Based on ALL of the above, provide your triage decision as JSON.
"""


# ──────────────────────────────────────────────
# LLM API call
# ──────────────────────────────────────────────

async def _call_llm(system: str, user_msg: str) -> str:
    """Call Anthropic Messages API and return the text response."""
    headers = {
        "x-api-key": GEMINI_API_KEY,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    body = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}],
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GEMINI_API_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    # Extract text from content blocks
    text_parts = [
        block["text"]
        for block in data.get("content", [])
        if block.get("type") == "text"
    ]
    return "\n".join(text_parts)


# ──────────────────────────────────────────────
# Parse + validate LLM response
# ──────────────────────────────────────────────

def _parse_decision(raw: str) -> TriageDecision:
    """Parse LLM JSON output into a validated TriageDecision."""
    # Strip markdown fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Fallback: if LLM output is malformed, return a safe escalation
        return _fallback_decision(f"LLM output parse error: {e}")

    try:
        return TriageDecision(
            final_severity=SeverityLevel(data["final_severity"]),
            escalated=data.get("escalated", False),
            escalation_reason=data.get("escalation_reason"),
            suspected_conditions=[
                SuspectedCondition(**c) for c in data.get("suspected_conditions", [])
            ],
            self_help_actions=[
                SelfHelpAction(**a) for a in data.get("self_help_actions", [])
            ],
            hospital_context=HospitalContext(**data.get("hospital_context", {
                "suggested_department": "General ED",
                "key_alerts": [],
                "recommended_prep": [],
            })),
            contact_priority=data.get("contact_priority", ["999"]),
            summary=data.get("summary", "AI triage completed"),
        )
    except Exception as e:
        return _fallback_decision(f"Validation error: {e}")


def _fallback_decision(reason: str) -> TriageDecision:
    """
    Safe fallback if AI fails — escalate to RED.
    A missed emergency is worse than a false alarm.
    """
    return TriageDecision(
        final_severity=SeverityLevel.RED,
        escalated=True,
        escalation_reason=f"AI fallback triggered: {reason}. Escalating to RED for safety.",
        suspected_conditions=[
            SuspectedCondition(
                condition="Unable to assess",
                confidence="low",
                reasoning="AI triage engine encountered an error. Defaulting to maximum severity.",
            )
        ],
        self_help_actions=[
            SelfHelpAction(
                action="Stay calm and do not move",
                priority=1,
                rationale="Default safety action while emergency services are contacted.",
            )
        ],
        hospital_context=HospitalContext(
            suggested_department="General ED",
            key_alerts=["AI triage failed — manual assessment required"],
            recommended_prep=["Standard emergency intake"],
        ),
        contact_priority=["999", "next_of_kin"],
        summary=f"AI FALLBACK: {reason}",
    )


# ──────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────

async def run_triage_agent(
    vitals: dict,
    patient_profile: PatientProfile,
    recent_history: list[dict],
    rule_severity: SeverityLevel,
) -> TriageDecision:
    """
    Run the agentic AI triage engine.

    Called by vitals.py when rule-based severity is AMBER
    (ambiguous cases needing contextual reasoning).

    Can also be called for YELLOW cases if compound flags are present,
    or forced for any severity via an override flag.

    Args:
        vitals:           Current reading as dict
        patient_profile:  Patient's medical profile from Firebase
        recent_history:   Last N readings from rolling buffer
        rule_severity:    What the threshold engine decided

    Returns:
        TriageDecision with final severity + action plan
    """
    # Build contextual prompt
    user_prompt = _build_user_prompt(vitals, patient_profile, recent_history, rule_severity)

    try:
        # Call the LLM
        raw_response = await _call_llm(SYSTEM_PROMPT, user_prompt)

        # Parse into structured decision
        decision = _parse_decision(raw_response)

        # Safety net: AI should never DOWNGRADE a RED from rule-based
        if rule_severity == SeverityLevel.RED and _severity_rank(decision.final_severity) < _severity_rank(SeverityLevel.RED):
            decision.final_severity = SeverityLevel.RED
            decision.escalation_reason = (
                "AI attempted to downgrade from RED — overridden for safety. "
                f"AI reasoning: {decision.escalation_reason or 'none'}"
            )

        return decision

    except httpx.TimeoutException:
        return _fallback_decision("LLM API timeout — network latency exceeded 15s")

    except httpx.HTTPStatusError as e:
        return _fallback_decision(f"LLM API error: HTTP {e.response.status_code}")

    except Exception as e:
        return _fallback_decision(f"Unexpected error: {str(e)}")


def _severity_rank(s: SeverityLevel) -> int:
    """Numeric rank for severity comparison."""
    return {
        SeverityLevel.NORMAL: 0,
        SeverityLevel.YELLOW: 1,
        SeverityLevel.AMBER: 2,
        SeverityLevel.RED: 3,
    }[s]