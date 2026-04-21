"""Lightweight CPR-flow smoke runner for the canonical fall session.

This script lets us exercise the communication -> reasoning -> execution path
without running the frontend dashboard. It uses the real backend services and
prints the session state after each turn so CPR regressions are easier to spot.

Example:
    py -3 backend/scripts/cpr_flow_smoke.py

Optional custom turns:
    py -3 backend/scripts/cpr_flow_smoke.py --turn "..." --turn "Yes, someone is here" --turn "No"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.bootstrap import configure_runtime
from app.fall.contracts import (  # noqa: E402
    ActionSummary,
    AuditSummary,
    ClinicalAssessmentSummary,
    CommunicationSessionStartRequest,
    CommunicationState,
    CommunicationTurnRequest,
    DetectionSummary,
    FallEvent,
    FallAssessment,
    GuidanceSummary,
    InteractionInput,
    InteractionSummary,
    ProtocolGuidanceSummary,
    ReasoningDecision,
    ReasoningRefreshSummary,
    ResponseActionItem,
    ResponsePlanSummary,
    EscalationActionSummary,
    ExecutionState,
    SessionState,
    ReasoningTraceSummary,
    VitalSigns,
)
from app.fall.conversation_service import (  # noqa: E402
    get_fall_conversation_session_state,
    reset_fall_conversation_session,
    run_fall_conversation_turn,
    start_fall_conversation_session,
)
from app.fall.session_store import fall_session_store  # noqa: E402

configure_runtime()

DEFAULT_TURNS = [
    "....",
    "Yes, someone is here",
    "No",
    "Not really",
    "Seems like it's not breathing",
    "How to do CPR",
    "Need next step",
    "Need next step",
]

SEEDED_CPR_TURNS = [
    "How to do CPR",
    "Need next step",
    "Need next step",
    "Repeat that",
]


def _build_event() -> FallEvent:
    return FallEvent(
        user_id="demo-user-001",
        timestamp="2026-04-19T12:00:00Z",
        motion_state="rapid_descent",
        confidence_score=0.98,
    )


def _build_vitals() -> VitalSigns:
    return VitalSigns(
        user_id="demo-user-001",
        heart_rate=118,
        blood_pressure_systolic=92,
        blood_pressure_diastolic=58,
        blood_oxygen_sp02=88,
    )


def _print_snapshot(label: str, response_or_state) -> None:
    assessment = getattr(response_or_state, "assessment", None)
    execution_state = getattr(response_or_state, "execution_state", None)
    reasoning_decision = getattr(response_or_state, "reasoning_decision", None)
    communication_state = getattr(response_or_state, "canonical_communication_state", None)
    guidance_steps = getattr(response_or_state, "guidance_steps", None) or []
    analysis = getattr(response_or_state, "communication_analysis", None)

    payload = {
        "label": label,
        "state": getattr(response_or_state, "state", None),
        "assistant_message": getattr(response_or_state, "assistant_message", None),
        "latest_prompt": communication_state.latest_prompt if communication_state is not None else None,
        "execution_signal": analysis.execution_signal if analysis is not None else None,
        "analysis_target": analysis.communication_target if analysis is not None else None,
        "reasoning_status": getattr(response_or_state, "reasoning_status", None),
        "reasoning_decision": {
            "scenario": reasoning_decision.scenario,
            "action": reasoning_decision.action,
            "instructions": reasoning_decision.instructions,
        }
        if reasoning_decision is not None
        else None,
        "execution_state": {
            "phase": execution_state.phase,
            "dispatch_status": str(execution_state.dispatch_status),
            "guidance_protocol": execution_state.guidance_protocol,
            "guidance_step_index": execution_state.guidance_step_index,
        }
        if execution_state is not None
        else None,
        "protocol_guidance": {
            "protocol_key": assessment.protocol_guidance.protocol_key,
            "ready": assessment.protocol_guidance.ready_for_communication,
            "steps": assessment.protocol_guidance.steps,
        }
        if assessment is not None
        else None,
        "guidance_steps": guidance_steps,
    }
    print(json.dumps(payload, indent=2))


async def _wait_for_reasoning(session_id: str, timeout_seconds: float = 12.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        state = get_fall_conversation_session_state(session_id)
        if state is None:
            return
        if state.reasoning_status in {"completed", "failed"}:
            _print_snapshot("post_reasoning", state)
            return
        await asyncio.sleep(0.25)

    state = get_fall_conversation_session_state(session_id)
    if state is not None:
        _print_snapshot("reasoning_timeout", state)


def _seed_cpr_ready_state(session_id: str) -> None:
    session = fall_session_store.get_session(session_id)
    if session is None:
        return

    interaction = session.interaction_summary or _build_seeded_interaction_summary()
    assessment = FallAssessment(
        incident_id=None,
        status="dispatch_pending_confirmation",
        responder_mode="bystander",
        interaction=interaction,
        detection=DetectionSummary(
            motion_state="rapid_descent",
            fall_detection_confidence_score=0.98,
            fall_detection_confidence_band="high",
            event_validity="likely_true",
        ),
        clinical_assessment=ClinicalAssessmentSummary(
            severity="critical",
            clinical_confidence_score=0.96,
            clinical_confidence_band="high",
            action_confidence_score=0.97,
            action_confidence_band="high",
            red_flags=["not_breathing", "unconscious"],
            protective_signals=[],
            suspected_risks=["cardiac_arrest"],
            vulnerability_modifiers=[],
            missing_facts=[],
            contradictions=[],
            uncertainty=[],
            hard_emergency_triggered=True,
            blocking_uncertainties=[],
            override_policy="Life-threatening breathing failure overrides uncertainty.",
            reasoning_summary="The patient appears unconscious and not breathing normally, so CPR should begin immediately and emergency services should be called.",
            response_plan=ResponsePlanSummary(
                escalation_action=EscalationActionSummary(
                    type="dispatch_pending_confirmation",
                    requires_confirmation=True,
                    cancel_allowed=True,
                    countdown_seconds=15,
                    reason="Critical breathing failure requires emergency dispatch with the mandated confirmation window.",
                ),
                notification_actions=[ResponseActionItem(type="inform_family", priority="secondary", reason="Keep family informed during the emergency.")],
                bystander_actions=[ResponseActionItem(type="cpr", priority="immediate", reason="Start CPR immediately for absent or abnormal breathing.")],
                followup_actions=[ResponseActionItem(type="monitor", priority="ongoing", reason="Continue monitoring until responders arrive.")],
            ),
            reasoning_trace=ReasoningTraceSummary(
                top_red_flags=["not_breathing", "unconscious"],
                severity_reason="Not breathing normally is a life-threatening red flag.",
                action_reason="Immediate CPR and emergency dispatch are required.",
                uncertainty_effect="Uncertainty does not block life-saving action.",
            ),
        ),
        action=ActionSummary(
            recommended="emergency_dispatch",
            requires_confirmation=True,
            cancel_allowed=True,
            countdown_seconds=15,
        ),
        response_plan=ResponsePlanSummary(
            escalation_action=EscalationActionSummary(
                type="dispatch_pending_confirmation",
                requires_confirmation=True,
                cancel_allowed=True,
                countdown_seconds=15,
                reason="Critical breathing failure requires emergency dispatch with the mandated confirmation window.",
            ),
            notification_actions=[ResponseActionItem(type="inform_family", priority="secondary", reason="Keep family informed during the emergency.")],
            bystander_actions=[ResponseActionItem(type="cpr", priority="immediate", reason="Start CPR immediately for absent or abnormal breathing.")],
            followup_actions=[ResponseActionItem(type="monitor", priority="ongoing", reason="Continue monitoring until responders arrive.")],
        ),
        guidance=GuidanceSummary(
            primary_message="Start CPR immediately.",
            steps=[
                "Start CPR immediately for the patient who is not breathing.",
                "Place the heel of one hand in the center of the chest and place your other hand on top.",
                "Push hard and fast at about 100 to 120 compressions per minute and let the chest fully rise between compressions.",
                "If trained, give 2 rescue breaths after every 30 compressions, then continue cycles of 30 compressions and 2 breaths.",
                "Use an AED as soon as one is available and follow its voice prompts.",
                "Continue CPR until the patient breathes normally or emergency responders take over.",
            ],
            warnings=[
                "Do not stop CPR unless the scene becomes unsafe, the patient resumes normal breathing, or responders take over.",
            ],
            escalation_triggers=["If the patient does not regain normal breathing, continue CPR until help arrives."],
        ),
        protocol_guidance=ProtocolGuidanceSummary(
            protocol_key="cpr",
            title="Cardiopulmonary Resuscitation",
            grounding_required=True,
            grounding_status="ready",
            retrieval_intents=["cpr_steps"],
            primary_message="Start CPR immediately for the patient who is not breathing.",
            steps=[
                "Confirm emergency services have been called or call them immediately.",
                "Place the heel of one hand in the center of the chest and place your other hand on top.",
                "Push hard and fast at about 100 to 120 compressions per minute and let the chest fully rise between compressions.",
                "If trained, give 2 rescue breaths after every 30 compressions, then continue cycles of 30 compressions and 2 breaths.",
                "Use an AED as soon as one is available and follow its voice prompts.",
                "Continue CPR until the patient breathes normally or emergency responders take over.",
            ],
            warnings=[
                "Do not stop CPR unless the scene becomes unsafe, the patient resumes normal breathing, or responders take over.",
            ],
            communication_message="Start CPR immediately for the patient who is not breathing.",
            ready_for_communication=True,
            rationale="Grounded CPR guidance is ready to be delivered step by step.",
        ),
        audit=AuditSummary(
            fallback_used=False,
            policy_version="seeded_cpr_smoke_v1",
            dispatch_triggered=False,
        ),
    )

    fall_session_store.set_latest_assessment(session_id=session_id, assessment=assessment)
    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        state=SessionState.AWAITING_DISPATCH_CONFIRMATION,
        communication_state=CommunicationState(
            session_id=session_id,
            state=SessionState.AWAITING_DISPATCH_CONFIRMATION,
            mode="bystander_only",
            responder_role="bystander",
            patient_responded=False,
            bystander_present=True,
            conscious=False,
            breathing_normal=False,
            flags=["not_breathing", "unconscious"],
            latest_prompt="Emergency help is preparing to be dispatched.",
            latest_message="Need next step",
            reasoning_call_count=1,
        ),
        reasoning_decision=ReasoningDecision(
            scenario="CPR",
            severity="critical",
            action="call_ambulance",
            reason="The patient appears unconscious and not breathing normally.",
            instructions="Start CPR immediately.",
            confidence=0.97,
            flags_used=["not_breathing", "unconscious"],
        ),
        execution_state=ExecutionState(
            phase="dispatch_countdown",
            countdown_seconds=15,
            family_notified_initial=True,
            family_notified_update=False,
            dispatch_status="pending_confirmation",
            guidance_protocol="cpr",
            guidance_step_index=0,
        ),
    )


def _build_seeded_interaction_summary():
    return InteractionSummary(
        communication_target="bystander",
        responder_mode="bystander_only",
        guidance_style="urgent_instruction",
        interaction_mode="bystander_execution",
        rationale="Seeded CPR smoke mode starts after reasoning has already identified a bystander-led CPR scenario.",
        reasoning_refresh=ReasoningRefreshSummary(
            required=False,
            reason="Reasoning is pre-seeded for the smoke scenario.",
        ),
        testing_assume_bystander=False,
    )


async def run_smoke(turns: list[str], *, seeded_cpr: bool = False) -> None:
    start_request = CommunicationSessionStartRequest(
        event=_build_event(),
        vitals=_build_vitals(),
        interaction=InteractionInput(),
    )
    opening = await start_fall_conversation_session(start_request)
    session_id = opening.session_id
    print(f"\n=== CPR smoke session: {session_id} ===")
    _print_snapshot("opening", opening)

    if seeded_cpr:
        _seed_cpr_ready_state(session_id)
        seeded_state = get_fall_conversation_session_state(session_id)
        if seeded_state is not None:
            _print_snapshot("seeded_cpr_ready", seeded_state)

    latest_assessment = opening.assessment
    if seeded_cpr:
        seeded_state = get_fall_conversation_session_state(session_id)
        if seeded_state is not None:
            latest_assessment = seeded_state.assessment or latest_assessment
    try:
        for index, turn in enumerate(turns, start=1):
            print(f"\n--- Turn {index}: {turn}")
            response = await run_fall_conversation_turn(
                CommunicationTurnRequest(
                    session_id=session_id,
                    event=_build_event(),
                    vitals=_build_vitals(),
                    interaction=InteractionInput(message_text=turn),
                    latest_responder_message=turn,
                    conversation_history=[],
                    previous_assessment=latest_assessment,
                ),
                background_tasks=None,
            )
            latest_assessment = response.assessment or latest_assessment
            _print_snapshot(f"turn_{index}", response)

            state = get_fall_conversation_session_state(session_id)
            if state is not None and state.reasoning_status == "pending":
                await _wait_for_reasoning(session_id)
    finally:
        reset_fall_conversation_session(session_id)
        print(f"\n=== Session reset: {session_id} ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a lightweight CPR-flow smoke test.")
    parser.add_argument(
        "--turn",
        action="append",
        dest="turns",
        help="Add a custom turn. If omitted, a default CPR flow is used.",
    )
    parser.add_argument(
        "--seed-cpr",
        action="store_true",
        help="Skip live reasoning and seed the session directly into a CPR-ready post-reasoning state.",
    )
    args = parser.parse_args()
    turns = args.turns or (SEEDED_CPR_TURNS if args.seed_cpr else DEFAULT_TURNS)
    asyncio.run(run_smoke(turns, seeded_cpr=args.seed_cpr))


if __name__ == "__main__":
    main()
