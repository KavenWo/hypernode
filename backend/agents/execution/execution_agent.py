"""Execution agent: owns all guidance/protocol Vertex AI Search retrieval.

This agent is invoked ONLY when the reasoning agent determines that hands-on
emergency action is needed (dispatch, bystander intervention, CPR, etc.).

It never performs clinical reasoning or severity assessment — that is the
reasoning agent's domain. Its sole job is to retrieve grounded step-by-step
execution content and assemble it into an ``ExecutionPlan``.

Vertex AI Search query ownership:
  - cpr_guidance, airway_management, bleeding_control, recovery_position,
    bystander_step_*, protocol_*
  - NEVER: severity_*_reasoning, red_flags_reasoning, escalation_logic_reasoning
"""

from __future__ import annotations

import logging

from agents.shared.schemas import (
    ClinicalAssessmentSummary,
    ExecutionGuidance,
    PatientAnswer,
    UserMedicalProfile,
)

logger = logging.getLogger(__name__)


def requires_execution_grounding(
    *,
    action: str,
    bystander_actions: list | None = None,
) -> bool:
    """Decide whether the execution agent should run after reasoning completes.

    This is the single gatekeeper for Phase 2 of the background task.
    """

    if action in {"dispatch_pending_confirmation", "emergency_dispatch"}:
        return True
    if bystander_actions:
        return True
    return False


async def run_execution_grounding(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> ExecutionGuidance:
    """Retrieve grounded guidance and build a narrow execution-guidance payload.

    This function owns all guidance/protocol Vertex AI Search queries. It
    imports the retrieval functions lazily to keep the module boundary clean
    and to allow the retrieval engine to evolve independently.
    """

    from app.fall.assessment_service import (
        _run_grounded_guidance_stage,
        _build_non_grounded_guidance,
        _should_trigger_grounded_guidance,
        _requires_mandatory_protocol_grounding,
        build_interaction_summary,
        build_protocol_guidance_summary,
    )
    from agents.bystander.protocol_grounding import collect_required_protocol_intents

    # Build a minimal interaction summary for guidance policy checks
    interaction_summary = build_interaction_summary(
        interaction=None,
        patient_answers=patient_answers,
        recommended_action=action,
    )

    should_ground_guidance = _should_trigger_grounded_guidance(
        action=action,
        clinical_assessment=clinical_assessment,
        interaction_summary=interaction_summary,
        allow_grounding=True,
    )
    requires_protocol = _requires_mandatory_protocol_grounding(
        clinical_assessment=clinical_assessment,
        allow_grounding=True,
    )
    forced_protocol_intents = collect_required_protocol_intents(
        clinical_assessment=clinical_assessment,
    )

    if should_ground_guidance or requires_protocol:
        logger.info(
            "[ExecutionAgent] Running grounded guidance retrieval | action=%s severity=%s",
            action,
            clinical_assessment.severity,
        )
        retrieval_plan, retrieval_result, normalized_guidance = _run_grounded_guidance_stage(
            patient_profile=patient_profile,
            patient_answers=patient_answers,
            clinical_severity=clinical_assessment.severity,
            action=action,
            forced_intents=forced_protocol_intents,
        )

        protocol_guidance = build_protocol_guidance_summary(
            clinical_assessment=clinical_assessment,
            retrieval_plan=retrieval_plan,
            retrieval_result=retrieval_result,
        )

        # Merge protocol steps and normalized guidance into the execution plan
        steps = protocol_guidance.steps if protocol_guidance.steps else normalized_guidance.steps
        warnings = protocol_guidance.warnings if protocol_guidance.warnings else normalized_guidance.warnings
        escalation_triggers = normalized_guidance.escalation_triggers

        logger.info(
            "[ExecutionAgent] Execution plan ready | steps=%d protocol=%s source=%s",
            len(steps),
            protocol_guidance.protocol_key or "none",
            retrieval_result.get("retrieval_source", "unknown"),
        )

        primary_message = (
            "Start CPR now."
            if protocol_guidance.protocol_key == "cpr"
            else (
                steps[0]
                if steps
                else "Follow the grounded safety guidance while help is on the way."
            )
        )
        return ExecutionGuidance(
            scenario=protocol_guidance.protocol_key or ("dispatch_wait" if action in {"dispatch_pending_confirmation", "emergency_dispatch"} else "guided_support"),
            primary_message=primary_message,
            steps=steps,
            warnings=warnings,
            escalation_triggers=escalation_triggers,
            quick_replies=["Done", "Need next step", "Condition worse"],
            protocol_key=protocol_guidance.protocol_key,
            source=retrieval_result.get("retrieval_source", "grounded"),
        )

    # Fallback: build a non-grounded execution plan from the response plan
    logger.info(
        "[ExecutionAgent] Building non-grounded execution plan | action=%s",
        action,
    )
    fallback_guidance = _build_non_grounded_guidance(
        action=action,
        clinical_assessment=clinical_assessment,
    )

    fallback_steps = fallback_guidance.steps
    fallback_message = fallback_guidance.primary_message or (fallback_steps[0] if fallback_steps else "")
    scenario = (
        "dispatch_wait"
        if action in {"dispatch_pending_confirmation", "emergency_dispatch"}
        else ("family_support" if action == "contact_family" else "monitoring")
    )
    return ExecutionGuidance(
        scenario=scenario,
        primary_message=fallback_message,
        steps=fallback_steps,
        warnings=fallback_guidance.warnings,
        escalation_triggers=fallback_guidance.escalation_triggers,
        quick_replies=["Okay", "Pain worse", "Breathing worse"],
        source="non_grounded",
    )
