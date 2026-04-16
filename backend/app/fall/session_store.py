"""In-memory fall session store for the Phase 4 communication loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from agents.shared.schemas import (
    CommunicationAgentAnalysis,
    ConversationMessage,
    ExecutionUpdate,
    FallAssessment,
    FallEvent,
    InteractionInput,
    InteractionSummary,
    VitalSigns,
)


@dataclass
class FallSessionRecord:
    session_id: str
    event: FallEvent
    vitals: VitalSigns | None = None
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
    version: int = 0
    execution_updates: list[ExecutionUpdate] = field(default_factory=list)
    announced_execution_types: set[str] = field(default_factory=set)


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

    def update_context(
        self,
        *,
        session_id: str,
        event: FallEvent,
        vitals: VitalSigns | None,
        interaction_input: InteractionInput,
    ) -> FallSessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.event = event.model_copy(deep=True)
            record.vitals = vitals.model_copy(deep=True) if vitals else None
            record.interaction_input = interaction_input.model_copy(deep=True)
            record.reasoning_input_version += 1
            self._touch_locked(record)
            return self._copy_record(record)

    def append_messages(self, session_id: str, messages: list[ConversationMessage]) -> FallSessionRecord | None:
        clean_messages = [message.model_copy(deep=True) for message in messages if message.text.strip()]
        if not clean_messages:
            return self.get_session(session_id)
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.conversation_history.extend(clean_messages)
            if any(message.role not in {"assistant", "system"} for message in clean_messages):
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
    ) -> bool:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return False
            record.latest_assessment = assessment.model_copy(deep=True)
            if assessment.interaction is not None:
                record.interaction_summary = assessment.interaction.model_copy(deep=True)
            record.reasoning_error = None
            if execution_updates is not None:
                record.execution_updates = [item.model_copy(deep=True) for item in execution_updates]
            if assistant_message and assistant_message.text.strip():
                should_append = (
                    not record.conversation_history
                    or record.conversation_history[-1].role != assistant_message.role
                    or record.conversation_history[-1].text != assistant_message.text
                )
                if should_append:
                    record.conversation_history.append(assistant_message.model_copy(deep=True))
            if record.reasoning_requested_version > processed_version:
                record.reasoning_status = "pending"
                record.reasoning_reason = "Newer clinical input arrived. Refreshing reasoning."
                self._touch_locked(record)
                return True
            record.reasoning_completed_version = processed_version
            record.reasoning_active_version = 0
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

    def fail_reasoning(self, *, session_id: str, error_message: str) -> bool:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return False
            if record.reasoning_requested_version > record.reasoning_active_version:
                record.reasoning_status = "pending"
                record.reasoning_reason = "Retrying reasoning after newer clinical input arrived."
                record.reasoning_error = error_message
                self._touch_locked(record)
                return True
            record.reasoning_active_version = 0
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
            version=record.version,
            execution_updates=[item.model_copy(deep=True) for item in record.execution_updates],
            announced_execution_types=set(record.announced_execution_types),
        )


fall_session_store = FallSessionStore()


__all__ = ["FallSessionRecord", "FallSessionStore", "fall_session_store"]
