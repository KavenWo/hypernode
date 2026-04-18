"""Agent runtime seam for routing fall-flow responsibilities by backend."""

from __future__ import annotations

import logging
import os
from typing import Literal, Protocol

AgentBackend = Literal["local", "vertex", "genkit", "adk"]

DEFAULT_AGENT_BACKEND: AgentBackend = "local"
SUPPORTED_AGENT_ROLES = {"vision", "vitals", "reasoning", "communication", "execution"}
ROLE_DEFAULT_BACKENDS: dict[str, AgentBackend] = {
    "vision": "local",
    "vitals": "local",
    "reasoning": "adk",
    "communication": "adk",
    "execution": "genkit",
}

logger = logging.getLogger(__name__)


def _normalize_backend(value: str | None) -> AgentBackend:
    normalized = (value or DEFAULT_AGENT_BACKEND).strip().lower()
    if normalized not in {"local", "vertex", "genkit", "adk"}:
        logger.warning(
            "Unsupported agent backend '%s'; falling back to '%s'.",
            value,
            DEFAULT_AGENT_BACKEND,
        )
        return DEFAULT_AGENT_BACKEND
    return normalized  # type: ignore[return-value]


def get_agent_backend(role: str) -> AgentBackend:
    """Resolve the configured backend for a fall-flow responsibility."""

    normalized_role = (role or "").strip().lower()
    if normalized_role not in SUPPORTED_AGENT_ROLES:
        raise ValueError(
            f"Unsupported fall agent role '{role}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_AGENT_ROLES))}."
        )

    role_env_name = f"AGENT_BACKEND_{normalized_role.upper()}"
    configured_value = os.getenv(role_env_name) or os.getenv("AGENT_BACKEND")
    if configured_value:
        return _normalize_backend(configured_value)
    return ROLE_DEFAULT_BACKENDS.get(normalized_role, DEFAULT_AGENT_BACKEND)


def role_uses_shared_genai_client(role: str) -> bool:
    """Return whether a role still relies on the legacy shared genai.Client path.

    Today, only the local reasoning and communication implementations consume
    the injected `client`. ADK owns its own model calls, Genkit execution does
    not use this client, and the Vertex runtime is still a placeholder.
    """

    return get_agent_backend(role) == "local"


class FallAgentRuntime(Protocol):
    async def inspect_fall_event(self, event): ...

    async def inspect_vitals(self, vitals): ...

    async def assess_clinical_severity(
        self,
        *,
        client,
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance=None,
        patient_answers=None,
    ): ...

    async def analyze_communication_turn(
        self,
        *,
        client,
        event,
        vitals,
        patient_profile,
        conversation_history,
        latest_message: str,
        previous_assessment,
        previous_analysis=None,
        pending_reasoning_context: str = "",
        execution_updates=None,
        acknowledged_reasoning_triggers=None,
    ): ...

    def requires_execution_grounding(self, *, action: str, bystander_actions=None) -> bool: ...

    async def run_execution_grounding(
        self,
        *,
        action: str,
        clinical_assessment,
        patient_profile,
        patient_answers,
    ): ...


class LocalFallAgentRuntime:
    """Phase A runtime that delegates to the current in-repo implementations."""

    async def inspect_fall_event(self, event):
        from agents.sentinel.vision_agent import inspect_fall_event as local_inspect_fall_event

        return await local_inspect_fall_event(event)

    async def inspect_vitals(self, vitals):
        from agents.sentinel.vital_agent import inspect_vitals as local_inspect_vitals

        return await local_inspect_vitals(vitals)

    async def assess_clinical_severity(
        self,
        *,
        client,
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance=None,
        patient_answers=None,
    ):
        from agents.reasoning.clinical_reasoning_service import (
            assess_clinical_severity as local_assess_clinical_severity,
        )

        return await local_assess_clinical_severity(
            client=client,
            event=event,
            patient_profile=patient_profile,
            vision_assessment=vision_assessment,
            vital_assessment=vital_assessment,
            grounded_medical_guidance=grounded_medical_guidance,
            patient_answers=patient_answers,
        )

    async def analyze_communication_turn(
        self,
        *,
        client,
        event,
        vitals,
        patient_profile,
        conversation_history,
        latest_message: str,
        previous_assessment,
        previous_analysis=None,
        pending_reasoning_context: str = "",
        execution_updates=None,
        acknowledged_reasoning_triggers=None,
    ):
        from agents.communication.session_agent import (
            analyze_communication_turn as local_analyze_communication_turn,
        )

        return await local_analyze_communication_turn(
            client=client,
            event=event,
            vitals=vitals,
            patient_profile=patient_profile,
            conversation_history=conversation_history,
            latest_message=latest_message,
            previous_assessment=previous_assessment,
            previous_analysis=previous_analysis,
            pending_reasoning_context=pending_reasoning_context,
            execution_updates=execution_updates,
            acknowledged_reasoning_triggers=acknowledged_reasoning_triggers,
        )

    def requires_execution_grounding(self, *, action: str, bystander_actions=None) -> bool:
        from agents.execution.execution_agent import (
            requires_execution_grounding as local_requires_execution_grounding,
        )

        return local_requires_execution_grounding(
            action=action,
            bystander_actions=bystander_actions,
        )

    async def run_execution_grounding(
        self,
        *,
        action: str,
        clinical_assessment,
        patient_profile,
        patient_answers,
    ):
        from agents.execution.execution_agent import run_execution_grounding as local_run_execution_grounding

        return await local_run_execution_grounding(
            action=action,
            clinical_assessment=clinical_assessment,
            patient_profile=patient_profile,
            patient_answers=patient_answers,
        )


