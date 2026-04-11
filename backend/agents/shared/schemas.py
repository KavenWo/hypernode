from pydantic import BaseModel, Field


class FallEvent(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user.")
    timestamp: str = Field(..., description="ISO8601 timestamp of the detected event.")
    motion_state: str = Field(..., description="State of motion, e.g. 'no_movement', 'rapid_descent'.")
    confidence_score: float = Field(..., description="Confidence score of the fall detection from 0.0 to 1.0.")


class VitalSigns(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user.")
    heart_rate: int = Field(..., description="Beats per minute.")
    blood_pressure_systolic: int = Field(..., description="Systolic blood pressure.")
    blood_pressure_diastolic: int = Field(..., description="Diastolic blood pressure.")
    blood_oxygen_sp02: float = Field(..., description="Blood oxygen saturation percentage.")


class VisionAssessment(BaseModel):
    fall_detected: bool = Field(..., description="Whether the vision or motion layer believes a fall occurred.")
    severity_hint: str = Field(..., description="Initial risk hint such as low, medium, high, or critical.")
    reasoning: str = Field(..., description="Short explanation of why the event was classified this way.")


class VitalAssessment(BaseModel):
    anomaly_detected: bool = Field(..., description="Whether abnormal vitals were found.")
    severity_hint: str = Field(..., description="Risk hint derived from vitals.")
    reasoning: str = Field(..., description="Short explanation of the vital-sign assessment.")


class UserMedicalProfile(BaseModel):
    user_id: str
    full_name: str | None = None
    age: int
    pre_existing_conditions: list[str] = Field(default_factory=list)
    emergency_contacts: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    blood_thinners: bool = False
    mobility_support: bool = False


class ClinicalAssessment(BaseModel):
    severity: str = Field(..., description="Assessed severity: low, medium, high, or critical.")
    reasoning: str = Field(..., description="Explanation of why this severity was chosen.")
    recommended_action: str = Field(..., description="Recommended next action such as monitor, contact_family, or emergency_dispatch.")


class DispatchDecision(BaseModel):
    call_emergency_services: bool = Field(..., description="Whether to call an ambulance.")
    notify_family: bool = Field(..., description="Whether to notify emergency contacts.")
    dispatch_reasoning: str = Field(..., description="Reasoning for this dispatch decision.")
    first_aid_instructions_needed: bool = Field(..., description="Whether bystander intervention is advised.")


class BystanderInstruction(BaseModel):
    title: str = Field(..., description="Short instruction title.")
    steps: list[str] = Field(..., description="Step-by-step actions for nearby helpers.")
