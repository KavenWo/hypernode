"""Helpers for turning grounded retrieval output into protocol-specific guidance state."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from agents.shared.schemas import (
    ClinicalAssessmentSummary,
    ProtocolGuidanceSummary,
    ResponseActionItem,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
POLICY_PATH = BACKEND_DIR / "data" / "protocol_grounding_policy.json"


@lru_cache(maxsize=1)
def load_protocol_grounding_policy() -> dict:
    """Load the mandatory-grounding protocol policy from disk once per process."""

    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _action_types(items: list[ResponseActionItem]) -> set[str]:
    """Extract the action vocabulary keys from a response-plan action list."""

    return {item.type for item in items}


_METADATA_LABELS = (
    "purpose",
    "tags",
    "drabc context",
    "step-by-step content",
    "decision logic",
    "important notes",
    "next step",
)


def _sanitize_protocol_step(raw_text: str) -> str:
    """Compress retrieval-heavy protocol chunks into a short responder-facing step.

    Vertex extractive segments sometimes return an entire handbook section with
    headings and metadata. Communication should receive only one short
    executable step, never the whole reference block.
    """

    text = " ".join((raw_text or "").split())
    if not text:
        return ""

    lower_text = text.lower()
    cut_positions = [
        lower_text.find(label)
        for label in _METADATA_LABELS
        if lower_text.find(label) > 0
    ]
    if cut_positions:
        text = text[: min(cut_positions)].strip()

    numbered_split = re.split(r"\s+\d+\.\s+", text, maxsplit=1)
    if len(numbered_split) > 1:
        text = numbered_split[0].strip()

    sentence_candidates = [
        candidate.strip()
        for candidate in re.split(r"(?<=[.!?])\s+", text)
        if candidate.strip()
    ]
    if sentence_candidates:
        text = sentence_candidates[0]

    text = re.sub(r"^[A-Z][A-Za-z\s()/-]{18,}?\s+-\s+", "", text).strip()
    text = re.sub(r"^[A-Z][A-Za-z\s()/-]{18,}?\s+", "", text).strip()

    if len(text) > 160:
        text = text[:157].rstrip(" ,;:-") + "..."

    return text


def _active_action_types(clinical_assessment: ClinicalAssessmentSummary) -> set[str]:
    """Collect all action keys that can activate grounded responder protocols."""

    return {
        *_action_types(clinical_assessment.response_plan.bystander_actions),
        *_action_types(clinical_assessment.response_plan.followup_actions),
    }


def identify_protocol_candidate(*, clinical_assessment: ClinicalAssessmentSummary) -> str | None:
    """Return the highest-priority protocol key suggested by the current response plan."""

    policy = load_protocol_grounding_policy()
    active_action_types = _active_action_types(clinical_assessment)
    if not active_action_types:
        return None

    ordered_protocols = sorted(
        policy.get("protocols", {}).items(),
        key=lambda item: item[1].get("priority", 999),
    )
    for protocol_key, protocol_policy in ordered_protocols:
        activation_action_types = set(protocol_policy.get("activation_action_types", []))
        if active_action_types.intersection(activation_action_types):
            return protocol_key
    return None


def collect_required_protocol_intents(*, clinical_assessment: ClinicalAssessmentSummary) -> list[str]:
    """Return the retrieval intents that must be forced for active grounded protocols."""

    policy = load_protocol_grounding_policy()
    active_action_types = _active_action_types(clinical_assessment)
    ordered_protocols = sorted(
        policy.get("protocols", {}).items(),
        key=lambda item: item[1].get("priority", 999),
    )

    forced_intents: list[str] = []
    seen: set[str] = set()
    for _, protocol_policy in ordered_protocols:
        activation_action_types = set(protocol_policy.get("activation_action_types", []))
        if not active_action_types.intersection(activation_action_types):
            continue
        for intent in protocol_policy.get("required_intents", []):
            if intent in seen:
                continue
            seen.add(intent)
            forced_intents.append(intent)
    return forced_intents


def build_protocol_guidance_summary(
    *,
    clinical_assessment: ClinicalAssessmentSummary,
    retrieval_plan: dict | None,
    retrieval_result: dict | None,
) -> ProtocolGuidanceSummary:
    """Build a structured protocol state for communication and execution consumers.

    The protocol is only marked ready when:
    - the response plan activates a protocol candidate
    - policy marks grounding as required
    - the relevant retrieval intent actually ran
    - grounded steps were returned for the protocol's preferred buckets
    """

    policy = load_protocol_grounding_policy()
    protocol_key = identify_protocol_candidate(clinical_assessment=clinical_assessment)
    if not protocol_key:
        return ProtocolGuidanceSummary(
            protocol_key="",
            grounding_required=False,
            grounding_status="not_needed",
            rationale="No mandatory-grounding protocol was activated by the current response plan.",
        )

    protocol_policy = policy["protocols"].get(protocol_key, {})
    grounding_required = bool(protocol_policy.get("grounding_required", False))
    required_intents = protocol_policy.get("required_intents", [])
    required_intent_mode = protocol_policy.get("required_intent_mode", "all")
    preferred_buckets = protocol_policy.get("preferred_buckets", [])
    selected_intents = retrieval_plan.get("selected_intents", []) if retrieval_plan else []
    bucketed_snippets = retrieval_result.get("bucketed_snippets", {}) if retrieval_result else {}

    steps: list[str] = []
    for bucket_name in preferred_buckets:
        steps.extend(bucketed_snippets.get(bucket_name, []))

    deduped_steps: list[str] = []
    seen: set[str] = set()
    for step in steps:
        normalized = _sanitize_protocol_step(step)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped_steps.append(normalized)

    missing_required_intents = [intent for intent in required_intents if intent not in selected_intents]
    has_required_intents = (
        any(intent in selected_intents for intent in required_intents)
        if required_intent_mode == "any"
        else not missing_required_intents
    )
    if grounding_required and retrieval_result is None:
        return ProtocolGuidanceSummary(
            protocol_key=protocol_key,
            title=protocol_policy.get("title", protocol_key.replace("_", " ").title()),
            grounding_required=True,
            grounding_status="pending",
            rationale="The protocol was activated, but grounded retrieval has not run yet.",
        )

    if grounding_required and not has_required_intents:
        return ProtocolGuidanceSummary(
            protocol_key=protocol_key,
            title=protocol_policy.get("title", protocol_key.replace("_", " ").title()),
            grounding_required=True,
            grounding_status="blocked",
            retrieval_intents=selected_intents,
            rationale=(
                f"Grounded retrieval did not include the required protocol intents: {', '.join(required_intents)}."
                if required_intent_mode == "any"
                else f"Grounded retrieval did not include the required protocol intents: {', '.join(missing_required_intents)}."
            ),
        )

    if grounding_required and not deduped_steps:
        return ProtocolGuidanceSummary(
            protocol_key=protocol_key,
            title=protocol_policy.get("title", protocol_key.replace("_", " ").title()),
            grounding_required=True,
            grounding_status="blocked",
            retrieval_intents=selected_intents,
            rationale="Grounded retrieval completed, but no protocol steps were returned for the required buckets.",
        )

    primary_message = deduped_steps[0] if deduped_steps else ""
    return ProtocolGuidanceSummary(
        protocol_key=protocol_key,
        title=protocol_policy.get("title", protocol_key.replace("_", " ").title()),
        grounding_required=grounding_required,
        grounding_status="ready" if deduped_steps or not grounding_required else "blocked",
        retrieval_intents=selected_intents,
        primary_message=primary_message,
        steps=deduped_steps[:5],
        warnings=bucketed_snippets.get("do_not_do_warnings", [])[:3],
        communication_message=protocol_policy.get("communication_message", primary_message),
        ready_for_communication=bool(deduped_steps or not grounding_required),
        rationale=(
            "Protocol grounding is ready and communication may present the grounded steps."
            if deduped_steps or not grounding_required
            else "Protocol grounding is not ready for communication."
        ),
    )
