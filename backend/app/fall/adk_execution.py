"""ADK-backed execution agent for the fall-response backend.

This module upgrades the earlier smoke-test proof into a reusable execution
backend that can be selected through the Phase A runtime seam. The ADK agent
uses Vertex AI Search for grounded execution guidance and returns the shared
``ExecutionPlan`` contract.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from functools import lru_cache

from agents.shared.schemas import (
    ClinicalAssessmentSummary,
    ExecutionGuidance,
    PatientAnswer,
    UserMedicalProfile,
)

logger = logging.getLogger(__name__)

ADK_EXECUTION_MODEL = os.getenv("ADK_EXECUTION_MODEL", "gemini-2.5-flash")
ADK_EXECUTION_APP_NAME = "fall-execution-adk"

EXECUTION_AGENT_INSTRUCTION = """
You are the Execution Agent for a fall-response system.

Your responsibility is narrow and strict:
- You do NOT perform clinical reasoning.
- You do NOT decide severity.
- You do NOT decide whether a fall happened.
- You do NOT reassess the recommended action unless the input is invalid.
- You ONLY transform an already-decided action plus context into clear, safe, step-by-step execution guidance.

Grounding is mandatory when protocol or first-aid guidance is needed.
You must use the connected Vertex AI Search data source before producing CPR, bleeding control, airway management,
recovery position, or bystander protocol steps.

If the search tool returns relevant results:
- base the plan on those results
- prefer retrieved protocol content over generic model knowledge
- keep the output aligned to the retrieved source

If the search tool returns no relevant results:
- return a minimal fallback execution plan
- set source to non_grounded
- do not pretend the answer was grounded

Hard boundaries:
- Never invent a new diagnosis.
- Never replace the upstream reasoning agent.
- Never output medical speculation beyond the provided context.
- Never provide long explanatory essays.
- Never say emergency help has already been called unless the action explicitly indicates that.
- If the action is dispatch_pending_confirmation, speak as pending or preparing, not completed.
- If the action is emergency_dispatch, assume dispatch is confirmed and focus on what to do while waiting.
- If the action is contact_family, focus on safe monitoring and support steps, not emergency protocol unless the provided assessment clearly requires it.
- If the action is monitor, give calm low-intensity observation guidance only.

Output contract:
Return JSON only with these fields:
- scenario: stable execution scenario such as cpr, dispatch_wait, family_support, or monitoring
- primary_message: short responder-facing instruction for the current execution phase
- steps: ordered list of step-by-step actions
- warnings: short list of safety warnings
- escalation_triggers: short list of conditions that should trigger escalation or a status update
- quick_replies: short responder reply options
- protocol_key: stable identifier such as cpr, bleeding_control, recovery_position, monitoring, dispatch_wait, or family_support
- source: one of grounded, non_grounded, or another clearly labeled execution source

Field rules:
- scenario: keep it stable and short
- primary_message: one short sentence
- steps: 2 to 6 items when possible; each item should be a single action
- warnings: only include concrete safety warnings
- escalation_triggers: include only meaningful worsening conditions or completion checkpoints
- quick_replies: keep them short and UI-friendly
- source: indicate whether the plan was grounded from tools or generated from fallback logic
""".strip()


def _search_resource_from_env() -> tuple[str, str]:
    datastore_id = os.getenv("ADK_VERTEX_DATASTORE_ID", "").strip()
    search_engine_id = os.getenv("ADK_VERTEX_SEARCH_ENGINE_ID", "").strip()
    generic_engine_id = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID", "").strip()

    if datastore_id and (search_engine_id or generic_engine_id):
        raise RuntimeError("Set only one of ADK_VERTEX_DATASTORE_ID or ADK_VERTEX_SEARCH_ENGINE_ID.")
    if datastore_id:
        return "datastore", datastore_id
    if search_engine_id:
        return "engine", search_engine_id
    if generic_engine_id:
        return "engine", generic_engine_id

    raise RuntimeError(
        "Missing ADK search resource. Set ADK_VERTEX_DATASTORE_ID, ADK_VERTEX_SEARCH_ENGINE_ID, or VERTEX_AI_SEARCH_ENGINE_ID."
    )


def _execution_prompt(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> str:
    answers = "\n".join(
        f"- {answer.question_id}: {answer.answer}" for answer in patient_answers
    ) or "- No responder answers available."
    return f"""
Recommended action: {action}

Clinical assessment:
- severity: {clinical_assessment.severity}
- reasoning_summary: {clinical_assessment.reasoning_summary}
- red_flags: {", ".join(clinical_assessment.red_flags) or "none"}
- missing_facts: {", ".join(clinical_assessment.missing_facts) or "none"}
- vulnerability_modifiers: {", ".join(clinical_assessment.vulnerability_modifiers) or "none"}

Patient profile:
- age: {patient_profile.age}
- blood_thinners: {patient_profile.blood_thinners}
- conditions: {", ".join(patient_profile.pre_existing_conditions) or "none"}
- mobility_support: {patient_profile.mobility_support}

Conversation context:
{answers}

