"""Structured communication-AI layer for the Phase 4 session loop."""

from __future__ import annotations

import asyncio
import logging

from google.genai import errors, types

from agents.shared.config import COMMUNICATION_FALLBACK_MODELS
from agents.shared.errors import parse_ai_error
from agents.shared.schemas import CommunicationAgentAnalysis, ExecutionPlan, FallAssessment
from app.fall.action_runtime_service import build_visible_execution_state_summary

from .prompts import build_communication_analysis_prompt, build_communication_render_prompt

logger = logging.getLogger(__name__)

COMMUNICATION_FACT_VOCAB = {
    "abnormal_breathing": ["breathing strangely", "abnormal breathing", "gasping", "struggling to breathe"],
    "breathing_normal": ["breathing normally", "breathing okay", "breathing fine", "can breathe normally"],
    "not_breathing": ["not breathing", "stopped breathing"],
    "severe_bleeding": ["heavy bleeding", "severe bleeding", "bleeding a lot"],
    "head_strike": ["hit my head", "hit their head", "head injury"],
    "cannot_stand": ["cannot stand", "can't stand", "unable to stand"],
    "chest_pain": ["chest pain"],
    "confusion": ["confused", "not making sense"],
    "dizziness": ["dizzy", "lightheaded"],
    "pain_present": ["pain", "hurts", "sore"],
    "mild_pain": ["mild pain", "just sore", "just hurts a bit", "a little pain"],
    "patient_ok": ["i'm okay", "i am okay", "okay now", "i feel okay", "i'm fine", "i am fine"],
    "stable_speaking": ["i can talk", "talking fine", "speaking clearly"],
}


def _normalize_message_key(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())


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
    resolved_facts = sorted(previous_resolved.union(extracted_facts.intersection({"breathing_normal", "mild_pain", "patient_ok", "stable_speaking"})))
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

    conversation_state_summary = analysis.conversation_state_summary.strip()
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


def _heuristic_role(message_text: str) -> tuple[str, bool, bool]:
    text = (message_text or "").strip().lower()
    if not text:
        return "unknown", False, False
    if any(token in text for token in ["he ", "she ", "the patient", "i am with", "i'm with", "my father", "my mother", "my friend"]):
        return "bystander", True, True
    if any(token in text for token in ["i fell", "i am", "i'm", "my head", "i can't", "i cannot"]):
        return "patient", True, False
    return "unknown", True, False


def _extract_facts(message_text: str, role: str) -> list[str]:
    text = (message_text or "").strip().lower()
    facts: list[str] = []
    for fact_key, keywords in COMMUNICATION_FACT_VOCAB.items():
        if any(keyword in text for keyword in keywords):
            facts.append(fact_key)
    if role == "patient":
        facts.append("patient_speaking")
    if role == "bystander":
        facts.extend(["bystander_present", "bystander_speaking", "bystander_can_help"])
    if "alone" in text or "by myself" in text:
        facts.append("alone")
    if "yes" in text or role in {"patient", "bystander"}:
        facts.append("responsive")
    if "not responding" in text or "won't wake" in text:
        facts.append("unresponsive")
    return sorted(set(facts))


