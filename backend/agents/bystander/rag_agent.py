"""Bystander agent: retrieves grounded first-aid guidance to help nearby people respond safely."""

from agents.bystander.knowledge_base import retrieve_medical_guidance
from agents.shared.schemas import BystanderInstruction

from .prompts import build_instruction_steps


def build_first_aid_instructions_from_guidance(grounded_steps: list[str]) -> BystanderInstruction:
    """Reuse already-grounded steps so the MVP does not perform duplicate retrieval."""
    if grounded_steps:
        return BystanderInstruction(
            title="Immediate First Aid Guidance",
            steps=grounded_steps,
        )
    return BystanderInstruction(
        title="Immediate First Aid Guidance",
        steps=build_instruction_steps("fall"),
    )


def retrieve_first_aid_instructions(emergency_type: str) -> BystanderInstruction:
    grounded_steps = retrieve_medical_guidance(f"{emergency_type} first aid guidance")
    if grounded_steps:
        return BystanderInstruction(
            title="Immediate First Aid Guidance",
            steps=grounded_steps,
        )
    return BystanderInstruction(
        title="Immediate First Aid Guidance",
        steps=build_instruction_steps(emergency_type),
    )