class VertexFallAgentRuntime:
    """Placeholder runtime for later Vertex agent cutover phases."""

    @staticmethod
    def _not_implemented(role: str) -> NotImplementedError:
        return NotImplementedError(
            f"Vertex backend is not implemented yet for the '{role}' fall agent responsibility."
        )

    async def inspect_fall_event(self, event):
        raise self._not_implemented("vision")

    async def inspect_vitals(self, vitals):
        raise self._not_implemented("vitals")

    async def assess_clinical_severity(
        self,
        *,
        client,
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance=None,
        patient_answers=None,
    ):
        raise self._not_implemented("reasoning")

    async def analyze_communication_turn(
        self,
        *,
        client,
        event,
        vitals,
        patient_profile,
        conversation_history,
        latest_message: str,
        previous_assessment,
        previous_analysis=None,
        pending_reasoning_context: str = "",
        execution_updates=None,
        acknowledged_reasoning_triggers=None,
    ):
        raise self._not_implemented("communication")

    def requires_execution_grounding(self, *, action: str, bystander_actions=None) -> bool:
        raise self._not_implemented("execution")

    async def run_execution_grounding(
        self,
        *,
        action: str,
        clinical_assessment,
        patient_profile,
        patient_answers,
    ):
        raise self._not_implemented("execution")


class GenkitFallAgentRuntime:
    """Phase B runtime that starts with execution-agent support only."""

    @staticmethod
    def _not_implemented(role: str) -> NotImplementedError:
        return NotImplementedError(
            f"Genkit backend is not implemented yet for the '{role}' fall agent responsibility."
        )

    async def inspect_fall_event(self, event):
        raise self._not_implemented("vision")

    async def inspect_vitals(self, vitals):
        raise self._not_implemented("vitals")

    async def assess_clinical_severity(
        self,
        *,
        client,
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance=None,
        patient_answers=None,
    ):
        raise self._not_implemented("reasoning")

    async def analyze_communication_turn(
        self,
        *,
        client,
        event,
        vitals,
        patient_profile,
        conversation_history,
        latest_message: str,
        previous_assessment,
        previous_analysis=None,
        pending_reasoning_context: str = "",
        execution_updates=None,
        acknowledged_reasoning_triggers=None,
    ):
        raise self._not_implemented("communication")

    def requires_execution_grounding(self, *, action: str, bystander_actions=None) -> bool:
        from agents.execution.execution_agent import (
            requires_execution_grounding as local_requires_execution_grounding,
        )

        return local_requires_execution_grounding(
            action=action,
            bystander_actions=bystander_actions,
        )

    async def run_execution_grounding(
        self,
        *,
        action: str,
        clinical_assessment,
        patient_profile,
        patient_answers,
    ):
        from app.fall.genkit_execution import run_genkit_execution_plan
        from app.fall.adk_execution import run_adk_execution_plan

        try:
            return await run_genkit_execution_plan(
                action=action,
                clinical_assessment=clinical_assessment,
                patient_profile=patient_profile,
                patient_answers=patient_answers,
            )
        except RuntimeError:
            logger.exception("Genkit execution backend unavailable; falling back to ADK execution | action=%s", action)
            return await run_adk_execution_plan(
                action=action,
                clinical_assessment=clinical_assessment,
                patient_profile=patient_profile,
                patient_answers=patient_answers,
            )


