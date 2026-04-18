"""In-memory fall session store for the Phase 4 communication loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from agents.shared.schemas import (
    ActionStateSummary,
    CommunicationAgentAnalysis,
    CommunicationState,
    ConversationMessage,
    ExecutionState,
    ExecutionUpdate,
    FallAssessment,
    FallEvent,
    InteractionInput,
    InteractionSummary,
    ReasoningDecision,
    ReasoningRunSummary,
    SessionState,
    VitalSigns,
)


@dataclass
class FallSessionRecord:
    session_id: str
    event: FallEvent
    vitals: VitalSigns | None = None
    state: SessionState = SessionState.IDLE
    canonical_communication_state: CommunicationState | None = None
    reasoning_decision: ReasoningDecision | None = None
    execution_state: ExecutionState | None = None
    interaction_input: InteractionInput = field(default_factory=InteractionInput)
    interaction_summary: InteractionSummary | None = None
    latest_analysis: CommunicationAgentAnalysis | None = None
    latest_assessment: FallAssessment | None = None
    conversation_history: list[ConversationMessage] = field(default_factory=list)
    reasoning_status: str = "idle"
    reasoning_reason: str = ""
    reasoning_error: str | None = None
    reasoning_input_version: int = 0
    reasoning_requested_version: int = 0
    reasoning_active_version: int = 0
    reasoning_completed_version: int = 0
    reasoning_run_count: int = 0
    active_reasoning_run_number: int = 0
    reasoning_triggered_fact_keys: set[str] = field(default_factory=set)
    active_protocol_key: str = ""
    active_protocol_step_index: int = 0
    version: int = 0
    execution_updates: list[ExecutionUpdate] = field(default_factory=list)
    action_states: list[ActionStateSummary] = field(default_factory=list)
    reasoning_runs: list[ReasoningRunSummary] = field(default_factory=list)
    announced_execution_types: set[str] = field(default_factory=set)
    pending_reasoning_context: str = ""


class FallSessionStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, FallSessionRecord] = {}

    def create_session(
        self,
        *,
        event: FallEvent,
        vitals: VitalSigns | None,
        interaction_input: InteractionInput,
    ) -> FallSessionRecord:
        session_id = f"phase4-{uuid4().hex[:12]}"
        record = FallSessionRecord(
            session_id=session_id,
            event=event.model_copy(deep=True),
            vitals=vitals.model_copy(deep=True) if vitals else None,
            state=SessionState.FALL_DETECTED,
            canonical_communication_state=CommunicationState(
                session_id=session_id,
                state=SessionState.FALL_DETECTED,
            ),
            execution_state=ExecutionState(),
            interaction_input=interaction_input.model_copy(deep=True),
            reasoning_input_version=1,
            version=1,
        )
        with self._lock:
            self._sessions[session_id] = record
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            return self._copy_record(record)

    def remove_session(self, session_id: str) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.pop(session_id, None)
            if record is None:
                return None
            return self._copy_record(record)

    def update_context(
        self,
        *,
        session_id: str,
        event: FallEvent,
        vitals: VitalSigns | None,
        interaction_input: InteractionInput,
        bump_reasoning_version: bool = True,
    ) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            context_changed = (
                record.event.model_dump() != event.model_dump()
                or (record.vitals.model_dump() if record.vitals else None)
                != (vitals.model_dump() if vitals else None)
                or record.interaction_input.model_dump() != interaction_input.model_dump()
            )
            record.event = event.model_copy(deep=True)
            record.vitals = vitals.model_copy(deep=True) if vitals else None
            record.interaction_input = interaction_input.model_copy(deep=True)
            if bump_reasoning_version and context_changed:
                record.reasoning_input_version += 1
            self._touch_locked(record)
            return self._copy_record(record)

    def append_messages(
        self,
        session_id: str,
        messages: list[ConversationMessage],
        *,
        bump_reasoning_version: bool = False,
    ) -> FallSessionRecord | None:
        clean_messages = [message.model_copy(deep=True) for message in messages if message.text.strip()]
        if not clean_messages:
            return self.get_session(session_id)
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            for message in clean_messages:
                if message.session_version is None:
                    message.session_version = record.version + 1
                if message.reasoning_input_version is None:
                    message.reasoning_input_version = record.reasoning_input_version
            record.conversation_history.extend(clean_messages)
            if bump_reasoning_version and any(message.role not in {"assistant", "system"} for message in clean_messages):
                record.reasoning_input_version += 1
            self._touch_locked(record)
            return self._copy_record(record)

    def store_turn_state(
        self,
        *,
        session_id: str,
        interaction_summary: InteractionSummary,
        latest_analysis: CommunicationAgentAnalysis,
    ) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.interaction_summary = interaction_summary.model_copy(deep=True)
            record.latest_analysis = latest_analysis.model_copy(deep=True)
            self._touch_locked(record)
            return self._copy_record(record)

    def store_canonical_flow_state(
        self,
        *,
        session_id: str,
        state: SessionState | None = None,
        communication_state: CommunicationState | None = None,
        reasoning_decision: ReasoningDecision | None = None,
        execution_state: ExecutionState | None = None,
    ) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            if state is not None:
                record.state = state
            if communication_state is not None:
                record.canonical_communication_state = communication_state.model_copy(deep=True)
            if reasoning_decision is not None:
                record.reasoning_decision = reasoning_decision.model_copy(deep=True)
            if execution_state is not None:
                record.execution_state = execution_state.model_copy(deep=True)
            self._touch_locked(record)
            return self._copy_record(record)

    def request_reasoning(self, *, session_id: str, reason: str) -> bool:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return False
            record.reasoning_requested_version = max(
                record.reasoning_requested_version,
                record.reasoning_input_version,
            )
            if record.reasoning_status == "pending":
                record.reasoning_reason = reason
                self._touch_locked(record)
                return False
            record.reasoning_status = "pending"
            record.reasoning_reason = reason
            record.reasoning_error = None
            record.reasoning_active_version = 0
            self._touch_locked(record)
            return True

    def begin_reasoning_run(self, *, session_id: str) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None or record.reasoning_status != "pending":
                return None
            record.reasoning_active_version = max(
                record.reasoning_requested_version,
                record.reasoning_input_version,
            )
            next_run_number = len(record.reasoning_runs) + 1
            record.active_reasoning_run_number = next_run_number
            record.reasoning_runs.append(
                ReasoningRunSummary(
                    run_number=next_run_number,
                    processed_version=record.reasoning_active_version,
                    reasoning_status="running",
                    reasoning_reason=record.reasoning_reason,
                    assessment=None,
                    execution_updates=[],
                )
            )
            self._touch_locked(record)
            return self._copy_record(record)

    def register_reasoning_trigger_facts(self, *, session_id: str, fact_keys: list[str]) -> FallSessionRecord | None:
        normalized_keys = {item.strip().lower() for item in fact_keys if item and item.strip()}
        if not normalized_keys:
            return self.get_session(session_id)
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            if not normalized_keys.issubset(record.reasoning_triggered_fact_keys):
                record.reasoning_triggered_fact_keys.update(normalized_keys)
                self._touch_locked(record)
            return self._copy_record(record)

    def complete_reasoning(
        self,
        *,
        session_id: str,
        processed_version: int,
        assessment: FallAssessment,
        assistant_message: ConversationMessage | None = None,
        execution_updates: list[ExecutionUpdate] | None = None,
        pending_reasoning_context: str = "",
    ) -> bool:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return False
            record.latest_assessment = assessment.model_copy(deep=True)
            # NOTE: interaction_summary is NOT overwritten here.
            # The communication agent is the sole authority on interaction state.
            protocol_key = assessment.protocol_guidance.protocol_key if assessment.protocol_guidance else ""
            protocol_steps = assessment.protocol_guidance.steps if assessment.protocol_guidance else []
            if protocol_key and protocol_steps:
                if record.active_protocol_key != protocol_key:
                    record.active_protocol_key = protocol_key
                    record.active_protocol_step_index = 0
                else:
                    record.active_protocol_step_index = min(
                        record.active_protocol_step_index,
                        max(len(protocol_steps) - 1, 0),
                    )
            else:
                record.active_protocol_key = ""
                record.active_protocol_step_index = 0
            record.reasoning_error = None
            if execution_updates is not None:
                record.execution_updates = [item.model_copy(deep=True) for item in execution_updates]
            # Only append auto-messages for time-critical notifications
            # (emergency dispatch, family notification). The caller controls this.
            if assistant_message and assistant_message.text.strip():
                should_append = (
                    not record.conversation_history
                    or record.conversation_history[-1].role != assistant_message.role
                    or record.conversation_history[-1].text != assistant_message.text
                )
                if should_append:
                    assistant_copy = assistant_message.model_copy(deep=True)
                    if assistant_copy.session_version is None:
                        assistant_copy.session_version = record.version + 1
                    if assistant_copy.reasoning_input_version is None:
                        assistant_copy.reasoning_input_version = processed_version
                    record.conversation_history.append(assistant_copy)
            # Store reasoning context for the communication agent to consume on next turn
            if pending_reasoning_context:
                record.pending_reasoning_context = pending_reasoning_context
            record.reasoning_run_count += 1
            active_run_number = record.active_reasoning_run_number
            if active_run_number > 0:
                for index, item in enumerate(record.reasoning_runs):
                    if item.run_number == active_run_number:
                        record.reasoning_runs[index] = item.model_copy(
                            update={
                                "processed_version": processed_version,
                                "reasoning_status": "completed",
                                "reasoning_reason": assessment.clinical_assessment.reasoning_summary,
                                "assessment": assessment.model_copy(deep=True),
                                "execution_updates": [entry.model_copy(deep=True) for entry in record.execution_updates],
                            }
                        )
                        break
            else:
                record.reasoning_runs.append(
                    ReasoningRunSummary(
                        run_number=len(record.reasoning_runs) + 1,
                        processed_version=processed_version,
                        reasoning_status="completed",
                        reasoning_reason=assessment.clinical_assessment.reasoning_summary,
                        assessment=assessment.model_copy(deep=True),
                        execution_updates=[item.model_copy(deep=True) for item in record.execution_updates],
                    )
                )
            if record.reasoning_requested_version > processed_version:
                record.reasoning_status = "pending"
                record.reasoning_reason = "Newer clinical input arrived. Refreshing reasoning."
                record.active_reasoning_run_number = 0
                self._touch_locked(record)
                return True
            record.reasoning_completed_version = processed_version
            record.reasoning_active_version = 0
            record.active_reasoning_run_number = 0
            record.reasoning_status = "completed"
            record.reasoning_reason = "Latest reasoning snapshot is ready."
            self._touch_locked(record)
            return False

    def mark_execution_announced(self, *, session_id: str, execution_type: str) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            if execution_type not in record.announced_execution_types:
                record.announced_execution_types.add(execution_type)
                self._touch_locked(record)
            return self._copy_record(record)

    def set_protocol_step_index(self, *, session_id: str, step_index: int) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.active_protocol_step_index = max(0, step_index)
            if record.execution_state is not None:
                record.execution_state = record.execution_state.model_copy(
                    update={"guidance_step_index": max(0, step_index)}
                )
            self._touch_locked(record)
            return self._copy_record(record)

    def store_action_execution_state(
        self,
        *,
        session_id: str,
        action_states: list[ActionStateSummary],
        execution_updates: list[ExecutionUpdate],
    ) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.action_states = [item.model_copy(deep=True) for item in action_states]
            record.execution_updates = [item.model_copy(deep=True) for item in execution_updates]
            self._touch_locked(record)
            return self._copy_record(record)

    def set_latest_assessment(self, *, session_id: str, assessment: FallAssessment) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.latest_assessment = assessment.model_copy(deep=True)
            self._touch_locked(record)
            return self._copy_record(record)

    def consume_pending_context(self, session_id: str) -> str:
        """Read and clear the one-time reasoning context for the next turn."""
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return ""
            context = record.pending_reasoning_context
            record.pending_reasoning_context = ""
            if context:
                self._touch_locked(record)
            return context

    def store_pending_context(self, *, session_id: str, context: str) -> FallSessionRecord | None:
        """Update the one-time communication context without mutating reasoning state."""
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.pending_reasoning_context = context
            self._touch_locked(record)
            return self._copy_record(record)

    def fail_reasoning(self, *, session_id: str, error_message: str) -> bool:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return False
            if record.reasoning_requested_version > record.reasoning_active_version:
                record.reasoning_status = "pending"
                record.reasoning_reason = "Retrying reasoning after newer clinical input arrived."
                record.reasoning_error = error_message
                if record.active_reasoning_run_number > 0:
                    for index, item in enumerate(record.reasoning_runs):
                        if item.run_number == record.active_reasoning_run_number:
                            record.reasoning_runs[index] = item.model_copy(
                                update={
                                    "reasoning_status": "failed",
                                    "reasoning_reason": error_message,
                                }
                            )
                            break
                    record.active_reasoning_run_number = 0
                self._touch_locked(record)
                return True
            record.reasoning_active_version = 0
            if record.active_reasoning_run_number > 0:
                for index, item in enumerate(record.reasoning_runs):
                    if item.run_number == record.active_reasoning_run_number:
                        record.reasoning_runs[index] = item.model_copy(
                            update={
                                "reasoning_status": "failed",
                                "reasoning_reason": error_message,
                            }
                        )
                        break
                record.active_reasoning_run_number = 0
            record.reasoning_status = "failed"
            record.reasoning_error = error_message
            record.reasoning_reason = "Background reasoning failed."
            self._touch_locked(record)
            return False

    @staticmethod
    def _touch_locked(record: FallSessionRecord) -> None:
        record.version += 1

    @staticmethod
    def _copy_record(record: FallSessionRecord) -> FallSessionRecord:
        return FallSessionRecord(
            session_id=record.session_id,
            event=record.event.model_copy(deep=True),
            vitals=record.vitals.model_copy(deep=True) if record.vitals else None,
            state=record.state,
            canonical_communication_state=(
                record.canonical_communication_state.model_copy(deep=True)
                if record.canonical_communication_state
                else None
            ),
            reasoning_decision=record.reasoning_decision.model_copy(deep=True) if record.reasoning_decision else None,
            execution_state=record.execution_state.model_copy(deep=True) if record.execution_state else None,
            interaction_input=record.interaction_input.model_copy(deep=True),
            interaction_summary=record.interaction_summary.model_copy(deep=True) if record.interaction_summary else None,
            latest_analysis=record.latest_analysis.model_copy(deep=True) if record.latest_analysis else None,
            latest_assessment=record.latest_assessment.model_copy(deep=True) if record.latest_assessment else None,
            conversation_history=[message.model_copy(deep=True) for message in record.conversation_history],
            reasoning_status=record.reasoning_status,
            reasoning_reason=record.reasoning_reason,
            reasoning_error=record.reasoning_error,
            reasoning_input_version=record.reasoning_input_version,
            reasoning_requested_version=record.reasoning_requested_version,
            reasoning_active_version=record.reasoning_active_version,
            reasoning_completed_version=record.reasoning_completed_version,
            reasoning_run_count=record.reasoning_run_count,
            active_reasoning_run_number=record.active_reasoning_run_number,
            reasoning_triggered_fact_keys=set(record.reasoning_triggered_fact_keys),
            active_protocol_key=record.active_protocol_key,
            active_protocol_step_index=record.active_protocol_step_index,
            version=record.version,
            execution_updates=[item.model_copy(deep=True) for item in record.execution_updates],
            action_states=[item.model_copy(deep=True) for item in record.action_states],
            reasoning_runs=[item.model_copy(deep=True) for item in record.reasoning_runs],
            announced_execution_types=set(record.announced_execution_types),
            pending_reasoning_context=record.pending_reasoning_context,
        )


fall_session_store = FallSessionStore()


__all__ = ["FallSessionRecord", "FallSessionStore", "fall_session_store"]