def _heuristic_analysis(
    *,
    latest_message: str,
    previous_assessment: FallAssessment | None,
    previous_analysis: CommunicationAgentAnalysis | None = None,
    acknowledged_reasoning_triggers: set[str] | None = None,
) -> CommunicationAgentAnalysis:
    if not latest_message.strip():
        return CommunicationAgentAnalysis(
            followup_text="A fall was detected. Are you okay?",
            responder_role="unknown",
            communication_target="patient",
            patient_responded=False,
            bystander_present=False,
            bystander_can_help=False,
            extracted_facts=[],
            resolved_fact_keys=[],
            open_question_key="general_check",
            open_question_resolved=False,
            conversation_state_summary="Resolved: none. Open question: general_check. Next focus: responsiveness.",
            reasoning_needed=False,
            reasoning_reason="The session just started, so the first step is a patient-first check.",
            should_surface_execution_update=False,
            guidance_intent="patient_check",
            next_focus="responsiveness",
            immediate_step=None,
            quick_replies=["Yes", "No", "Need help", "I can answer"],
        )

    role, patient_responded, bystander_present = _heuristic_role(latest_message)
    facts = _extract_facts(latest_message, role)
    bystander_can_help = "bystander_can_help" in facts
    critical_facts = {"abnormal_breathing", "not_breathing", "severe_bleeding", "head_strike", "unresponsive", "chest_pain"}
    acknowledged = {item.strip().lower() for item in (acknowledged_reasoning_triggers or set()) if item and item.strip()}
    new_critical_facts = critical_facts.intersection(facts).difference(acknowledged)
    reasoning_needed = bool(new_critical_facts)
    previous_open_question = previous_analysis.open_question_key if previous_analysis else None
    resolved_question_key = _resolved_question_key_from_facts(set(facts))
    open_question_resolved = bool(previous_open_question and resolved_question_key == previous_open_question)
    action = previous_assessment.action.recommended if previous_assessment is not None else None

    if role == "bystander":
        if previous_open_question == "breathing" and open_question_resolved:
            followup = "Okay. Tell me if anything else changes."
            next_focus = "general_check"
            open_question_key = None
        else:
            followup = "Okay. Is the patient awake and breathing normally?"
            next_focus = "breathing"
            open_question_key = "breathing"
        target = "bystander"
        quick_replies = ["Awake", "Breathing normally", "Breathing strangely", "Not responding"]
    elif role == "patient":
        if previous_open_question == "breathing" and open_question_resolved:
            if reasoning_needed:
                followup = "Okay. Stay still for me."
            else:
                followup = "Okay. Stay calm and tell me what hurts most."
            next_focus = "pain"
            open_question_key = "pain"
        elif "head_strike" in facts:
            followup = "Okay. Stay still for me. Did you black out at all?"
            next_focus = "head_injury"
            open_question_key = "head_injury"
        elif "abnormal_breathing" in facts or "not_breathing" in facts:
            followup = "Okay. Stay still. Tell me if breathing gets worse."
            next_focus = "breathing"
            open_question_key = None
        else:
            followup = "Okay. Can you breathe normally and tell me where it hurts?"
            next_focus = "breathing"
            open_question_key = "breathing"
        target = "patient"
        quick_replies = ["Breathing okay", "Hard to breathe", "Head hurts", "I can't stand"]
    else:
        followup = "A fall was detected. Are you the patient or helping someone?"
        target = "unknown"
        next_focus = "general_check"
        open_question_key = "general_check"
        quick_replies = ["I am the patient", "I am helping", "No response", "Need help now"]

    immediate_step = None
    if "not_breathing" in facts:
        immediate_step = "Check breathing now."
    elif "severe_bleeding" in facts:
        immediate_step = "Apply firm pressure."
    elif previous_assessment is not None and previous_assessment.guidance.steps:
        immediate_step = previous_assessment.guidance.steps[0]

    if action == "monitor" and immediate_step:
        immediate_step = None

    analysis = CommunicationAgentAnalysis(
        followup_text=followup,
        responder_role=role,
        communication_target=target,
        patient_responded=patient_responded and role == "patient",
        bystander_present=bystander_present,
        bystander_can_help=bystander_can_help,
        extracted_facts=facts,
        resolved_fact_keys=[],
        open_question_key=open_question_key,
        open_question_resolved=open_question_resolved,
        conversation_state_summary="",
        reasoning_needed=reasoning_needed,
        reasoning_reason=(
            f"Critical new facts were reported: {', '.join(sorted(new_critical_facts))}."
            if reasoning_needed
            else "No new escalation reason was detected beyond what reasoning already knows."
        ),
        should_surface_execution_update=action in {"contact_family", "dispatch_pending_confirmation", "emergency_dispatch"},
        guidance_intent="instruction" if immediate_step else "question",
        next_focus=next_focus,
        immediate_step=immediate_step,
        quick_replies=quick_replies, ai_server_error=ai_error)
    return _finalize_analysis_memory(analysis=analysis, previous_analysis=previous_analysis)