class AdkFallAgentRuntime:
    """Phase migration runtime that uses ADK for reasoning, communication, and execution."""

    @staticmethod
    def _not_implemented(role: str) -> NotImplementedError:
        return NotImplementedError(
            f"ADK backend is not implemented yet for the '{role}' fall agent responsibility."
        )

    async def inspect_fall_event(self, event):
        raise self._not_implemented("vision")

    async def inspect_vitals(self, vitals):
        raise self._not_implemented("vitals")

    async def assess_clinical_severity(
        self,
        *,
        client,
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance=None,
        patient_answers=None,
    ):
        from app.fall.adk_reasoning import assess_clinical_severity_with_adk

        return await assess_clinical_severity_with_adk(
            event=event,
            patient_profile=patient_profile,
            vision_assessment=vision_assessment,
            vital_assessment=vital_assessment,
            grounded_medical_guidance=grounded_medical_guidance,
            patient_answers=patient_answers,
        )

    async def analyze_communication_turn(
        self,
        *,
        client,
        event,
        vitals,
        patient_profile,
        conversation_history,
        latest_message: str,
        previous_assessment,
        previous_analysis=None,
        pending_reasoning_context: str = "",
        execution_updates=None,
        acknowledged_reasoning_triggers=None,
    ):
        from app.fall.adk_communication import analyze_communication_turn_with_adk

        return await analyze_communication_turn_with_adk(
            event=event,
            vitals=vitals,
            patient_profile=patient_profile,
            conversation_history=conversation_history,
            latest_message=latest_message,
            previous_assessment=previous_assessment,
            previous_analysis=previous_analysis,
            pending_reasoning_context=pending_reasoning_context,
            execution_updates=execution_updates,
            acknowledged_reasoning_triggers=acknowledged_reasoning_triggers,
        )

    def requires_execution_grounding(self, *, action: str, bystander_actions=None) -> bool:
        from agents.execution.execution_agent import (
            requires_execution_grounding as local_requires_execution_grounding,
        )

        return local_requires_execution_grounding(
            action=action,
            bystander_actions=bystander_actions,
        )

    async def run_execution_grounding(
        self,
        *,
        action: str,
        clinical_assessment,
        patient_profile,
        patient_answers,
    ):
        from app.fall.adk_execution import run_adk_execution_plan

        return await run_adk_execution_plan(
            action=action,
            clinical_assessment=clinical_assessment,
            patient_profile=patient_profile,
            patient_answers=patient_answers,
        )


_LOCAL_RUNTIME = LocalFallAgentRuntime()
_VERTEX_RUNTIME = VertexFallAgentRuntime()
_GENKIT_RUNTIME = GenkitFallAgentRuntime()
_ADK_RUNTIME = AdkFallAgentRuntime()


def _runtime_for(role: str) -> FallAgentRuntime:
    backend = get_agent_backend(role)
    if backend == "vertex":
        return _VERTEX_RUNTIME
    if backend == "genkit":
        return _GENKIT_RUNTIME
    if backend == "adk":
        return _ADK_RUNTIME
    return _LOCAL_RUNTIME


class RoutedFallAgentRuntime:
    """Route each responsibility independently so migration can happen gradually."""

    async def inspect_fall_event(self, event):
        return await _runtime_for("vision").inspect_fall_event(event)

    async def inspect_vitals(self, vitals):
        return await _runtime_for("vitals").inspect_vitals(vitals)

    async def assess_clinical_severity(
        self,
        *,
        client,
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance=None,
        patient_answers=None,
    ):
        return await _runtime_for("reasoning").assess_clinical_severity(
            client=client,
            event=event,
            patient_profile=patient_profile,
            vision_assessment=vision_assessment,
            vital_assessment=vital_assessment,
            grounded_medical_guidance=grounded_medical_guidance,
            patient_answers=patient_answers,
        )

    async def analyze_communication_turn(
        self,
        *,
        client,
        event,
        vitals,
        patient_profile,
        conversation_history,
        latest_message: str,
        previous_assessment,
        previous_analysis=None,
        pending_reasoning_context: str = "",
        execution_updates=None,
        acknowledged_reasoning_triggers=None,
    ):
        return await _runtime_for("communication").analyze_communication_turn(
            client=client,
            event=event,
            vitals=vitals,
            patient_profile=patient_profile,
            conversation_history=conversation_history,
            latest_message=latest_message,
            previous_assessment=previous_assessment,
            previous_analysis=previous_analysis,
            pending_reasoning_context=pending_reasoning_context,
            execution_updates=execution_updates,
            acknowledged_reasoning_triggers=acknowledged_reasoning_triggers,
        )

    def requires_execution_grounding(self, *, action: str, bystander_actions=None) -> bool:
        return _runtime_for("execution").requires_execution_grounding(
            action=action,
            bystander_actions=bystander_actions,
        )

    async def run_execution_grounding(
        self,
        *,
        action: str,
        clinical_assessment,
        patient_profile,
        patient_answers,
    ):
        return await _runtime_for("execution").run_execution_grounding(
            action=action,
            clinical_assessment=clinical_assessment,
            patient_profile=patient_profile,
            patient_answers=patient_answers,
        )


_ROUTED_RUNTIME = RoutedFallAgentRuntime()


def get_fall_agent_runtime() -> RoutedFallAgentRuntime:
    return _ROUTED_RUNTIME
