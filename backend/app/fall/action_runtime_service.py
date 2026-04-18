"""Stateful runtime for fall-related execution actions.

This module owns deterministic execution state transitions for the active
fall session. It is intentionally separate from ``conversation_service`` so the
conversation layer can focus on transcript flow and user-facing wording.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from hashlib import sha1

from app.fall.assessment_service import (
    _build_dispatch_ai_summary,
    _map_assessment_severity_to_dispatch,
    _vitals_to_dispatch_payload,
    load_user_profile,
)
from app.fall.contracts import (
    ActionStateSummary,
    CommunicationState,
    DispatchStatus,
    ExecutionUpdate,
    ExecutionState,
    FallAssessment,
    PatientAnswer,
    SessionState,
    SessionActionResponse,
)
from app.fall.execution_service import trigger_emergency
from app.fall.session_store import fall_session_store

DISPATCH_CONFIRMATION_WINDOW_SECONDS = 15
MAIN_ACTION_ORDER = ("monitor", "contact_family", "emergency_dispatch")
_dispatch_confirmation_tasks: dict[str, asyncio.Task[None]] = {}


def _default_action_state(action_type: str) -> ActionStateSummary:
    if action_type == "monitor":
        return ActionStateSummary(
            action_type="monitor",
            desired=True,
            status="active",
            reason="Continuous monitoring should stay active while the incident is unresolved.",
            detail="The system is continuing to monitor the patient for changes.",
            last_updated_at=datetime.utcnow(),
        )
    return ActionStateSummary(action_type=action_type)


def _normalize_action_state_map(action_states: list[ActionStateSummary] | None) -> dict[str, ActionStateSummary]:
    state_map: dict[str, ActionStateSummary] = {
        action_type: _default_action_state(action_type)
        for action_type in MAIN_ACTION_ORDER
    }
    for item in action_states or []:
        state_map[item.action_type] = item.model_copy(deep=True)
    return state_map


def _ordered_action_states(state_map: dict[str, ActionStateSummary]) -> list[ActionStateSummary]:
    return [
        state_map.get(action_type, _default_action_state(action_type)).model_copy(deep=True)
        for action_type in MAIN_ACTION_ORDER
    ]


def _set_execution_update(execution_updates: list[ExecutionUpdate], update: ExecutionUpdate) -> list[ExecutionUpdate]:
    filtered = [item.model_copy(deep=True) for item in execution_updates if item.type != update.type]
    filtered.append(update)
    return filtered


def _family_reminder_script(patient_profile) -> list[str]:
    patient_name = patient_profile.full_name or patient_profile.user_id
    return [
        f"A fall may have been detected for {patient_name}.",
        "The monitoring system is continuing to assess the situation.",
        "Please stay reachable in case a follow-up update or urgent assistance is needed.",
    ]


def _family_support_script(*, patient_profile, assessment: FallAssessment) -> list[str]:
    patient_name = patient_profile.full_name or patient_profile.user_id
    red_flags = ", ".join(assessment.clinical_assessment.red_flags[:3]) or "a concerning fall assessment"
    return [
        f"This is an urgent family support update for {patient_name}.",
        f"The system detected {red_flags}.",
        "Please contact or check on the patient as soon as possible while monitoring continues.",
    ]


def _render_script_message(script_lines: list[str]) -> str:
    return " ".join(line.strip() for line in script_lines if line and line.strip()).strip()


def _build_family_notification_key(*, assessment: FallAssessment, family_script: list[str]) -> str:
    key_parts = [
        assessment.clinical_assessment.severity,
        assessment.action.recommended,
        ",".join(sorted(assessment.clinical_assessment.red_flags[:5])),
        _render_script_message(family_script),
    ]
    return sha1("||".join(key_parts).encode("utf-8")).hexdigest()[:12]


def _dispatch_script_lines(
    *,
    patient_profile,
    assessment: FallAssessment,
    patient_answers: list[PatientAnswer],
) -> list[str]:
    dispatch_summary = _build_dispatch_ai_summary(
        assessment=assessment,
        patient_answers=patient_answers,
        patient_profile=patient_profile,
    )
    patient_name = patient_profile.full_name or patient_profile.user_id
    red_flags = ", ".join(assessment.clinical_assessment.red_flags[:4]) or "fall-related injury"
    return [
        f"AI-assisted fall alert for patient {patient_name}.",
        f"Severity assessed as {assessment.clinical_assessment.severity}.",
        f"Key risks: {red_flags}.",
        f"Recommended department: {dispatch_summary.get('suggested_department', 'General ED')}.",
        "Please dispatch emergency medical responders and advise them that live monitoring is ongoing.",
    ]


def build_visible_execution_state_summary(execution_updates: list[ExecutionUpdate]) -> str:
    visible = [
        item for item in execution_updates
        if item.type not in {"monitor", "family_fall_reminder"}
    ]
    if not visible:
        return "No visible execution updates."
    return " | ".join(f"{item.type}:{item.status}:{item.detail}" for item in visible[:4])


def _get_action_state(session_id: str, action_type: str) -> ActionStateSummary | None:
    session = fall_session_store.get_session(session_id)
    if session is None:
        return None
    for state in session.action_states:
        if state.action_type == action_type:
            return state
    return None


def _cancel_dispatch_confirmation_task(session_id: str) -> None:
    task = _dispatch_confirmation_tasks.pop(session_id, None)
    if task is not None and not task.done():
        task.cancel()


def _remaining_countdown_seconds(deadline: datetime | None, *, now: datetime | None = None) -> int | None:
    if deadline is None:
        return None
    current_time = now or datetime.utcnow()
    return max(1, int((deadline - current_time).total_seconds()))


def _sync_canonical_execution_snapshot(session_id: str, *, session) -> None:
    """Mirror deterministic action-state facts into the canonical execution state."""

    previous_execution = session.execution_state or ExecutionState()
    action_map = {
        item.action_type: item
        for item in session.action_states
    }
    family_state = action_map.get("contact_family")
    dispatch_state = action_map.get("emergency_dispatch")

    dispatch_status = previous_execution.dispatch_status
    phase = previous_execution.phase
    countdown_seconds = previous_execution.countdown_seconds

    if dispatch_state is not None:
        if dispatch_state.status == "pending_confirmation":
            dispatch_status = DispatchStatus.PENDING_CONFIRMATION
            phase = "dispatch_countdown"
            countdown_seconds = _remaining_countdown_seconds(dispatch_state.confirmation_deadline)
        elif dispatch_state.status == "completed":
            dispatch_status = (
                DispatchStatus.CONFIRMED
                if dispatch_state.confirmation_status == "confirmed"
                else DispatchStatus.AUTO_DISPATCHED
            )
            phase = "dispatch_triggered"
            countdown_seconds = None
        elif dispatch_state.status == "cancelled":
            dispatch_status = DispatchStatus.CANCELLED
            phase = "guidance"
            countdown_seconds = None
        elif dispatch_state.desired:
            dispatch_status = DispatchStatus.PENDING_CONFIRMATION
            phase = "dispatch_countdown"
            countdown_seconds = _remaining_countdown_seconds(dispatch_state.confirmation_deadline)
        else:
            dispatch_status = DispatchStatus.NOT_REQUESTED
            if phase == "dispatch_countdown":
                phase = "guidance"
            countdown_seconds = None

    family_notified_initial = previous_execution.family_notified_initial
    family_notified_update = previous_execution.family_notified_update
    if family_state is not None and family_state.status == "completed":
        family_notified_initial = True
        family_notified_update = family_state.occurrence_count > 1

    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        execution_state=ExecutionState(
            phase=phase,
            countdown_seconds=countdown_seconds,
            family_notified_initial=family_notified_initial,
            family_notified_update=family_notified_update,
            dispatch_status=dispatch_status,
            guidance_protocol=previous_execution.guidance_protocol,
            guidance_step_index=previous_execution.guidance_step_index,
        ),
    )


def _store_canonical_dispatch_state(
    session_id: str,
    *,
    session,
    state: SessionState,
    latest_prompt: str,
    dispatch_status: DispatchStatus,
    phase: str,
    countdown_seconds: int | None,
) -> None:
    previous_comm = session.canonical_communication_state
    previous_execution = session.execution_state or ExecutionState()

    fall_session_store.store_canonical_flow_state(
        session_id=session_id,
        state=state,
        communication_state=CommunicationState(
            session_id=session_id,
            state=state,
            mode=previous_comm.mode if previous_comm is not None else "patient_only",
            responder_role=previous_comm.responder_role if previous_comm is not None else "unknown",
            patient_responded=previous_comm.patient_responded if previous_comm is not None else False,
            bystander_present=previous_comm.bystander_present if previous_comm is not None else False,
            conscious=previous_comm.conscious if previous_comm is not None else None,
            breathing_normal=previous_comm.breathing_normal if previous_comm is not None else None,
            flags=list(previous_comm.flags) if previous_comm is not None else [],
            latest_prompt=latest_prompt,
            latest_message=previous_comm.latest_message if previous_comm is not None else "",
            reasoning_call_count=previous_comm.reasoning_call_count if previous_comm is not None else 0,
        ),
        reasoning_decision=session.reasoning_decision,
        execution_state=ExecutionState(
            phase=phase,
            countdown_seconds=countdown_seconds,
            family_notified_initial=previous_execution.family_notified_initial,
            family_notified_update=previous_execution.family_notified_update,
            dispatch_status=dispatch_status,
            guidance_protocol=previous_execution.guidance_protocol,
            guidance_step_index=previous_execution.guidance_step_index,
        ),
    )


def _sync_canonical_dispatch_pending(session_id: str, *, session, dispatch_state: ActionStateSummary) -> None:
    if dispatch_state.status != "pending_confirmation":
        return
    _store_canonical_dispatch_state(
        session_id,
        session=session,
        state=SessionState.AWAITING_DISPATCH_CONFIRMATION,
        latest_prompt="Emergency help is preparing to be dispatched.",
        dispatch_status=DispatchStatus.PENDING_CONFIRMATION,
        phase="dispatch_countdown",
        countdown_seconds=_remaining_countdown_seconds(dispatch_state.confirmation_deadline),
    )


def _sync_canonical_dispatch_executed(
    session_id: str,
    *,
    session,
    confirmation_status: str,
) -> None:
    latest_prompt = "Emergency help has been called."
    dispatch_status = (
        DispatchStatus.CONFIRMED
        if confirmation_status == "confirmed"
        else DispatchStatus.AUTO_DISPATCHED
    )
    _store_canonical_dispatch_state(
        session_id,
        session=session,
        state=SessionState.EXECUTION_IN_PROGRESS,
        latest_prompt=latest_prompt,
        dispatch_status=dispatch_status,
        phase="dispatch_triggered",
        countdown_seconds=None,
    )


def _sync_canonical_dispatch_cancelled(session_id: str, *, session) -> None:
    fallback_prompt = "Emergency dispatch was cancelled. Continue monitoring closely."
    if session.reasoning_decision and session.reasoning_decision.instructions:
        fallback_prompt = session.reasoning_decision.instructions
    _store_canonical_dispatch_state(
        session_id,
        session=session,
        state=SessionState.EXECUTION_IN_PROGRESS,
        latest_prompt=fallback_prompt,
        dispatch_status=DispatchStatus.CANCELLED,
        phase="guidance",
        countdown_seconds=None,
    )


async def _execute_dispatch_action(session_id: str, *, confirmation_status: str) -> ActionStateSummary | None:
    session = fall_session_store.get_session(session_id)
    if session is None or session.latest_assessment is None:
        return None

    state_map = _normalize_action_state_map(session.action_states)
    dispatch_state = state_map["emergency_dispatch"]
    if dispatch_state.status in {"completed", "cancelled"}:
        return dispatch_state

    patient_answers = _answers_from_conversation_history(session.conversation_history)
    patient_profile = load_user_profile(session.event.user_id)
    incident_id = await trigger_emergency(
        patient_id=session.event.user_id,
        severity=_map_assessment_severity_to_dispatch(session.latest_assessment.clinical_assessment.severity),
        vitals=_vitals_to_dispatch_payload(session.vitals),
        flags=["fall_detected", f"motion_state:{session.event.motion_state}", f"session:{session_id}"],
        ai_decision=_build_dispatch_ai_summary(
            assessment=session.latest_assessment,
            patient_answers=patient_answers,
            patient_profile=patient_profile,
        ),
        background_tasks=None,
    )
    completed_detail = (
        "Emergency dispatch was confirmed and executed."
        if confirmation_status == "confirmed"
        else "Emergency dispatch was executed automatically after the 15-second confirmation window expired."
    )
    completed_state = dispatch_state.model_copy(
        update={
            "desired": True,
            "status": "completed",
            "detail": completed_detail,
            "message_text": _render_script_message(dispatch_state.script_lines),
            "requires_confirmation": False,
            "confirmation_status": confirmation_status,
            "countdown_seconds": None,
            "confirmation_deadline": None,
            "incident_id": incident_id,
            "last_updated_at": datetime.utcnow(),
        }
    )
    state_map["emergency_dispatch"] = completed_state

    updated_execution = _set_execution_update(
        session.execution_updates,
        ExecutionUpdate(
            type="emergency_dispatch",
            status="completed",
            detail=completed_detail,
            message_text=completed_state.message_text,
            script_lines=completed_state.script_lines,
            sent_at=completed_state.last_updated_at,
            incident_id=incident_id,
        ),
    )
    fall_session_store.store_action_execution_state(
        session_id=session_id,
        action_states=_ordered_action_states(state_map),
        execution_updates=updated_execution,
    )
    updated_assessment = session.latest_assessment.model_copy(
        update={
            "incident_id": incident_id,
            "status": "dispatch_confirmed",
            "audit": session.latest_assessment.audit.model_copy(update={"dispatch_triggered": True}),
        }
    )
    fall_session_store.set_latest_assessment(session_id=session_id, assessment=updated_assessment)
    refreshed_session = fall_session_store.get_session(session_id)
    if refreshed_session is not None:
        _sync_canonical_dispatch_executed(
            session_id,
            session=refreshed_session,
            confirmation_status=confirmation_status,
        )
        latest_session = fall_session_store.get_session(session_id)
        if latest_session is not None:
            _sync_canonical_execution_snapshot(session_id, session=latest_session)
    return completed_state


async def _run_dispatch_confirmation_timeout(session_id: str, deadline: datetime) -> None:
    try:
        remaining = (deadline - datetime.utcnow()).total_seconds()
        if remaining > 0:
            await asyncio.sleep(remaining)
        current_state = _get_action_state(session_id, "emergency_dispatch")
        if current_state is None or current_state.status != "pending_confirmation":
            return
        if current_state.confirmation_deadline and current_state.confirmation_deadline != deadline:
            return
        await _execute_dispatch_action(session_id, confirmation_status="timed_out")
    except asyncio.CancelledError:
        raise
    finally:
        current_task = _dispatch_confirmation_tasks.get(session_id)
        if current_task is not None and current_task.done():
            _dispatch_confirmation_tasks.pop(session_id, None)


def sync_dispatch_confirmation_task(session_id: str) -> None:
    dispatch_state = _get_action_state(session_id, "emergency_dispatch")
    if dispatch_state is None or dispatch_state.status != "pending_confirmation" or dispatch_state.confirmation_deadline is None:
        _cancel_dispatch_confirmation_task(session_id)
        return

    session = fall_session_store.get_session(session_id)
    if session is not None:
        _sync_canonical_dispatch_pending(session_id, session=session, dispatch_state=dispatch_state)
        latest_session = fall_session_store.get_session(session_id)
        if latest_session is not None:
            _sync_canonical_execution_snapshot(session_id, session=latest_session)

    existing_task = _dispatch_confirmation_tasks.get(session_id)
    if existing_task is not None and not existing_task.done():
        return

    task = asyncio.create_task(_run_dispatch_confirmation_timeout(session_id, dispatch_state.confirmation_deadline))
    _dispatch_confirmation_tasks[session_id] = task


def reset_action_runtime_session(session_id: str) -> None:
    _cancel_dispatch_confirmation_task(session_id)


def sync_action_state_with_assessment(
    *,
    session_id: str,
    assessment: FallAssessment,
    patient_answers: list[PatientAnswer],
) -> tuple[list[ActionStateSummary], list[ExecutionUpdate]]:
    session = fall_session_store.get_session(session_id)
    if session is None:
        return [_default_action_state(action_type) for action_type in MAIN_ACTION_ORDER], []

    patient_profile = load_user_profile(session.event.user_id)
    state_map = _normalize_action_state_map(session.action_states)
    execution_updates = [item.model_copy(deep=True) for item in session.execution_updates]
    now = datetime.utcnow()

    state_map["monitor"] = state_map["monitor"].model_copy(
        update={
            "desired": True,
            "status": "active",
            "reason": "Monitoring continues so the system can detect worsening breathing, pain, or responsiveness.",
            "detail": "Monitoring remains active while the current fall incident is unresolved.",
            "last_updated_at": now,
        }
    )
    execution_updates = _set_execution_update(
        execution_updates,
        ExecutionUpdate(
            type="monitor",
            status="active",
            detail="Monitoring remains active while the incident is being managed.",
            sent_at=now,
        ),
    )

    reminder_sent = any(item.type == "family_fall_reminder" for item in execution_updates)
    if not reminder_sent:
        execution_updates.append(
            ExecutionUpdate(
                type="family_fall_reminder",
                status="completed",
                detail="A non-urgent family reminder was sent because a fall may have occurred.",
                message_text=_render_script_message(_family_reminder_script(patient_profile)),
                script_lines=_family_reminder_script(patient_profile),
                sent_at=now,
            )
        )

    family_action = next(
        (item for item in assessment.response_plan.notification_actions if item.type == "inform_family"),
        None,
    )
    family_state = state_map["contact_family"]
    if family_action is not None:
        family_script = _family_support_script(patient_profile=patient_profile, assessment=assessment)
        family_message = _render_script_message(family_script)
        family_notification_key = _build_family_notification_key(
            assessment=assessment,
            family_script=family_script,
        )
        previous_notification_key = family_state.notification_key
        previous_count = max(family_state.occurrence_count, 0)
        is_new_family_notification = family_notification_key != previous_notification_key
        family_count = previous_count + 1 if is_new_family_notification else max(previous_count, 1)
        family_detail = (
            f"Family support notification #{family_count} was sent with updated incident details."
            if is_new_family_notification and previous_notification_key
            else (
                "A family support notification was sent with the latest incident details."
                if is_new_family_notification
                else f"Family support notification #{family_count} remains the latest sent update."
            )
        )
        state_map["contact_family"] = family_state.model_copy(
            update={
                "desired": True,
                "status": "completed",
                "reason": family_action.reason or "Family support is needed for this fall incident.",
                "detail": family_detail,
                "message_text": family_message,
                "script_lines": family_script,
                "notification_key": family_notification_key,
                "occurrence_count": family_count,
                "last_updated_at": now if is_new_family_notification else family_state.last_updated_at or now,
            }
        )
        execution_updates = _set_execution_update(
            execution_updates,
            ExecutionUpdate(
                type="inform_family",
                status="completed",
                detail=family_detail,
                message_text=family_message,
                script_lines=family_script,
                notification_key=family_notification_key,
                occurrence_count=family_count,
                sent_at=now if is_new_family_notification else family_state.last_updated_at or now,
            ),
        )
    else:
        preserved_status = family_state.status if family_state.status == "completed" else "idle"
        state_map["contact_family"] = family_state.model_copy(
            update={
                "desired": False,
                "status": preserved_status,
                "reason": "No urgent family support request is active in the latest reasoning snapshot.",
                "detail": family_state.detail if preserved_status == "completed" else "",
                "message_text": family_state.message_text if preserved_status == "completed" else "",
                "script_lines": family_state.script_lines if preserved_status == "completed" else [],
                "notification_key": family_state.notification_key if preserved_status == "completed" else None,
                "occurrence_count": family_state.occurrence_count if preserved_status == "completed" else 0,
                "last_updated_at": family_state.last_updated_at if preserved_status == "completed" else None,
            }
        )
        if preserved_status != "completed":
            execution_updates = [item for item in execution_updates if item.type != "inform_family"]

    escalation = assessment.response_plan.escalation_action
    dispatch_requested = escalation.type in {"dispatch_pending_confirmation", "emergency_dispatch"}
    dispatch_state = state_map["emergency_dispatch"]
    existing_deadline = dispatch_state.confirmation_deadline
    if dispatch_requested and dispatch_state.status not in {"completed", "cancelled"}:
        deadline = existing_deadline if existing_deadline and existing_deadline > now else now + timedelta(
            seconds=DISPATCH_CONFIRMATION_WINDOW_SECONDS
        )
        seconds_left = max(1, int((deadline - now).total_seconds()))
        dispatch_detail = (
            "Emergency dispatch is pending confirmation. If there is no response within 15 seconds, dispatch will run automatically."
        )
        dispatch_script = _dispatch_script_lines(
            patient_profile=patient_profile,
            assessment=assessment,
            patient_answers=patient_answers,
        )
        state_map["emergency_dispatch"] = dispatch_state.model_copy(
            update={
                "desired": True,
                "status": "pending_confirmation",
                "reason": escalation.reason or assessment.clinical_assessment.reasoning_summary,
                "detail": dispatch_detail,
                "message_text": _render_script_message(dispatch_script),
                "requires_confirmation": True,
                "confirmation_status": "pending",
                "countdown_seconds": seconds_left,
                "confirmation_deadline": deadline,
                "script_lines": dispatch_script,
                "last_updated_at": now,
            }
        )
        execution_updates = _set_execution_update(
            execution_updates,
        ExecutionUpdate(
            type="emergency_dispatch",
            status="pending_confirmation",
            detail=dispatch_detail,
            message_text=_render_script_message(dispatch_script),
            script_lines=dispatch_script,
            sent_at=now,
        ),
    )
    elif dispatch_state.status == "completed":
        state_map["emergency_dispatch"] = dispatch_state.model_copy(update={"desired": True})
        execution_updates = _set_execution_update(
            execution_updates,
            ExecutionUpdate(
                type="emergency_dispatch",
                status="completed",
                detail=dispatch_state.detail or "Emergency dispatch was executed for this incident.",
                message_text=dispatch_state.message_text,
                script_lines=dispatch_state.script_lines,
                sent_at=dispatch_state.last_updated_at,
                incident_id=dispatch_state.incident_id,
            ),
        )
    elif dispatch_state.status == "cancelled":
        state_map["emergency_dispatch"] = dispatch_state.model_copy(update={"desired": dispatch_requested})
        execution_updates = _set_execution_update(
            execution_updates,
            ExecutionUpdate(
                type="emergency_dispatch",
                status="cancelled",
                detail=dispatch_state.detail or "Emergency dispatch was cancelled before execution.",
                message_text=dispatch_state.message_text,
                script_lines=dispatch_state.script_lines,
                sent_at=dispatch_state.last_updated_at,
            ),
        )
    else:
        state_map["emergency_dispatch"] = dispatch_state.model_copy(
            update={
                "desired": False,
                "status": "idle",
                "reason": "Emergency dispatch is not currently required.",
                "detail": "",
                "message_text": "",
                "requires_confirmation": False,
                "confirmation_status": "not_needed",
                "countdown_seconds": None,
                "confirmation_deadline": None,
                "incident_id": None,
                "script_lines": [],
                "notification_key": None,
                "occurrence_count": 0,
                "last_updated_at": None,
            }
        )
        execution_updates = [item for item in execution_updates if item.type != "emergency_dispatch"]

    ordered_states = _ordered_action_states(state_map)
    fall_session_store.store_action_execution_state(
        session_id=session_id,
        action_states=ordered_states,
        execution_updates=execution_updates,
    )
    refreshed_session = fall_session_store.get_session(session_id)
    if refreshed_session is not None:
        _sync_canonical_execution_snapshot(session_id, session=refreshed_session)
        refreshed_session = fall_session_store.get_session(session_id) or refreshed_session
        refreshed_dispatch_state = next(
            (item for item in refreshed_session.action_states if item.action_type == "emergency_dispatch"),
            None,
        )
        if refreshed_dispatch_state is not None:
            if refreshed_dispatch_state.status == "pending_confirmation":
                _sync_canonical_dispatch_pending(
                    session_id,
                    session=refreshed_session,
                    dispatch_state=refreshed_dispatch_state,
                )
            elif refreshed_dispatch_state.status == "completed":
                _sync_canonical_dispatch_executed(
                    session_id,
                    session=refreshed_session,
                    confirmation_status=refreshed_dispatch_state.confirmation_status or "confirmed",
                )
            elif refreshed_dispatch_state.status == "cancelled":
                _sync_canonical_dispatch_cancelled(session_id, session=refreshed_session)
    return ordered_states, execution_updates


async def apply_session_action_decision(
    session_id: str,
    *,
    action_type: str,
    decision: str,
) -> SessionActionResponse | None:
    session = fall_session_store.get_session(session_id)
    if session is None:
        return None

    if action_type != "emergency_dispatch":
        raise ValueError(f"Unsupported action control: {action_type}")

    state_map = _normalize_action_state_map(session.action_states)
    dispatch_state = state_map["emergency_dispatch"]
    if dispatch_state.status not in {"pending_confirmation", "cancelled", "completed"}:
        raise ValueError("Emergency dispatch is not awaiting a control decision.")

    if decision == "confirm":
        _cancel_dispatch_confirmation_task(session_id)
        updated_state = await _execute_dispatch_action(session_id, confirmation_status="confirmed")
    elif decision == "cancel":
        _cancel_dispatch_confirmation_task(session_id)
        updated_state = dispatch_state.model_copy(
            update={
                "desired": False,
                "status": "cancelled",
                "detail": "Emergency dispatch was cancelled before execution.",
                "message_text": dispatch_state.message_text,
                "requires_confirmation": False,
                "confirmation_status": "cancelled",
                "countdown_seconds": None,
                "confirmation_deadline": None,
                "last_updated_at": datetime.utcnow(),
            }
        )
        state_map["emergency_dispatch"] = updated_state
        execution_updates = _set_execution_update(
            session.execution_updates,
            ExecutionUpdate(
                type="emergency_dispatch",
                status="cancelled",
                detail=updated_state.detail,
                message_text=updated_state.message_text,
                script_lines=updated_state.script_lines,
                sent_at=updated_state.last_updated_at,
            ),
        )
        fall_session_store.store_action_execution_state(
            session_id=session_id,
            action_states=_ordered_action_states(state_map),
            execution_updates=execution_updates,
        )
        refreshed_session = fall_session_store.get_session(session_id)
        if refreshed_session is not None:
            _sync_canonical_dispatch_cancelled(session_id, session=refreshed_session)
            latest_session = fall_session_store.get_session(session_id)
            if latest_session is not None:
                _sync_canonical_execution_snapshot(session_id, session=latest_session)
    else:
        raise ValueError(f"Unsupported decision: {decision}")

    latest_session = fall_session_store.get_session(session_id)
    if latest_session is None or updated_state is None:
        return None
    return SessionActionResponse(
        session_id=session_id,
        action_state=updated_state,
        execution_updates=latest_session.execution_updates,
        state=latest_session.state,
        canonical_communication_state=latest_session.canonical_communication_state,
        reasoning_decision=latest_session.reasoning_decision,
        execution_state=latest_session.execution_state,
    )


def _answers_from_conversation_history(conversation_history) -> list[PatientAnswer]:
    answers: list[PatientAnswer] = []
    for index, message in enumerate(conversation_history):
        if message.role in {"assistant", "system"}:
            continue
        normalized_text = message.text.strip()
        if not normalized_text:
            continue
        answers.append(
            PatientAnswer(
                question_id=f"{message.role}_turn_{index + 1}",
                answer=normalized_text,
            )
        )
    return answers


__all__ = [
    "apply_session_action_decision",
    "build_visible_execution_state_summary",
    "reset_action_runtime_session",
    "sync_action_state_with_assessment",
    "sync_dispatch_confirmation_task",
]
