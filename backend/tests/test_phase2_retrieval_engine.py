"""Smoke checks for the Phase 2 retrieval engine and its bucketed debug output."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from agents.bystander.retrieval_engine import run_phase2_retrieval
from agents.shared.schemas import PatientAnswer, UserMedicalProfile


def test_retrieval_engine_returns_bucketed_debug_output() -> None:
    profile = UserMedicalProfile(user_id="u3", age=84, blood_thinners=True)
    answers = [
        PatientAnswer(question_id="injury", answer="I hit my head after the fall."),
        PatientAnswer(question_id="mobility", answer="I cannot stand safely."),
    ]

    result = run_phase2_retrieval(
        patient_profile=profile,
        patient_answers=answers,
        severity_hint="critical",
    )

    assert "head_injury_blood_thinners" in result["selected_intents"]
    assert isinstance(result["bucketed_snippets"], dict)
    assert isinstance(result["queries_by_bucket"], dict)
