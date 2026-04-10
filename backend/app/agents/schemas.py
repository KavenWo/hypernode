from pydantic import BaseModel, Field
from typing import Optional

# 1. Sentinel Layer Input
class FallEvent(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user.")
    timestamp: str = Field(..., description="ISO8601 timestamp of the detected event.")
    motion_state: str = Field(..., description="State of motion, e.g., 'no_movement', 'rapid_descent'.")
    confidence_score: float = Field(..., description="Confidence score of the fall detection (0.0 to 1.0).")

class VitalSigns(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user.")
    heart_rate: int = Field(..., description="Beats per minute.")
    blood_pressure_systolic: int = Field(..., description="Systolic pressure.")
    blood_pressure_diastolic: int = Field(..., description="Diastolic pressure.")
    blood_oxygen_sp02: float = Field(..., description="Blood oxygen saturation percentage.")

# 2. Reasoning Layer State
class UserMedicalProfile(BaseModel):
    user_id: str
    age: int
    pre_existing_conditions: list[str]
    emergency_contacts: list[str]

class ClinicalAssessment(BaseModel):
    severity: str = Field(..., description="Assessed severity: 'low', 'medium', 'high', 'critical'.")
    reasoning: str = Field(..., description="Explanation of why this severity was chosen.")
    recommended_action: str = Field(..., description="E.g., 'monitor', 'contact_family', 'emergency_dispatch'.")

# 3. Coordinator/Dispatch Decision
class DispatchDecision(BaseModel):
    call_emergency_services: bool = Field(..., description="Whether to call an ambulance.")
    notify_family: bool = Field(..., description="Whether to notify emergency contacts.")
    dispatch_reasoning: str = Field(..., description="Reasoning for this dispatch decision.")
    first_aid_instructions_needed: bool = Field(..., description="Whether bystander intervention is advised.")
