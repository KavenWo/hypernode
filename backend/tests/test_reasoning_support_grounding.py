"""Smoke checks for the reasoning-support grounding policy and intent selection."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from agents.reasoning.support_grounding import (  # noqa: E402
    build_reasoning_support_plan,
    load_reasoning_support_policy,
)
from agents.shared.schemas import ClinicalAssessmentSummary, PatientAnswer, UserMedicalProfile  # noqa: E402


def _clinical_summary(**updates) -> ClinicalAssessmentSummary:
    base = ClinicalAssessmentSummary(
        severity="critical",
        clinical_confidence_score=0.82,
        clinical_confidence_band="high",
        action_confidence_score=0.79,
        action_confidence_band="high",
        red_flags=["head_strike", "blood_thinner_use"],
        vulnerability_modifiers=["blood_thinner_use"],
        blocking_uncertainties=["head_strike_unconfirmed"],
        reasoning_summary="test",
    )
    return base.model_copy(update=updates)


def test_reasoning_support_policy_file_loads() -> None:
    policy = load_reasoning_support_policy()
    assert policy["policy_version"] == "reasoning_support_v1"
    assert "special_risk_factors_reasoning" in policy["intents"]


def test_reasoning_support_prioritizes_special_risk_factors() -> None:
    plan = build_reasoning_support_plan(
        patient_profile=UserMedicalProfile(user_id="u1", age=80, blood_thinners=True),
        patient_answers=[
            PatientAnswer(question_id="injury", answer="He hit his head and is dizzy."),
            PatientAnswer(question_id="mobility", answer="He cannot stand."),
        ],
        clinical_assessment=_clinical_summary(),
    )

    assert "special_risk_factors_reasoning" in plan["selected_intents"]
    assert any("blood thinners" in query or "risk factors" in query for query in plan["queries"])
