"""Phase 2 retrieval engine that runs planned queries, groups grounded snippets into buckets, and returns debug-friendly retrieval output."""

from __future__ import annotations

from collections import defaultdict

from agents.bystander.knowledge_base import retrieve_medical_guidance_with_source
from agents.bystander.retrieval_policy import build_phase2_retrieval_plan
from agents.shared.schemas import PatientAnswer, UserMedicalProfile

BUCKET_PRIORITY = [
    "cpr_or_airway_steps",
    "immediate_actions",
    "do_not_do_warnings",
    "bystander_instructions",
    "red_flags_and_escalation",
    "monitoring_and_followup",
    "scene_safety",
]

BUCKET_LIMITS = {
    "scene_safety": 2,
    "red_flags_and_escalation": 3,
    "immediate_actions": 3,
    "do_not_do_warnings": 2,
    "bystander_instructions": 3,
    "cpr_or_airway_steps": 3,
    "monitoring_and_followup": 2,
}

INTENT_BUCKETS = {
    "fall_general_first_aid": ["immediate_actions", "scene_safety", "monitoring_and_followup"],
    "fall_red_flags": ["red_flags_and_escalation", "monitoring_and_followup"],
    "bystander_check_consciousness": ["bystander_instructions", "red_flags_and_escalation"],
    "bystander_check_breathing": ["bystander_instructions", "cpr_or_airway_steps"],
    "unconscious_after_fall": ["red_flags_and_escalation", "cpr_or_airway_steps", "bystander_instructions"],
    "abnormal_breathing_after_fall": ["red_flags_and_escalation", "cpr_or_airway_steps"],
    "cpr_trigger_guidance": ["cpr_or_airway_steps", "red_flags_and_escalation"],
    "head_injury_after_fall": ["red_flags_and_escalation", "immediate_actions", "monitoring_and_followup"],
    "head_injury_blood_thinners": ["red_flags_and_escalation", "immediate_actions"],
    "severe_bleeding_after_fall": ["immediate_actions", "red_flags_and_escalation", "do_not_do_warnings"],
    "possible_spinal_injury": ["do_not_do_warnings", "immediate_actions", "red_flags_and_escalation"],
    "fracture_or_cannot_stand": ["immediate_actions", "do_not_do_warnings", "red_flags_and_escalation"],
    "do_not_move_possible_injury": ["do_not_do_warnings", "immediate_actions"],
    "monitor_low_risk_fall": ["monitoring_and_followup", "immediate_actions"],
    "bystander_instruction_mode": ["bystander_instructions", "scene_safety", "immediate_actions"],
}


def _score_snippet(snippet: str, query: str, intent: str) -> int:
    lowered_snippet = snippet.lower()
    lowered_query = query.lower()
    score = 0

    for token in lowered_query.split():
        if len(token) > 3 and token in lowered_snippet:
            score += 2

    if any(keyword in lowered_snippet for keyword in ["call emergency", "emergency help", "seek urgent", "call 999"]):
        score += 3
    if any(keyword in lowered_snippet for keyword in ["do not", "don't", "keep still", "start cpr", "aed"]):
        score += 3
    if "bystander" in intent and any(keyword in lowered_snippet for keyword in ["check", "ask", "look", "help"]):
        score += 2
    return score


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def run_phase2_retrieval(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    severity_hint: str | None = None,
    max_results_per_query: int = 2,
) -> dict:
    retrieval_plan = build_phase2_retrieval_plan(
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        severity_hint=severity_hint,
    )

    query_pairs = list(zip(retrieval_plan["selected_intents"], retrieval_plan["queries"]))
    bucket_entries: dict[str, list[dict]] = defaultdict(list)
    all_references: list[dict] = []
    sources_seen: list[str] = []

    for intent, query in query_pairs:
        result = retrieve_medical_guidance_with_source(query, max_results=max_results_per_query)
        if result["source"] not in sources_seen:
            sources_seen.append(result["source"])
        all_references.extend(result.get("references", []))

        buckets = INTENT_BUCKETS.get(intent, ["immediate_actions"])
        for snippet in result["snippets"]:
            entry = {
                "snippet": snippet.strip(),
                "intent": intent,
                "query": query,
                "score": _score_snippet(snippet, query, intent),
            }
            for bucket in buckets:
                bucket_entries[bucket].append(entry)

    selected_buckets: dict[str, list[str]] = {}
    for bucket_name, entries in bucket_entries.items():
        ranked = sorted(entries, key=lambda item: item["score"], reverse=True)
        selected = [entry["snippet"] for entry in ranked[: BUCKET_LIMITS.get(bucket_name, 2)]]
        deduped = _dedupe_preserve_order(selected)
        if deduped:
            selected_buckets[bucket_name] = deduped

    prioritized_guidance: list[str] = []
    for bucket_name in BUCKET_PRIORITY:
        prioritized_guidance.extend(selected_buckets.get(bucket_name, []))

    return {
        "policy_version": retrieval_plan["policy_version"],
        "selected_intents": retrieval_plan["selected_intents"],
        "queries": retrieval_plan["queries"],
        "primary_query": retrieval_plan["primary_query"],
        "retrieval_source": "+".join(sources_seen) if sources_seen else "fallback_file",
        "bucketed_snippets": selected_buckets,
        "guidance_snippets": _dedupe_preserve_order(prioritized_guidance)[:5],
        "references": all_references[:6],
    }
