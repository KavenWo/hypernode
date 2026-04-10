"""
Phase 2 Test Script: Running the Genkit AI Agent with Gemini.
"""
import os
import asyncio
from dotenv import load_dotenv

# Load environmental variables from .env
load_dotenv()

# We need to add the backend folder to sys.path so 'app' can be imported
import sys
sys.path.append(os.path.join(os.getcwd()))

from app.agents.schemas import FallEvent
from app.agents.flows import vital_signs_emergency_workflow

async def main():
    print("--- [PHASE 2: RUNNING AI AGENT] ---")
    api_key = os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("\n❌ ERROR: GOOGLE_GENAI_API_KEY is not set in your .env file!")
        print("Please grab an API key from https://aistudio.google.com/app/apikey and put it in backend/.env")
        return

    # Simulate a critical fall
    critical_event = FallEvent(
        user_id="user_elderly_01",
        timestamp="2024-04-10T12:00:00Z",
        motion_state="rapid_descent",
        confidence_score=0.98
    )

    print("\n--- Triggering Workflow with Dummy Fall Event ---")
    try:
        final_decision = await vital_signs_emergency_workflow(critical_event)
        print("\n--- Final Workflow Execution Success ---")
        print(f"Call Emergency: {final_decision.call_emergency_services}")
        print(f"Notify Family: {final_decision.notify_family}")
        print(f"First Aid Needed: {final_decision.first_aid_instructions_needed}")
    except Exception as e:
        print(f"\n❌ Execution Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
