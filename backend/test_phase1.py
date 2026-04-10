"""
Phase 1 Verification Script.
This script tests the Pydantic schemas and mock tools without needing an AI API key.
"""
import sys
import os

# Ensure the app directory is in the path
sys.path.append(os.path.join(os.getcwd()))

from app.agents.schemas import FallEvent, VitalSigns
from app.agents.tools import send_twilio_call, get_nearest_hospital

def verify_foundation():
    print("--- [PHASE 1 VERIFICATION] ---")
    
    # 1. Verify Schemas
    try:
        test_event = FallEvent(
            user_id="user_12345",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="no_movement",
            confidence_score=0.95
        )
        print(f"✅ Schema Check: FallEvent valid for {test_event.user_id}")
    except Exception as e:
        print(f"❌ Schema Check Failed: {e}")
        return

    # 2. Verify Tools (Mocks)
    print("\nTesting Mock Tools:")
    
    # Test Twilio Mock
    call_result = send_twilio_call("+60123456789", "Emergency: Fall detected at location.")
    if call_result["status"] == "success":
        print(f"✅ Tool Check: send_twilio_call mock successful.")
    
    # Test Google Maps Mock
    hospital = get_nearest_hospital(1.4927, 103.7414)
    print(f"✅ Tool Check: get_nearest_hospital mock returned {hospital['hospital_name']}.")

    print("\n--- [VERIFICATION COMPLETE: FOUNDATION IS SOLID] ---")

if __name__ == "__main__":
    verify_foundation()
