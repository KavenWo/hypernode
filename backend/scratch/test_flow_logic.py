import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.insert(0, os.path.abspath('backend'))

from app.fall.conversation_service import _next_canonical_state_from_analysis
from app.fall.contracts import SessionState, CommunicationAgentAnalysis, CommunicationState

def test_flow():
    print("--- Testing Optimized Conversation Flow (Revised) ---")
    
    # Test 1: Patient responds "Yes" to opening check. 
    # Should ALWAYS go to BYSTANDER_CHECK now, but flag consciousness.
    mock_analysis = MagicMock(spec=CommunicationAgentAnalysis)
    mock_analysis.patient_responded = True
    mock_analysis.bystander_present = False
    
    state, prompt, updates = _next_canonical_state_from_analysis(
        current_state=SessionState.AWAITING_OPENING_RESPONSE,
        latest_message="Yes",
        analysis=mock_analysis
    )
    print(f"Test 1 (Patient 'Yes'): Next State={state}, Prompt='{prompt}', Updates={updates}")
    assert state == SessionState.BYSTANDER_CHECK
    assert updates.get("conscious") is True

    # Test 2: Bystander responds to bystander check AFTER patient said Yes earlier.
    # Should SKIP consciousness check.
    prev_state = MagicMock(spec=CommunicationState)
    prev_state.conscious = True
    prev_state.mode = "patient_only"
    
    mock_analysis = MagicMock(spec=CommunicationAgentAnalysis)
    mock_analysis.bystander_present = True
    
    state, prompt, updates = _next_canonical_state_from_analysis(
        current_state=SessionState.BYSTANDER_CHECK,
        latest_message="I'm here",
        analysis=mock_analysis,
        previous_state=prev_state
    )
    print(f"Test 2 (Bystander 'I'm here', conscious=True): Next State={state}, Prompt='{prompt}', Updates={updates}")
    assert state == SessionState.BREATHING_CHECK

    # Test 3: Bystander responds to bystander check when patient never replied.
    # Should NOT skip consciousness check.
    prev_state = MagicMock(spec=CommunicationState)
    prev_state.conscious = None
    
    mock_analysis = MagicMock(spec=CommunicationAgentAnalysis)
    mock_analysis.bystander_present = True
    
    state, prompt, updates = _next_canonical_state_from_analysis(
        current_state=SessionState.BYSTANDER_CHECK,
        latest_message="Yes, I am here",
        analysis=mock_analysis,
        previous_state=prev_state
    )
    print(f"Test 3 (Bystander 'Yes', conscious=None): Next State={state}, Prompt='{prompt}', Updates={updates}")
    assert state == SessionState.CONSCIOUSNESS_CHECK

    print("\n--- All Isolation Tests Passed! ---")

if __name__ == "__main__":
    try:
        test_flow()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
