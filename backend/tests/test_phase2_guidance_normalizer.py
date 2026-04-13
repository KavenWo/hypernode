"""Smoke checks for normalizing bucketed retrieval evidence into MVP guidance fields."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from agents.bystander.guidance_normalizer import normalize_guidance_from_buckets


def test_normalizer_prefers_airway_bucket_for_primary_message() -> None:
    guidance = normalize_guidance_from_buckets(
        buckets={
            "cpr_or_airway_steps": ["Start CPR if the person is not breathing normally."],
            "immediate_actions": ["Keep the patient still."],
            "do_not_do_warnings": ["Do not delay emergency help."],
            "red_flags_and_escalation": ["Not breathing normally requires urgent escalation."],
        },
        action="emergency_dispatch",
    )

    assert guidance.primary_message == "Start CPR if the person is not breathing normally."
    assert guidance.warnings == ["Do not delay emergency help."]
    assert guidance.escalation_triggers == ["Not breathing normally requires urgent escalation."]
