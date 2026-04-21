"""Reasoning-support grounding helpers for clinical severity and escalation judgments."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from agents.bystander.knowledge_base import retrieve_medical_guidance_with_source
from agents.shared.schemas import ClinicalAssessmentSummary, PatientAnswer, UserMedicalProfile

BACKEND_DIR = Path(__file__).resolve().parents[2]
POLICY_PATH = BACKEND_DIR / "data" / "reasoning_support_policy.json"


def _normalized_answer_text(patient_answers: list[PatientAnswer]) -> str:
    return " ".join(answer.answer.lower() for answer in patient_answers)


@lru_cache(maxsize=1)
def load_reasoning_support_policy() -> dict:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_reasoning_support_plan(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    clinical_assessment: ClinicalAssessmentSummary,
) -> dict:
    policy = load_reasoning_support_policy()
    answer_text = _normalized_answer_text(patient_answers)
    red_flags = set(clinical_assessment.red_flags)
    intents: list[str] = []

    if {"unresponsive", "loss_of_consciousness", "not_breathing"} & red_flags:
        intents.append("assessment_unconscious_reasoning")
    else:
        intents.append("assessment_conscious_reasoning")

    if any(flag in red_flags for flag in ["abnormal_breathing", "not_breathing", "severe_bleeding", "head_strike", "chest_pain"]):
        intents.append("red_flags_reasoning")

    if {"head_strike", "blood_thinner_use"} <= red_flags or patient_profile.blood_thinners:
        intents.append("special_risk_factors_reasoning")

    if any(flag in red_flags for flag in ["cannot_stand", "suspected_fracture", "suspected_spinal_injury", "severe_back_pain", "severe_neck_pain"]):
        intents.append("mobility_do_not_move_reasoning")

    if any(token in answer_text for token in ["pain", "hurt", "fracture", "broken", "sore"]):
        intents.append("pain_injury_reasoning")

    if clinical_assessment.severity == "critical":
        intents.extend(["severity_high_reasoning", "escalation_logic_reasoning"])
    elif clinical_assessment.severity == "medium":
        intents.extend(["severity_moderate_reasoning", "escalation_logic_reasoning"])
    else:
        intents.append("severity_low_reasoning")

    if clinical_assessment.blocking_uncertainties or clinical_assessment.contradictions:
        intents.append("escalation_logic_reasoning")

    if any(term in answer_text for term in ["rapid descent", "fell hard", "hard fall", "collapsed suddenly"]):
        intents.append("scene_mechanism_reasoning")

    if clinical_assessment.action_confidence_band == "low" or clinical_assessment.missing_facts:
        intents.append("response_general_reasoning")

    if clinical_assessment.severity in {"low", "medium"}:
        intents.append("delayed_red_flags_reasoning")

    seen: set[str] = set()
    unique_intents: list[str] = []
    for intent in intents:
        if intent not in seen and intent in policy["intents"]:
            seen.add(intent)
            unique_intents.append(intent)

    if not unique_intents:
        unique_intents = list(policy["fallback_intents"])

    ordered_intents = sorted(
        unique_intents,
        key=lambda intent: (
            policy["intents"][intent]["priority"],
            unique_intents.index(intent),
        ),
    )
    selected_intents = ordered_intents[: policy["default_intent_limit"]]
    selected_queries = [policy["intents"][intent]["queries"][0] for intent in selected_intents]

    return {
        "policy_version": policy["policy_version"],
        "selected_intents": selected_intents,
        "queries": selected_queries,
        "primary_query": selected_queries[0] if selected_queries else "",
    }


def run_reasoning_support_grounding(
    *,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    clinical_assessment: ClinicalAssessmentSummary,
    max_results_per_query: int = 2,
) -> dict:
    plan = build_reasoning_support_plan(
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        clinical_assessment=clinical_assessment,
    )

    snippets: list[str] = []
    references: list[dict] = []
    sources_seen: list[str] = []

    for query in plan["queries"]:
        result = retrieve_medical_guidance_with_source(query, max_results=max_results_per_query)
        if result["source"] not in sources_seen:
            sources_seen.append(result["source"])
        snippets.extend(snippet.strip() for snippet in result["snippets"] if snippet.strip())
        references.extend(result.get("references", []))

    deduped_snippets: list[str] = []
    seen_snippets: set[str] = set()
    for snippet in snippets:
        if snippet not in seen_snippets:
            seen_snippets.add(snippet)
            deduped_snippets.append(snippet)

    return {
        "policy_version": plan["policy_version"],
        "selected_intents": plan["selected_intents"],
        "queries": plan["queries"],
        "primary_query": plan["primary_query"],
        "source": "+".join(sources_seen) if sources_seen else "fallback_file",
        "snippets": deduped_snippets[:6],
        "references": references[:6],
    }
