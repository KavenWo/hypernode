"""Deterministic fall assessment service.

This module now owns the single-pass retrieval + reasoning path used for both
direct evaluation and conversation-session refreshes.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import BackgroundTasks

from agents.bystander.guidance_normalizer import normalize_guidance_from_buckets
from agents.bystander.protocol_grounding import (
    build_protocol_guidance_summary,
    collect_required_protocol_intents,
    identify_protocol_candidate,
)
from agents.bystander.retrieval_engine import run_phase2_retrieval
from agents.bystander.retrieval_policy import build_phase2_retrieval_plan
from agents.communication.interaction_policy import (
    InteractionContext,
    choose_interaction_target,
    should_refresh_reasoning,
)
from agents.reasoning.support_grounding import run_reasoning_support_grounding
from agents.shared.config import get_genai_client
from app.fall.agent_runtime import get_fall_agent_runtime
from app.fall.contracts import (
    ActionSummary,
    AuditSummary,
    ClinicalAssessment,
    ClinicalAssessmentSummary,
    CommunicationHandoffSummary,
    DetectionSummary,
    FallAssessment,
    FallEvent,
    GroundingPassSummary,
    GroundingSummary,
    GuidanceSummary,
    InteractionInput,
    InteractionSummary,
    PatientAnswer,
    ProtocolGuidanceSummary,
    ReasoningRefreshSummary,
    TriageQuestionSet,
    UserMedicalProfile,
    VisionAssessment,
    VitalAssessment,
    VitalSigns,
)
from app.fall.execution_service import SeverityLevel as EmergencySeverityLevel
from app.fall.execution_service import trigger_emergency
from db.firebase_client import load_patient_profile

logger = logging.getLogger(__name__)

FALLBACK_REASONING_PREFIX = "Fallback assessment used because the live reasoning model was unavailable."


def load_user_profile(user_id: str) -> UserMedicalProfile:
    """Load the patient profile once and normalize it to the shared schema."""
    return UserMedicalProfile.model_validate(load_patient_profile(user_id).model_dump())


def _confidence_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def get_runtime_status() -> dict:
    """Expose lightweight runtime state for the frontend MVP tester."""
    vertex_project = os.getenv("VERTEX_AI_SEARCH_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    vertex_engine = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID") or os.getenv("ADK_VERTEX_SEARCH_ENGINE_ID")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")

    return {
        "backend_ok": True,
        "gemini_configured": bool(gemini_key and gemini_key != "your_api_key_here"),
        "vertex_search_configured": bool(vertex_project and vertex_engine),
        "vertex_project": vertex_project or "",
        "vertex_engine": vertex_engine or "",
    }


def build_guidance_query(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    severity_hint: str | None = None,
    forced_intents: list[str] | None = None,
) -> str:
    """Choose the primary query from the lightweight Phase 2 retrieval policy."""
    retrieval_plan = build_phase2_retrieval_plan(
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        severity_hint=severity_hint,
        forced_intents=forced_intents,
    )
    return retrieval_plan["primary_query"]


def _responder_mode(patient_answers: list[PatientAnswer]) -> str:
    answer_text = " ".join(answer.answer.lower() for answer in patient_answers)
    if not patient_answers:
        return "no_response"
    if "bystander" in answer_text or "he is" in answer_text or "she is" in answer_text or "the patient" in answer_text:
        return "bystander"
    return "patient"


def _serious_action_required(recommended_action: str | None) -> bool:
    return recommended_action in {
        "dispatch_pending_confirmation",
        "emergency_dispatch",
        "contact_family",
        "urgent_monitoring",
    }


def _extract_fact_keys_from_answers(patient_answers: list[PatientAnswer]) -> list[str]:
    answer_text = " ".join(answer.answer.lower() for answer in patient_answers)
    facts: list[str] = []
    signal_map = {
        "abnormal_breathing": ["breathing strangely", "abnormal breathing", "gasping"],
        "not_breathing": ["not breathing", "stopped breathing"],
        "severe_bleeding": ["heavy bleeding", "severe bleeding", "bleeding a lot"],
        "unresponsive": ["not responding", "unresponsive", "won't wake up"],
        "lost_consciousness": ["lost consciousness", "passed out", "blacked out"],
        "head_strike": ["hit my head", "hit their head", "head injury"],
        "chest_pain": ["chest pain"],
        "new_confusion": ["confused", "new confusion"],
    }
    for fact_key, keywords in signal_map.items():
        if any(keyword in answer_text for keyword in keywords):
            facts.append(fact_key)
    return facts


def _has_meaningful_conversation_context(
    *,
    patient_answers: list[PatientAnswer],
    interaction: InteractionInput | None,
) -> bool:
    """Return whether we have enough conversational context to justify retrieval.

    The first bootstrap reasoning pass should be fast and provisional. Until we
    have at least one meaningful responder message or extracted fact, grounding
    retrieval adds latency without enough context to be worth it.
    """

    if any((answer.answer or "").strip() for answer in patient_answers):
        return True
    if interaction is None:
        return False
    if (interaction.message_text or "").strip():
        return True
    if interaction.new_fact_keys:
        return True
    return False


def build_interaction_summary(
    *,
    interaction: InteractionInput | None,
    patient_answers: list[PatientAnswer],
    recommended_action: str | None,
) -> InteractionSummary:
    responder_mode_hint = interaction.responder_mode_hint if interaction else None
    inferred_mode = responder_mode_hint or _responder_mode(patient_answers)
    context = InteractionContext(
        patient_response_status=(interaction.patient_response_status if interaction else "unknown"),
        bystander_available=bool(interaction and interaction.bystander_available),
        bystander_can_help=bool(interaction and interaction.bystander_can_help),
        serious_action_required=_serious_action_required(recommended_action),
        testing_assume_bystander=bool(interaction and interaction.testing_assume_bystander),
        active_execution_action=interaction.active_execution_action if interaction else None,
        responder_mode_hint=responder_mode_hint,
    )
    interaction_decision = choose_interaction_target(context)

    fact_keys = (
        interaction.new_fact_keys
        if interaction and interaction.new_fact_keys
        else _extract_fact_keys_from_answers(patient_answers)
    )
    message_text = interaction.message_text if interaction and interaction.message_text else " ".join(
        answer.answer for answer in patient_answers
    )
    refresh_decision = should_refresh_reasoning(
        message_text=message_text,
        new_fact_keys=fact_keys,
        previous_action=recommended_action,
        responder_mode_changed=bool(interaction and interaction.responder_mode_changed),
        contradiction_detected=bool(interaction and interaction.contradiction_detected),
        no_response_timeout=bool(interaction and interaction.no_response_timeout),
        active_execution_action=interaction.active_execution_action if interaction else None,
    )

    if inferred_mode == "no_response" and interaction_decision.communication_target == "patient":
        interaction_decision = choose_interaction_target(
            context.model_copy(update={"patient_response_status": "no_response"})
        )

    return InteractionSummary(
        communication_target=interaction_decision.communication_target,
        responder_mode=interaction_decision.responder_mode,
        guidance_style=interaction_decision.guidance_style,
        interaction_mode=interaction_decision.interaction_mode,
        rationale=interaction_decision.rationale,
        reasoning_refresh=ReasoningRefreshSummary(
            required=refresh_decision.refresh_required,
            reason=refresh_decision.reason,
        ),
        testing_assume_bystander=bool(interaction and interaction.testing_assume_bystander),
    )


def build_fall_questions(
    event: FallEvent,
    vitals: VitalSigns | None = None,
    interaction: InteractionInput | None = None,
) -> TriageQuestionSet:
    """Return a stub question set since the legacy triage agent is deprecated."""
    return TriageQuestionSet(questions=[])


def _should_trigger_dispatch(action: str) -> bool:
    return action == "emergency_dispatch"


def _event_validity(event: FallEvent, vision_assessment) -> str:
    if vision_assessment.fall_detected and event.confidence_score >= 0.75:
        return "likely_true"
    if event.confidence_score >= 0.4:
        return "uncertain"
    return "weak_signal"


def _status_for_action(action: str) -> str:
    if action == "dispatch_pending_confirmation":
        return "dispatch_pending_confirmation"
    if action == "emergency_dispatch":
        return "dispatch_confirmed"
    if action == "contact_family":
        return "triage_in_progress"
    return "guidance_active"


def _map_assessment_severity_to_dispatch(severity: str) -> EmergencySeverityLevel:
    normalized = severity.lower().strip()
    if normalized in {"critical", "high"}:
        return EmergencySeverityLevel.RED
    if normalized == "medium":
        return EmergencySeverityLevel.AMBER
    return EmergencySeverityLevel.YELLOW


def _build_dispatch_ai_summary(
    *,
    assessment: FallAssessment,
    patient_answers: list[PatientAnswer],
    patient_profile: UserMedicalProfile,
) -> dict:
    answer_text = " ".join(answer.answer for answer in patient_answers).strip()
    key_alerts: list[str] = []

    if patient_profile.blood_thinners:
        key_alerts.append("Patient uses blood thinners")
    if "head" in answer_text.lower():
        key_alerts.append("Possible head injury reported")

    plan_actions = [
        *assessment.response_plan.bystander_actions,
        *assessment.response_plan.followup_actions,
        *assessment.response_plan.notification_actions,
    ]

    return {
        "suspected_conditions": [
            {
                "condition": "Fall-related injury",
                "confidence": assessment.clinical_assessment.action_confidence_band,
                "reasoning": assessment.clinical_assessment.reasoning_summary,
            }
        ],
        "self_help_actions": (
            [
                {
                    "action": item.type,
                    "priority": index + 1,
                    "rationale": item.reason or "Generated from the Phase 3 response plan.",
                }
                for index, item in enumerate(plan_actions[:4])
            ]
            or [
                {
                    "action": assessment.action.recommended,
                    "priority": 1,
                    "rationale": "Generated from the centralized fall reasoning flow.",
                }
            ]
        ),
        "suggested_department": "Trauma" if "head" in answer_text.lower() else "General ED",
        "key_alerts": key_alerts,
        "recommended_prep": ["Prepare fall-injury intake", "Review patient profile on arrival"],
        "contact_priority": ["999", "next_of_kin"],
        "summary": assessment.clinical_assessment.reasoning_summary,
    }


async def _run_clinical_state_stage(
    *,
    client,
    event: FallEvent,
    vitals: VitalSigns | None,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> tuple[VisionAssessment, VitalAssessment | None, ClinicalAssessment]:
    runtime = get_fall_agent_runtime()
    vision_assessment = await runtime.inspect_fall_event(event)
    vital_assessment = await runtime.inspect_vitals(vitals)
    clinical_assessment = await runtime.assess_clinical_severity(
        client=client,
        event=event,
        patient_profile=patient_profile,
        vision_assessment=vision_assessment,
        vital_assessment=vital_assessment,
        grounded_medical_guidance=None,
        patient_answers=patient_answers,
    )
    return vision_assessment, vital_assessment, clinical_assessment


def _run_grounded_guidance_stage(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    clinical_severity: str,
    action: str,
    forced_intents: list[str] | None = None,
) -> tuple[dict, dict, GuidanceSummary]:
    retrieval_plan = build_phase2_retrieval_plan(
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        severity_hint=clinical_severity,
        forced_intents=forced_intents,
    )
    retrieval_result = run_phase2_retrieval(
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        severity_hint=clinical_severity,
        forced_intents=forced_intents,
    )
    normalized_guidance = normalize_guidance_from_buckets(
        buckets=retrieval_result["bucketed_snippets"],
        action=action,
    )
    return retrieval_plan, retrieval_result, normalized_guidance


def _build_clinical_assessment_summary(clinical_assessment) -> ClinicalAssessmentSummary:
    return ClinicalAssessmentSummary(
        severity=clinical_assessment.severity,
        clinical_confidence_score=clinical_assessment.clinical_confidence_score,
        clinical_confidence_band=clinical_assessment.clinical_confidence_band,
        action_confidence_score=clinical_assessment.action_confidence_score,
        action_confidence_band=clinical_assessment.action_confidence_band,
        red_flags=clinical_assessment.red_flags,
        protective_signals=clinical_assessment.protective_signals,
        suspected_risks=clinical_assessment.suspected_risks,
        vulnerability_modifiers=clinical_assessment.vulnerability_modifiers,
        missing_facts=clinical_assessment.missing_facts,
        contradictions=clinical_assessment.contradictions,
        uncertainty=clinical_assessment.uncertainty,
        hard_emergency_triggered=clinical_assessment.hard_emergency_triggered,
        blocking_uncertainties=clinical_assessment.blocking_uncertainties,
        override_policy=clinical_assessment.override_policy,
        reasoning_summary=clinical_assessment.reasoning_summary,
        response_plan=clinical_assessment.response_plan,
        reasoning_trace=clinical_assessment.reasoning_trace,
        ai_server_error=getattr(clinical_assessment, "ai_server_error", None),
    )


def _should_trigger_reasoning_support(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
    allow_grounding: bool,
) -> bool:
    if not allow_grounding:
        return False
    high_risk_flags = {
        "abnormal_breathing",
        "not_breathing",
        "severe_bleeding",
        "head_strike",
        "blood_thinner_use",
        "suspected_spinal_injury",
        "suspected_fracture",
        "cannot_stand",
        "chest_pain",
        "unresponsive",
        "loss_of_consciousness",
    }
    if action in {"dispatch_pending_confirmation", "emergency_dispatch"}:
        return True
    if clinical_assessment.contradictions or clinical_assessment.blocking_uncertainties:
        return True
    if any(flag in high_risk_flags for flag in clinical_assessment.red_flags):
        return True
    if clinical_assessment.vulnerability_modifiers:
        return True
    return False


def _action_item_to_instruction(action_type: str) -> str | None:
    mapping = {
        "start_cpr_guidance": "Start CPR if the patient is not breathing normally.",
        "retrieve_aed_if_available": "Get an AED if one is available nearby.",
        "check_breathing": "Check whether the patient is breathing normally.",
        "apply_pressure_to_bleeding": "Apply firm pressure to any severe bleeding.",
        "keep_patient_still": "Keep the patient still.",
        "do_not_move_patient": "Do not move the patient unless there is immediate danger.",
        "check_consciousness": "Check whether the patient is awake and responding.",
        "wait_for_responders": "Stay with the patient while responders are on the way.",
        "stay_on_scene": "Stay on scene if it is safe to do so.",
        "monitor_for_worsening_signs": "Watch for worsening pain, breathing, or responsiveness.",
        "continue_reassessment": "Keep reassessing the patient and tell me what changes.",
        "inform_family": "I can inform the family for support.",
    }
    return mapping.get(action_type)


def _should_trigger_grounded_guidance(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
    interaction_summary: InteractionSummary,
    allow_grounding: bool,
) -> bool:
    if not allow_grounding:
        return False
    if action in {"dispatch_pending_confirmation", "emergency_dispatch"}:
        return True
    if clinical_assessment.response_plan.bystander_actions:
        return True
    if interaction_summary.communication_target == "bystander" and clinical_assessment.response_plan.followup_actions:
        return True
    return False


def _requires_mandatory_protocol_grounding(
    *,
    clinical_assessment: ClinicalAssessmentSummary,
    allow_grounding: bool,
) -> bool:
    """Return whether the response plan activated a protocol that must be grounded.

    This function is intentionally deterministic. The reasoning model may suggest
    CPR or another protocol through the response plan, but the backend policy is
    the final authority on whether retrieval is mandatory before communication can
    present the instructions.
    """

    return allow_grounding and identify_protocol_candidate(clinical_assessment=clinical_assessment) is not None


def _build_non_grounded_guidance(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
) -> GuidanceSummary:
    prioritized_actions = [
        *clinical_assessment.response_plan.bystander_actions,
        *clinical_assessment.response_plan.followup_actions,
        *clinical_assessment.response_plan.notification_actions,
    ]
    steps = [
        instruction
        for instruction in (_action_item_to_instruction(item.type) for item in prioritized_actions)
        if instruction
    ][:4]

    if not steps:
        if action == "contact_family":
            steps = ["Stay in a safe position while support is arranged."]
        elif action == "monitor":
            steps = ["Stay in a safe position and monitor for changes."]
        else:
            steps = ["Stay still and wait for the next instruction."]

    primary_message = steps[0]
    warnings: list[str] = []
    if any(flag in clinical_assessment.red_flags for flag in ["head_strike", "suspected_spinal_injury"]):
        warnings.append("Do not move too quickly if head, neck, or back injury is possible.")

    escalation_triggers = [
        trigger
        for trigger in [
            "Breathing that becomes abnormal requires urgent escalation."
            if any(flag in clinical_assessment.red_flags for flag in ["abnormal_breathing", "not_breathing"])
            else None,
            "Heavy bleeding requires immediate help."
            if "severe_bleeding" in clinical_assessment.red_flags
            else None,
        ]
        if trigger
    ][:3]

    return GuidanceSummary(
        primary_message=primary_message,
        steps=steps,
        warnings=warnings,
        escalation_triggers=escalation_triggers,
    )


def _targeted_followup_for_missing_fact(
    missing_fact: str | None,
    *,
    communication_target: str,
) -> tuple[str | None, str, list[str]]:
    if missing_fact == "breathing_status_unconfirmed":
        return (
            "Is the patient breathing normally right now?",
            "breathing",
            ["Breathing normally", "Breathing strangely", "Not breathing"],
        )
    if missing_fact == "bleeding_status_unconfirmed":
        return (
            "Is there any heavy bleeding right now?",
            "bleeding",
            ["Heavy bleeding", "A little bleeding", "No bleeding"],
        )
    if missing_fact == "responsiveness_unconfirmed":
        return (
            "Is the patient awake and responding right now?",
            "responsiveness",
            ["Awake", "Slow to respond", "Not responding"],
        )
    if missing_fact == "head_strike_unconfirmed":
        return (
            "Did the patient hit their head in the fall?",
            "head_injury",
            ["Yes", "No", "Not sure"],
        )
    if communication_target == "bystander":
        return (None, "observation", [])
    return (None, "general_check", [])


def _cap_message_length(text: str, max_words: int = 30) -> str:
    """Hard cap a message to max_words as a safety net against protocol dumps."""

    words = (text or "").split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def _build_communication_handoff(
    *,
    action: str,
    interaction_summary: InteractionSummary,
    clinical_assessment: ClinicalAssessmentSummary,
    response_plan: ResponsePlanSummary,
    guidance: GuidanceSummary,
    protocol_guidance: ProtocolGuidanceSummary,
) -> CommunicationHandoffSummary:
    target = interaction_summary.communication_target
    immediate_step = guidance.steps[0] if guidance.steps else None
    priority_missing_fact = clinical_assessment.reasoning_trace.priority_missing_fact
    question, next_focus, quick_replies = _targeted_followup_for_missing_fact(
        priority_missing_fact,
        communication_target=target,
    )
    has_bystander_actions = bool(response_plan.bystander_actions)
    has_notification_actions = bool(response_plan.notification_actions)
    context_bits: list[str] = []
    if priority_missing_fact:
        context_bits.append(f"missing:{priority_missing_fact}")
    for red_flag in clinical_assessment.red_flags[:3]:
        context_bits.append(f"red_flag:{red_flag}")
    for action_item in response_plan.notification_actions[:2]:
        context_bits.append(f"notification:{action_item.type}")
    for action_item in response_plan.bystander_actions[:2]:
        context_bits.append(f"scene_action:{action_item.type}")
    if action in {"dispatch_pending_confirmation", "emergency_dispatch"}:
        context_bits.append(f"execution:{action}")
    if protocol_guidance.protocol_key:
        context_bits.append(f"protocol:{protocol_guidance.protocol_key}")

    if protocol_guidance.ready_for_communication:
        return CommunicationHandoffSummary(
            mode="instruction",
            priority="execution",
            immediate_step=protocol_guidance.steps[0] if protocol_guidance.steps else immediate_step,
            next_focus=protocol_guidance.protocol_key or "guided_action",
            quick_replies=["Done", "Need next step", "Condition worse"],
            open_question_key=None,
            should_surface_execution_update=False,
            recommended_context_bits=context_bits,
            rationale=f"Grounded {protocol_guidance.protocol_key} protocol is ready, so communication should present the confirmed protocol guidance.",
        )

    if action == "emergency_dispatch":
        return CommunicationHandoffSummary(
            mode="status_update",
            priority="execution",
            immediate_step=immediate_step,
            next_focus="scene_safety",
            quick_replies=["Okay", "Breathing changed", "Condition worse"],
            open_question_key=None,
            should_surface_execution_update=True,
            recommended_context_bits=context_bits,
            rationale="Emergency dispatch is active, so communication should prioritize status and immediate safety guidance.",
        )

    if action == "dispatch_pending_confirmation":
        return CommunicationHandoffSummary(
            mode="urgent_instruction",
            priority="execution",
            immediate_step=immediate_step,
            next_focus=next_focus,
            quick_replies=quick_replies,
            open_question_key=next_focus if question else None,
            should_surface_execution_update=True,
            recommended_context_bits=context_bits,
            rationale="Urgent escalation is pending confirmation, so communication should give a safety step and ask only the top missing fact.",
        )

    if has_bystander_actions:
        return CommunicationHandoffSummary(
            mode="instruction",
            priority="safety",
            immediate_step=immediate_step,
            next_focus="guided_action",
            quick_replies=["Done", "Need next step", "Condition worse"],
            open_question_key=None,
            should_surface_execution_update=False,
            recommended_context_bits=context_bits,
            rationale="Immediate bystander or patient actions are available, so communication should prioritize execution over more triage questions.",
        )

    if has_notification_actions and action == "contact_family":
        return CommunicationHandoffSummary(
            mode="status_update",
            priority="reassure",
            immediate_step=immediate_step,
            next_focus="support",
            quick_replies=["Okay", "Pain worse", "Breathing worse"],
            open_question_key=None,
            should_surface_execution_update=True,
            recommended_context_bits=context_bits,
            rationale="Support notifications are the main active track, so communication should reassure and keep the scene stable.",
        )

    if question and clinical_assessment.blocking_uncertainties:
        return CommunicationHandoffSummary(
            mode="question",
            priority="clarify",
            immediate_step=immediate_step,
            next_focus=next_focus,
            quick_replies=quick_replies,
            open_question_key=next_focus,
            should_surface_execution_update=False,
            recommended_context_bits=context_bits,
            rationale="A blocking uncertainty remains, so communication should ask one targeted question while keeping current guidance active.",
        )

    return CommunicationHandoffSummary(
        mode="instruction" if immediate_step or guidance.primary_message else "reassure",
        priority="safety" if immediate_step else "reassure",
        immediate_step=immediate_step,
        next_focus="monitoring",
        quick_replies=["Okay", "Pain worse", "Breathing worse"],
        open_question_key=None,
        should_surface_execution_update=False,
        recommended_context_bits=context_bits,
        rationale="Current guidance is sufficient for this turn, so communication should reinforce the plan rather than reopen broad triage questions.",
    )


async def run_reasoning_assessment(
    event: FallEvent,
    vitals: VitalSigns | None = None,
    patient_answers: list[PatientAnswer] | None = None,
    interaction: InteractionInput | None = None,
    *,
    trigger_dispatch: bool = False,
    background_tasks: Optional[BackgroundTasks] = None,
) -> FallAssessment:
    """Run the fast-path reasoning assessment WITHOUT guidance grounding.

    This function owns only the clinical decision pipeline:
      - Step A: Deterministic clinical policy (no I/O)
      - Step B: Gemini Pro → ClinicalAssessment (1 call)
      - Step B' (conditional): Reasoning-support grounding via Vertex AI Search
        + second Gemini Pro call — only when blocking_uncertainties,
        contradictions, or high-risk flags are present.

    It does NOT call run_phase2_retrieval, normalize_guidance_from_buckets,
    build_protocol_guidance_summary, or any guidance-related Vertex AI Search.

    The execution agent is responsible for guidance/protocol grounding and is
    invoked separately in Phase 2 of the background task.
    """

    logger.info(
        "[Reasoning] Starting fast-path assessment | user=%s motion=%s confidence=%.2f answers=%d",
        event.user_id,
        event.motion_state,
        event.confidence_score,
        len(patient_answers or []),
    )
    try:
        client = get_genai_client()
    except RuntimeError:
        client = None

    patient_profile = load_user_profile(event.user_id)
    answers = patient_answers or []
    allow_grounding = _has_meaningful_conversation_context(
        patient_answers=answers,
        interaction=interaction,
    )
    initial_interaction = build_interaction_summary(
        interaction=interaction,
        patient_answers=answers,
        recommended_action=None,
    )

    # Step A + B: Clinical state assessment (1 Gemini Pro call)
    vision_assessment, vital_assessment, clinical_assessment = await _run_clinical_state_stage(
        client=client,
        event=event,
        vitals=vitals,
        patient_profile=patient_profile,
        patient_answers=answers,
    )
    clinical_assessment_summary = _build_clinical_assessment_summary(clinical_assessment)
    next_action = clinical_assessment.recommended_action
    reasoning_support_summary = GroundingPassSummary(source="not_requested")

    # Step B' (conditional): Reasoning-support grounding only
    if _should_trigger_reasoning_support(
        action=next_action,
        clinical_assessment=clinical_assessment_summary,
        allow_grounding=allow_grounding,
    ):
        reasoning_support_result = run_reasoning_support_grounding(
            patient_profile=patient_profile,
            patient_answers=answers,
            clinical_assessment=clinical_assessment_summary,
        )
        logger.info(
            "[Reasoning] Support grounding ready | user=%s source=%s intents=%s",
            event.user_id,
            reasoning_support_result["source"],
            ", ".join(reasoning_support_result["selected_intents"][:3]) or "none",
        )
        clinical_assessment = await get_fall_agent_runtime().assess_clinical_severity(
            client=client,
            event=event,
            patient_profile=patient_profile,
            vision_assessment=vision_assessment,
            vital_assessment=vital_assessment,
            grounded_medical_guidance=reasoning_support_result["snippets"],
            patient_answers=answers,
        )
        clinical_assessment_summary = _build_clinical_assessment_summary(clinical_assessment)
        next_action = clinical_assessment.recommended_action
        reasoning_support_summary = GroundingPassSummary(
            source=reasoning_support_result["source"],
            references=reasoning_support_result["references"],
            preview=reasoning_support_result["snippets"][:3],
            retrieval_intents=reasoning_support_result["selected_intents"],
            queries=reasoning_support_result["queries"],
        )

    interaction_summary = build_interaction_summary(
        interaction=interaction,
        patient_answers=answers,
        recommended_action=next_action,
    )

    # Build non-grounded guidance (lightweight, no Vertex AI Search)
    normalized_guidance = _build_non_grounded_guidance(
        action=next_action,
        clinical_assessment=clinical_assessment_summary,
    )

    # Build communication handoff without protocol grounding
    communication_handoff = _build_communication_handoff(
        action=next_action,
        interaction_summary=interaction_summary,
        clinical_assessment=clinical_assessment_summary,
        response_plan=clinical_assessment.response_plan,
        guidance=normalized_guidance,
        protocol_guidance=ProtocolGuidanceSummary(),
    )

    assessment = FallAssessment(
        incident_id=None,
        status=_status_for_action(next_action),
        responder_mode=interaction_summary.responder_mode,
        interaction=interaction_summary,
        detection=DetectionSummary(
            motion_state=event.motion_state,
            fall_detection_confidence_score=event.confidence_score,
            fall_detection_confidence_band=_confidence_band(event.confidence_score),
            event_validity=_event_validity(event, vision_assessment),
        ),
        clinical_assessment=clinical_assessment_summary,
        action=ActionSummary(
            recommended=next_action,
            requires_confirmation=(next_action == "dispatch_pending_confirmation"),
            cancel_allowed=(next_action in {"dispatch_pending_confirmation", "emergency_dispatch"}),
            countdown_seconds=30 if next_action == "dispatch_pending_confirmation" else None,
        ),
        response_plan=clinical_assessment.response_plan,
        guidance=GuidanceSummary(
            primary_message=normalized_guidance.primary_message,
            steps=normalized_guidance.steps,
            warnings=normalized_guidance.warnings,
            escalation_triggers=normalized_guidance.escalation_triggers,
        ),
        protocol_guidance=ProtocolGuidanceSummary(),
        communication_handoff=communication_handoff,
        grounding=GroundingSummary(
            source=reasoning_support_summary.source,
            reasoning_support=reasoning_support_summary,
            guidance_support=GroundingPassSummary(source="not_requested"),
        ),
        audit=AuditSummary(
            fallback_used=clinical_assessment.reasoning_summary.startswith(FALLBACK_REASONING_PREFIX),
            policy_version="reasoning_only+clinical_reasoning_policy_v1",
            dispatch_triggered=False,
        ),
    )
    logger.info(
        "[Reasoning] Fast-path assessment complete | user=%s severity=%s action=%s target=%s fallback=%s",
        event.user_id,
        assessment.clinical_assessment.severity,
        assessment.action.recommended,
        assessment.interaction.communication_target if assessment.interaction else initial_interaction.communication_target,
        assessment.audit.fallback_used,
    )

    if not trigger_dispatch or not _should_trigger_dispatch(assessment.action.recommended):
        return assessment

    incident_id = await trigger_emergency(
        patient_id=event.user_id,
        severity=_map_assessment_severity_to_dispatch(assessment.clinical_assessment.severity),
        vitals=_vitals_to_dispatch_payload(vitals),
        flags=["fall_detected", f"motion_state:{event.motion_state}"],
        ai_decision=_build_dispatch_ai_summary(
            assessment=assessment,
            patient_answers=answers,
            patient_profile=patient_profile,
        ),
        background_tasks=background_tasks,
    )
    logger.info(
        "[Reasoning] Emergency dispatch triggered | user=%s incident=%s",
        event.user_id,
        incident_id,
    )

    return assessment.model_copy(
        update={
            "incident_id": incident_id,
            "status": "dispatch_confirmed",
            "audit": assessment.audit.model_copy(update={"dispatch_triggered": True}),
        }
    )


def _vitals_to_dispatch_payload(vitals: VitalSigns | None) -> dict:
    if vitals is None:
        return {}

    return {
        "heart_rate": vitals.heart_rate,
        "spo2": vitals.blood_oxygen_sp02,
        "systolic_bp": vitals.blood_pressure_systolic,
        "diastolic_bp": vitals.blood_pressure_diastolic,
    }


async def run_fall_assessment(
    event: FallEvent,
    vitals: VitalSigns | None = None,
    patient_answers: list[PatientAnswer] | None = None,
    interaction: InteractionInput | None = None,
    *,
    trigger_dispatch: bool = False,
    background_tasks: Optional[BackgroundTasks] = None,
) -> FallAssessment:
    """Run the full single-pass fall assessment and optionally bridge to dispatch."""
    logger.info(
        "[Reasoning] Starting assessment | user=%s motion=%s confidence=%.2f answers=%d",
        event.user_id,
        event.motion_state,
        event.confidence_score,
        len(patient_answers or []),
    )
    try:
        client = get_genai_client()
    except RuntimeError:
        client = None

    patient_profile = load_user_profile(event.user_id)
    answers = patient_answers or []
    allow_grounding = _has_meaningful_conversation_context(
        patient_answers=answers,
        interaction=interaction,
    )
    initial_interaction = build_interaction_summary(
        interaction=interaction,
        patient_answers=answers,
        recommended_action=None,
    )

    vision_assessment, vital_assessment, clinical_assessment = await _run_clinical_state_stage(
        client=client,
        event=event,
        vitals=vitals,
        patient_profile=patient_profile,
        patient_answers=answers,
    )
    clinical_assessment_summary = _build_clinical_assessment_summary(clinical_assessment)
    next_action = clinical_assessment.recommended_action
    reasoning_support_summary = GroundingPassSummary(source="not_requested")

    if _should_trigger_reasoning_support(
        action=next_action,
        clinical_assessment=clinical_assessment_summary,
        allow_grounding=allow_grounding,
    ):
        reasoning_support_result = run_reasoning_support_grounding(
            patient_profile=patient_profile,
            patient_answers=answers,
            clinical_assessment=clinical_assessment_summary,
        )
        logger.info(
            "[Reasoning] Support grounding ready | user=%s source=%s intents=%s",
            event.user_id,
            reasoning_support_result["source"],
            ", ".join(reasoning_support_result["selected_intents"][:3]) or "none",
        )
        clinical_assessment = await get_fall_agent_runtime().assess_clinical_severity(
            client=client,
            event=event,
            patient_profile=patient_profile,
            vision_assessment=vision_assessment,
            vital_assessment=vital_assessment,
            grounded_medical_guidance=reasoning_support_result["snippets"],
            patient_answers=answers,
        )
        clinical_assessment_summary = _build_clinical_assessment_summary(clinical_assessment)
        next_action = clinical_assessment.recommended_action
        reasoning_support_summary = GroundingPassSummary(
            source=reasoning_support_result["source"],
            references=reasoning_support_result["references"],
            preview=reasoning_support_result["snippets"][:3],
            retrieval_intents=reasoning_support_result["selected_intents"],
            queries=reasoning_support_result["queries"],
        )

    interaction_summary = build_interaction_summary(
        interaction=interaction,
        patient_answers=answers,
        recommended_action=next_action,
    )
    should_ground_guidance = _should_trigger_grounded_guidance(
        action=next_action,
        clinical_assessment=clinical_assessment_summary,
        interaction_summary=interaction_summary,
        allow_grounding=allow_grounding,
    )
    requires_protocol_grounding = _requires_mandatory_protocol_grounding(
        clinical_assessment=clinical_assessment_summary,
        allow_grounding=allow_grounding,
    )
    forced_protocol_intents = collect_required_protocol_intents(
        clinical_assessment=clinical_assessment_summary,
    ) if allow_grounding else []

    if should_ground_guidance or requires_protocol_grounding:
        retrieval_plan, retrieval_result, normalized_guidance = _run_grounded_guidance_stage(
            patient_profile=patient_profile,
            patient_answers=answers,
            clinical_severity=clinical_assessment.severity,
            action=next_action,
            forced_intents=forced_protocol_intents,
        )
        grounded_medical_guidance = retrieval_result["guidance_snippets"]
        logger.info(
            "[Guidance] Retrieval ready | user=%s source=%s intents=%s",
            event.user_id,
            retrieval_result["retrieval_source"],
            ", ".join(retrieval_plan["selected_intents"][:3]) or "none",
        )
        guidance_support_summary = GroundingPassSummary(
            source=retrieval_result["retrieval_source"],
            references=retrieval_result.get("references", []),
            preview=grounded_medical_guidance[:3],
            retrieval_intents=retrieval_plan["selected_intents"],
            queries=retrieval_plan["queries"],
            buckets=retrieval_result["bucketed_snippets"],
            queries_by_bucket=retrieval_result.get("queries_by_bucket", {}),
            references_by_bucket=retrieval_result.get("references_by_bucket", {}),
            bucket_sources=retrieval_result.get("bucket_sources", {}),
        )
        guidance_policy_version = retrieval_plan["policy_version"]
        overall_grounding_source = retrieval_result["retrieval_source"]
    else:
        retrieval_plan = None
        retrieval_result = None
        normalized_guidance = _build_non_grounded_guidance(
            action=next_action,
            clinical_assessment=clinical_assessment_summary,
        )
        logger.info(
            "[Guidance] Retrieval skipped | user=%s action=%s severity=%s target=%s",
            event.user_id,
            next_action,
            clinical_assessment.severity,
            interaction_summary.communication_target,
        )
        guidance_support_summary = GroundingPassSummary(source="not_requested")
        guidance_policy_version = "guidance_skipped"
        overall_grounding_source = reasoning_support_summary.source

    protocol_guidance = build_protocol_guidance_summary(
        clinical_assessment=clinical_assessment_summary,
        retrieval_plan=retrieval_plan,
        retrieval_result=retrieval_result,
    )
    if protocol_guidance.grounding_required and not protocol_guidance.ready_for_communication:
        logger.info(
            "[Guidance] Protocol blocked | user=%s protocol=%s status=%s rationale=%s",
            event.user_id,
            protocol_guidance.protocol_key,
            protocol_guidance.grounding_status,
            protocol_guidance.rationale,
        )

    communication_handoff = _build_communication_handoff(
        action=next_action,
        interaction_summary=interaction_summary,
        clinical_assessment=clinical_assessment_summary,
        response_plan=clinical_assessment.response_plan,
        guidance=normalized_guidance,
        protocol_guidance=protocol_guidance,
    )

    assessment = FallAssessment(
        incident_id=None,
        status=_status_for_action(next_action),
        responder_mode=interaction_summary.responder_mode,
        interaction=interaction_summary,
        detection=DetectionSummary(
            motion_state=event.motion_state,
            fall_detection_confidence_score=event.confidence_score,
            fall_detection_confidence_band=_confidence_band(event.confidence_score),
            event_validity=_event_validity(event, vision_assessment),
        ),
        clinical_assessment=clinical_assessment_summary,
        action=ActionSummary(
            recommended=next_action,
            requires_confirmation=(next_action == "dispatch_pending_confirmation"),
            cancel_allowed=(next_action in {"dispatch_pending_confirmation", "emergency_dispatch"}),
            countdown_seconds=30 if next_action == "dispatch_pending_confirmation" else None,
        ),
        response_plan=clinical_assessment.response_plan,
        guidance=GuidanceSummary(
            primary_message=normalized_guidance.primary_message,
            steps=normalized_guidance.steps,
            warnings=normalized_guidance.warnings,
            escalation_triggers=normalized_guidance.escalation_triggers,
        ),
        protocol_guidance=protocol_guidance,
        communication_handoff=communication_handoff,
        grounding=GroundingSummary(
            source=overall_grounding_source,
            references=guidance_support_summary.references,
            preview=guidance_support_summary.preview,
            retrieval_intents=guidance_support_summary.retrieval_intents,
            queries=guidance_support_summary.queries,
            buckets=guidance_support_summary.buckets,
            queries_by_bucket=guidance_support_summary.queries_by_bucket,
            references_by_bucket=guidance_support_summary.references_by_bucket,
            bucket_sources=guidance_support_summary.bucket_sources,
            reasoning_support=reasoning_support_summary,
            guidance_support=guidance_support_summary,
        ),
        audit=AuditSummary(
            fallback_used=clinical_assessment.reasoning_summary.startswith(FALLBACK_REASONING_PREFIX),
            policy_version=f"{guidance_policy_version}+clinical_reasoning_policy_v1",
            dispatch_triggered=False,
        ),
    )
    logger.info(
        "[Reasoning] Assessment complete | user=%s severity=%s action=%s target=%s fallback=%s",
        event.user_id,
        assessment.clinical_assessment.severity,
        assessment.action.recommended,
        assessment.interaction.communication_target if assessment.interaction else initial_interaction.communication_target,
        assessment.audit.fallback_used,
    )

    if not trigger_dispatch or not _should_trigger_dispatch(assessment.action.recommended):
        return assessment

    incident_id = await trigger_emergency(
        patient_id=event.user_id,
        severity=_map_assessment_severity_to_dispatch(assessment.clinical_assessment.severity),
        vitals=_vitals_to_dispatch_payload(vitals),
        flags=["fall_detected", f"motion_state:{event.motion_state}"],
        ai_decision=_build_dispatch_ai_summary(
            assessment=assessment,
            patient_answers=answers,
            patient_profile=patient_profile,
        ),
        background_tasks=background_tasks,
    )
    logger.info(
        "[Reasoning] Emergency dispatch triggered | user=%s incident=%s",
        event.user_id,
        incident_id,
    )

    return assessment.model_copy(
        update={
            "incident_id": incident_id,
            "status": "dispatch_confirmed",
            "audit": assessment.audit.model_copy(update={"dispatch_triggered": True}),
        }
    )

