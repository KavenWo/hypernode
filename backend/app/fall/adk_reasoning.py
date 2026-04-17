"""ADK-backed clinical reasoning agent for the fall-response backend.

This keeps the deterministic reasoning policy as the safety rail while moving
the model-driven reasoning step into ADK. The ADK agent returns the shared
``ClinicalAssessment`` schema, and backend policy helpers still normalize and
validate the result.
"""

from __future__ import annotations

import json
import logging
import os
import re

from pydantic import BaseModel, Field

from agents.reasoning.clinical_reasoning_policy import (
    apply_reasoning_defaults,
    render_clinical_reasoning_context,
    run_clinical_reasoning_policy,
)
from agents.reasoning.support_grounding import run_reasoning_support_grounding
from agents.shared.errors import parse_ai_error
from agents.shared.schemas import (
    ClinicalAssessment,
    FallEvent,
    PatientAnswer,
    UserMedicalProfile,
    VisionAssessment,
    VitalAssessment,
)

logger = logging.getLogger(__name__)

ADK_REASONING_MODEL = os.getenv("ADK_REASONING_MODEL", "gemini-2.5-pro")
ADK_REASONING_APP_NAME = "fall-reasoning-adk"


class AdkReasoningDraft(BaseModel):
    severity: str = Field(description="Overall severity: low, medium, or critical.")
    recommended_action: str = Field(
        description="Recommended action: monitor, contact_family, dispatch_pending_confirmation, or emergency_dispatch."
    )
    reasoning_summary: str = Field(description="Short operational explanation of the reasoning result.")
    red_flags: list[str] = Field(default_factory=list)
    protective_signals: list[str] = Field(default_factory=list)
    suspected_risks: list[str] = Field(default_factory=list)
    vulnerability_modifiers: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    hard_emergency_triggered: bool = False
    blocking_uncertainties: list[str] = Field(default_factory=list)
    override_policy: str = ""

REASONING_AGENT_INSTRUCTION = """
You are the Clinical Reasoning Agent for an emergency fall-response workflow.

You must return structured JSON only.

Allowed severity values:
- low
- medium
- critical

Allowed recommended_action values:
- monitor
- contact_family
- dispatch_pending_confirmation
- emergency_dispatch

Allowed confidence band values:
- low
- medium
- high

Rules:
- Follow the provided deterministic policy context carefully.
- Use the grounded medical support as advisory clinical context, not as a source of made-up facts.
- Separate severity choice from action choice.
- Keep reasoning_summary short and operational.
- Do not use fall confidence as a synonym for medical severity.
- Do not invent diagnoses beyond the evidence.
- Preserve uncertainty, missing facts, contradictions, blocking uncertainties, and override_policy when supported.
- Do not return response_plan, reasoning_trace, or confidence values. The backend will supply those safely.
- Return only JSON with these fields:
  severity
  recommended_action
  reasoning_summary
  red_flags
  protective_signals
  suspected_risks
  vulnerability_modifiers
  missing_facts
  contradictions
  uncertainty
  hard_emergency_triggered
  blocking_uncertainties
  override_policy
""".strip()


