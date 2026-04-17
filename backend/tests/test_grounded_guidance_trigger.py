"""Checks for when grounded guidance retrieval should or should not run."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from app.fall.assessment_service import _should_trigger_grounded_guidance
from agents.shared.schemas import (
    ClinicalAssessmentSummary,
    EscalationActionSummary,
    InteractionSummary,
    ReasoningRefreshSummary,
    ResponseActionItem,
    ResponsePlanSummary,
)


def _interaction(target: str) -> InteractionSummary:
    return InteractionSummary(
        communication_target=target,
        responder_mode=target if target in {"patient", "bystander"} else "patient",
        guidance_style="patient_calm_direct",
        interaction_mode="patient_first_check",
        rationale="test",
    reasoning_refresh=ReasoningRefreshSummary(required=False, reason="test"),
    )


def _clinical(response_plan: ResponsePlanSummary) -> ClinicalAssessmentSummary:
    return ClinicalAssessmentSummary(
        severity="low",
        clinical_confidence_score=0.7,
        clinical_confidence_band="medium",
        action_confidence_score=0.7,
        action_confidence_band="medium",
        reasoning_summary="test",
        response_plan=response_plan,
    )


def test_grounded_guidance_triggers_for_urgent_actions() -> None:
    clinical = _clinical(ResponsePlanSummary())
    assert _should_trigger_grounded_guidance(
        action="dispatch_pending_confirmation",
        clinical_assessment=clinical,
        interaction_summary=_interaction("patient"),
        allow_grounding=True,
    )


def test_grounded_guidance_triggers_for_bystander_execution() -> None:
    clinical = _clinical(
        ResponsePlanSummary(
            bystander_actions=[
                ResponseActionItem(type="check_breathing", priority="immediate", reason="test"),
            ],
            escalation_action=EscalationActionSummary(),
        )
    )
    assert _should_trigger_grounded_guidance(
        action="monitor",
        clinical_assessment=clinical,
        interaction_summary=_interaction("bystander"),
        allow_grounding=True,
    )


def test_grounded_guidance_skips_for_low_risk_patient_monitoring() -> None:
    clinical = _clinical(
        ResponsePlanSummary(
            followup_actions=[
                ResponseActionItem(type="monitor_for_worsening_signs", priority="ongoing", reason="test"),
            ],
            escalation_action=EscalationActionSummary(),
        )
    )
    assert not _should_trigger_grounded_guidance(
        action="monitor",
        clinical_assessment=clinical,
        interaction_summary=_interaction("patient"),
        allow_grounding=True,
    )
