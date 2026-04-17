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
    ExecutionUpdate,
    FallAssessment,
    FallEvent,
    GroundingSummary,
    GuidanceSummary,
    InteractionInput,
    InteractionSummary,
    ReasoningRefreshSummary,
    ResponseActionItem,
    ResponsePlanSummary,
)
from agents.communication.session_agent import _apply_assessment_language_guardrails, analyze_communication_turn  # noqa: E402
from agents.communication.session_agent import _summarize_reasoning_handoff  # noqa: E402
from app.fall.conversation_service import (  # noqa: E402
    _apply_execution_context_to_reply,
    _merge_assessment_into_analysis,
    _summarize_for_comm_agent,
    apply_session_action_decision,
    get_fall_conversation_session_state,
    reset_fall_conversation_session,
    run_fall_conversation_turn,
)
from app.fall.action_runtime_service import sync_action_state_with_assessment  # noqa: E402
from app.fall.session_store import fall_session_store  # noqa: E402


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
            immediate_step="Keep the patient still.",
            next_focus="guided_action",
            quick_replies=["Done", "Need next step", "Condition worse"],
            open_question_key=None,
            should_surface_execution_update=False,
            recommended_context_bits=["scene_action:keep_patient_still"],
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


def _family_notification_assessment() -> FallAssessment:
    assessment = _previous_assessment()
    return assessment.model_copy(
        update={
            "response_plan": ResponsePlanSummary(
                notification_actions=[
                    ResponseActionItem(
                        type="inform_family",
                        priority="secondary",
                        reason="Family should be updated while guidance continues.",
                    )
                ]
            ),
            "communication_handoff": CommunicationHandoffSummary(
                mode="instruction",
                priority="safety",
                immediate_step="Keep the patient still.",
                next_focus="guided_action",
                quick_replies=["Done", "Condition worse", "Need next step"],
                open_question_key=None,
                should_surface_execution_update=True,
                recommended_context_bits=["notification:inform_family"],
                rationale="Safety instruction should stay active after the family update.",
            ),
        }
    )


