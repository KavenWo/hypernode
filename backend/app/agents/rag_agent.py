from .config import ai

@ai.tool(
    name="retrieve_first_aid_instructions",
    description="Retrieves specific first-aid and CPR instructions for a given medical emergency."
)
def retrieve_first_aid_instructions(emergency_type: str) -> str:
    """
    Mock RAG Tool: In a production app, this would query Vertex AI Search 
    with trusted medical guidelines. For offline/demo, it returns static safety data.
    """
    print(f"[RAG MEDIC AGENT] Querying knowledge base for: {emergency_type}...")
    
    if "fall" in emergency_type.lower() or "unconscious" in emergency_type.lower():
        return (
            "1. Check for responsiveness. Tap the shoulder and shout 'Are you okay?'.\n"
            "2. If no response and not breathing normally, prepare for hands-only CPR.\n"
            "3. Place hands on the center of the chest and push hard and fast (100-120 compressions/min).\n"
            "4. Do not move the patient if you suspect a spinal injury unless they are in immediate danger."
        )
        
    return "Ensure the scene is safe, keep the patient calm, monitor vitals, and wait for emergency services."
