from .config import ai
from .schemas import FallEvent, ClinicalAssessment, DispatchDecision
from .tools import send_twilio_call, get_nearest_hospital

# This defines a Genkit "Action" (Tool) that the LLM can use
@ai.tool(
    name="dispatch_ambulance",
    description="Calls emergency services via Twilio and provides routing information."
)
def dispatch_ambulance(lat: float, lon: float, contact_number: str, message: str) -> str:
    nearest = get_nearest_hospital(lat, lon)
    send_twilio_call(contact_number, message)
    return f"Ambulance dispatched. Nearest hospital is {nearest['hospital_name']} (ETA: {nearest['eta_minutes']} mins)."

# 1. Main Agentic Flow
@ai.flow(
    name="vital_signs_emergency_workflow"
)
async def vital_signs_emergency_workflow(event: FallEvent) -> DispatchDecision:
    """
    The orchestrator flow that processes a fall event, reasons about severity,
    and decides on actions.
    """
    print(f"Received Fall Event for User: {event.user_id} with Confidence {event.confidence_score}")
    
    # Step A: Clinical Reasoning Agent
    # We ask the model to act as the reasoning agent and return structured output.
    reasoning_prompt = f"""
    You are a Vital Diagnostics Reasoning Agent operating during Malaysia's "Golden Hour" of medical emergencies.
    
    A user has triggered a fall event:
    - Motion State: {event.motion_state}
    - Confidence Score: {event.confidence_score}
    
    CRITICAL INSTRUCTIONS:
    - If the motion state is 'rapid_descent' or 'no_movement' and confidence > 0.85, this is a 'critical' event.
    - If the motion state is 'minor_stumble' or confidence is low, it might be 'low' or 'medium' severity.
    
    Provide your assessment of the severity based on the data.
    Recommend an action: 'monitor', 'contact_family', or 'emergency_dispatch'.
    """
    
    # We use ai.generate to call Gemini and force structured output matching Pydantic schema
    assessment_response = await ai.generate(
        prompt=reasoning_prompt,
        output_format=ClinicalAssessment
    )
    
    assessment = assessment_response.output
    print(f"Clinical Assessment: [{assessment.severity.upper()}] - {assessment.reasoning}")
    
    # Step B: Coordinator / Dispatch Agent
    # Based on the clinical assessment, determine if emergency protocols need activating.
    
    coordinator_prompt = f"""
    The Clinical Agent assessed a fall event as '{assessment.severity}'.
    Recommended action: '{assessment.recommended_action}'.
    Reasoning: {assessment.reasoning}
    
    Your task is to orchestrate the response.
    - If action is 'emergency_dispatch', YOU MUST use the `dispatch_ambulance` tool!
    - For high/critical severity, set `notify_family` to true and `first_aid_instructions_needed` to true.
    - For low severity, do not dispatch an ambulance.
    
    Current User Coordinates: lat 1.4927, lon 103.7414 (Malaysia)
    Emergency Contact: +60123456789
    
    Provide your final dispatch decision.
    """
    
    dispatch_response = await ai.generate(
        prompt=coordinator_prompt,
        tools=[dispatch_ambulance], # Allow LLM to trigger real-world API
        output_format=DispatchDecision
    )
    
    decision = dispatch_response.output
    print(f"Final Decision: {decision}")
    
    return decision
