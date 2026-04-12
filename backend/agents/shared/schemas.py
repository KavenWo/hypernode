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


class TriageQuestion(BaseModel):
    question_id: str = Field(..., description="Stable identifier for the triage question.")
    text: str = Field(..., description="Question shown to the patient or bystander.")


class TriageQuestionSet(BaseModel):
    questions: list[TriageQuestion] = Field(..., description="Two to three targeted follow-up triage questions.")


class PatientAnswer(BaseModel):
    question_id: str = Field(..., description="Identifier matching the question that was asked.")
    answer: str = Field(..., description="Free-form patient or bystander answer.")


class VisionAssessment(BaseModel):
    fall_detected: bool = Field(..., description="Whether the vision or motion layer believes a fall occurred.")
    severity_hint: str = Field(..., description="Initial risk hint such as low, medium, or critical.")
    reasoning: str = Field(..., description="Short explanation of why the event was classified this way.")


class VitalAssessment(BaseModel):
    anomaly_detected: bool = Field(..., description="Whether abnormal vitals were found.")
    severity_hint: str = Field(..., description="Risk hint derived from vitals using low, medium, or critical.")
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
    severity: str = Field(..., description="Assessed severity: low, medium, or critical.")
    clinical_confidence_score: float = Field(..., description="Confidence that the severity is appropriate.")
    clinical_confidence_band: str = Field(..., description="Band form of clinical confidence: low, medium, high.")
    action_confidence_score: float = Field(..., description="Confidence that the recommended action should happen now.")
    action_confidence_band: str = Field(..., description="Band form of action confidence: low, medium, high.")
    red_flags: list[str] = Field(default_factory=list, description="Normalized red-flag keys.")
    protective_signals: list[str] = Field(default_factory=list, description="Signals that suggest stability.")
    suspected_risks: list[str] = Field(default_factory=list, description="Short suspected risk labels.")
    uncertainty: list[str] = Field(default_factory=list, description="Important unknowns or ambiguities.")
    reasoning_summary: str = Field(..., description="Short explanation of why this severity and action were chosen.")
    recommended_action: str = Field(..., description="Recommended next action from the fixed action vocabulary.")


class FallQuestionsRequest(BaseModel):
    event: FallEvent
    vitals: VitalSigns | None = None


class FallAssessmentRequest(BaseModel):
    event: FallEvent
    vitals: VitalSigns | None = None
    patient_answers: list[PatientAnswer] = Field(default_factory=list)


class DispatchDecision(BaseModel):
    call_emergency_services: bool = Field(..., description="Whether to call an ambulance.")
    notify_family: bool = Field(..., description="Whether to notify emergency contacts.")
    dispatch_reasoning: str = Field(..., description="Reasoning for this dispatch decision.")
    first_aid_instructions_needed: bool = Field(..., description="Whether bystander intervention is advised.")


class BystanderInstruction(BaseModel):
    title: str = Field(..., description="Short instruction title.")
    steps: list[str] = Field(..., description="Step-by-step actions for nearby helpers.")


class DetectionSummary(BaseModel):
    motion_state: str = Field(..., description="Event motion state.")
    fall_detection_confidence_score: float = Field(..., description="Numeric fall detection confidence score.")
    fall_detection_confidence_band: str = Field(..., description="Band form of fall detection confidence.")
    event_validity: str = Field(..., description="Normalized event validity such as likely_true or uncertain.")


class ClinicalAssessmentSummary(BaseModel):
    severity: str = Field(..., description="Overall severity for the incident.")
    clinical_confidence_score: float = Field(..., description="Numeric clinical confidence score.")
    clinical_confidence_band: str = Field(..., description="Band form of clinical confidence.")
    action_confidence_score: float = Field(..., description="Numeric action confidence score.")
    action_confidence_band: str = Field(..., description="Band form of action confidence.")
    red_flags: list[str] = Field(default_factory=list, description="Normalized red-flag keys.")
    protective_signals: list[str] = Field(default_factory=list, description="Signals that suggest stability.")
    suspected_risks: list[str] = Field(default_factory=list, description="Short suspected risk labels.")
    uncertainty: list[str] = Field(default_factory=list, description="Important unknowns or ambiguities.")
    reasoning_summary: str = Field(..., description="Short explanation of the clinical reasoning result.")


class ActionSummary(BaseModel):
    recommended: str = Field(..., description="Recommended next action from the fixed action vocabulary.")
    requires_confirmation: bool = Field(..., description="Whether the action needs a short confirmation window.")
    cancel_allowed: bool = Field(..., description="Whether the user can cancel the action.")
    countdown_seconds: int | None = Field(default=None, description="Optional countdown before escalation.")


class GuidanceSummary(BaseModel):
    primary_message: str = Field(..., description="Short immediate instruction.")
    steps: list[str] = Field(default_factory=list, description="Step-by-step actions for the patient or bystander.")
    warnings: list[str] = Field(default_factory=list, description="Short do-not-do warnings.")


class GroundingSummary(BaseModel):
    source: str = Field(default="fallback_file", description="Where grounded medical guidance came from.")
    references: list[dict] = Field(default_factory=list, description="Reference metadata from retrieval.")
    preview: list[str] = Field(default_factory=list, description="Small preview of grounded snippets used.")


class AuditSummary(BaseModel):
    fallback_used: bool = Field(default=True, description="Whether fallback reasoning was used.")
    policy_version: str = Field(default="phase1_v1", description="Version of the response policy contract.")
    dispatch_triggered: bool = Field(default=False, description="Whether emergency dispatch started.")


class MvpAssessment(BaseModel):
    incident_id: str | None = Field(default=None, description="Incident identifier returned by the dispatch layer when applicable.")
    status: str = Field(..., description="Current incident status.")
    responder_mode: str = Field(..., description="Who is currently responding: patient, bystander, or no_response.")
    detection: DetectionSummary
    clinical_assessment: ClinicalAssessmentSummary
    action: ActionSummary
    guidance: GuidanceSummary
    grounding: GroundingSummary = Field(default_factory=GroundingSummary)
    audit: AuditSummary = Field(default_factory=AuditSummary)