Use Vertex AI Search before giving protocol-style steps.
Return only JSON matching the execution plan schema.
""".strip()


def _extract_json_block(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("ADK execution response was empty.")
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    brace_match = re.search(r"(\{.*\})", stripped, re.DOTALL)
    if brace_match:
        return brace_match.group(1)

    raise ValueError("ADK execution response did not contain a JSON object.")


def _normalize_execution_guidance(guidance: ExecutionGuidance) -> ExecutionGuidance:
    if not guidance.quick_replies:
        guidance.quick_replies = ["Done", "Need next step", "Condition worse"]
    if not guidance.primary_message:
        guidance.primary_message = guidance.steps[0] if guidance.steps else "Follow the safety guidance."
    if not guidance.source:
        guidance.source = "grounded"
    return guidance


def _fallback_execution_guidance(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
) -> ExecutionGuidance:
    from app.fall.assessment_service import _build_non_grounded_guidance

    fallback_guidance = _build_non_grounded_guidance(
        action=action,
        clinical_assessment=clinical_assessment,
    )
    fallback_steps = fallback_guidance.steps
    scenario = (
        "dispatch_wait"
        if action in {"dispatch_pending_confirmation", "emergency_dispatch"}
        else ("family_support" if action == "contact_family" else "monitoring")
    )
    return ExecutionGuidance(
        scenario=scenario,
        primary_message=fallback_guidance.primary_message or (fallback_steps[0] if fallback_steps else ""),
        steps=fallback_steps,
        warnings=fallback_guidance.warnings,
        escalation_triggers=fallback_guidance.escalation_triggers,
        quick_replies=["Okay", "Pain worse", "Breathing worse"],
        source="non_grounded",
    )


def _should_use_adk_execution(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
    patient_answers: list[PatientAnswer],
) -> bool:
    """Return whether this case truly needs an ADK execution-model call.

    The session runtime may still enter the execution phase for non-emergency
    cases when the response plan contains bystander actions. We should only pay
    the network/model cost when grounded protocol guidance is actually needed.
    """

    from app.fall.assessment_service import (
        _requires_mandatory_protocol_grounding,
        _should_trigger_grounded_guidance,
        build_interaction_summary,
    )

    interaction_summary = build_interaction_summary(
        interaction=None,
        patient_answers=patient_answers,
        recommended_action=action,
    )
    should_ground_guidance = _should_trigger_grounded_guidance(
        action=action,
        clinical_assessment=clinical_assessment,
        interaction_summary=interaction_summary,
        allow_grounding=True,
    )
    requires_protocol = _requires_mandatory_protocol_grounding(
        clinical_assessment=clinical_assessment,
        allow_grounding=True,
    )
    return should_ground_guidance or requires_protocol


@lru_cache(maxsize=1)
def _build_execution_agent():
    from google.adk.agents import llm_agent
    from google.adk.tools import VertexAiSearchTool

    resource_kind, resource_id = _search_resource_from_env()
    tool_kwargs = (
        {"data_store_id": resource_id}
        if resource_kind == "datastore"
        else {"search_engine_id": resource_id}
    )

    return llm_agent.LlmAgent(
        name="ExecutionAgent",
        model=ADK_EXECUTION_MODEL,
        description="Produces grounded fall-response execution steps after the reasoning layer has selected the action.",
        sub_agents=[],
        instruction=EXECUTION_AGENT_INSTRUCTION,
        tools=[VertexAiSearchTool(**tool_kwargs)],
    )


async def _run_agent_prompt(prompt: str) -> str:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    user_id = os.getenv("ADK_TEST_USER_ID", "fall-execution-user")
    session_id = f"session-{abs(hash(prompt)) % 10_000_000}"
    session_service = InMemorySessionService()
    runner = Runner(
        agent=_build_execution_agent(),
        app_name=ADK_EXECUTION_APP_NAME,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name=ADK_EXECUTION_APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )

    final_text_parts: list[str] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        content = getattr(event, "content", None)
        if content and getattr(content, "parts", None) and event.is_final_response():
            for part in content.parts:
                text = getattr(part, "text", None)
                if text:
                    final_text_parts.append(text)

    return "\n".join(final_text_parts).strip()


async def run_adk_execution_plan(
    *,
    action: str,
    clinical_assessment: ClinicalAssessmentSummary,
    patient_profile: UserMedicalProfile,
    patient_answers: list[PatientAnswer],
) -> ExecutionGuidance:
    """Run the ADK-backed execution agent with safe fallback semantics."""

    if not _should_use_adk_execution(
        action=action,
        clinical_assessment=clinical_assessment,
        patient_answers=patient_answers,
    ):
        logger.info(
            "[AdkExecution] Skipping ADK model call; non-grounded execution is sufficient | action=%s severity=%s",
            action,
            clinical_assessment.severity,
        )
        return _fallback_execution_guidance(
            action=action,
            clinical_assessment=clinical_assessment,
        )

    prompt = _execution_prompt(
        action=action,
        clinical_assessment=clinical_assessment,
        patient_profile=patient_profile,
        patient_answers=patient_answers,
    )

    try:
        response_text = await _run_agent_prompt(prompt)
        guidance = ExecutionGuidance.model_validate(json.loads(_extract_json_block(response_text)))
        guidance = _normalize_execution_guidance(guidance)
        logger.info(
            "[AdkExecution] Agent succeeded | action=%s severity=%s source=%s protocol=%s",
            action,
            clinical_assessment.severity,
            guidance.source,
            guidance.protocol_key or "none",
        )
        return guidance
    except Exception:
        logger.exception(
            "[AdkExecution] Agent failed; falling back to deterministic execution guidance | action=%s",
            action,
        )
        return _fallback_execution_guidance(
            action=action,
            clinical_assessment=clinical_assessment,
        )