def _fallback_rendered_followup(
    *,
    analysis: CommunicationAgentAnalysis,
    assessment: FallAssessment,
) -> tuple[str, str | None]:
    action = assessment.action.recommended
    first_step = assessment.guidance.steps[0] if assessment.guidance.steps else analysis.immediate_step
    primary_message = (assessment.guidance.primary_message or "").strip()
    step_text = (first_step or "").strip()

    if action == "contact_family":
        if analysis.communication_target == "patient":
            return "Okay. Stay seated and move slowly. I can notify your family for support.", "Stay seated and move slowly."
        if analysis.communication_target == "bystander":
            return "Okay. Stay with them. I can notify the family while you keep watching them.", "Stay with them."
        return "Okay. Stay in a safe position. I can notify family for support.", "Stay in a safe position."

    if action == "monitor":
        if analysis.communication_target == "patient":
            return "Okay. Stay calm and tell me if pain or breathing gets worse.", None
        if analysis.communication_target == "bystander":
            return "Okay. Tell me if anything gets worse.", None
        return "Okay. Tell me if anything changes.", None

    if analysis.communication_target == "bystander":
        if step_text:
            return f"Okay. {step_text} Tell me what you see next.", step_text
        return "Okay. Stay with them and tell me what happens next.", None

    if analysis.communication_target == "patient":
        if step_text:
            return f"Okay. {step_text} Tell me if anything changes.", step_text
        return "Okay. Stay still and tell me if anything changes.", None

    if primary_message:
        return primary_message, step_text or None
    return "Tell me what happens next.", step_text or None


def _safe_pending_dispatch_followup(target: str) -> tuple[str, str | None]:
    if target == "bystander":
        return "I may need to call emergency help. Is the patient awake and breathing normally?", None
    if target == "patient":
        return "I may need emergency help. Are you breathing normally right now?", None
    return "Emergency help may be needed. Tell me if the patient is awake and breathing normally.", None


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


async def _generate_structured_output(*, client, prompt: str, schema):
    last_error = None
    for model_name in COMMUNICATION_FALLBACK_MODELS:
        for attempt in range(2):
            try:
                return await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
            except errors.APIError as exc:
                last_error = exc
                is_retryable = exc.code in {429, 500, 503}
                is_last_attempt = attempt == 1 and model_name == COMMUNICATION_FALLBACK_MODELS[-1]
                if not is_retryable or is_last_attempt:
                    raise
                await asyncio.sleep(1 + attempt)
    if last_error is not None:
        raise last_error
    raise RuntimeError("No communication-model response was produced.")


