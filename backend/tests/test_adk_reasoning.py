"""Regression tests for ADK reasoning payload normalization."""

from __future__ import annotations

from app.fall.adk_reasoning import REASONING_AGENT_INSTRUCTION, _normalize_draft_payload, _reasoning_prompt
from agents.shared.schemas import FallEvent, UserMedicalProfile, VisionAssessment


def test_normalize_draft_payload_coerces_boolean_blocking_uncertainties() -> None:
    normalized = _normalize_draft_payload(
        {
            "severity": "medium",
            "recommended_action": "contact_family",
            "reasoning_summary": "Needs follow-up.",
            "blocking_uncertainties": True,
        }
    )

    assert normalized["blocking_uncertainties"] == []


def test_normalize_draft_payload_wraps_string_list_fields() -> None:
    normalized = _normalize_draft_payload(
        {
            "severity": "low",
            "recommended_action": "monitor",
            "reasoning_summary": "Stable for now.",
            "missing_facts": "breathing_status_unconfirmed",
        }
    )

    assert normalized["missing_facts"] == ["breathing_status_unconfirmed"]


def test_reasoning_instruction_explicitly_forbids_boolean_list_fields() -> None:
    assert "For every list field, return `[]` when there are no items." in REASONING_AGENT_INSTRUCTION
    assert "Never return booleans, null, numbers, or objects for list fields." in REASONING_AGENT_INSTRUCTION
    assert '"blocking_uncertainties": ["head_strike_unconfirmed"]' in REASONING_AGENT_INSTRUCTION


def test_reasoning_prompt_repeats_schema_reminders() -> None:
    prompt = _reasoning_prompt(
        event=FallEvent(
            user_id="u1",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="rapid_descent",
            confidence_score=0.93,
        ),
        patient_profile=UserMedicalProfile(user_id="u1", age=79, blood_thinners=True),
        vision_assessment=VisionAssessment(
            fall_detected=True,
            severity_hint="critical",
            reasoning="Rapid descent detected with no immediate recovery.",
        ),
        vital_assessment=None,
        grounded_medical_guidance=["Consider occult injury risk in older adults on blood thinners."],
        phase3_context="priority_missing_fact=head_strike_unconfirmed",
        patient_answers=[],
    )

    assert "Every list field must be a JSON array of strings" in prompt
    assert 'Use "" for override_policy when there is no override.' in prompt
    assert "Use false for hard_emergency_triggered" in prompt
