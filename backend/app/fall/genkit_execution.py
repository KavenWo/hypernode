"""Genkit-backed execution flow for the fall-response backend.

This module introduces a Phase B execution path that uses Genkit for the
execution agent while preserving the current local execution agent as the
fallback. The flow remains intentionally narrow: it consumes an already-decided
action and produces an ``ExecutionPlan``.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field

from agents.shared.schemas import (
    ClinicalAssessmentSummary,
    ExecutionGuidance,
    PatientAnswer,
    UserMedicalProfile,
)

logger = logging.getLogger(__name__)

GENKIT_EXECUTION_MODEL = os.getenv("GENKIT_EXECUTION_MODEL", "googleai/gemini-2.5-flash")


class _GroundedExecutionContext(BaseModel):
    should_ground_guidance: bool = Field(default=False)
    requires_protocol: bool = Field(default=False)
    retrieval_source: str = Field(default="not_requested")
    protocol_key: str = Field(default="")
    grounded_steps: list[str] = Field(default_factory=list)
    protocol_steps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    escalation_triggers: list[str] = Field(default_factory=list)
    forced_protocol_intents: list[str] = Field(default_factory=list)


class GenkitExecutionInput(BaseModel):
    action: str = Field(description="Already-decided action from the reasoning layer.")
    clinical_assessment: ClinicalAssessmentSummary
    patient_profile: UserMedicalProfile
    patient_answers: list[PatientAnswer] = Field(default_factory=list)


def _execution_prompt(input_data: GenkitExecutionInput) -> str:
    profile = input_data.patient_profile
    assessment = input_data.clinical_assessment
    answers = "\n".join(
        f"- {answer.question_id}: {answer.answer}" for answer in input_data.patient_answers
    ) or "- No responder answers available."
    return f"""
You are the Execution Agent for an emergency fall-response workflow.

You are given an already-decided action. You do NOT perform clinical reasoning.
You do NOT change severity or re-triage the patient. Your only job is to
produce narrow structured execution guidance.

Execution rules:
- Use the execution_grounding tool before producing CPR, airway management,
  bleeding control, recovery position, or bystander protocol steps.
- If the tool returns grounded content, prefer it over generic model knowledge.
- If the tool returns no grounded content, produce the safest minimal fallback
  plan from the provided action and assessment.
- Keep steps short, ordered, and practical.
- Keep warnings concrete.
- Keep escalation triggers meaningful.
- Never claim emergency help is already called unless action is emergency_dispatch.
- If action is dispatch_pending_confirmation, speak as pending or preparing.

Current action: {input_data.action}

Clinical assessment:
- severity: {assessment.severity}
- reasoning_summary: {assessment.reasoning_summary}
- red_flags: {", ".join(assessment.red_flags) or "none"}
- missing_facts: {", ".join(assessment.missing_facts) or "none"}
- vulnerability_modifiers: {", ".join(assessment.vulnerability_modifiers) or "none"}

Patient profile:
- age: {profile.age}
- blood_thinners: {profile.blood_thinners}
- conditions: {", ".join(profile.pre_existing_conditions) or "none"}
- mobility_support: {profile.mobility_support}

Conversation context:
{answers}

