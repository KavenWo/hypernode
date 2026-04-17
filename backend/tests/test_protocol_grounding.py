"""Checks for mandatory-grounding protocol activation and readiness."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from agents.bystander.protocol_grounding import (  # noqa: E402
    build_protocol_guidance_summary,
    collect_required_protocol_intents,
    identify_protocol_candidate,
    load_protocol_grounding_policy,
)
from agents.shared.schemas import (  # noqa: E402
    ClinicalAssessmentSummary,
    ResponseActionItem,
    ResponsePlanSummary,
)


def _clinical_with_bystander_actions(*action_types: str) -> ClinicalAssessmentSummary:
    return ClinicalAssessmentSummary(
        severity="critical",
        clinical_confidence_score=0.85,
        clinical_confidence_band="high",
        action_confidence_score=0.82,
        action_confidence_band="high",
        reasoning_summary="test",
        response_plan=ResponsePlanSummary(
            bystander_actions=[
                ResponseActionItem(type=action_type, priority="immediate", reason="test")
                for action_type in action_types
            ]
        ),
    )


def test_protocol_grounding_policy_loads() -> None:
    policy = load_protocol_grounding_policy()
    assert policy["policy_version"] == "protocol_grounding_v1"
    assert "cpr" in policy["protocols"]


def test_identify_protocol_candidate_for_cpr() -> None:
    clinical = _clinical_with_bystander_actions("start_cpr_guidance", "retrieve_aed_if_available")
    assert identify_protocol_candidate(clinical_assessment=clinical) == "cpr"


def test_collect_required_protocol_intents_for_emergency_actions() -> None:
    clinical = _clinical_with_bystander_actions("check_breathing", "apply_pressure_to_bleeding")
    intents = collect_required_protocol_intents(clinical_assessment=clinical)

    assert "abnormal_breathing_after_fall" in intents
    assert "bystander_check_breathing" in intents
    assert "severe_bleeding_after_fall" in intents


def test_protocol_guidance_ready_when_required_intent_and_steps_exist() -> None:
    clinical = _clinical_with_bystander_actions("start_cpr_guidance")
    protocol = build_protocol_guidance_summary(
        clinical_assessment=clinical,
        retrieval_plan={"selected_intents": ["cpr_trigger_guidance"]},
        retrieval_result={
            "bucketed_snippets": {
                "cpr_or_airway_steps": [
                    "Start CPR now if the patient is not breathing normally.",
                    "Begin chest compressions in the center of the chest.",
                ],
                "do_not_do_warnings": [
                    "Do not delay emergency help while beginning CPR.",
                ],
            }
        },
    )

    assert protocol.protocol_key == "cpr"
    assert protocol.grounding_status == "ready"
    assert protocol.ready_for_communication is True
    assert protocol.steps


def test_protocol_guidance_blocked_without_required_intent() -> None:
    clinical = _clinical_with_bystander_actions("start_cpr_guidance")
    protocol = build_protocol_guidance_summary(
        clinical_assessment=clinical,
        retrieval_plan={"selected_intents": ["fall_general_first_aid"]},
        retrieval_result={
            "bucketed_snippets": {
                "cpr_or_airway_steps": [
                    "Begin chest compressions.",
                ]
            }
        },
    )

    assert protocol.protocol_key == "cpr"
    assert protocol.grounding_status == "blocked"
    assert protocol.ready_for_communication is False
