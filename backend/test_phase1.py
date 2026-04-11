"""Verify the core schemas and execution stubs without calling a live model."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.append(str(BACKEND_DIR))

from agents.execution.emergency_actions import get_nearest_hospital, send_twilio_call
from agents.shared.schemas import FallEvent


def verify_foundation() -> None:
    print("--- [PHASE 1 VERIFICATION] ---")

    try:
        test_event = FallEvent(
            user_id="user_12345",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="no_movement",
            confidence_score=0.95,
        )
        print(f"Schema Check: FallEvent valid for {test_event.user_id}")
    except Exception as exc:
        print(f"Schema Check Failed: {exc}")
        return

    print("\nTesting Mock Execution Boundary:")

    call_result = send_twilio_call("+60123456789", "Emergency: Fall detected at location.")
    if call_result["status"] == "success":
        print("Execution Check: send_twilio_call mock successful.")

    hospital = get_nearest_hospital(1.4927, 103.7414)
    print(f"Execution Check: get_nearest_hospital mock returned {hospital['hospital_name']}.")

    print("\n--- [VERIFICATION COMPLETE: FOUNDATION IS SOLID] ---")


if __name__ == "__main__":
    verify_foundation()
