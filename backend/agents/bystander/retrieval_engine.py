"""Phase 2 retrieval engine that runs planned queries, groups grounded snippets into buckets, and returns debug-friendly retrieval output."""

from __future__ import annotations

from collections import defaultdict

from agents.bystander.knowledge_base import retrieve_medical_guidance_with_source
from agents.bystander.retrieval_policy import build_phase2_bucket_query_plan
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

def _score_snippet(snippet: str, query: str, intent: str, bucket_name: str) -> int:
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
    if bucket_name == "do_not_do_warnings" and any(keyword in lowered_snippet for keyword in ["do not", "don't", "avoid", "not to"]):
        score += 4
    if bucket_name == "cpr_or_airway_steps" and any(keyword in lowered_snippet for keyword in ["breathing", "airway", "cpr", "aed"]):
        score += 4
    if bucket_name == "red_flags_and_escalation" and any(keyword in lowered_snippet for keyword in ["emergency", "urgent", "warning", "high risk"]):
        score += 4
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
    retrieval_plan = build_phase2_bucket_query_plan(
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        severity_hint=severity_hint,
    )

    bucket_entries: dict[str, list[dict]] = defaultdict(list)
    all_references: list[dict] = []
    sources_seen: list[str] = []
    queries_by_bucket: dict[str, list[str]] = {}
    references_by_bucket: dict[str, list[dict]] = {}
    bucket_sources: dict[str, str] = {}

    for bucket_name, queries in retrieval_plan["queries_by_bucket"].items():
        bucket_intent = retrieval_plan["bucket_to_intent"].get(bucket_name, "fall_general_first_aid")
        bucket_queries = []
        bucket_references: list[dict] = []

        for query in queries[:1]:
            result = retrieve_medical_guidance_with_source(query, max_results=max_results_per_query)
            bucket_queries.append(query)
            bucket_sources[bucket_name] = result["source"]
            if result["source"] not in sources_seen:
                sources_seen.append(result["source"])
            bucket_references.extend(result.get("references", []))
            all_references.extend(result.get("references", []))

            for snippet in result["snippets"]:
                bucket_entries[bucket_name].append(
                    {
                        "snippet": snippet.strip(),
                        "intent": bucket_intent,
                        "query": query,
                        "score": _score_snippet(snippet, query, bucket_intent, bucket_name),
                    }
                )

        queries_by_bucket[bucket_name] = bucket_queries
        references_by_bucket[bucket_name] = bucket_references[:4]

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
        "queries": [query for queries in queries_by_bucket.values() for query in queries],
        "primary_query": retrieval_plan["primary_query"],
        "retrieval_source": "+".join(sources_seen) if sources_seen else "fallback_file",
        "bucketed_snippets": selected_buckets,
        "guidance_snippets": _dedupe_preserve_order(prioritized_guidance)[:5],
        "references": all_references[:6],
        "queries_by_bucket": queries_by_bucket,
        "references_by_bucket": references_by_bucket,
        "bucket_sources": bucket_sources,
    }