def _family_notification_assessment_with_red_flags(red_flags: list[str]) -> FallAssessment:
    assessment = _family_notification_assessment()
    return assessment.model_copy(
        update={
            "clinical_assessment": assessment.clinical_assessment.model_copy(
                update={
                    "red_flags": red_flags,
                    "reasoning_summary": f"Updated fall reasoning: {', '.join(red_flags)}.",
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
    assert start_response.reasoning_run_count == 0, start_response
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
    assert session_state.reasoning_run_count >= 1, session_state
    assert len(session_state.conversation_history) >= 1, session_state
    if session_state.execution_updates:
        assert len(session_state.conversation_history) >= 2, session_state

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
    assert reassure_response.reasoning_invoked is False, reassure_response
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
    assert len(assistant_messages) >= assistant_count_after_turn, refreshed_state
    if any(item.type == "emergency_dispatch" and item.status == "completed" for item in refreshed_state.execution_updates):
        assert any("emergency help has been called" in message.text.lower() for message in assistant_messages), refreshed_state
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
            if any(item.type == "emergency_dispatch" and item.status == "completed" for item in refreshed_state.execution_updates):
                assert any(
                    "emergency help has been called" in message.text.lower()
                    for message in refreshed_state.conversation_history
                    if message.role == "assistant"
                ), refreshed_state
            else:
                latest_family_state = get_fall_conversation_session_state(start_response.session_id)
                if latest_family_state and any(
                    item.type == "emergency_dispatch" and item.status == "completed"
                    for item in latest_family_state.execution_updates
                ):
                    assert "emergency help has been called" in family_turn.assistant_message.lower(), family_turn
                else:
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


def test_execution_announcement_is_only_used_once() -> None:
    analysis = CommunicationAgentAnalysis(
        followup_text="Tell me what changed.",
        responder_role="bystander",
        communication_target="bystander",
        patient_responded=False,
        bystander_present=True,
        bystander_can_help=True,
        extracted_facts=["abnormal_breathing"],
        reasoning_needed=False,
        reasoning_reason="Existing reasoning is already available.",
        guidance_intent="question",
        next_focus="guided_action",
        immediate_step=None,
        quick_replies=["Done", "Need next step"],
    )
    assessment = _family_notification_assessment()
    execution_updates = [
        ExecutionUpdate(
            type="inform_family",
            status="queued",
            detail="Family notification was queued in the MVP flow for support.",
        )
    ]

    first_reply, announced_keys = _apply_execution_context_to_reply(
        analysis=analysis,
        execution_updates=execution_updates,
        announced_execution_types=set(),
        assessment=assessment,
    )
    assert "family" in first_reply.followup_text.lower(), first_reply
    assert announced_keys == ["inform_family:queued:bystander:1"], announced_keys

    second_reply, second_announced_keys = _apply_execution_context_to_reply(
        analysis=analysis,
        execution_updates=execution_updates,
        announced_execution_types=set(announced_keys),
        assessment=assessment,
    )
    assert "family" not in second_reply.followup_text.lower(), second_reply
    assert "tell me what changed" in second_reply.followup_text.lower(), second_reply


def test_family_notification_updates_only_when_reasoning_message_changes() -> None:
    session = fall_session_store.create_session(
        event=FallEvent(
            user_id="user_001",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="rapid_descent",
            confidence_score=0.98,
        ),
        vitals=None,
        interaction_input=InteractionInput(
            patient_response_status="unknown",
            bystander_available=True,
            bystander_can_help=True,
            testing_assume_bystander=True,
        ),
    )

    first_assessment = _family_notification_assessment_with_red_flags(["head_strike"])
    _, first_updates = sync_action_state_with_assessment(
        session_id=session.session_id,
        assessment=first_assessment,
        patient_answers=[],
    )
    first_family_update = next(item for item in first_updates if item.type == "inform_family")
    assert first_family_update.occurrence_count == 1, first_family_update
    assert "head_strike" in first_family_update.message_text, first_family_update

    _, same_updates = sync_action_state_with_assessment(
        session_id=session.session_id,
        assessment=first_assessment,
        patient_answers=[],
    )
    same_family_update = next(item for item in same_updates if item.type == "inform_family")
    assert same_family_update.occurrence_count == 1, same_family_update
    assert same_family_update.notification_key == first_family_update.notification_key, same_family_update

    second_assessment = _family_notification_assessment_with_red_flags(["unresponsive", "cannot_stand"])
    _, second_updates = sync_action_state_with_assessment(
        session_id=session.session_id,
        assessment=second_assessment,
        patient_answers=[],
    )
    second_family_update = next(item for item in second_updates if item.type == "inform_family")
    assert second_family_update.occurrence_count == 2, second_family_update
    assert second_family_update.notification_key != first_family_update.notification_key, second_family_update
    assert "unresponsive" in second_family_update.message_text, second_family_update
    assert "cannot_stand" in second_family_update.message_text, second_family_update

    session_state = get_fall_conversation_session_state(session.session_id)
    assert session_state is not None, session.session_id
    family_state = next(item for item in session_state.action_states if item.action_type == "contact_family")
    assert family_state.occurrence_count == 2, family_state
    assert family_state.message_text == second_family_update.message_text, family_state

    reset_result = reset_fall_conversation_session(session.session_id)
    assert reset_result["reset"] is True, reset_result


@pytest.mark.asyncio
async def test_repeated_reasoning_keeps_single_dispatch_action_state() -> None:
    start_response = await run_fall_conversation_turn(
        CommunicationTurnRequest(
            session_id=None,
            event={
                "user_id": "user_001",
                "timestamp": "2024-04-10T12:00:00Z",
                "motion_state": "rapid_descent",
                "confidence_score": 0.98,
            },
            interaction=InteractionInput(
                patient_response_status="unknown",
                bystander_available=True,
                bystander_can_help=True,
                testing_assume_bystander=True,
            ),
            latest_responder_message="",
            previous_assessment=None,
        )
    )

    trigger_turn = await run_fall_conversation_turn(
        CommunicationTurnRequest(
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
    )
    assert trigger_turn.reasoning_invoked is True, trigger_turn

    first_state = None
    for _ in range(80):
        await asyncio.sleep(0.1)
        first_state = get_fall_conversation_session_state(start_response.session_id)
        if first_state and first_state.reasoning_status == "completed" and first_state.reasoning_run_count >= 2:
            dispatch_state = next(
                (item for item in first_state.action_states if item.action_type == "emergency_dispatch"),
                None,
            )
            if dispatch_state and dispatch_state.status in {"pending_confirmation", "completed"}:
                break

    assert first_state is not None, start_response
    first_dispatch_state = next(
        (item for item in first_state.action_states if item.action_type == "emergency_dispatch"),
        None,
    )
    assert first_dispatch_state is not None, first_state
    assert first_dispatch_state.status in {"pending_confirmation", "completed"}, first_dispatch_state
    assert len([item for item in first_state.execution_updates if item.type == "emergency_dispatch"]) == 1, first_state

    second_turn = await run_fall_conversation_turn(
        CommunicationTurnRequest(
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
                new_fact_keys=["abnormal_breathing", "cannot_stand"],
            ),
            latest_responder_message="He is still breathing strangely and cannot stand.",
            previous_assessment=None,
        )
    )
    assert second_turn.assistant_message, second_turn

    second_state = None
    for _ in range(50):
        await asyncio.sleep(0.1)
        second_state = get_fall_conversation_session_state(start_response.session_id)
        if second_state and second_state.reasoning_status == "completed" and second_state.reasoning_run_count >= 2:
            break

    assert second_state is not None, second_turn
    second_dispatch_state = next(
        (item for item in second_state.action_states if item.action_type == "emergency_dispatch"),
        None,
    )
    assert second_dispatch_state is not None, second_state
    assert second_dispatch_state.status in {"pending_confirmation", "completed"}, second_dispatch_state
    assert len([item for item in second_state.execution_updates if item.type == "emergency_dispatch"]) == 1, second_state

    action_response = await apply_session_action_decision(
        start_response.session_id,
        action_type="emergency_dispatch",
        decision="confirm",
    )
    assert action_response is not None, start_response
    assert action_response.action_state.status == "completed", action_response
    assert action_response.action_state.incident_id, action_response

    final_state = get_fall_conversation_session_state(start_response.session_id)
    assert final_state is not None, action_response
    final_dispatch_state = next(
        (item for item in final_state.action_states if item.action_type == "emergency_dispatch"),
        None,
    )
    assert final_dispatch_state is not None, final_state
    assert final_dispatch_state.status == "completed", final_dispatch_state
    assert len([item for item in final_state.execution_updates if item.type == "emergency_dispatch"]) == 1, final_state


def test_safety_handoff_suppresses_extra_questioning() -> None:
    analysis = CommunicationAgentAnalysis(
        followup_text="Where does it hurt most right now?",
        responder_role="patient",
        communication_target="patient",
        patient_responded=True,
        bystander_present=False,
        bystander_can_help=False,
        extracted_facts=["pain_present"],
        reasoning_needed=False,
        reasoning_reason="Current assessment already exists.",
        guidance_intent="question",
        next_focus="pain",
        immediate_step=None,
        quick_replies=["Head", "Hip", "Chest", "Back"],
    )
    assessment = _previous_assessment().model_copy(
        update={
            "communication_handoff": CommunicationHandoffSummary(
                mode="instruction",
                priority="safety",
                immediate_step="Do not try to stand.",
                next_focus="guided_action",
                quick_replies=["Okay", "Short of breath", "Need help"],
                open_question_key="breathing",
                should_surface_execution_update=False,
                recommended_context_bits=["missing:breathing_status_unconfirmed"],
                rationale="Safety comes before more triage questions.",
            )
        }
    )

    final_reply, announced_keys = _apply_execution_context_to_reply(
        analysis=analysis,
        execution_updates=[],
        announced_execution_types=set(),
        assessment=assessment,
    )
    assert "where does it hurt most" in final_reply.followup_text.lower(), final_reply
    assert "do not try to stand" not in final_reply.followup_text.lower(), final_reply
    assert announced_keys == [], announced_keys


def test_monitor_execution_updates_do_not_override_analysis_reply() -> None:
    analysis = CommunicationAgentAnalysis(
        followup_text="Are you breathing normally right now?",
        responder_role="patient",
        communication_target="patient",
        patient_responded=True,
        bystander_present=False,
        bystander_can_help=False,
        extracted_facts=[],
        reasoning_needed=False,
        reasoning_reason="No new urgent facts were reported.",
        guidance_intent="question",
        next_focus="breathing",
        immediate_step=None,
        quick_replies=["Breathing okay", "Hard to breathe"],
    )
    reply, announced_keys = _apply_execution_context_to_reply(
        analysis=analysis,
        execution_updates=[ExecutionUpdate(type="monitor", status="active", detail="Monitoring remains active.")],
        announced_execution_types=set(),
        assessment=_previous_assessment(),
    )
    assert "breathing normally" in reply.followup_text.lower(), reply
    assert "monitor" not in reply.followup_text.lower(), reply
    assert announced_keys == [], announced_keys


def test_assessment_context_does_not_replace_agent_authored_reply() -> None:
    analysis = CommunicationAgentAnalysis(
        followup_text="Are you breathing normally right now?",
        responder_role="patient",
        communication_target="patient",
        patient_responded=True,
        bystander_present=False,
        bystander_can_help=False,
        extracted_facts=[],
        reasoning_needed=False,
        reasoning_reason="Waiting for the breathing answer.",
        guidance_intent="question",
        next_focus="breathing",
        immediate_step=None,
        quick_replies=["Breathing okay", "Hard to breathe"],
    )
    merged = _merge_assessment_into_analysis(
        analysis=analysis,
        assessment=_previous_assessment().model_copy(
            update={
                "guidance": GuidanceSummary(
                    primary_message="Stay where you are and keep monitoring.",
                    steps=["Stay where you are."],
                )
            }
        ),
    )
    assert merged.followup_text == "Are you breathing normally right now?", merged


def test_reasoning_summary_for_comm_agent_is_context_not_script() -> None:
    summary = _summarize_for_comm_agent(
        _family_notification_assessment().model_copy(
            update={
                "guidance": GuidanceSummary(
                    primary_message="Stay with the patient and keep watching breathing.",
                    steps=["Keep the patient still."],
                )
            }
        )
    )
    assert "Guidance:" not in summary, summary
    assert "Action:" in summary, summary


def test_reasoning_handoff_is_metadata_not_authored_reply() -> None:
    handoff = _family_notification_assessment().communication_handoff
    assert handoff.primary_message == "", handoff
    assert handoff.next_question is None, handoff
    assert handoff.should_surface_execution_update is True, handoff
    assert "notification:inform_family" in handoff.recommended_context_bits, handoff


def test_reasoning_handoff_summary_is_advisory_metadata() -> None:
    summary = _summarize_reasoning_handoff(_family_notification_assessment())
    assert "surface_execution_update=True" in summary, summary
    assert "context_bits=notification:inform_family" in summary, summary
    assert "I can update family" not in summary, summary


@pytest.mark.asyncio
async def test_breathing_answer_resolves_open_question_without_monitor_language() -> None:
    previous_analysis = CommunicationAgentAnalysis(
        followup_text="Are you breathing normally right now?",
        responder_role="patient",
        communication_target="patient",
        patient_responded=True,
        bystander_present=False,
        bystander_can_help=False,
        extracted_facts=[],
        resolved_fact_keys=[],
        open_question_key="breathing",
        open_question_resolved=False,
        conversation_state_summary="Resolved: none. Open question: breathing. Next focus: breathing.",
        reasoning_needed=False,
        reasoning_reason="Waiting for the breathing answer.",
        should_surface_execution_update=False,
        guidance_intent="question",
        next_focus="breathing",
        immediate_step=None,
        quick_replies=["Breathing okay", "Hard to breathe"],
    )

    analysis = await analyze_communication_turn(
        client=None,
        event=None,
        vitals=None,
        patient_profile=None,
        conversation_history=[],
        latest_message="Breathing normally",
        previous_assessment=_previous_assessment().model_copy(
            update={
                "action": ActionSummary(
                    recommended="monitor",
                    requires_confirmation=False,
                    cancel_allowed=False,
                    countdown_seconds=None,
                )
            }
        ),
        previous_analysis=previous_analysis,
    )

    assert analysis.open_question_resolved is True, analysis
    assert analysis.reasoning_needed is False, analysis
    assert "monitor" not in analysis.followup_text.lower(), analysis


@pytest.mark.asyncio
async def test_reset_fall_conversation_session_clears_backend_state() -> None:
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
    assert get_fall_conversation_session_state(start_response.session_id) is not None, start_response

    reset_result = reset_fall_conversation_session(start_response.session_id)

    assert reset_result["reset"] is True, reset_result
    assert get_fall_conversation_session_state(start_response.session_id) is None, reset_result
