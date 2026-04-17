"""ADK-backed communication agent for the fall-response backend.

This keeps the existing session controller in charge of transcript ownership,
execution-priority messaging, and safety guardrails while moving the turn-level
communication analysis into ADK.
"""

from __future__ import annotations

import json
import logging
import os
import re

from agents.communication.prompts import build_communication_analysis_prompt
from agents.communication.session_agent import (
    _finalize_analysis_memory,
    _heuristic_analysis,
)
from agents.shared.errors import parse_ai_error
from agents.shared.schemas import (
    CommunicationAgentAnalysis,
    ExecutionPlan,
    FallAssessment,
)
from app.fall.action_runtime_service import build_visible_execution_state_summary

logger = logging.getLogger(__name__)

ADK_COMMUNICATION_MODEL = os.getenv("ADK_COMMUNICATION_MODEL", "gemini-2.5-flash")
ADK_COMMUNICATION_APP_NAME = "fall-communication-adk"

COMMUNICATION_AGENT_INSTRUCTION = """
You are the Communication Agent for an emergency fall-response workflow.

Return structured JSON only.

Your job is to interpret the latest human turn and produce the next short,
calm, human-facing follow-up.

Important communication rules:
- Be brief, calm, and natural.
- Usually keep followup_text under 18 words.
- Usually keep immediate_step under 10 words.
- Ask only one short thing at a time.
- Do not repeat a question that was already answered unless the situation changed.
- Treat the reasoning snapshot as hidden context, not a script.
- Only mark reasoning_needed=true when the latest turn adds a genuinely new
  risk-changing fact, contradiction, responder change, timeout, or another
  materially new escalation reason.
- Never say help is already on the way unless the reasoning state confirms
  emergency_dispatch.
- If the reasoning state is dispatch_pending_confirmation, speak as pending or
  preparing, not completed.

Allowed responder_role values:
- patient
- bystander
- unknown
- no_response

Allowed communication_target values:
- patient
- bystander
- unknown
- no_response

Allowed open_question_key values:
- none
- breathing
- pain
- bleeding
- consciousness
- head_injury
- mobility
- general_check

Return JSON with these fields:
- followup_text
- responder_role
- communication_target
- patient_responded
- bystander_present
- bystander_can_help
- extracted_facts
- resolved_fact_keys
- open_question_key
- open_question_resolved
- conversation_state_summary
- reasoning_needed
- reasoning_reason
- should_surface_execution_update
- guidance_intent
- next_focus
- immediate_step
- quick_replies
""".strip()


