"""Smoke checks for the deterministic clinical reasoning policy and policy asset."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from agents.reasoning.clinical_reasoning_policy import (
    load_clinical_reasoning_policy,
    run_clinical_reasoning_policy,
)
from agents.shared.schemas import FallEvent, PatientAnswer, UserMedicalProfile, VisionAssessment, VitalAssessment


def test_clinical_reasoning_policy_file_loads() -> None:
    policy = load_clinical_reasoning_policy()
    assert policy["policy_version"] == "clinical_reasoning_policy_v1"
    assert "breathing_status_unconfirmed" in policy["missing_fact_priority"]


def test_clinical_reasoning_policy_escalates_explicit_airway_case() -> None:
    outcome = run_clinical_reasoning_policy(
        event=FallEvent(
            user_id="u1",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="no_movement",
            confidence_score=0.96,
        ),
        patient_profile=UserMedicalProfile(user_id="u1", age=72),
        vision_assessment=VisionAssessment(
            fall_detected=True,
            severity_hint="critical",
            reasoning="No movement after a sudden descent.",
        ),
        vital_assessment=VitalAssessment(
            anomaly_detected=True,
            severity_hint="critical",
            reasoning="SpO2 is low and blood pressure is unstable.",
        ),
        patient_answers=[
            PatientAnswer(question_id="consciousness", answer="The patient is barely responding."),
            PatientAnswer(question_id="breathing", answer="He is breathing strangely after the fall."),
        ],
    )

    assert outcome.severity == "critical"
    assert outcome.recommended_action == "emergency_dispatch"
    assert "abnormal_breathing" in outcome.signals.red_flags
    assert outcome.signals.hard_emergency_triggered is True
    assert outcome.response_plan.escalation_action.type == "emergency_dispatch"
    assert any(
        item.type in {"check_breathing", "start_cpr_guidance"}
        for item in outcome.response_plan.bystander_actions
    )


def test_clinical_reasoning_policy_surfaces_priority_missing_fact() -> None:
    outcome = run_clinical_reasoning_policy(
        event=FallEvent(
            user_id="u2",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="rapid_descent",
            confidence_score=0.93,
        ),
        patient_profile=UserMedicalProfile(user_id="u2", age=80, blood_thinners=True),
        vision_assessment=VisionAssessment(
            fall_detected=True,
            severity_hint="critical",
            reasoning="High-confidence rapid descent.",
        ),
        vital_assessment=VitalAssessment(
            anomaly_detected=True,
            severity_hint="medium",
            reasoning="Tachycardia without severe hypoxia.",
        ),
        patient_answers=[
            PatientAnswer(question_id="consciousness", answer="Yes, I am awake but dizzy."),
            PatientAnswer(question_id="mobility", answer="I have strong pain and cannot stand."),
        ],
    )

    assert outcome.severity == "critical"
    assert outcome.recommended_action == "dispatch_pending_confirmation"
    assert outcome.signals.priority_missing_fact in {"breathing_status_unconfirmed", "head_strike_unconfirmed"}
    assert outcome.signals.blocking_uncertainties
    assert outcome.response_plan.notification_actions


def test_clinical_reasoning_policy_keeps_simple_fall_in_support_flow() -> None:
    outcome = run_clinical_reasoning_policy(
        event=FallEvent(
            user_id="u3",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="rapid_descent",
            confidence_score=0.91,
        ),
        patient_profile=UserMedicalProfile(user_id="u3", age=78),
        vision_assessment=VisionAssessment(
            fall_detected=True,
            severity_hint="critical",
            reasoning="Rapid descent was detected.",
        ),
        vital_assessment=VitalAssessment(
            anomaly_detected=False,
            severity_hint="low",
            reasoning="Vitals are stable.",
        ),
        patient_answers=[
            PatientAnswer(question_id="status", answer="I am okay and breathing okay."),
            PatientAnswer(question_id="pain", answer="Just sore with mild pain. I can stand."),
        ],
    )

    assert outcome.severity in {"low", "medium"}
    assert outcome.recommended_action in {"monitor", "contact_family"}
    assert "awake_and_answering" in outcome.signals.protective_signals
    assert "breathing_normally" in outcome.signals.protective_signals
