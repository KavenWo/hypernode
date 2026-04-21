"""Guidance normalization helpers that turn retrieval buckets into product-facing primary steps, warnings, and escalation triggers."""

from __future__ import annotations

from agents.shared.schemas import GuidanceSummary


def _first_from_bucket(buckets: dict[str, list[str]], bucket_names: list[str]) -> str | None:
    for bucket_name in bucket_names:
        values = buckets.get(bucket_name, [])
        if values:
            return values[0]
    return None


def _merge_bucket_values(
    buckets: dict[str, list[str]],
    bucket_names: list[str],
    *,
    limit: int,
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for bucket_name in bucket_names:
        for value in buckets.get(bucket_name, []):
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
            if len(merged) >= limit:
                return merged
    return merged


def normalize_guidance_from_buckets(
    *,
    buckets: dict[str, list[str]],
    action: str,
) -> GuidanceSummary:
    primary_message = _first_from_bucket(
        buckets,
        ["cpr_or_airway_steps", "immediate_actions", "bystander_instructions", "monitoring_and_followup"],
    )

    if not primary_message:
        if action in {"dispatch_pending_confirmation", "emergency_dispatch"}:
            primary_message = "Stay still and wait for emergency help."
        elif action == "contact_family":
            primary_message = "Stay in a safe position and contact a caregiver or family member."
        else:
            primary_message = "Monitor symptoms and avoid standing up too quickly."

    steps = _merge_bucket_values(
        buckets,
        ["cpr_or_airway_steps", "immediate_actions", "bystander_instructions", "monitoring_and_followup"],
        limit=4,
    )

    if not steps:
        steps = [primary_message]

    warnings = _merge_bucket_values(
        buckets,
        ["do_not_do_warnings"],
        limit=3,
    )

    escalation_triggers = _merge_bucket_values(
        buckets,
        ["red_flags_and_escalation"],
        limit=3,
    )

    return GuidanceSummary(
        primary_message=primary_message,
        steps=steps,
        warnings=warnings,
        escalation_triggers=escalation_triggers,
    )
