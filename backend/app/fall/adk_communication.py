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
from agents.shared.errors import parse_ai_error
from agents.shared.schemas import (
    CommunicationAgentAnalysis,
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
- execution_signal
- guidance_intent
- next_focus
- immediate_step
- quick_replies
""".strip()


def _fallback_open_question(previous_analysis: CommunicationAgentAnalysis | None) -> str | None:
    if previous_analysis and previous_analysis.open_question_key:
        return previous_analysis.open_question_key
    return "general_check"


def _fallback_role_from_message(latest_message: str) -> tuple[str, bool, bool]:
    normalized = " ".join((latest_message or "").strip().lower().split())
    if not normalized:
        return "unknown", False, False
    if any(phrase in normalized for phrase in {"i am here", "i'm here", "helping", "with him", "with her", "nearby"}):
        return "bystander", False, True
    if any(phrase in normalized for phrase in {"he is", "she is", "they are", "patient is"}):
        return "bystander", False, True
    if normalized in {"no response", "not responding"}:
        return "no_response", False, False
    return "patient", True, False


def _fallback_fact_extraction(latest_message: str) -> list[str]:
    normalized = " ".join((latest_message or "").strip().lower().split())
    extracted: list[str] = []
    if any(phrase in normalized for phrase in {"bleeding", "blood"}):
        extracted.append("severe_bleeding")
    if any(phrase in normalized for phrase in {"pain", "hurts", "hurt"}):
        extracted.append("pain_present")
    if any(phrase in normalized for phrase in {"can't move", "cannot move", "can't stand", "cannot stand", "unable to move"}):
        extracted.append("cannot_stand")
    if any(phrase in normalized for phrase in {"not breathing", "breathing strangely", "breathing abnormal"}):
        extracted.append("abnormal_breathing")
    if any(phrase in normalized for phrase in {"unconscious", "not conscious"}):
        extracted.append("unresponsive")
    if any(phrase in normalized for phrase in {"awake", "conscious"}):
        extracted.append("responsive")
    return extracted


def _fallback_prompt_for_question(open_question_key: str | None) -> tuple[str, str, list[str]]:
    prompt_map = {
        "general_check": ("Are you okay?", "opening_check", ["Yes", "No", "Need help", "I can answer"]),
        "consciousness": ("I need to confirm: is the patient conscious?", "consciousness", ["Yes", "No", "Not sure", "Can't tell"]),
        "breathing": ("I need to confirm: is the patient breathing normally?", "breathing", ["Yes", "No", "Breathing strangely", "Not sure"]),
        "mobility": ("I need to confirm: is the patient unable to move?", "mobility", ["Yes", "No", "Not sure"]),
        "bleeding": ("I need to confirm: is the patient bleeding?", "bleeding", ["Yes", "No", "Not sure"]),
        "pain": ("I need to confirm: is the patient in pain?", "pain", ["Yes", "No", "Not sure"]),
    }
    return prompt_map.get(open_question_key or "general_check", prompt_map["general_check"])


def _deterministic_fallback_analysis(
    *,
    latest_message: str,
    previous_analysis: CommunicationAgentAnalysis | None = None,
    ai_error: str | None = None,
) -> CommunicationAgentAnalysis:
    if not (latest_message or "").strip():
        return CommunicationAgentAnalysis(
            followup_text="Are you okay?",
            responder_role="unknown",
            communication_target="patient",
            patient_responded=False,
            bystander_present=False,
            bystander_can_help=False,
            extracted_facts=[],
            resolved_fact_keys=[],
            open_question_key="general_check",
            open_question_resolved=False,
            conversation_state_summary="Controlled opening check is active.",
            reasoning_needed=False,
            reasoning_reason="The controlled flow starts with the opening check.",
            should_surface_execution_update=False,
            execution_signal="none",
            guidance_intent="question",
            next_focus="opening_check",
            immediate_step=None,
            quick_replies=["Yes", "No", "Need help", "I can answer"],
            ai_server_error=ai_error,
        )

    responder_role, patient_responded, bystander_present = _fallback_role_from_message(latest_message)
    extracted_facts = _fallback_fact_extraction(latest_message)
    previous_open_question = _fallback_open_question(previous_analysis)
    followup_text, next_focus, quick_replies = _fallback_prompt_for_question(previous_open_question)

    return CommunicationAgentAnalysis(
        followup_text=followup_text,
        responder_role=responder_role,
        communication_target="bystander" if bystander_present else ("patient" if patient_responded else "unknown"),
        patient_responded=patient_responded,
        bystander_present=bystander_present,
        bystander_can_help=bystander_present,
        extracted_facts=extracted_facts,
        resolved_fact_keys=[],
        open_question_key=previous_open_question,
        open_question_resolved=bool(previous_open_question and latest_message.strip()),
        conversation_state_summary="Deterministic fallback kept the communication in the controlled flow.",
        reasoning_needed=False,
        reasoning_reason="Reasoning stays controller-gated in the fallback path.",
        should_surface_execution_update=False,
        execution_signal="none",
        guidance_intent="question",
        next_focus=next_focus,
        immediate_step=None,
        quick_replies=quick_replies,
        ai_server_error=ai_error,
    )


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


def _summarize_active_guidance(assessment: FallAssessment | None, previous_analysis: CommunicationAgentAnalysis | None) -> str:
    if assessment is None:
        return "No active grounded guidance."
    protocol = assessment.protocol_guidance
    if protocol and protocol.ready_for_communication and protocol.steps:
        current_hint = previous_analysis.immediate_step if previous_analysis and previous_analysis.immediate_step else protocol.steps[0]
        return (
            f"protocol={protocol.protocol_key or 'none'}; "
            f"authoritative_step={current_hint}; "
            f"available_steps={', '.join(protocol.steps[:4])}"
        )
    if assessment.guidance.steps:
        current_hint = previous_analysis.immediate_step if previous_analysis and previous_analysis.immediate_step else assessment.guidance.steps[0]
        return (
            f"protocol=generic_guidance; "
            f"authoritative_step={current_hint}; "
            f"available_steps={', '.join(assessment.guidance.steps[:4])}"
        )
    return "No active grounded guidance."


def _normalize_analysis_payload(payload: dict) -> dict:
    normalized = dict(payload)

    def _normalize_string_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, dict):
            normalized_items: list[str] = []
            for key, item_value in value.items():
                key_text = str(key).strip()
                if not key_text:
                    continue
                if isinstance(item_value, bool):
                    if item_value:
                        normalized_items.append(key_text)
                elif item_value is None:
                    continue
                elif isinstance(item_value, str):
                    if item_value.strip().lower() not in {"", "false", "no", "none", "0"}:
                        normalized_items.append(key_text)
                else:
                    normalized_items.append(key_text)
            return normalized_items
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []

    def _normalize_bool(value, *, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "1", "on"}:
                return True
            if lowered in {"false", "no", "0", "off", ""}:
                return False
        return default

    list_fields = {
        "extracted_facts",
        "resolved_fact_keys",
        "quick_replies",
    }

    for field in list_fields:
        normalized[field] = _normalize_string_list(normalized.get(field))

    bool_fields = {
        "patient_responded": False,
        "bystander_present": False,
        "bystander_can_help": False,
        "open_question_resolved": False,
        "reasoning_needed": False,
        "should_surface_execution_update": False,
    }
    for field, default in bool_fields.items():
        normalized[field] = _normalize_bool(normalized.get(field), default=default)

    if normalized.get("open_question_key") == "none":
        normalized["open_question_key"] = None

    text_fields = {
        "followup_text": "",
        "responder_role": "unknown",
        "communication_target": "unknown",
        "conversation_state_summary": "",
        "reasoning_reason": "",
        "execution_signal": "none",
        "guidance_intent": "question",
        "next_focus": "general_check",
    }
    for field, default in text_fields.items():
        value = normalized.get(field)
        if value is None:
            normalized[field] = default
        elif isinstance(value, str):
            normalized[field] = value.strip()
        elif isinstance(value, (dict, list)):
            normalized[field] = json.dumps(value)
        else:
            normalized[field] = str(value).strip()

    return normalized


def _resolved_question_key_from_facts(facts: set[str]) -> str | None:
    if {"breathing_normal", "abnormal_breathing", "not_breathing"}.intersection(facts):
        return "breathing"
    if {"pain_present", "mild_pain", "chest_pain"}.intersection(facts):
        return "pain"
    if "head_strike" in facts:
        return "head_injury"
    if "cannot_stand" in facts:
        return "mobility"
    return None


def _state_summary(*, resolved_fact_keys: list[str], open_question_key: str | None, next_focus: str) -> str:
    resolved = ", ".join(resolved_fact_keys) if resolved_fact_keys else "none"
    return f"Resolved: {resolved}. Open question: {open_question_key or 'none'}. Next focus: {next_focus}."


def _finalize_analysis_memory(
    *,
    analysis: CommunicationAgentAnalysis,
    previous_analysis: CommunicationAgentAnalysis | None,
) -> CommunicationAgentAnalysis:
    previous_resolved = set(previous_analysis.resolved_fact_keys if previous_analysis else [])
    extracted_facts = set(analysis.extracted_facts)
    resolved_facts = sorted(
        previous_resolved.union(
            extracted_facts.intersection({"breathing_normal", "mild_pain", "patient_ok", "stable_speaking"})
        )
    )
    previous_open_question = previous_analysis.open_question_key if previous_analysis else None
    resolved_question_key = _resolved_question_key_from_facts(extracted_facts)
    open_question_resolved = bool(previous_open_question and resolved_question_key == previous_open_question)
    open_question_key = analysis.open_question_key

    if not open_question_key:
        open_question_key = None
    if open_question_resolved and open_question_key == previous_open_question:
        open_question_key = None
    if open_question_key == "none":
        open_question_key = None

    conversation_state_summary = (analysis.conversation_state_summary or "").strip()
    if not conversation_state_summary:
        conversation_state_summary = _state_summary(
            resolved_fact_keys=resolved_facts,
            open_question_key=open_question_key,
            next_focus=analysis.next_focus,
        )

    return analysis.model_copy(
        update={
            "resolved_fact_keys": resolved_facts,
            "open_question_key": open_question_key,
            "open_question_resolved": open_question_resolved,
            "conversation_state_summary": conversation_state_summary,
        }
    )


def _safe_pending_dispatch_followup(target: str) -> tuple[str, str | None]:
    if target == "bystander":
        return "I may need to call emergency help. Is the patient awake and breathing normally?", None
    if target == "patient":
        return "I may need emergency help. Are you breathing normally right now?", None
    return "Emergency help may be needed. Tell me if the patient is awake and breathing normally?", None


def _apply_assessment_language_guardrails(
    *,
    analysis: CommunicationAgentAnalysis,
    assessment: FallAssessment | None,
) -> CommunicationAgentAnalysis:
    if assessment is None:
        return analysis

    action = assessment.action.recommended
    text = (analysis.followup_text or "").strip()
    lowered = text.lower()
    claims_dispatch_confirmed = any(
        phrase in lowered
        for phrase in [
            "help is on the way",
            "ambulance is on the way",
            "emergency help is on the way",
            "an ambulance is coming",
        ]
    )

    if action == "dispatch_pending_confirmation" and claims_dispatch_confirmed:
        safe_text, safe_step = _safe_pending_dispatch_followup(analysis.communication_target)
        return analysis.model_copy(
            update={
                "followup_text": safe_text,
                "immediate_step": safe_step or analysis.immediate_step,
                "guidance_intent": "question",
            }
        )

    if action != "emergency_dispatch" and claims_dispatch_confirmed:
        safe_text, safe_step = _safe_pending_dispatch_followup(analysis.communication_target)
        return analysis.model_copy(
            update={
                "followup_text": safe_text,
                "immediate_step": safe_step or analysis.immediate_step,
            }
        )

    return analysis


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
    execution_updates: list | None = None,
    acknowledged_reasoning_triggers: set[str] | None = None,
) -> CommunicationAgentAnalysis:
    """Run the ADK-backed communication analysis with heuristic fallback."""

    if not (latest_message or "").strip():
        logger.info(
            "[AdkCommunication] Empty bootstrap turn detected; using deterministic opening prompt."
        )
        return _deterministic_fallback_analysis(
            latest_message="",
            previous_analysis=previous_analysis,
            ai_error=None,
        )

    event_summary, vitals_summary = _summarize_event(event, vitals)
    assessment_summary = _summarize_assessment(previous_assessment)
    if pending_reasoning_context:
        assessment_summary += f"\n[Background reasoning update]: {pending_reasoning_context}"

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
        active_guidance_summary=_summarize_active_guidance(previous_assessment, previous_analysis),
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
            "[AdkCommunication] Agent failed; falling back to deterministic controlled communication | user=%s",
            event.user_id,
        )
        fallback = _deterministic_fallback_analysis(
            latest_message=latest_message,
            previous_analysis=previous_analysis,
            ai_error=parse_ai_error(exc),
        )
        return _finalize_analysis_memory(
            analysis=fallback,
            previous_analysis=previous_analysis,
        )
