"""Structured communication-AI layer for the Phase 4 session loop."""

from __future__ import annotations

import asyncio
import logging

from google.genai import errors, types

from agents.shared.config import FALLBACK_MODELS
from agents.shared.schemas import CommunicationAgentAnalysis, MvpAssessment

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


def _summarize_assessment(assessment: MvpAssessment | None) -> str:
    if assessment is None:
        return "No prior reasoning snapshot."
    return (
        f"severity={assessment.clinical_assessment.severity}; "
        f"action={assessment.action.recommended}; "
        f"reasoning={assessment.clinical_assessment.reasoning_summary}; "
        f"primary_guidance={assessment.guidance.primary_message}"
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
    previous_assessment: MvpAssessment | None,
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
            reasoning_needed=False,
            reasoning_reason="The session just started, so the first step is a patient-first check.",
            guidance_intent="patient_check",
            next_focus="responsiveness",
            immediate_step=None,
            quick_replies=["Yes", "No", "Need help", "I can answer"],
        )

    role, patient_responded, bystander_present = _heuristic_role(latest_message)
    facts = _extract_facts(latest_message, role)
    bystander_can_help = "bystander_can_help" in facts
    critical_facts = {"abnormal_breathing", "not_breathing", "severe_bleeding", "head_strike", "unresponsive", "chest_pain"}
    reasoning_needed = bool(critical_facts.intersection(facts))

    if role == "bystander":
        followup = "Okay. Is the patient awake and breathing normally?"
        target = "bystander"
        quick_replies = ["Awake", "Breathing normally", "Breathing strangely", "Not responding"]
    elif role == "patient":
        if "head_strike" in facts:
            followup = "Okay. Stay still for me. Did you black out at all?"
        elif "abnormal_breathing" in facts or "not_breathing" in facts:
            followup = "Okay. Stay still. Tell me if breathing gets worse."
        else:
            followup = "Okay. Can you breathe normally and tell me where it hurts?"
        target = "patient"
        quick_replies = ["Breathing okay", "Hard to breathe", "Head hurts", "I can't stand"]
    else:
        followup = "A fall was detected. Are you the patient or helping someone?"
        target = "unknown"
        quick_replies = ["I am the patient", "I am helping", "No response", "Need help now"]

    immediate_step = None
    if "not_breathing" in facts:
        immediate_step = "Check breathing now."
    elif "severe_bleeding" in facts:
        immediate_step = "Apply firm pressure."
    elif previous_assessment is not None and previous_assessment.guidance.steps:
        immediate_step = previous_assessment.guidance.steps[0]

    return CommunicationAgentAnalysis(
        followup_text=followup,
        responder_role=role,
        communication_target=target,
        patient_responded=patient_responded and role == "patient",
        bystander_present=bystander_present,
        bystander_can_help=bystander_can_help,
        extracted_facts=facts,
        reasoning_needed=reasoning_needed,
        reasoning_reason="Critical new facts were reported." if reasoning_needed else "No critical new facts were detected yet.",
        guidance_intent="instruction" if immediate_step else "question",
        next_focus="breathing" if "abnormal_breathing" in facts or "not_breathing" in facts else "responsiveness",
        immediate_step=immediate_step,
        quick_replies=quick_replies,
    )


def _fallback_rendered_followup(
    *,
    analysis: CommunicationAgentAnalysis,
    assessment: MvpAssessment,
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
            return "Okay. Rest where you are and tell me if pain or breathing gets worse.", "Rest where you are."
        if analysis.communication_target == "bystander":
            return "Okay. Keep watching them and tell me if anything gets worse.", "Keep watching them."
        return "Okay. Stay safe and tell me if anything changes.", "Stay safe."

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
    assessment: MvpAssessment | None,
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
    for model_name in FALLBACK_MODELS:
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
                is_last_attempt = attempt == 1 and model_name == FALLBACK_MODELS[-1]
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
    previous_assessment: MvpAssessment | None,
) -> CommunicationAgentAnalysis:
    if client is None:
        return _heuristic_analysis(
            latest_message=latest_message,
            previous_assessment=previous_assessment,
        )

    event_summary, vitals_summary = _summarize_event(event, vitals)
    prompt = build_communication_analysis_prompt(
        event_summary=event_summary,
        patient_summary=_summarize_patient(patient_profile),
        vitals_summary=vitals_summary,
        transcript_summary=_summarize_transcript(conversation_history),
        latest_message=latest_message,
        previous_assessment_summary=_summarize_assessment(previous_assessment),
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
        return parsed
    except Exception as exc:
        logger.warning("Communication analysis model failed. Using heuristic fallback. Error: %s", exc)
        return _heuristic_analysis(
            latest_message=latest_message,
            previous_assessment=previous_assessment,
        )


async def render_communication_turn(
    *,
    client,
    event,
    vitals,
    conversation_history,
    analysis: CommunicationAgentAnalysis,
    assessment: MvpAssessment | None,
) -> CommunicationAgentAnalysis:
    if client is None:
        if assessment is None:
            return analysis
        followup_text, immediate_step = _fallback_rendered_followup(
            analysis=analysis,
            assessment=assessment,
        )
        guarded = analysis.model_copy(
            update={
                "followup_text": followup_text,
                "immediate_step": immediate_step,
                "guidance_intent": "instruction",
            }
        )
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
                "reasoning_needed": analysis.reasoning_needed,
                "reasoning_reason": analysis.reasoning_reason,
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
        guarded = analysis.model_copy(
            update={
                "followup_text": followup_text,
                "immediate_step": immediate_step,
                "guidance_intent": "instruction",
            }
        )
        return _apply_assessment_language_guardrails(
            analysis=guarded,
            assessment=assessment,
        )
