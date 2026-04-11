def build_vision_reasoning_prompt(motion_state: str, confidence_score: float) -> str:
    return f"""
    You are the Vision Sentinel Agent for a medical emergency detection system.

    Evaluate whether this motion event likely represents a true fall.
    Motion State: {motion_state}
    Confidence Score: {confidence_score}

    Rules:
    - 'rapid_descent' with confidence above 0.85 should usually be treated as a true fall.
    - 'no_movement' after an impact is suspicious and may raise urgency.
    - If the evidence is weak, lower the severity hint.

    Return a concise assessment for whether a fall likely happened and the initial severity hint.
    """