async def analyze_communication_turn(
    *,
    client,
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
    if client is None:
        return _heuristic_analysis(latest_message=latest_message, previous_assessment=previous_assessment, previous_analysis=previous_analysis, ai_error='Live reasoning model client is unavailable.' if client is None else parse_ai_error(exc) if 'exc' in locals() else None)

    event_summary, vitals_summary = _summarize_event(event, vitals)

    # Enrich the assessment summary with background reasoning context
    assessment_summary = _summarize_assessment(previous_assessment)
    if pending_reasoning_context:
        assessment_summary += f"\n[Background reasoning update]: {pending_reasoning_context}"
    if execution_plan and execution_plan.steps:
        step_preview = execution_plan.steps[0]
        assessment_summary += f"\n[Execution plan available]: Next step: {step_preview} (deliver one step at a time, ask for confirmation before proceeding)"

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
        response = await _generate_structured_output(
            client=client,
            prompt=prompt,
            schema=CommunicationAgentAnalysis,
        )
        parsed = response.parsed
        if parsed is None:
            parsed = CommunicationAgentAnalysis.model_validate_json(response.text or "{}")
        return _finalize_analysis_memory(
            analysis=parsed,
            previous_analysis=previous_analysis,
        )
    except Exception as exc:
        logger.warning("Communication analysis model failed. Using heuristic fallback. Error: %s", exc)
        return _heuristic_analysis(latest_message=latest_message, previous_assessment=previous_assessment, previous_analysis=previous_analysis, acknowledged_reasoning_triggers=acknowledged_reasoning_triggers, ai_error='Live reasoning model client is unavailable.' if client is None else parse_ai_error(exc) if 'exc' in locals() else None)


async def render_communication_turn(
    *,
    client,
    event,
    vitals,
    conversation_history,
    analysis: CommunicationAgentAnalysis,
    assessment: FallAssessment | None,
) -> CommunicationAgentAnalysis:
    if client is None:
        if assessment is None:
            return analysis
        followup_text, immediate_step = _fallback_rendered_followup(
            analysis=analysis,
            assessment=assessment,
        )
        guarded = analysis.model_copy(update={"followup_text": followup_text, "immediate_step": immediate_step, "guidance_intent": "instruction", "ai_server_error": analysis.ai_server_error or "Live reasoning model client is unavailable."})
        return _apply_assessment_language_guardrails(
            analysis=guarded,
            assessment=assessment,
        )

    event_summary, _ = _summarize_event(event, vitals)
    analysis_summary = (
        f"role={analysis.responder_role}; target={analysis.communication_target}; "
        f"facts={', '.join(analysis.extracted_facts) or 'none'}; "
        f"reasoning_needed={analysis.reasoning_needed}; "
        f"reasoning_reason={analysis.reasoning_reason}"
    )
    prompt = build_communication_render_prompt(
        event_summary=event_summary,
        transcript_summary=_summarize_transcript(conversation_history),
        analysis_summary=analysis_summary,
        assessment_summary=_summarize_assessment(assessment),
    )

    try:
        response = await _generate_structured_output(
            client=client,
            prompt=prompt,
            schema=CommunicationAgentAnalysis,
        )
        parsed = response.parsed
        if parsed is None:
            parsed = CommunicationAgentAnalysis.model_validate_json(response.text or "{}")
        guarded = parsed.model_copy(
            update={
                "responder_role": analysis.responder_role,
                "communication_target": analysis.communication_target,
                "patient_responded": analysis.patient_responded,
                "bystander_present": analysis.bystander_present,
                "bystander_can_help": analysis.bystander_can_help,
                "extracted_facts": analysis.extracted_facts,
                "resolved_fact_keys": analysis.resolved_fact_keys,
                "open_question_key": analysis.open_question_key,
                "open_question_resolved": analysis.open_question_resolved,
                "conversation_state_summary": analysis.conversation_state_summary,
                "reasoning_needed": analysis.reasoning_needed,
                "reasoning_reason": analysis.reasoning_reason,
                "should_surface_execution_update": analysis.should_surface_execution_update,
                "ai_server_error": analysis.ai_server_error,
            }
        )
        return _apply_assessment_language_guardrails(
            analysis=guarded,
            assessment=assessment,
        )
    except Exception as exc:
        logger.warning("Communication render model failed. Using heuristic fallback. Error: %s", exc)
        if assessment is None:
            return analysis
        followup_text, immediate_step = _fallback_rendered_followup(
            analysis=analysis,
            assessment=assessment,
        )
        guarded = analysis.model_copy(update={"followup_text": followup_text, "immediate_step": immediate_step, "guidance_intent": "instruction", "ai_server_error": analysis.ai_server_error or "Live reasoning model client is unavailable."})
        return _apply_assessment_language_guardrails(
            analysis=guarded,
            assessment=assessment,
        )