def _extract_json_block(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("ADK reasoning response was empty.")
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    brace_match = re.search(r"(\{.*\})", stripped, re.DOTALL)
    if brace_match:
        return brace_match.group(1)

    raise ValueError("ADK reasoning response did not contain a JSON object.")


def _normalize_draft_payload(payload: dict) -> dict:
    normalized = dict(payload)
    list_fields = {
        "red_flags",
        "protective_signals",
        "suspected_risks",
        "vulnerability_modifiers",
        "missing_facts",
        "contradictions",
        "uncertainty",
        "blocking_uncertainties",
    }

    for field in list_fields:
        value = normalized.get(field)
        if value is None:
            normalized[field] = []
        elif isinstance(value, str):
            normalized[field] = [value] if value.strip() else []

    override_policy = normalized.get("override_policy")
    if override_policy is None:
        normalized["override_policy"] = ""
    elif isinstance(override_policy, bool):
        normalized["override_policy"] = "true" if override_policy else ""

    return normalized


def _reasoning_prompt(
    *,
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    vision_assessment: VisionAssessment,
    vital_assessment: VitalAssessment | None,
    grounded_medical_guidance: list[str] | None,
    phase3_context: str,
    patient_answers: list[PatientAnswer],
) -> str:
    vitals_context = (
        f"Vital assessment: {vital_assessment.reasoning} Severity hint: {vital_assessment.severity_hint}."
        if vital_assessment
        else "No vital-sign assessment is available yet."
    )
    guidance_context = "\n".join(f"- {item}" for item in (grounded_medical_guidance or [])) or "- No external medical guidance retrieved."
    answer_context = (
        "\n".join(f"- {answer.question_id}: {answer.answer}" for answer in patient_answers)
        or "- No patient answers were collected."
    )

    return f"""
Event details:
- Motion State: {event.motion_state}
- Confidence Score: {event.confidence_score}
- Patient Age: {patient_profile.age}
- Blood Thinners: {patient_profile.blood_thinners}
- Pre-existing Conditions: {", ".join(patient_profile.pre_existing_conditions) or "None listed"}
- Medications: {", ".join(patient_profile.medications) or "None listed"}
- Vision Sentinel: fall_detected={vision_assessment.fall_detected}, severity_hint={vision_assessment.severity_hint}
- Vision Reasoning: {vision_assessment.reasoning}
- {vitals_context}

Patient or bystander answers:
{answer_context}

Grounded medical guidance:
{guidance_context}

Deterministic policy context:
{phase3_context}

Decision rules:
- If rapid_descent or no_movement occurs with confidence above 0.85, bias toward critical severity.
- If both motion evidence and vitals suggest danger, bias toward critical.
- If the patient reports trouble breathing, heavy bleeding, head strike on blood thinners, loss of consciousness, or inability to move safely, bias toward critical severity.
- Elderly patients, blood thinners, or concerning fall red flags should increase caution.
- If explicit life-threatening red flags are present, prefer emergency_dispatch unless a brief confirmation window is clearly safer and still appropriate.
- If explicit life-threatening red flags are present, hard_emergency_triggered should usually be true and blocking_uncertainties should not stop emergency escalation.
- If the case is concerning but not clearly life-threatening, prefer contact_family.
- If the case appears stable with limited evidence of danger, prefer monitor.
- The response_plan should separate escalation, notifications, bystander actions, and follow-up actions.

Return JSON only with the fields listed in the instruction block.
""".strip()


def _fallback_clinical_assessment(*, reasoning_outcome, ai_error: str | None = None) -> ClinicalAssessment:
    return reasoning_outcome.to_clinical_assessment().model_copy(
        update={
            "reasoning_summary": (
                "Fallback assessment used because the ADK reasoning model was unavailable. "
                f"{reasoning_outcome.reasoning_summary}"
            ),
            "ai_server_error": ai_error,
        }
    )


def _build_reasoning_agent():
    from google.adk.agents import llm_agent

    return llm_agent.LlmAgent(
        name="ReasoningAgent",
        model=ADK_REASONING_MODEL,
        description="Assesses clinical severity and recommended action for a fall event using policy-backed reasoning.",
        sub_agents=[],
        instruction=REASONING_AGENT_INSTRUCTION,
        tools=[],
    )


async def _run_agent_prompt(prompt: str) -> str:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    user_id = os.getenv("ADK_TEST_USER_ID", "fall-reasoning-user")
    session_id = f"session-{abs(hash(prompt)) % 10_000_000}"
    session_service = InMemorySessionService()
    runner = Runner(
        agent=_build_reasoning_agent(),
        app_name=ADK_REASONING_APP_NAME,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name=ADK_REASONING_APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )

    final_text_parts: list[str] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        content = getattr(event, "content", None)
        if content and getattr(content, "parts", None) and event.is_final_response():
            for part in content.parts:
                text = getattr(part, "text", None)
                if text:
                    final_text_parts.append(text)

    return "\n".join(final_text_parts).strip()


async def assess_clinical_severity_with_adk(
    *,
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    vision_assessment: VisionAssessment,
    vital_assessment: VitalAssessment | None,
    grounded_medical_guidance: list[str] | None = None,
    patient_answers: list[PatientAnswer] | None = None,
) -> ClinicalAssessment:
    """Run the ADK-backed reasoning path while preserving policy guardrails."""

    answers = patient_answers or []
    reasoning_outcome = run_clinical_reasoning_policy(
        event=event,
        patient_profile=patient_profile,
        vision_assessment=vision_assessment,
        vital_assessment=vital_assessment,
        patient_answers=answers,
    )

    support_guidance = grounded_medical_guidance
    if support_guidance is None:
        support_result = run_reasoning_support_grounding(
            patient_profile=patient_profile,
            patient_answers=answers,
            clinical_assessment=reasoning_outcome.to_clinical_assessment(),
        )
        support_guidance = support_result["snippets"]

    prompt = _reasoning_prompt(
        event=event,
        patient_profile=patient_profile,
        vision_assessment=vision_assessment,
        vital_assessment=vital_assessment,
        grounded_medical_guidance=support_guidance,
        phase3_context=render_clinical_reasoning_context(reasoning_outcome),
        patient_answers=answers,
    )

    try:
        response_text = await _run_agent_prompt(prompt)
        draft = AdkReasoningDraft.model_validate(
            _normalize_draft_payload(json.loads(_extract_json_block(response_text)))
        )
        baseline = reasoning_outcome.to_clinical_assessment()
        parsed = baseline.model_copy(
            update={
                "severity": draft.severity,
                "recommended_action": draft.recommended_action,
                "reasoning_summary": draft.reasoning_summary,
                "red_flags": draft.red_flags,
                "protective_signals": draft.protective_signals,
                "suspected_risks": draft.suspected_risks,
                "vulnerability_modifiers": draft.vulnerability_modifiers,
                "missing_facts": draft.missing_facts,
                "contradictions": draft.contradictions,
                "uncertainty": draft.uncertainty,
                "hard_emergency_triggered": draft.hard_emergency_triggered,
                "blocking_uncertainties": draft.blocking_uncertainties,
                "override_policy": draft.override_policy,
            }
        )
        assessment = apply_reasoning_defaults(assessment=parsed, outcome=reasoning_outcome)
        logger.info(
            "[AdkReasoning] Agent succeeded | user=%s severity=%s action=%s",
            event.user_id,
            assessment.severity,
            assessment.recommended_action,
        )
        return assessment
    except Exception as exc:
        logger.exception(
            "[AdkReasoning] Agent failed; falling back to deterministic reasoning | user=%s",
            event.user_id,
        )
        return _fallback_clinical_assessment(
            reasoning_outcome=reasoning_outcome,
            ai_error=parse_ai_error(exc),
        )
