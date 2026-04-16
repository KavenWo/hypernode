"""Smoke checks for the Phase 4 interaction policy."""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from agents.communication.interaction_policy import (  # noqa: E402
    InteractionContext,
    choose_interaction_target,
    should_refresh_reasoning,
)


def main() -> None:
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

    patient_stays_primary = choose_interaction_target(
        InteractionContext(
            patient_response_status="confused",
            bystander_available=True,
            bystander_can_help=False,
            serious_action_required=True,
        )
    )
    assert patient_stays_primary.communication_target == "patient", patient_stays_primary

    no_refresh = should_refresh_reasoning(
        message_text="okay",
        new_fact_keys=[],
        active_execution_action="cpr_in_progress",
    )
    assert not no_refresh.refresh_required, no_refresh

    critical_refresh = should_refresh_reasoning(
        message_text="She is breathing strangely now.",
        new_fact_keys=["abnormal_breathing"],
    )
    assert critical_refresh.refresh_required, critical_refresh
    assert critical_refresh.priority == "critical", critical_refresh

    role_change_refresh = should_refresh_reasoning(
        message_text="I am the bystander now.",
        responder_mode_changed=True,
    )
    assert role_change_refresh.refresh_required, role_change_refresh

    print("Phase 4 interaction policy verified.")


if __name__ == "__main__":
    main()
