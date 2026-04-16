"""Phase 4 interaction policy helpers.

This module introduces a lightweight interaction-controller layer for the MVP.
It does not replace the reasoning agent. Instead, it decides:

- who the system should address right now
- whether the interaction should stay in guidance mode
- whether a new reasoning pass is actually required

The intent is to let the text MVP behave more like a responder-facing assistant
now, while keeping the contract transport-neutral enough for future live mode.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


CRITICAL_REASONING_FACT_KEYS = {
    "abnormal_breathing",
    "not_breathing",
    "severe_bleeding",
    "unresponsive",
    "lost_consciousness",
    "head_strike",
    "chest_pain",
    "new_confusion",
    "seizure",
}

PROTECTIVE_REASONING_FACT_KEYS = {
    "breathing_normal",
    "mild_pain",
    "patient_ok",
    "stable_speaking",
}

LOW_SIGNAL_ACKNOWLEDGEMENTS = {
    "ok",
    "okay",
    "done",
    "checking",
    "i am checking",
    "i'm checking",
    "understood",
    "got it",
}

GUIDANCE_ONLY_ACTIONS = {
    "cpr_in_progress",
    "recovery_position_guidance",
    "bleeding_control_guidance",
    "keep_patient_still",
}


class InteractionContext(BaseModel):
    """Small state snapshot used to pick the communication focus."""

    patient_response_status: str = Field(
        default="unknown",
        description="One of responsive, confused, unresponsive, unknown, or no_response.",
    )
    bystander_available: bool = Field(
        default=False,
        description="Whether a bystander is known or assumed to be available.",
    )
    bystander_can_help: bool = Field(
        default=False,
        description="Whether the bystander is actually able and willing to follow instructions.",
    )
    serious_action_required: bool = Field(
        default=False,
        description="Whether the current plan already requires hands-on execution or urgent observation.",
    )
    testing_assume_bystander: bool = Field(
        default=False,
        description="Testing override so the MVP can exercise bystander communication paths.",
    )
    active_execution_action: str | None = Field(
        default=None,
        description="Current step-guidance action such as cpr_in_progress.",
    )
    responder_mode_hint: str | None = Field(
        default=None,
        description="Optional existing responder hint from the session state.",
    )


class InteractionDecision(BaseModel):
    """Decision returned to the caller after applying the interaction policy."""

    communication_target: str = Field(
        ...,
        description="Who the system should address now: patient, bystander, or no_response.",
    )
    responder_mode: str = Field(
        ...,
        description="Normalized responder mode for the current turn.",
    )
    guidance_style: str = Field(
        ...,
        description="Formatting style such as patient_calm_direct or bystander_stepwise.",
    )
    interaction_mode: str = Field(
        ...,
        description="Mode name such as patient_first_check, bystander_execution, or urgent_no_response.",
    )
    rationale: str = Field(
        ...,
        description="Short explanation for debugging and MVP visibility.",
    )


class ReasoningRefreshDecision(BaseModel):
    """Decision for whether a new reasoning pass should run."""

    refresh_required: bool = Field(..., description="Whether the reasoning engine should refresh now.")
    reason: str = Field(..., description="Short explanation of why a refresh is or is not needed.")
    priority: str = Field(..., description="critical, medium, or low.")


def choose_interaction_target(context: InteractionContext) -> InteractionDecision:
    """Pick who the communication layer should address right now.

    Policy summary:
    - Start patient-first whenever response ability is still plausible.
    - Switch toward the bystander when hands-on action is required or the patient
      cannot safely self-report.
    - Allow a testing override so the MVP can exercise bystander flows.
    """

    status = (context.patient_response_status or "unknown").strip().lower()

    helper_ready = context.bystander_available and context.bystander_can_help

    if context.testing_assume_bystander and context.bystander_available:
        return InteractionDecision(
            communication_target="bystander",
            responder_mode="bystander",
            guidance_style="bystander_stepwise",
            interaction_mode="bystander_test_flow",
            rationale="Testing mode assumes a bystander is available so the MVP can exercise the full guided-assistance flow.",
        )

    if status in {"unresponsive", "no_response"}:
        if helper_ready:
            return InteractionDecision(
                communication_target="bystander",
                responder_mode="bystander",
                guidance_style="bystander_stepwise",
                interaction_mode="bystander_urgent_takeover",
                rationale="The patient is not responding, so the system should shift to the bystander for observation and action.",
            )
        return InteractionDecision(
            communication_target="no_response",
            responder_mode="no_response",
            guidance_style="urgent_minimal",
            interaction_mode="urgent_no_response",
            rationale="No patient response and no ready helper is available, so the system must move into urgent no-response handling.",
        )

    if context.serious_action_required and helper_ready:
        return InteractionDecision(
            communication_target="bystander",
            responder_mode="bystander",
            guidance_style="bystander_stepwise",
            interaction_mode="bystander_execution",
            rationale="Hands-on action is needed, so the bystander should receive direct step-based guidance.",
        )

    if status == "confused" and helper_ready:
        return InteractionDecision(
            communication_target="bystander",
            responder_mode="bystander",
            guidance_style="bystander_stepwise",
            interaction_mode="bystander_supported_patient",
            rationale="The patient is confused and a bystander is available, so communication should shift toward the helper.",
        )

    return InteractionDecision(
        communication_target="patient",
        responder_mode="patient",
        guidance_style="patient_calm_direct",
        interaction_mode="patient_first_check",
        rationale="Incidents should begin with a patient-first check whenever the patient may still be able to respond.",
    )


def should_refresh_reasoning(
    *,
    message_text: str,
    new_fact_keys: list[str] | None = None,
    previous_action: str | None = None,
    responder_mode_changed: bool = False,
    contradiction_detected: bool = False,
    no_response_timeout: bool = False,
    active_execution_action: str | None = None,
) -> ReasoningRefreshDecision:
    """Decide whether a new reasoning pass is necessary for the current turn."""

    normalized_message = " ".join((message_text or "").strip().lower().split())
    facts = {item.strip().lower() for item in (new_fact_keys or []) if item and item.strip()}

    if no_response_timeout:
        return ReasoningRefreshDecision(
            refresh_required=True,
            reason="A no-response timeout can change escalation behavior and should trigger a new reasoning pass.",
            priority="critical",
        )

    if responder_mode_changed:
        return ReasoningRefreshDecision(
            refresh_required=True,
            reason="A responder-role change affects which questions and instructions are appropriate.",
            priority="medium",
        )

    if contradiction_detected:
        return ReasoningRefreshDecision(
            refresh_required=True,
            reason="A contradiction was detected in the incoming information and the reasoning state should be reevaluated.",
            priority="critical",
        )

    critical_facts = sorted(facts.intersection(CRITICAL_REASONING_FACT_KEYS))
    if critical_facts:
        return ReasoningRefreshDecision(
            refresh_required=True,
            reason=f"Critical new facts were reported: {', '.join(critical_facts)}.",
            priority="critical",
        )

    protective_facts = sorted(facts.intersection(PROTECTIVE_REASONING_FACT_KEYS))
    if protective_facts and previous_action in {"dispatch_pending_confirmation", "emergency_dispatch", "contact_family"}:
        return ReasoningRefreshDecision(
            refresh_required=True,
            reason=f"Reassuring new facts were reported: {', '.join(protective_facts)}.",
            priority="medium",
        )

    if normalized_message in LOW_SIGNAL_ACKNOWLEDGEMENTS:
        return ReasoningRefreshDecision(
            refresh_required=False,
            reason="The message is only a low-signal acknowledgement and does not materially change the clinical state.",
            priority="low",
        )

    if active_execution_action in GUIDANCE_ONLY_ACTIONS and not facts:
        return ReasoningRefreshDecision(
            refresh_required=False,
            reason="Guidance is already in execution mode and no new risk-changing information was supplied.",
            priority="low",
        )

    if facts:
        return ReasoningRefreshDecision(
            refresh_required=True,
            reason="New structured facts were reported and the reasoning state should be updated.",
            priority="medium",
        )

    return ReasoningRefreshDecision(
        refresh_required=False,
        reason="No new critical information was detected, so the interaction can continue without refreshing reasoning yet.",
        priority="low",
    )
