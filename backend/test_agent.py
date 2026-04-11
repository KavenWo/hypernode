"""Run the orchestrated agent workflow locally."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.append(str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from agents.orchestrator import vital_signs_emergency_workflow
from agents.shared.schemas import FallEvent


async def main() -> None:
    print("--- [PHASE 2: RUNNING AI AGENT] ---")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("\nERROR: GEMINI_API_KEY is not set in your .env file.")
        print("Please grab an API key from https://aistudio.google.com/app/apikey and put it in backend/.env")
        return

    critical_event = FallEvent(
        user_id="user_elderly_01",
        timestamp="2024-04-10T12:00:00Z",
        motion_state="rapid_descent",
        confidence_score=0.98,
    )

    print("\n--- Triggering Workflow with Dummy Fall Event ---")
    try:
        final_decision = await vital_signs_emergency_workflow(critical_event)
        print("\n--- Final Workflow Execution Success ---")
        print(f"Call Emergency: {final_decision.call_emergency_services}")
        print(f"Notify Family: {final_decision.notify_family}")
        print(f"First Aid Needed: {final_decision.first_aid_instructions_needed}")
    except Exception as exc:
        print(f"\nExecution Failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
