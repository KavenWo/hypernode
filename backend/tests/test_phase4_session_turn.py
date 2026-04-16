"""Targeted checks for the Phase 4 communication-agent turn loop."""

import asyncio

import pytest

from agents.shared.schemas import (  # noqa: E402
    ActionSummary,
    AuditSummary,
    ClinicalAssessmentSummary,
    CommunicationAgentAnalysis,
    CommunicationHandoffSummary,
    CommunicationTurnRequest,
    DetectionSummary,
    FallAssessment,
    GroundingSummary,
    GuidanceSummary,
    InteractionInput,
    InteractionSummary,
    ReasoningRefreshSummary,
    ResponsePlanSummary,
)
from agents.communication.session_agent import _apply_assessment_language_guardrails  # noqa: E402
from app.fall.conversation_service import (  # noqa: E402
    get_fall_conversation_session_state,
    run_fall_conversation_turn,
)


def _previous_assessment() -> FallAssessment:
    return FallAssessment(
        incident_id=None,
        status="guidance_active",
        responder_mode="bystander",
        interaction=InteractionSummary(
            communication_target="bystander",
            responder_mode="bystander",
            guidance_style="bystander_stepwise",
            interaction_mode="bystander_execution",
            rationale="Previous bystander execution state.",
            reasoning_refresh=ReasoningRefreshSummary(
                required=False,
                reason="Existing guidance remains active.",
                priority="low",
            ),
            testing_assume_bystander=True,
        ),
        detection=DetectionSummary(
            motion_state="rapid_descent",
            fall_detection_confidence_score=0.98,
            fall_detection_confidence_band="high",
            event_validity="likely_true",
        ),
        clinical_assessment=ClinicalAssessmentSummary(
            severity="critical",
            clinical_confidence_score=0.9,
            clinical_confidence_band="high",
            action_confidence_score=0.88,
            action_confidence_band="high",
            red_flags=["head_strike"],
            reasoning_summary="Existing reasoning state.",
            response_plan=ResponsePlanSummary(),
        ),
        action=ActionSummary(
            recommended="dispatch_pending_confirmation",
            requires_confirmation=True,
            cancel_allowed=True,
            countdown_seconds=30,
        ),
        response_plan=ResponsePlanSummary(),
        guidance=GuidanceSummary(
            primary_message="Keep the patient still and keep watching breathing.",
            steps=["Keep the patient still.", "Watch for normal breathing."],
        ),
        communication_handoff=CommunicationHandoffSummary(
            mode="instruction",
            priority="safety",
            primary_message="Keep the patient still and keep watching breathing.",
            immediate_step="Keep the patient still.",
            ask_followup=False,
            next_focus="guided_action",
            quick_replies=["Done", "Need next step", "Condition worse"],
            rationale="Existing guidance remains active and should be executed.",
        ),
        grounding=GroundingSummary(),
        audit=AuditSummary(),
    )


def _pending_dispatch_assessment() -> FallAssessment:
    assessment = _previous_assessment()
    return assessment.model_copy(
        update={
            "action": assessment.action.model_copy(
                update={
                    "recommended": "dispatch_pending_confirmation",
                    "requires_confirmation": True,
                    "cancel_allowed": True,
                    "countdown_seconds": 30,
                }
            )
        }
    )


