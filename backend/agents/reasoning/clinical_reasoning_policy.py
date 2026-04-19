"""Deterministic clinical reasoning policy for signal extraction and fallback assessment."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from agents.shared.schemas import (
    ClinicalAssessment,
    EscalationActionSummary,
    FallEvent,
    PatientAnswer,
    ReasoningTraceSummary,
    ResponseActionItem,
    ResponsePlanSummary,
    UserMedicalProfile,
    VitalAssessment,
    VisionAssessment,
)

CLINICAL_REASONING_POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "clinical_reasoning_policy.json"


@dataclass
class ReasoningSignalBundle:
    red_flags: list[str] = field(default_factory=list)
    protective_signals: list[str] = field(default_factory=list)
    suspected_risks: list[str] = field(default_factory=list)
    vulnerability_modifiers: list[str] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    uncertainty: list[str] = field(default_factory=list)
    priority_missing_fact: str | None = None
    blocking_uncertainties: list[str] = field(default_factory=list)
    hard_emergency_triggered: bool = False
    override_policy: str = ""


@dataclass
class ClinicalReasoningOutcome:
    signals: ReasoningSignalBundle
    severity: str
    recommended_action: str
    clinical_confidence_score: float
    action_confidence_score: float
    severity_reason: str
    action_reason: str
    uncertainty_effect: str
    reasoning_summary: str
    response_plan: ResponsePlanSummary

    def to_clinical_assessment(self) -> ClinicalAssessment:
        """Convert the deterministic outcome into the shared clinical schema."""
        return ClinicalAssessment(
            severity=self.severity,
            clinical_confidence_score=self.clinical_confidence_score,
            clinical_confidence_band=_confidence_band(self.clinical_confidence_score),
            action_confidence_score=self.action_confidence_score,
            action_confidence_band=_confidence_band(self.action_confidence_score),
            red_flags=self.signals.red_flags,
            protective_signals=self.signals.protective_signals,
            suspected_risks=self.signals.suspected_risks[:5],
            vulnerability_modifiers=self.signals.vulnerability_modifiers,
            missing_facts=self.signals.missing_facts,
            contradictions=self.signals.contradictions,
            uncertainty=self.signals.uncertainty[:4],
            hard_emergency_triggered=self.signals.hard_emergency_triggered,
            blocking_uncertainties=self.signals.blocking_uncertainties[:4],
            override_policy=self.signals.override_policy,
            reasoning_summary=self.reasoning_summary,
            recommended_action=self.recommended_action,
            response_plan=self.response_plan,
            reasoning_trace=build_reasoning_trace(self),
        )


def _confidence_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def load_clinical_reasoning_policy() -> dict:
    """Load the deterministic clinical reasoning policy asset."""
    with CLINICAL_REASONING_POLICY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _add_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _combined_answers(patient_answers: list[PatientAnswer]) -> str:
    return " ".join(answer.answer.lower() for answer in patient_answers)


def _has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def extract_reasoning_signals(
    *,
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
    vital_assessment: VitalAssessment | None,
) -> ReasoningSignalBundle:
    """Normalize raw answers and profile context into structured reasoning signals."""
    answer_text = _combined_answers(patient_answers)
    signals = ReasoningSignalBundle()

    checks = [
        (["unresponsive", "not responding", "barely responding"], "unresponsive", "airway_compromise"),
        (["lost consciousness", "loss of consciousness", "passed out", "blacked out"], "loss_of_consciousness", "head_injury"),
        (["not breathing"], "not_breathing", "airway_compromise"),
        (["abnormal breathing", "breathing strangely", "trouble breathing", "difficulty breathing"], "abnormal_breathing", "respiratory_distress"),
        (["heavy bleeding", "severe bleeding", "bleeding heavily"], "severe_bleeding", "hemorrhage_risk"),
        (["chest pain"], "chest_pain", "cardiac_event"),
        (["seizure", "convuls"], "seizure_activity", "neurological_event"),
        (["hit my head", "hit their head", "head strike", "head injury"], "head_strike", "head_injury"),
        (["vomiting"], "vomiting_after_head_injury", "head_injury"),
        (["confusion", "confused", "disoriented"], "confusion_after_fall", "head_injury"),
        (["sudden collapse", "collapsed suddenly"], "sudden_collapse", "medical_collapse"),
        (["cannot stand", "can't stand", "unable to get up", "unable to stand"], "cannot_stand", "fracture_risk"),
        (["severe pain", "strong pain"], "severe_pain", "serious_injury"),
        (["hip pain"], "severe_hip_pain", "fracture_risk"),
        (["back pain"], "severe_back_pain", "spinal_injury"),
        (["neck pain"], "severe_neck_pain", "spinal_injury"),
        (["fracture", "broken"], "suspected_fracture", "fracture_risk"),
        (["spinal", "spine"], "suspected_spinal_injury", "spinal_injury"),
    ]

    for phrases, red_flag, risk in checks:
        if _has_any(answer_text, phrases):
            _add_unique(signals.red_flags, red_flag)
            _add_unique(signals.suspected_risks, risk)

    if _has_any(answer_text, ["awake", "speaking clearly", "responding clearly", "i'm okay", "i am okay", "i'm fine", "i am fine"]):
        _add_unique(signals.protective_signals, "awake_and_answering")
    if _has_any(answer_text, ["breathing normally", "breathing fine", "no trouble breathing", "breathing okay"]):
        _add_unique(signals.protective_signals, "breathing_normally")
    if _has_any(answer_text, ["mild pain", "just sore", "just hurts a bit", "can move safely", "walking", "able to stand"]):
        _add_unique(signals.protective_signals, "mobile_without_major_pain")

    if event.motion_state in {"rapid_descent", "no_movement"} and event.confidence_score >= 0.75:
        _add_unique(signals.suspected_risks, "high_impact_fall")

    if patient_profile.age >= 65:
        _add_unique(signals.red_flags, "older_adult")
        _add_unique(signals.vulnerability_modifiers, "older_adult")
    if patient_profile.blood_thinners:
        _add_unique(signals.red_flags, "blood_thinner_use")
        _add_unique(signals.vulnerability_modifiers, "blood_thinner_use")
    if patient_profile.mobility_support:
        _add_unique(signals.red_flags, "mobility_support_user")
        _add_unique(signals.vulnerability_modifiers, "mobility_support_user")
    if any("recurrent fall" in condition.lower() for condition in patient_profile.pre_existing_conditions):
        _add_unique(signals.red_flags, "recurrent_falls")
        _add_unique(signals.vulnerability_modifiers, "recurrent_falls")

    for condition in patient_profile.pre_existing_conditions:
        lowered = condition.lower()
        if any(term in lowered for term in ["heart", "atrial", "cardiac"]):
            _add_unique(signals.red_flags, "known_heart_disease")
            _add_unique(signals.vulnerability_modifiers, "known_heart_disease")
        if any(term in lowered for term in ["neuro", "stroke", "seizure", "parkinson"]):
            _add_unique(signals.red_flags, "known_neurological_disease")
            _add_unique(signals.vulnerability_modifiers, "known_neurological_disease")

    if vital_assessment and vital_assessment.anomaly_detected:
        _add_unique(signals.suspected_risks, "physiologic_instability")
        if vital_assessment.severity_hint == "critical":
            _add_unique(signals.uncertainty, "Vital instability raises urgency even if answers are incomplete")

    breathing_mentions = ["breathing", "breath", "oxygen", "respir"]
    bleeding_mentions = ["bleeding", "blood loss", "hemorrhage"]
    responsiveness_mentions = ["awake", "conscious", "respond", "unresponsive", "confused"]
    head_mentions = ["head", "head strike", "hit my head", "hit their head", "loss of consciousness", "passed out"]

    if not _has_any(answer_text, breathing_mentions):
        _add_unique(signals.missing_facts, "breathing_status_unconfirmed")
        _add_unique(signals.uncertainty, "Breathing status is still not clearly confirmed")
    if not _has_any(answer_text, bleeding_mentions):
        _add_unique(signals.missing_facts, "bleeding_status_unconfirmed")
    if not _has_any(answer_text, responsiveness_mentions):
        _add_unique(signals.missing_facts, "responsiveness_unconfirmed")
        _add_unique(signals.uncertainty, "Responsiveness is not clearly confirmed")
    if (
        patient_profile.blood_thinners
        or event.motion_state in {"rapid_descent", "no_movement"}
        or event.confidence_score >= 0.85
    ) and not _has_any(answer_text, head_mentions):
        _add_unique(signals.missing_facts, "head_strike_unconfirmed")

    if "breathing normally" in answer_text and any(flag in signals.red_flags for flag in ["not_breathing", "abnormal_breathing"]):
        _add_unique(signals.contradictions, "breathing_report_conflict")
    if "awake" in answer_text and any(flag in signals.red_flags for flag in ["unresponsive", "loss_of_consciousness"]):
        _add_unique(signals.contradictions, "responsiveness_conflict")
    if "mild pain" in answer_text and any(flag in signals.red_flags for flag in ["severe_pain", "cannot_stand"]):
        _add_unique(signals.contradictions, "pain_mobility_conflict")

    if signals.contradictions:
        _add_unique(signals.uncertainty, "Conflicting reports lower certainty and should be reviewed carefully")

    for fact_name in load_clinical_reasoning_policy()["missing_fact_priority"]:
        if fact_name in signals.missing_facts:
            signals.priority_missing_fact = fact_name
            break

    return signals


def run_clinical_reasoning_policy(
    *,
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    vision_assessment: VisionAssessment,
    vital_assessment: VitalAssessment | None,
    patient_answers: list[PatientAnswer],
) -> ClinicalReasoningOutcome:
    """Run the deterministic fallback policy used for reasoning and debug traces."""
    signals = extract_reasoning_signals(
        event=event,
        patient_profile=patient_profile,
        patient_answers=patient_answers,
        vital_assessment=vital_assessment,
    )

    immediate_flags = {
        "unresponsive",
        "loss_of_consciousness",
        "not_breathing",
        "abnormal_breathing",
        "severe_bleeding",
        "chest_pain",
        "seizure_activity",
    }
    high_risk_flags = {
        "head_strike",
        "vomiting_after_head_injury",
        "confusion_after_fall",
        "sudden_collapse",
        "cannot_stand",
        "severe_pain",
        "severe_hip_pain",
        "severe_back_pain",
        "severe_neck_pain",
        "suspected_fracture",
        "suspected_spinal_injury",
    }

    score = 0
    severity_reasons: list[str] = []

    if vision_assessment.severity_hint == "critical":
        score += 2
        severity_reasons.append("motion pattern looks critical")
    elif vision_assessment.severity_hint == "medium":
        score += 1
        severity_reasons.append("motion pattern looks concerning")

    if vital_assessment and vital_assessment.anomaly_detected:
        vital_weight = 2 if vital_assessment.severity_hint == "critical" else 1
        score += vital_weight
        severity_reasons.append("vitals suggest physiologic instability")

    immediate_present = [flag for flag in signals.red_flags if flag in immediate_flags]
    high_risk_present = [flag for flag in signals.red_flags if flag in high_risk_flags]

    if immediate_present:
        score += 4
        severity_reasons.append("immediate emergency red flags are present")
    if high_risk_present:
        score += 2
        severity_reasons.append("high-risk injury signals are present")
    if signals.vulnerability_modifiers:
        score += 1
        severity_reasons.append("profile modifiers increase caution")
    if len(signals.protective_signals) >= 2 and not immediate_present:
        score -= 1
        severity_reasons.append("reassuring self-reported protective signals reduce urgency")

    if signals.contradictions:
        severity_reasons.append("conflicting reports reduce certainty")

    head_strike_on_blood_thinners = {"head_strike", "blood_thinner_use"} <= set(signals.red_flags)
    if immediate_present or head_strike_on_blood_thinners:
        severity = "critical"
    elif score >= 5:
        severity = "critical"
    elif score >= 3:
        severity = "medium"
    else:
        severity = "low"

    if immediate_present:
        action = "emergency_dispatch"
        action_reason = "Explicit danger signs justify immediate emergency dispatch."
        uncertainty_effect = "Explicit danger signs override uncertainty."
        signals.hard_emergency_triggered = True
        signals.override_policy = "Hard emergency triggers overrode remaining uncertainty."
    elif severity == "critical" and signals.priority_missing_fact:
        action = "dispatch_pending_confirmation"
        action_reason = "Critical risk is present, but the top missing fact should be clarified during a short confirmation window."
        uncertainty_effect = "Urgency stays high, but uncertainty keeps the action at confirmation-pending."
        signals.blocking_uncertainties = [signals.priority_missing_fact]
        signals.override_policy = "A short confirmation window is allowed because no explicit life-threatening trigger has been confirmed."
    elif severity == "critical":
        action = "dispatch_pending_confirmation"
        action_reason = "Critical injury concern warrants urgent escalation even without a confirmed life-threatening signal."
        uncertainty_effect = "There is still limited uncertainty, but the action remains urgent."
        signals.override_policy = "Urgency is high, but the case still allows a brief confirmation window."
    elif severity == "medium":
        action = "contact_family"
        action_reason = "The case is concerning and should involve support, but it is not yet a confirmed emergency."
        uncertainty_effect = (
            "The top missing fact should guide the next follow-up."
            if signals.priority_missing_fact
            else "Uncertainty lowers confidence, but not enough to trigger emergency dispatch."
        )
        if signals.priority_missing_fact:
            signals.blocking_uncertainties = [signals.priority_missing_fact]
        signals.override_policy = "Uncertainty affects follow-up choice but does not require emergency escalation yet."
    else:
        action = "monitor"
        action_reason = "Available evidence points to a stable case that can be monitored with clear guidance."
        uncertainty_effect = (
            "Low-risk signals are stronger than the remaining unknowns."
            if signals.protective_signals
            else "The case remains low risk, but follow-up should still watch for changes."
        )
        signals.override_policy = "Protective signals outweighed the remaining uncertainty."

    clinical_confidence_score = {"low": 0.78, "medium": 0.67, "critical": 0.82}[severity]
    action_confidence_score = {
        "monitor": 0.76,
        "contact_family": 0.64,
        "dispatch_pending_confirmation": 0.79,
        "emergency_dispatch": 0.9,
    }[action]

    confidence_penalty = min(0.18, (0.05 * len(signals.missing_facts)) + (0.04 * len(signals.contradictions)))
    if not immediate_present:
        clinical_confidence_score = max(0.35, clinical_confidence_score - confidence_penalty)
        action_confidence_score = max(0.35, action_confidence_score - confidence_penalty)

    if signals.uncertainty and signals.priority_missing_fact and action != "emergency_dispatch":
        _add_unique(signals.uncertainty, f"Highest-priority missing fact: {signals.priority_missing_fact}")

    reasoning_summary = (
        "Phase 3 staged reasoning used structured signal extraction before severity and action selection. "
        f"Severity is {severity} because {severity_reasons[0] if severity_reasons else 'only limited risk signals were found'}. "
        f"Action is {action} because {action_reason.lower()}"
    )

    response_plan = _build_response_plan(
        signals=signals,
        severity=severity,
        action=action,
        action_reason=action_reason,
    )

    return ClinicalReasoningOutcome(
        signals=signals,
        severity=severity,
        recommended_action=action,
        clinical_confidence_score=round(clinical_confidence_score, 2),
        action_confidence_score=round(action_confidence_score, 2),
        severity_reason="; ".join(severity_reasons) if severity_reasons else "Limited risk signals were found.",
        action_reason=action_reason,
        uncertainty_effect=uncertainty_effect,
        reasoning_summary=reasoning_summary,
        response_plan=response_plan,
    )


def _build_response_plan(
    *,
    signals: ReasoningSignalBundle,
    severity: str,
    action: str,
    action_reason: str,
) -> ResponsePlanSummary:
    """Build the richer multi-track execution plan while preserving a legacy action summary."""
    escalation_action = EscalationActionSummary(
        type="none" if action in {"monitor", "contact_family"} else action,
        requires_confirmation=(action == "dispatch_pending_confirmation"),
        cancel_allowed=(action == "dispatch_pending_confirmation"),
        countdown_seconds=30 if action == "dispatch_pending_confirmation" else None,
        reason=action_reason,
    )
    notification_actions: list[ResponseActionItem] = []
    bystander_actions: list[ResponseActionItem] = []
    followup_actions: list[ResponseActionItem] = []

    if severity in {"medium", "critical"}:
        notification_actions.append(
            ResponseActionItem(
                type="inform_family",
                priority="secondary",
                reason="Family or caregivers should be aware of a concerning fall event.",
            )
        )

    if "not_breathing" in signals.red_flags:
        bystander_actions.append(ResponseActionItem(type="start_cpr_guidance", priority="immediate", reason="Breathing has stopped."))
        bystander_actions.append(ResponseActionItem(type="retrieve_aed_if_available", priority="immediate", reason="AED support may be needed during resuscitation."))
    elif "abnormal_breathing" in signals.red_flags or (
        "breathing_status_unconfirmed" in signals.missing_facts and severity == "critical"
    ):
        bystander_actions.append(ResponseActionItem(type="check_breathing", priority="immediate", reason="Breathing status is dangerous or unclear."))

    if "severe_bleeding" in signals.red_flags:
        bystander_actions.append(ResponseActionItem(type="apply_pressure_to_bleeding", priority="immediate", reason="Visible severe bleeding needs immediate pressure if safe."))

    cpr_active = "not_breathing" in signals.red_flags

    if ({"head_strike", "suspected_spinal_injury"} & set(signals.red_flags) or "head_strike_unconfirmed" in signals.missing_facts) and not cpr_active:
        bystander_actions.append(ResponseActionItem(type="keep_patient_still", priority="immediate", reason="Movement may worsen head, neck, or spinal injury."))
        bystander_actions.append(ResponseActionItem(type="do_not_move_patient", priority="immediate", reason="Avoid moving the patient unless there is immediate danger."))

    if not bystander_actions and severity in {"medium", "critical"}:
        bystander_actions.append(ResponseActionItem(type="check_consciousness", priority="immediate", reason="Responsiveness should be reassessed while waiting for further help."))

    if action in {"emergency_dispatch", "dispatch_pending_confirmation"}:
        followup_actions.append(ResponseActionItem(type="wait_for_responders", priority="ongoing", reason="Emergency escalation is active or likely."))
        followup_actions.append(ResponseActionItem(type="stay_on_scene", priority="ongoing", reason="A nearby helper should remain with the patient if safe."))
    if severity in {"low", "medium", "critical"}:
        followup_actions.append(ResponseActionItem(type="monitor_for_worsening_signs", priority="ongoing", reason="The situation should be watched for deterioration."))
    if signals.priority_missing_fact:
        followup_actions.append(ResponseActionItem(type="continue_reassessment", priority="ongoing", reason=f"Reassess until {signals.priority_missing_fact} is clarified."))

    return ResponsePlanSummary(
        escalation_action=escalation_action,
        notification_actions=notification_actions,
        bystander_actions=bystander_actions,
        followup_actions=followup_actions,
    )


def build_reasoning_trace(outcome: ClinicalReasoningOutcome) -> ReasoningTraceSummary:
    """Create the compact, non-chain-of-thought debug trace shown in the MVP."""
    return ReasoningTraceSummary(
        top_red_flags=outcome.signals.red_flags[:5],
        top_protective_signals=outcome.signals.protective_signals[:4],
        vulnerability_modifiers=outcome.signals.vulnerability_modifiers[:4],
        missing_facts=outcome.signals.missing_facts[:4],
        priority_missing_fact=outcome.signals.priority_missing_fact,
        contradictions=outcome.signals.contradictions[:4],
        severity_reason=outcome.severity_reason,
        action_reason=outcome.action_reason,
        uncertainty_effect=outcome.uncertainty_effect,
    )


def render_clinical_reasoning_context(outcome: ClinicalReasoningOutcome) -> str:
    """Render deterministic reasoning signals into prompt-friendly text for the live reasoning model."""
    trace = build_reasoning_trace(outcome)
    return (
        "Deterministic clinical reasoning context:\n"
        f"- Top red flags: {', '.join(trace.top_red_flags) or 'None'}\n"
        f"- Protective signals: {', '.join(trace.top_protective_signals) or 'None'}\n"
        f"- Vulnerability modifiers: {', '.join(trace.vulnerability_modifiers) or 'None'}\n"
        f"- Missing facts: {', '.join(trace.missing_facts) or 'None'}\n"
        f"- Priority missing fact: {trace.priority_missing_fact or 'None'}\n"
        f"- Contradictions: {', '.join(trace.contradictions) or 'None'}\n"
        f"- Severity reason: {trace.severity_reason or 'None'}\n"
        f"- Action reason: {trace.action_reason or 'None'}\n"
        f"- Uncertainty effect: {trace.uncertainty_effect or 'None'}"
    )


def apply_reasoning_defaults(
    *,
    assessment: ClinicalAssessment,
    outcome: ClinicalReasoningOutcome,
) -> ClinicalAssessment:
    """Backfill additive reasoning fields so live and fallback paths stay consistent."""
    merged_red_flags = assessment.red_flags or outcome.signals.red_flags
    merged_protective_signals = assessment.protective_signals or outcome.signals.protective_signals
    merged_suspected_risks = assessment.suspected_risks or outcome.signals.suspected_risks[:5]
    merged_uncertainty = assessment.uncertainty or outcome.signals.uncertainty[:4]
    has_structured_plan = bool(
        assessment.response_plan.escalation_action.type != "none"
        or assessment.response_plan.notification_actions
        or assessment.response_plan.bystander_actions
        or assessment.response_plan.followup_actions
    )

    return assessment.model_copy(
        update={
            "red_flags": merged_red_flags,
            "protective_signals": merged_protective_signals,
            "suspected_risks": merged_suspected_risks,
            "vulnerability_modifiers": assessment.vulnerability_modifiers or outcome.signals.vulnerability_modifiers,
            "missing_facts": assessment.missing_facts or outcome.signals.missing_facts,
            "contradictions": assessment.contradictions or outcome.signals.contradictions,
            "uncertainty": merged_uncertainty,
            "hard_emergency_triggered": assessment.hard_emergency_triggered or outcome.signals.hard_emergency_triggered,
            "blocking_uncertainties": assessment.blocking_uncertainties or outcome.signals.blocking_uncertainties,
            "override_policy": assessment.override_policy or outcome.signals.override_policy,
            "response_plan": assessment.response_plan if has_structured_plan else outcome.response_plan,
            "reasoning_trace": (
                assessment.reasoning_trace
                if assessment.reasoning_trace and (
                    assessment.reasoning_trace.top_red_flags
                    or assessment.reasoning_trace.priority_missing_fact
                    or assessment.reasoning_trace.severity_reason
                )
                else build_reasoning_trace(outcome)
            ),
        }
    )
