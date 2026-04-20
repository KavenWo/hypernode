"""Unified agent runtime for fall-flow responsibilities.

This module has been simplified to remove multi-backend routing logic.
All agents now run via the modern ADK or Genkit implementations.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class FallAgentRuntime(Protocol):
    async def inspect_fall_event(self, event): ...

    async def inspect_vitals(self, vitals): ...

    async def assess_clinical_severity(
        self,
        *,
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


class ConsolidatedFallAgentRuntime:
    """Unified runtime that uses ADK and Genkit for all fall agent responsibilities."""

    async def inspect_fall_event(self, event):
        """Bridge to the Sentinel vision agent."""
        from agents.sentinel.vision_agent import inspect_fall_event as local_inspect_fall_event

        return await local_inspect_fall_event(event)

    async def inspect_vitals(self, vitals):
        """Bridge to the Sentinel vitals agent."""
        from agents.sentinel.vital_agent import inspect_vitals as local_inspect_vitals

        return await local_inspect_vitals(vitals)

    async def assess_clinical_severity(
        self,
        *,
        event,
        patient_profile,
        vision_assessment,
        vital_assessment,
        grounded_medical_guidance=None,
        patient_answers=None,
    ):
        """Call the primary ADK clinical reasoning agent."""
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
        """Call the primary ADK communication agent."""
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
        """Determining if grounding is needed via the shared execution policy."""
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
        """Run execution grounding via Genkit with a reliable ADK fallback."""
        from app.fall.adk_execution import run_adk_execution_plan
        from app.fall.genkit_execution import run_genkit_execution_plan

        try:
            return await run_genkit_execution_plan(
                action=action,
                clinical_assessment=clinical_assessment,
                patient_profile=patient_profile,
                patient_answers=patient_answers,
            )
        except Exception:
            logger.exception(
                "Genkit execution backend unavailable; falling back to ADK execution | action=%s",
                action,
            )
            return await run_adk_execution_plan(
                action=action,
                clinical_assessment=clinical_assessment,
                patient_profile=patient_profile,
                patient_answers=patient_answers,
            )


_SINGLE_RUNTIME = ConsolidatedFallAgentRuntime()


def get_fall_agent_runtime() -> FallAgentRuntime:
    """Return the unified agent runtime."""
    return _SINGLE_RUNTIME  # type: ignore[return-value]


def get_agent_backend(role: str) -> str:
    """Legacy helper for telemetry; all roles now use 'adk' or 'genkit'."""
    if role == "execution":
        return "genkit"
    return "adk"
