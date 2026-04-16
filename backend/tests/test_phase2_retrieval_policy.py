"""Smoke checks for the Phase 2 retrieval policy asset and intent selection behavior."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from agents.bystander.retrieval_policy import (
    build_phase2_bucket_query_plan,
    build_phase2_retrieval_plan,
    load_phase2_retrieval_policy,
)
from agents.shared.schemas import PatientAnswer, UserMedicalProfile


def test_phase2_policy_file_loads() -> None:
    policy = load_phase2_retrieval_policy()
    assert policy["policy_version"] == "phase2_retrieval_v1"
    assert "head_injury_blood_thinners" in policy["intents"]


def test_prioritizes_cpr_query_for_breathing_emergency() -> None:
    profile = UserMedicalProfile(user_id="u1", age=78)
    answers = [PatientAnswer(question_id="breathing", answer="He is not breathing and needs help now.")]

    plan = build_phase2_retrieval_plan(
        patient_profile=profile,
        patient_answers=answers,
        severity_hint="critical",
    )

    assert plan["selected_intents"][0] == "cpr_trigger_guidance"
    assert "CPR" in plan["primary_query"] or "cpr" in plan["primary_query"].lower()


def test_prioritizes_head_injury_on_blood_thinners() -> None:
    profile = UserMedicalProfile(user_id="u2", age=82, blood_thinners=True)
    answers = [
        PatientAnswer(question_id="injury", answer="I hit my head and feel dizzy after the fall."),
        PatientAnswer(question_id="mobility", answer="I cannot stand safely."),
    ]

    plan = build_phase2_retrieval_plan(
        patient_profile=profile,
        patient_answers=answers,
        severity_hint="critical",
    )

    assert "head_injury_blood_thinners" in plan["selected_intents"]
    assert any("blood thinners" in query for query in plan["queries"])


def test_builds_bucket_queries_for_mixed_case() -> None:
    profile = UserMedicalProfile(user_id="u4", age=79)
    answers = [PatientAnswer(question_id="breathing", answer="The patient is breathing strangely and I am a bystander.")]

    plan = build_phase2_bucket_query_plan(
        patient_profile=profile,
        patient_answers=answers,
        severity_hint="critical",
    )

    assert "cpr_or_airway_steps" in plan["queries_by_bucket"]
    assert "red_flags_and_escalation" in plan["queries_by_bucket"]