def _extract_json_block(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("ADK communication response was empty.")
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    brace_match = re.search(r"(\{.*\})", stripped, re.DOTALL)
    if brace_match:
        return brace_match.group(1)

    raise ValueError("ADK communication response did not contain a JSON object.")


def _summarize_previous_analysis(analysis: CommunicationAgentAnalysis | None) -> str:
    if analysis is None:
        return "No prior communication state."
    return (
        f"resolved={', '.join(analysis.resolved_fact_keys) or 'none'}; "
        f"open_question={analysis.open_question_key or 'none'}; "
        f"open_question_resolved={analysis.open_question_resolved}; "
        f"next_focus={analysis.next_focus}; "
        f"state={analysis.conversation_state_summary or 'none'}"
    )


def _summarize_acknowledged_reasoning_triggers(triggered_fact_keys: list[str] | set[str] | None) -> str:
    normalized = sorted({item.strip().lower() for item in (triggered_fact_keys or []) if item and item.strip()})
    if not normalized:
        return "none"
    return ", ".join(normalized)


def _summarize_event(event, vitals) -> tuple[str, str]:
    event_summary = (
        f"motion_state={event.motion_state}, fall_detection_confidence={event.confidence_score:.2f}"
    )
    if vitals is None:
        vitals_summary = "No vitals available."
    else:
        vitals_summary = (
            f"heart_rate={vitals.heart_rate}, "
            f"blood_pressure={vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic}, "
            f"spo2={vitals.blood_oxygen_sp02}"
        )
    return event_summary, vitals_summary


def _summarize_patient(profile) -> str:
    return (
        f"age={profile.age}, blood_thinners={profile.blood_thinners}, "
        f"conditions={', '.join(profile.pre_existing_conditions) or 'none'}"
    )


def _summarize_transcript(conversation_history) -> str:
    if not conversation_history:
        return "- No prior conversation."
    return "\n".join(f"- {message.role}: {message.text}" for message in conversation_history[-6:])


def _summarize_assessment(assessment: FallAssessment | None) -> str:
    if assessment is None:
        return "No prior reasoning snapshot."
    parts = [
        f"severity={assessment.clinical_assessment.severity}",
        f"action={assessment.action.recommended}",
        f"reasoning={assessment.clinical_assessment.reasoning_summary}",
    ]
    if assessment.clinical_assessment.missing_facts:
        parts.append(f"missing={', '.join(assessment.clinical_assessment.missing_facts[:2])}")
    if assessment.clinical_assessment.red_flags:
        parts.append(f"red_flags={', '.join(assessment.clinical_assessment.red_flags[:3])}")
    return "; ".join(parts)


def _summarize_reasoning_handoff(assessment: FallAssessment | None) -> str:
    if assessment is None:
        return "No reasoning handoff metadata."
    handoff = assessment.communication_handoff
    bits = ", ".join(handoff.recommended_context_bits[:4]) if handoff.recommended_context_bits else "none"
    return (
        f"mode={handoff.mode}; "
        f"priority={handoff.priority}; "
        f"open_question={handoff.open_question_key or 'none'}; "
        f"surface_execution_update={handoff.should_surface_execution_update}; "
        f"next_focus={handoff.next_focus}; "
        f"context_bits={bits}; "
        f"rationale={handoff.rationale or 'none'}"
    )


def _normalize_analysis_payload(payload: dict) -> dict:
    normalized = dict(payload)
    list_fields = {
        "extracted_facts",
        "resolved_fact_keys",
        "quick_replies",
    }

    for field in list_fields:
        value = normalized.get(field)
        if value is None:
            normalized[field] = []
        elif isinstance(value, str):
            normalized[field] = [value] if value.strip() else []

    if normalized.get("open_question_key") == "none":
        normalized["open_question_key"] = None

    text_fields = {
        "followup_text": "",
        "responder_role": "unknown",
        "communication_target": "unknown",
        "conversation_state_summary": "",
        "reasoning_reason": "",
        "guidance_intent": "question",
        "next_focus": "general_check",
    }
    for field, default in text_fields.items():
        value = normalized.get(field)
        if value is None:
            normalized[field] = default

    return normalized


def _build_communication_agent():
    from google.adk.agents import llm_agent

    return llm_agent.LlmAgent(
        name="CommunicationAgent",
        model=ADK_COMMUNICATION_MODEL,
        description="Interprets the latest responder turn and produces the next calm follow-up.",
        sub_agents=[],
        instruction=COMMUNICATION_AGENT_INSTRUCTION,
        tools=[],
    )


async def _run_agent_prompt(prompt: str) -> str:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    user_id = os.getenv("ADK_TEST_USER_ID", "fall-communication-user")
    session_id = f"session-{abs(hash(prompt)) % 10_000_000}"
    session_service = InMemorySessionService()
    runner = Runner(
        agent=_build_communication_agent(),
        app_name=ADK_COMMUNICATION_APP_NAME,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name=ADK_COMMUNICATION_APP_NAME,
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


async def analyze_communication_turn_with_adk(
    *,
    event,
    vitals,
    patient_profile,
    conversation_history,
    latest_message: str,
    previous_assessment: FallAssessment | None,
    previous_analysis: CommunicationAgentAnalysis | None = None,
    pending_reasoning_context: str = "",
    execution_plan: ExecutionPlan | None = None,
    execution_updates: list | None = None,
    acknowledged_reasoning_triggers: set[str] | None = None,
) -> CommunicationAgentAnalysis:
    """Run the ADK-backed communication analysis with heuristic fallback."""

    event_summary, vitals_summary = _summarize_event(event, vitals)
    assessment_summary = _summarize_assessment(previous_assessment)
    if pending_reasoning_context:
        assessment_summary += f"\n[Background reasoning update]: {pending_reasoning_context}"
    if execution_plan and execution_plan.steps:
        assessment_summary += (
            "\n[Execution plan available]: "
            f"Next step: {execution_plan.steps[0]} "
            "(deliver one step at a time, ask for confirmation before proceeding)"
        )

    prompt = build_communication_analysis_prompt(
        event_summary=event_summary,
        patient_summary=_summarize_patient(patient_profile),
        vitals_summary=vitals_summary,
        transcript_summary=_summarize_transcript(conversation_history),
        latest_message=latest_message,
        previous_assessment_summary=assessment_summary,
        reasoning_handoff_summary=_summarize_reasoning_handoff(previous_assessment),
        previous_communication_summary=_summarize_previous_analysis(previous_analysis),
        acknowledged_reasoning_summary=_summarize_acknowledged_reasoning_triggers(acknowledged_reasoning_triggers),
        execution_state_summary=build_visible_execution_state_summary(execution_updates or []),
    )

    try:
        response_text = await _run_agent_prompt(prompt)
        parsed = CommunicationAgentAnalysis.model_validate(
            _normalize_analysis_payload(json.loads(_extract_json_block(response_text)))
        )
        finalized = _finalize_analysis_memory(
            analysis=parsed,
            previous_analysis=previous_analysis,
        )
        logger.info(
            "[AdkCommunication] Agent succeeded | user=%s role=%s target=%s reasoning_needed=%s",
            event.user_id,
            finalized.responder_role,
            finalized.communication_target,
            finalized.reasoning_needed,
        )
        return finalized
    except Exception as exc:
        logger.exception(
            "[AdkCommunication] Agent failed; falling back to heuristic communication | user=%s",
            event.user_id,
        )
        return _heuristic_analysis(
            latest_message=latest_message,
            previous_assessment=previous_assessment,
            previous_analysis=previous_analysis,
            acknowledged_reasoning_triggers=acknowledged_reasoning_triggers,
            ai_error=parse_ai_error(exc),
        )
