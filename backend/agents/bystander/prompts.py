def build_instruction_steps(emergency_type: str) -> list[str]:
    if "fall" in emergency_type.lower() or "unconscious" in emergency_type.lower():
        return [
            "Check for responsiveness. Tap the shoulder and ask if the person is okay.",
            "If there is no normal breathing, prepare for hands-only CPR.",
            "Keep the patient still if spinal injury is possible unless there is immediate danger.",
            "Stay with the patient until emergency services arrive.",
        ]

    return [
        "Ensure the scene is safe.",
        "Keep the patient calm.",
        "Monitor breathing and consciousness while waiting for help.",
    ]
