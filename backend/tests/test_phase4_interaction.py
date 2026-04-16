"""Smoke checks for the Phase 4 interaction policy."""

from agents.communication.interaction_policy import (  # noqa: E402
    InteractionContext,
    choose_interaction_target,
    should_refresh_reasoning,
)


def test_patient_first_targeting() -> None:
    patient_first = choose_interaction_target(
        InteractionContext(
            patient_response_status="unknown",
            bystander_available=True,
            bystander_can_help=False,
            serious_action_required=False,
        )
    )
    assert patient_first.communication_target == "patient", patient_first
    assert patient_first.interaction_mode == "patient_first_check", patient_first


def test_bystander_takeover_when_patient_is_unresponsive() -> None:
    bystander_takeover = choose_interaction_target(
        InteractionContext(
            patient_response_status="unresponsive",
            bystander_available=True,
            bystander_can_help=True,
            serious_action_required=True,
        )
    )
    assert bystander_takeover.communication_target == "bystander", bystander_takeover
    assert bystander_takeover.interaction_mode == "bystander_urgent_takeover", bystander_takeover


def test_testing_override_enables_bystander_flow() -> None:
    testing_flow = choose_interaction_target(
        InteractionContext(
            patient_response_status="unknown",
            bystander_available=True,
            bystander_can_help=False,
            serious_action_required=True,
            testing_assume_bystander=True,
        )
    )
    assert testing_flow.communication_target == "bystander", testing_flow
    assert testing_flow.interaction_mode == "bystander_test_flow", testing_flow


def test_patient_stays_primary_without_ready_helper() -> None:
    patient_stays_primary = choose_interaction_target(
        InteractionContext(
            patient_response_status="confused",
            bystander_available=True,
            bystander_can_help=False,
            serious_action_required=True,
        )
    )
    assert patient_stays_primary.communication_target == "patient", patient_stays_primary


def test_low_signal_acknowledgement_does_not_refresh_reasoning() -> None:
    no_refresh = should_refresh_reasoning(
        message_text="okay",
        new_fact_keys=[],
        active_execution_action="cpr_in_progress",
    )
    assert not no_refresh.refresh_required, no_refresh


def test_critical_fact_refreshes_reasoning() -> None:
    critical_refresh = should_refresh_reasoning(
        message_text="She is breathing strangely now.",
        new_fact_keys=["abnormal_breathing"],
    )
    assert critical_refresh.refresh_required, critical_refresh
    assert critical_refresh.priority == "critical", critical_refresh


def test_role_change_refreshes_reasoning() -> None:
    role_change_refresh = should_refresh_reasoning(
        message_text="I am the bystander now.",
        responder_mode_changed=True,
    )
    assert role_change_refresh.refresh_required, role_change_refresh
