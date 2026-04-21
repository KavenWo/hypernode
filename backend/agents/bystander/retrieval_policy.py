"""Phase 2 retrieval planner that converts profile and answer signals into intents and query plans for the MVP backend."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from agents.shared.schemas import PatientAnswer, UserMedicalProfile

BACKEND_DIR = Path(__file__).resolve().parents[2]
POLICY_PATH = BACKEND_DIR / "data" / "phase2_retrieval_policy.json"
BUCKET_POLICY_PATH = BACKEND_DIR / "data" / "phase2_bucket_query_policy.json"


def _normalized_answer_text(patient_answers: list[PatientAnswer]) -> str:
    return " ".join(answer.answer.lower() for answer in patient_answers)


def _detect_red_flags(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> set[str]:
    answer_text = _normalized_answer_text(patient_answers)
    red_flags: set[str] = set()

    if any(phrase in answer_text for phrase in ["not breathing", "stopped breathing", "no breathing"]):
        red_flags.add("not_breathing")
    if any(phrase in answer_text for phrase in ["abnormal breathing", "gasping", "agonal", "breathing strangely"]):
        red_flags.add("abnormal_breathing")
    if any(phrase in answer_text for phrase in ["unconscious", "unresponsive", "not responding", "passed out"]):
        red_flags.add("unresponsive")
    if any(phrase in answer_text for phrase in ["bleeding heavily", "severe bleeding", "a lot of blood"]):
        red_flags.add("severe_bleeding")
    if any(phrase in answer_text for phrase in ["hit my head", "hit his head", "hit her head", "head injury", "head strike"]):
        red_flags.add("head_strike")
    if any(phrase in answer_text for phrase in ["confused", "slow to respond", "disoriented"]):
        red_flags.add("confusion_after_fall")
    if any(phrase in answer_text for phrase in ["cannot stand", "can't stand", "unable to stand"]):
        red_flags.add("cannot_stand")
    if any(phrase in answer_text for phrase in ["spinal", "neck pain", "back pain", "cannot move neck"]):
        red_flags.add("suspected_spinal_injury")
    if any(phrase in answer_text for phrase in ["fracture", "broken hip", "broken leg", "hip pain"]):
        red_flags.add("suspected_fracture")

    if patient_profile.blood_thinners:
        red_flags.add("blood_thinner_use")

    return red_flags


def _responder_mode(patient_answers: list[PatientAnswer]) -> str:
    if not patient_answers:
        return "no_response"

    answer_text = _normalized_answer_text(patient_answers)
    if any(phrase in answer_text for phrase in ["he is", "she is", "the patient", "my father", "my mother", "bystander"]):
        return "bystander"
    return "patient"


@lru_cache(maxsize=1)
def load_phase2_retrieval_policy() -> dict:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_phase2_bucket_query_policy() -> dict:
    with BUCKET_POLICY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_phase2_retrieval_plan(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    severity_hint: str | None = None,
    forced_intents: list[str] | None = None,
) -> dict:
    policy = load_phase2_retrieval_policy()
    red_flags = _detect_red_flags(patient_profile=patient_profile, patient_answers=patient_answers)
    responder_mode = _responder_mode(patient_answers)
    intents: list[str] = []

    if "not_breathing" in red_flags:
        intents.append("cpr_trigger_guidance")
    elif "abnormal_breathing" in red_flags:
        intents.append("abnormal_breathing_after_fall")
    elif "unresponsive" in red_flags:
        intents.append("unconscious_after_fall")

    if "severe_bleeding" in red_flags:
        intents.append("severe_bleeding_after_fall")

    if {"head_strike", "blood_thinner_use"}.issubset(red_flags):
        intents.append("head_injury_blood_thinners")
    elif "head_strike" in red_flags:
        intents.append("head_injury_after_fall")

    if "suspected_spinal_injury" in red_flags:
        intents.append("possible_spinal_injury")
    elif {"cannot_stand", "suspected_fracture"} & red_flags:
        intents.append("fracture_or_cannot_stand")
    elif "cannot_stand" in red_flags:
        intents.append("do_not_move_possible_injury")

    if responder_mode == "bystander":
        if not {"not_breathing", "abnormal_breathing"} & red_flags:
            intents.append("bystander_check_breathing")
        if "unresponsive" not in red_flags:
            intents.append("bystander_instruction_mode")

    normalized_severity = (severity_hint or "").strip().lower()
    if not intents:
        if normalized_severity == "low" and not red_flags:
            intents.append("monitor_low_risk_fall")
        else:
            intents.extend(policy["fallback_intents"])

    seen: set[str] = set()
    unique_intents: list[str] = []
    ordered_candidates = [*(forced_intents or []), *intents]
    for intent in ordered_candidates:
        if intent not in seen and intent in policy["intents"]:
            seen.add(intent)
            unique_intents.append(intent)

    ordered_intents = sorted(
        unique_intents,
        key=lambda intent: (
            policy["intents"][intent]["priority"],
            unique_intents.index(intent),
        ),
    )
    forced_intent_set = {intent for intent in (forced_intents or []) if intent in policy["intents"]}
    required_intents = [intent for intent in ordered_intents if intent in forced_intent_set]
    optional_intents = [intent for intent in ordered_intents if intent not in forced_intent_set]
    selected_intents = required_intents + optional_intents[: policy["default_intent_limit"]]
    selected_queries = [policy["intents"][intent]["queries"][0] for intent in selected_intents]

    return {
        "policy_version": policy["policy_version"],
        "responder_mode": responder_mode,
        "detected_red_flags": sorted(red_flags),
        "selected_intents": selected_intents,
        "queries": selected_queries,
        "primary_query": selected_queries[0] if selected_queries else policy["intents"]["fall_general_first_aid"]["queries"][0],
    }


def build_phase2_bucket_query_plan(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    severity_hint: str | None = None,
    forced_intents: list[str] | None = None,
) -> dict:
    retrieval_plan = build_phase2_retrieval_plan(
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        severity_hint=severity_hint,
        forced_intents=forced_intents,
    )
    bucket_policy = load_phase2_bucket_query_policy()

    queries_by_bucket: dict[str, list[str]] = {}
    bucket_to_intent: dict[str, str] = {}

    for intent in retrieval_plan["selected_intents"]:
        intent_policy = bucket_policy["intents"].get(intent, {})
        bucket_queries = intent_policy.get("bucket_queries", {})
        for bucket_name, queries in bucket_queries.items():
            if bucket_name not in queries_by_bucket and queries:
                queries_by_bucket[bucket_name] = queries
                bucket_to_intent[bucket_name] = intent

    if not queries_by_bucket:
        fallback_policy = bucket_policy["intents"].get("fall_general_first_aid", {})
        for bucket_name, queries in fallback_policy.get("bucket_queries", {}).items():
            if queries:
                queries_by_bucket[bucket_name] = queries
                bucket_to_intent[bucket_name] = "fall_general_first_aid"

    return {
        **retrieval_plan,
        "bucket_query_policy_version": bucket_policy["policy_version"],
        "queries_by_bucket": queries_by_bucket,
        "bucket_to_intent": bucket_to_intent,
    }