Return only structured execution guidance matching the schema.
""".strip()


def _build_grounded_execution_context(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> _GroundedExecutionContext:
    from agents.bystander.protocol_grounding import (
        build_protocol_guidance_summary,
        collect_required_protocol_intents,
    )
    from app.fall.assessment_service import (
        _requires_mandatory_protocol_grounding,
        _run_grounded_guidance_stage,
        _should_trigger_grounded_guidance,
        build_interaction_summary,
    )

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

    if not (should_ground_guidance or requires_protocol):
        return _GroundedExecutionContext(
            should_ground_guidance=should_ground_guidance,
            requires_protocol=requires_protocol,
            forced_protocol_intents=forced_protocol_intents,
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

    return _GroundedExecutionContext(
        should_ground_guidance=should_ground_guidance,
        requires_protocol=requires_protocol,
        retrieval_source=retrieval_result.get("retrieval_source", "grounded"),
        protocol_key=protocol_guidance.protocol_key,
        grounded_steps=normalized_guidance.steps,
        protocol_steps=protocol_guidance.steps,
        warnings=protocol_guidance.warnings if protocol_guidance.warnings else normalized_guidance.warnings,
        escalation_triggers=normalized_guidance.escalation_triggers,
        forced_protocol_intents=forced_protocol_intents,
    )


def _fallback_execution_guidance(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
) -> ExecutionGuidance:
    from app.fall.assessment_service import _build_non_grounded_guidance

    fallback_guidance = _build_non_grounded_guidance(
        action=action,
        clinical_assessment=clinical_assessment,
    )
    fallback_steps = fallback_guidance.steps
    scenario = (
        "dispatch_wait"
        if action in {"dispatch_pending_confirmation", "emergency_dispatch"}
        else ("family_support" if action == "contact_family" else "monitoring")
    )
    return ExecutionGuidance(
        scenario=scenario,
        primary_message=fallback_guidance.primary_message or (fallback_steps[0] if fallback_steps else ""),
        steps=fallback_steps,
        warnings=fallback_guidance.warnings,
        escalation_triggers=fallback_guidance.escalation_triggers,
        quick_replies=["Okay", "Pain worse", "Breathing worse"],
        source="non_grounded",
    )


def _import_genkit_symbols() -> tuple[Any, Any]:
    try:
        from genkit import Genkit
    except ImportError:
        from genkit.ai import Genkit  # type: ignore[attr-defined]

    from genkit.plugins.google_genai import GoogleAI

    return Genkit, GoogleAI


@lru_cache(maxsize=1)
def _get_genkit_execution_flow():
    Genkit, GoogleAI = _import_genkit_symbols()
    ai = Genkit(
        plugins=[GoogleAI()],
        model=GENKIT_EXECUTION_MODEL,
    )

    @ai.tool()
    def execution_grounding(input_data: GenkitExecutionInput) -> _GroundedExecutionContext:
        """Retrieve execution-only grounded guidance and protocol context."""

        return _build_grounded_execution_context(
            action=input_data.action,
            clinical_assessment=input_data.clinical_assessment,
            patient_profile=input_data.patient_profile,
            patient_answers=input_data.patient_answers,
        )

    @ai.flow()
    async def execution_plan_flow(input_data: GenkitExecutionInput) -> ExecutionGuidance:
        grounded_context = execution_grounding(input_data)
        response = await ai.generate(
            prompt=_execution_prompt(input_data),
            tools=[execution_grounding],
            output_schema=ExecutionGuidance,
        )

        output: ExecutionGuidance | None = getattr(response, "output", None)
        if output is None:
            raise RuntimeError("Genkit execution flow did not return structured output.")

        if not output.primary_message:
            output.primary_message = output.steps[0] if output.steps else "Follow the safety guidance."
        if not output.scenario:
            output.scenario = grounded_context.protocol_key or (
                "dispatch_wait"
                if input_data.action in {"dispatch_pending_confirmation", "emergency_dispatch"}
                else ("family_support" if input_data.action == "contact_family" else "monitoring")
            )
        if not output.quick_replies:
            output.quick_replies = (
                ["Done", "Need next step", "Condition worse"]
                if grounded_context.should_ground_guidance or grounded_context.requires_protocol
                else ["Okay", "Pain worse", "Breathing worse"]
            )
        if not output.protocol_key and grounded_context.protocol_key:
            output.protocol_key = grounded_context.protocol_key
        if not output.source or output.source == "not_requested":
            output.source = (
                grounded_context.retrieval_source
                if grounded_context.should_ground_guidance or grounded_context.requires_protocol
                else "non_grounded"
            )
        if grounded_context.protocol_key and grounded_context.protocol_steps:
            output.protocol_key = grounded_context.protocol_key
            output.scenario = grounded_context.protocol_key or output.scenario
            output.primary_message = grounded_context.protocol_steps[0]
            output.steps = list(grounded_context.protocol_steps)
            if grounded_context.warnings:
                output.warnings = list(grounded_context.warnings)
            if grounded_context.escalation_triggers:
                output.escalation_triggers = list(grounded_context.escalation_triggers)
            output.source = grounded_context.retrieval_source or output.source or "grounded"
            logger.info(
                "[GenkitExecution] Deterministic protocol override applied | protocol=%s steps=%d source=%s",
                grounded_context.protocol_key,
                len(grounded_context.protocol_steps),
                output.source,
            )
        return output

    return execution_plan_flow


async def run_genkit_execution_plan(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> ExecutionGuidance:
    """Run the Genkit-backed execution flow with safe fallback semantics."""

    try:
        flow = _get_genkit_execution_flow()
    except ImportError as exc:
        raise RuntimeError(
            "Genkit is not installed. Add 'genkit' and 'genkit-plugin-google-genai' to the environment."
        ) from exc

    input_data = GenkitExecutionInput(
        action=action,
        clinical_assessment=clinical_assessment,
        patient_profile=patient_profile,
        patient_answers=patient_answers,
    )

    try:
        guidance = await flow(input_data)
        logger.info(
            "[GenkitExecution] Flow succeeded | action=%s severity=%s source=%s protocol=%s",
            action,
            clinical_assessment.severity,
            guidance.source,
            guidance.protocol_key or "none",
        )
        return guidance
    except Exception:
        logger.exception(
            "[GenkitExecution] Flow failed; falling back to deterministic execution guidance | action=%s",
            action,
        )
        return _fallback_execution_guidance(
            action=action,
            clinical_assessment=clinical_assessment,
        )