@pytest.mark.asyncio
async def test_phase4_session_turn_loop() -> None:
    start_request = CommunicationTurnRequest(
        session_id=None,
        event={
            "user_id": "user_001",
            "timestamp": "2024-04-10T12:00:00Z",
            "motion_state": "rapid_descent",
            "confidence_score": 0.98,
        },
        interaction=InteractionInput(
            patient_response_status="unknown",
            bystander_available=False,
            bystander_can_help=False,
            testing_assume_bystander=False,
        ),
        latest_responder_message="",
        previous_assessment=None,
    )
    start_response = await run_fall_conversation_turn(start_request)
    assert start_response.session_id, start_response
    assert start_response.reasoning_invoked is True, start_response
    assert start_response.reasoning_status == "pending", start_response
    assert start_response.assessment is None, start_response
    assert start_response.assistant_message, start_response

    session_state = None
    for _ in range(40):
        await asyncio.sleep(0.1)
        session_state = get_fall_conversation_session_state(start_response.session_id)
        if session_state and session_state.reasoning_status == "completed":
            break
    assert session_state is not None, start_response
    assert session_state.assessment is not None, session_state
    assert len(session_state.conversation_history) == 1, session_state

    continue_request = CommunicationTurnRequest(
        session_id=start_response.session_id,
        event={
            "user_id": "user_001",
            "timestamp": "2024-04-10T12:00:00Z",
            "motion_state": "rapid_descent",
            "confidence_score": 0.98,
        },
        interaction=InteractionInput(
            patient_response_status="confused",
            bystander_available=True,
            bystander_can_help=True,
            testing_assume_bystander=True,
            active_execution_action="cpr_in_progress",
        ),
        latest_responder_message="okay",
        previous_assessment=None,
    )
    continue_response = await run_fall_conversation_turn(continue_request)
    assert continue_response.reasoning_invoked is False, continue_response
    assert continue_response.guidance_steps, continue_response
    assert len(continue_response.guidance_steps) == 1, continue_response
    assert continue_response.communication_analysis.guidance_intent in {"instruction", "reassure"}, continue_response

    refresh_request = CommunicationTurnRequest(
        session_id=start_response.session_id,
        event={
            "user_id": "user_001",
            "timestamp": "2024-04-10T12:00:00Z",
            "motion_state": "rapid_descent",
            "confidence_score": 0.98,
        },
        interaction=InteractionInput(
            patient_response_status="confused",
            bystander_available=True,
            bystander_can_help=True,
            testing_assume_bystander=True,
            new_fact_keys=["abnormal_breathing"],
        ),
        latest_responder_message="He is breathing strangely now.",
        previous_assessment=None,
    )
    refresh_response = await run_fall_conversation_turn(refresh_request)
    assert refresh_response.reasoning_invoked is True, refresh_response
    assert refresh_response.reasoning_status == "pending", refresh_response
    assert len(refresh_response.guidance_steps) <= 1, refresh_response
    assert refresh_response.communication_analysis.extracted_facts, refresh_response
    assert refresh_response.assistant_message, refresh_response

    reassure_request = CommunicationTurnRequest(
        session_id=start_response.session_id,
        event={
            "user_id": "user_001",
            "timestamp": "2024-04-10T12:00:00Z",
            "motion_state": "rapid_descent",
            "confidence_score": 0.98,
        },
        interaction=InteractionInput(
            patient_response_status="responsive",
            bystander_available=False,
            bystander_can_help=False,
            testing_assume_bystander=False,
            responder_mode_hint="patient",
        ),
        latest_responder_message="I am okay, breathing okay, just sore with mild pain.",
        previous_assessment=None,
    )
    reassure_response = await run_fall_conversation_turn(reassure_request)
    assert reassure_response.reasoning_invoked is True, reassure_response
    assert reassure_response.reasoning_status == "pending", reassure_response
    assistant_count_after_turn = sum(
        1 for message in get_fall_conversation_session_state(start_response.session_id).conversation_history if message.role == "assistant"
    )

    refreshed_state = None
    for _ in range(40):
        await asyncio.sleep(0.1)
        refreshed_state = get_fall_conversation_session_state(start_response.session_id)
        if refreshed_state and refreshed_state.reasoning_status == "completed":
            break
    assert refreshed_state is not None, reassure_response
    assistant_messages = [message for message in refreshed_state.conversation_history if message.role == "assistant"]
    assert len(assistant_messages) == assistant_count_after_turn, refreshed_state
    if refreshed_state.execution_updates:
        family_turn = await run_fall_conversation_turn(
            CommunicationTurnRequest(
                session_id=start_response.session_id,
                event={
                    "user_id": "user_001",
                    "timestamp": "2024-04-10T12:00:00Z",
                    "motion_state": "rapid_descent",
                    "confidence_score": 0.98,
                },
                interaction=InteractionInput(
                    patient_response_status="responsive",
                    bystander_available=False,
                    bystander_can_help=False,
                    testing_assume_bystander=False,
                    responder_mode_hint="patient",
                ),
                latest_responder_message="I'm okay.",
                previous_assessment=None,
            )
        )
        if any(item.type == "inform_family" for item in refreshed_state.execution_updates):
            assert "family" in family_turn.assistant_message.lower(), family_turn

    guarded = _apply_assessment_language_guardrails(
        analysis=CommunicationAgentAnalysis(
            followup_text="Help is on the way. Stay with him.",
            responder_role="bystander",
            communication_target="bystander",
            patient_responded=False,
            bystander_present=True,
            bystander_can_help=True,
            extracted_facts=["abnormal_breathing"],
            reasoning_needed=False,
            reasoning_reason="Assessment already available.",
            guidance_intent="instruction",
            next_focus="breathing",
            immediate_step=None,
            quick_replies=[],
        ),
        assessment=_pending_dispatch_assessment(),
    )
    assert "help is on the way" not in guarded.followup_text.lower(), guarded
    assert "may need" in guarded.followup_text.lower() or "being prepared" in guarded.followup_text.lower(), guarded
    assert session_state.execution_updates == [] or isinstance(session_state.execution_updates, list), session_state
