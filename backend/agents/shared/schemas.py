"""Shared Pydantic schemas for the fall-flow backend.

This file currently serves several layers at once:

- input contracts coming from the frontend
- internal agent outputs used during reasoning/communication
- API/session response payloads sent back to the frontend

The models are grouped below so it is easier to see which ones are runtime
inputs, internal analysis artifacts, or final product-facing responses.
"""

from __future__ import annotations

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


#
# Frontend/session input models
#
# These are the lightweight payloads the UI sends into the backend so the fall
# services can decide who to talk to, whether reasoning should refresh, and
# what context is already known for this turn.
#
class InteractionInput(BaseModel):
    patient_response_status: str = Field(
        default="unknown",
        description="Current patient response state such as responsive, confused, unresponsive, unknown, or no_response.",
    )
    bystander_available: bool = Field(
        default=False,
        description="Whether a bystander is available to observe or help.",
    )
    bystander_can_help: bool = Field(
        default=False,
        description="Whether the bystander is actually able and willing to follow guidance.",
    )
    testing_assume_bystander: bool = Field(
        default=False,
        description="Testing override so the MVP can exercise bystander communication flows.",
    )
    active_execution_action: str | None = Field(
        default=None,
        description="Optional active execution script such as cpr_in_progress.",
    )
    message_text: str = Field(
        default="",
        description="Latest communication turn text used for selective reasoning refresh decisions.",
    )
    new_fact_keys: list[str] = Field(
        default_factory=list,
        description="Structured fact keys extracted from the latest turn.",
    )
    responder_mode_hint: str | None = Field(
        default=None,
        description="Optional responder-mode hint carried by the frontend session.",
    )
    responder_mode_changed: bool = Field(
        default=False,
        description="Whether the active responder changed since the previous turn.",
    )
    contradiction_detected: bool = Field(
        default=False,
        description="Whether the latest turn conflicts with established facts.",
    )
    no_response_timeout: bool = Field(
        default=False,
        description="Whether a no-response timeout fired before this turn.",
    )


class ReasoningRefreshSummary(BaseModel):
    required: bool = Field(..., description="Whether a new reasoning pass should run for the current turn.")
    reason: str = Field(..., description="Short explanation for the refresh decision.")
    priority: str = Field(..., description="Priority band for the refresh trigger.")


#
# Interaction-layer decision models
#
# `InteractionSummary` is the backend's normalized view of who the system is
# addressing and whether the current turn should trigger a reasoning refresh.
# This is different from `CommunicationAgentAnalysis`, which is the
# communication agent's turn-by-turn interpretation artifact.
#
class InteractionSummary(BaseModel):
    communication_target: str = Field(..., description="Who the system should address now.")
    responder_mode: str = Field(..., description="Normalized responder mode for the current turn.")
    guidance_style: str = Field(..., description="Instruction style for the current responder.")
    interaction_mode: str = Field(..., description="Interaction mode such as patient_first_check or bystander_execution.")
    rationale: str = Field(..., description="Short explanation for the interaction decision.")
    reasoning_refresh: ReasoningRefreshSummary = Field(..., description="Whether the latest turn should refresh reasoning.")
    testing_assume_bystander: bool = Field(
        default=False,
        description="Whether the current interaction path was forced into bystander testing mode.",
    )


class TriageQuestionSet(BaseModel):
    questions: list[TriageQuestion] = Field(..., description="Two to three targeted follow-up triage questions.")
    interaction: InteractionSummary | None = Field(
        default=None,
        description="Interaction-layer metadata describing who the questions are aimed at.",
    )


class PatientAnswer(BaseModel):
    question_id: str = Field(..., description="Identifier matching the question that was asked.")
    answer: str = Field(..., description="Free-form patient or bystander answer.")


class ConversationMessage(BaseModel):
    role: str = Field(..., description="conversation role such as system, assistant, patient, or bystander.")
    text: str = Field(..., description="Message content for the session transcript.")


class ExecutionUpdate(BaseModel):
    type: str = Field(..., description="Execution action key such as inform_family or emergency_dispatch.")
    status: str = Field(..., description="Execution status such as planned, queued, completed, or skipped.")
    detail: str = Field(..., description="Short human-readable explanation of what happened.")


#
# Low-level detection and profile models
#
# These models are used by the sentinel/reasoning layers before the final
# product-facing fall assessment is assembled.
#
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


#
# Internal agent output models
#
# `ClinicalAssessment` is still the direct output shape used inside the
# reasoning/coordinator agent layer. The product-facing response uses
# `ClinicalAssessmentSummary` further below inside `FallAssessment`.
#
class ClinicalAssessment(BaseModel):
    severity: str = Field(..., description="Assessed severity: low, medium, or critical.")
    clinical_confidence_score: float = Field(..., description="Confidence that the severity is appropriate.")
    clinical_confidence_band: str = Field(..., description="Band form of clinical confidence: low, medium, high.")
    action_confidence_score: float = Field(..., description="Confidence that the recommended action should happen now.")
    action_confidence_band: str = Field(..., description="Band form of action confidence: low, medium, high.")
    red_flags: list[str] = Field(default_factory=list, description="Normalized red-flag keys.")
    protective_signals: list[str] = Field(default_factory=list, description="Signals that suggest stability.")
    suspected_risks: list[str] = Field(default_factory=list, description="Short suspected risk labels.")
    vulnerability_modifiers: list[str] = Field(default_factory=list, description="Risk modifiers such as age, medications, or mobility concerns.")
    missing_facts: list[str] = Field(default_factory=list, description="Important unknowns that could still change the next step.")
    contradictions: list[str] = Field(default_factory=list, description="Conflicting signals that should lower certainty.")
    uncertainty: list[str] = Field(default_factory=list, description="Important unknowns or ambiguities.")
    hard_emergency_triggered: bool = Field(default=False, description="Whether explicit life-threatening signs overrode uncertainty.")
    blocking_uncertainties: list[str] = Field(default_factory=list, description="Unknowns that are still preventing a stronger escalation action.")
    override_policy: str = Field(default="", description="Short explanation of whether uncertainty blocked or was overridden.")
    reasoning_summary: str = Field(..., description="Short explanation of why this severity and action were chosen.")
    recommended_action: str = Field(..., description="Recommended next action from the fixed action vocabulary.")
    response_plan: "ResponsePlanSummary" = Field(default_factory=lambda: ResponsePlanSummary(), description="Structured multi-track operational response plan.")
    reasoning_trace: "ReasoningTraceSummary" = Field(default_factory=lambda: ReasoningTraceSummary(), description="Compact Phase 3 reasoning trace for debugging and MVP inspection.")


class FallQuestionsRequest(BaseModel):
    event: FallEvent
    vitals: VitalSigns | None = None
    interaction: InteractionInput | None = None


class FallAssessmentRequest(BaseModel):
    event: FallEvent
    vitals: VitalSigns | None = None
    patient_answers: list[PatientAnswer] = Field(default_factory=list)
    interaction: InteractionInput | None = None


#
# Older specialized agent outputs
#
# These are still used by a few lower-level agent modules even though they are
# no longer the main product contracts.
#
class DispatchDecision(BaseModel):
    call_emergency_services: bool = Field(..., description="Whether to call an ambulance.")
    notify_family: bool = Field(..., description="Whether to notify emergency contacts.")
    dispatch_reasoning: str = Field(..., description="Reasoning for this dispatch decision.")
    first_aid_instructions_needed: bool = Field(..., description="Whether bystander intervention is advised.")


class BystanderInstruction(BaseModel):
    title: str = Field(..., description="Short instruction title.")
    steps: list[str] = Field(..., description="Step-by-step actions for nearby helpers.")


#
# Product-facing assessment models
#
# These are the normalized structures the backend returns after combining
# detection, reasoning, retrieval grounding, and execution planning.
#
class DetectionSummary(BaseModel):
    motion_state: str = Field(..., description="Event motion state.")
    fall_detection_confidence_score: float = Field(..., description="Numeric fall detection confidence score.")
    fall_detection_confidence_band: str = Field(..., description="Band form of fall detection confidence.")
    event_validity: str = Field(..., description="Normalized event validity such as likely_true or uncertain.")


class ReasoningTraceSummary(BaseModel):
    stage_version: str = Field(default="clinical_reasoning_policy_v1", description="Reasoning policy version used for the deterministic reasoning trace.")
    top_red_flags: list[str] = Field(default_factory=list, description="Most important red flags that drove the decision.")
    top_protective_signals: list[str] = Field(default_factory=list, description="Protective signals that argued against escalation.")
    vulnerability_modifiers: list[str] = Field(default_factory=list, description="Profile or context modifiers that increased caution.")
    missing_facts: list[str] = Field(default_factory=list, description="Important unknowns still present after extraction.")
    priority_missing_fact: str | None = Field(default=None, description="The single missing fact that matters most right now.")
    contradictions: list[str] = Field(default_factory=list, description="Conflicting signals detected across answers, profile, or vitals.")
    severity_reason: str = Field(default="", description="Short explanation of why this severity was chosen.")
    action_reason: str = Field(default="", description="Short explanation of why this action was chosen.")
    uncertainty_effect: str = Field(default="", description="How uncertainty changed confidence or action behavior.")


class ResponseActionItem(BaseModel):
    type: str = Field(..., description="Action vocabulary key for this operational step.")
    priority: str = Field(default="secondary", description="Relative urgency such as immediate, secondary, or ongoing.")
    reason: str = Field(default="", description="Short reason for including this action.")


class EscalationActionSummary(BaseModel):
    type: str = Field(default="none", description="Main escalation route such as none, dispatch_pending_confirmation, or emergency_dispatch.")
    requires_confirmation: bool = Field(default=False, description="Whether a short confirmation window is still allowed.")
    cancel_allowed: bool = Field(default=False, description="Whether the escalation can still be canceled.")
    countdown_seconds: int | None = Field(default=None, description="Optional countdown before the escalation upgrades or executes.")
    reason: str = Field(default="", description="Why this escalation track was chosen.")


class ResponsePlanSummary(BaseModel):
    escalation_action: EscalationActionSummary = Field(default_factory=EscalationActionSummary, description="Primary emergency escalation decision.")
    notification_actions: list[ResponseActionItem] = Field(default_factory=list, description="Who else should be informed without blocking escalation.")
    bystander_actions: list[ResponseActionItem] = Field(default_factory=list, description="Immediate helper actions that should happen on scene.")
    followup_actions: list[ResponseActionItem] = Field(default_factory=list, description="Ongoing monitoring or reassessment actions after the first response.")


class ClinicalAssessmentSummary(BaseModel):
    severity: str = Field(..., description="Overall severity for the incident.")
    clinical_confidence_score: float = Field(..., description="Numeric clinical confidence score.")
    clinical_confidence_band: str = Field(..., description="Band form of clinical confidence.")
    action_confidence_score: float = Field(..., description="Numeric action confidence score.")
    action_confidence_band: str = Field(..., description="Band form of action confidence.")
    red_flags: list[str] = Field(default_factory=list, description="Normalized red-flag keys.")
    protective_signals: list[str] = Field(default_factory=list, description="Signals that suggest stability.")
    suspected_risks: list[str] = Field(default_factory=list, description="Short suspected risk labels.")
    vulnerability_modifiers: list[str] = Field(default_factory=list, description="Risk modifiers such as age, medications, or mobility concerns.")
    missing_facts: list[str] = Field(default_factory=list, description="Important unknowns that could still change the next step.")
    contradictions: list[str] = Field(default_factory=list, description="Conflicting signals that should lower certainty.")
    uncertainty: list[str] = Field(default_factory=list, description="Important unknowns or ambiguities.")
    hard_emergency_triggered: bool = Field(default=False, description="Whether explicit life-threatening signs overrode uncertainty.")
    blocking_uncertainties: list[str] = Field(default_factory=list, description="Unknowns that are still preventing a stronger escalation action.")
    override_policy: str = Field(default="", description="Short explanation of whether uncertainty blocked or was overridden.")
    reasoning_summary: str = Field(..., description="Short explanation of the clinical reasoning result.")
    response_plan: ResponsePlanSummary = Field(default_factory=ResponsePlanSummary, description="Structured multi-track operational response plan.")
    reasoning_trace: ReasoningTraceSummary = Field(default_factory=ReasoningTraceSummary, description="Compact Phase 3 reasoning trace for debugging and MVP inspection.")


class ActionSummary(BaseModel):
    recommended: str = Field(..., description="Recommended next action from the fixed action vocabulary.")
    requires_confirmation: bool = Field(..., description="Whether the action needs a short confirmation window.")
    cancel_allowed: bool = Field(..., description="Whether the user can cancel the action.")
    countdown_seconds: int | None = Field(default=None, description="Optional countdown before escalation.")


class GuidanceSummary(BaseModel):
    primary_message: str = Field(..., description="Short immediate instruction.")
    steps: list[str] = Field(default_factory=list, description="Step-by-step actions for the patient or bystander.")
    warnings: list[str] = Field(default_factory=list, description="Short do-not-do warnings.")
    escalation_triggers: list[str] = Field(default_factory=list, description="Grounded escalation cues that explain when urgent help is needed.")


class CommunicationHandoffSummary(BaseModel):
    mode: str = Field(
        default="question",
        description="Communication mode such as question, instruction, status_update, urgent_instruction, or reassure.",
    )
    priority: str = Field(
        default="clarify",
        description="Conversation priority such as execution, safety, reassure, or clarify.",
    )
    primary_message: str = Field(
        default="",
        description="Short message the communication layer should prefer for the next turn.",
    )
    immediate_step: str | None = Field(
        default=None,
        description="Optional single step the communication layer should emphasize right now.",
    )
    ask_followup: bool = Field(
        default=False,
        description="Whether the communication layer should append one short follow-up question now.",
    )
    next_question: str | None = Field(
        default=None,
        description="Optional follow-up question to ask when clarification is still needed.",
    )
    next_focus: str = Field(
        default="general_check",
        description="What the next communication turn should focus on.",
    )
    quick_replies: list[str] = Field(
        default_factory=list,
        description="Suggested short replies for the communication layer.",
    )
    rationale: str = Field(
        default="",
        description="Short explanation of why this communication mode was chosen.",
    )


class GroundingPassSummary(BaseModel):
    source: str = Field(default="not_requested", description="Where this grounding pass retrieved support from.")
    references: list[dict] = Field(default_factory=list, description="Reference metadata from retrieval.")
    preview: list[str] = Field(default_factory=list, description="Small preview of grounded snippets used.")
    retrieval_intents: list[str] = Field(default_factory=list, description="Selected retrieval intents used for this grounding pass.")
    queries: list[str] = Field(default_factory=list, description="Ordered retrieval queries issued or planned for this grounding pass.")
    buckets: dict[str, list[str]] = Field(default_factory=dict, description="Grouped snippets selected for retrieval debug views when applicable.")
    queries_by_bucket: dict[str, list[str]] = Field(default_factory=dict, description="Bucket-specific queries used during retrieval.")
    references_by_bucket: dict[str, list[dict]] = Field(default_factory=dict, description="Bucket-specific references returned by retrieval.")
    bucket_sources: dict[str, str] = Field(default_factory=dict, description="Source used for each bucket retrieval pass.")


class GroundingSummary(BaseModel):
    source: str = Field(default="fallback_file", description="Where grounded medical guidance came from.")
    references: list[dict] = Field(default_factory=list, description="Reference metadata from retrieval.")
    preview: list[str] = Field(default_factory=list, description="Small preview of grounded snippets used.")
    retrieval_intents: list[str] = Field(default_factory=list, description="Selected retrieval intents used for this guidance run.")
    queries: list[str] = Field(default_factory=list, description="Ordered retrieval queries issued or planned for this guidance run.")
    buckets: dict[str, list[str]] = Field(default_factory=dict, description="Grouped snippets selected for the retrieval debug view.")
    queries_by_bucket: dict[str, list[str]] = Field(default_factory=dict, description="Bucket-specific queries used during retrieval.")
    references_by_bucket: dict[str, list[dict]] = Field(default_factory=dict, description="Bucket-specific references returned by retrieval.")
    bucket_sources: dict[str, str] = Field(default_factory=dict, description="Source used for each bucket retrieval pass.")
    reasoning_support: GroundingPassSummary = Field(
        default_factory=GroundingPassSummary,
        description="Grounding support used to refine the clinical reasoning stage.",
    )
    guidance_support: GroundingPassSummary = Field(
        default_factory=GroundingPassSummary,
        description="Grounding support used to build responder-facing guidance.",
    )


class AuditSummary(BaseModel):
    fallback_used: bool = Field(default=True, description="Whether fallback reasoning was used.")
    policy_version: str = Field(default="phase1_v1", description="Version of the response policy contract.")
    dispatch_triggered: bool = Field(default=False, description="Whether emergency dispatch started.")


class FallAssessment(BaseModel):
    incident_id: str | None = Field(default=None, description="Incident identifier returned by the dispatch layer when applicable.")
    status: str = Field(..., description="Current incident status.")
    responder_mode: str = Field(..., description="Who is currently responding: patient, bystander, or no_response.")
    interaction: InteractionSummary | None = Field(
        default=None,
        description="Interaction-controller metadata for the current turn.",
    )
    detection: DetectionSummary
    clinical_assessment: ClinicalAssessmentSummary
    action: ActionSummary
    response_plan: ResponsePlanSummary = Field(default_factory=ResponsePlanSummary)
    guidance: GuidanceSummary
    communication_handoff: CommunicationHandoffSummary = Field(
        default_factory=CommunicationHandoffSummary,
        description="Structured handoff telling the communication layer what to say or ask next.",
    )
    grounding: GroundingSummary = Field(default_factory=GroundingSummary)
    audit: AuditSummary = Field(default_factory=AuditSummary)
class CommunicationTurnRequest(BaseModel):
    session_id: str | None = Field(
        default=None,
        description="Optional server-side session identifier for the ongoing communication loop.",
    )
    event: FallEvent
    vitals: VitalSigns | None = None
    interaction: InteractionInput = Field(default_factory=InteractionInput)
    latest_responder_message: str = Field(
        default="",
        description="Latest free-form responder message for this turn.",
    )
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        description="Short transcript history for the communication session.",
    )
    previous_assessment: FallAssessment | None = Field(
        default=None,
        description="Most recent reasoning snapshot so guidance can continue without refreshing reasoning every turn.",
    )


#
# Communication/session models
#
# `CommunicationAgentAnalysis` describes what the communication layer inferred
# on the latest turn. The response/state models below wrap that analysis
# together with session-level reasoning status and the latest assessment.
#
class CommunicationAgentAnalysis(BaseModel):
    followup_text: str = Field(..., description="Short human-facing next message from the communication AI.")
    responder_role: str = Field(..., description="Best guess for who is speaking: patient, bystander, unknown, or no_response.")
    communication_target: str = Field(..., description="Who the next message should address: patient, bystander, unknown, or no_response.")
    patient_responded: bool = Field(default=False, description="Whether the patient appears to have responded in this turn.")
    bystander_present: bool = Field(default=False, description="Whether a bystander appears to be present.")
    bystander_can_help: bool = Field(default=False, description="Whether the bystander appears able or willing to help.")
    extracted_facts: list[str] = Field(default_factory=list, description="Structured facts extracted from the latest responder message.")
    reasoning_needed: bool = Field(default=False, description="Whether the communication AI believes a reasoning refresh is needed.")
    reasoning_reason: str = Field(default="", description="Short explanation for why reasoning is or is not needed.")
    guidance_intent: str = Field(default="question", description="Conversational intent such as question, instruction, clarify, or reassure.")
    next_focus: str = Field(default="general_check", description="What the communication AI wants to learn or accomplish next.")
    immediate_step: str | None = Field(default=None, description="Optional single immediate step for the responder.")
    quick_replies: list[str] = Field(default_factory=list, description="Short suggested reply options.")


class CommunicationTurnResponse(BaseModel):
    session_id: str = Field(..., description="Server-side session identifier for the communication loop.")
    interaction: InteractionSummary
    communication_analysis: CommunicationAgentAnalysis
    reasoning_invoked: bool = Field(..., description="Whether the reasoning engine was invoked for this turn.")
    reasoning_status: str = Field(..., description="Current reasoning status such as idle, pending, completed, or failed.")
    reasoning_reason: str = Field(default="", description="Short explanation for the current reasoning state.")
    reasoning_error: str | None = Field(default=None, description="Most recent background reasoning error, if any.")
    assistant_message: str = Field(..., description="Primary assistant message for the next conversational turn.")
    assistant_question: str | None = Field(default=None, description="Optional next question when more information is needed.")
    guidance_steps: list[str] = Field(default_factory=list, description="Step-by-step instructions for the current responder.")
    quick_replies: list[str] = Field(default_factory=list, description="Short suggested replies for the current turn.")
    assessment: FallAssessment | None = Field(default=None, description="Updated reasoning snapshot when reasoning was invoked.")
    execution_updates: list[ExecutionUpdate] = Field(
        default_factory=list,
        description="Operational updates such as family notification or dispatch execution state.",
    )
    transcript_append: list[ConversationMessage] = Field(
        default_factory=list,
        description="Messages that should be appended to the session transcript.",
    )


class CommunicationSessionStateResponse(BaseModel):
    session_id: str = Field(..., description="Server-side session identifier for the communication loop.")
    version: int = Field(default=0, description="Monotonic session-state version for streaming updates.")
    reasoning_status: str = Field(..., description="Current reasoning status such as idle, pending, completed, or failed.")
    reasoning_reason: str = Field(default="", description="Short explanation for the current reasoning state.")
    reasoning_error: str | None = Field(default=None, description="Most recent background reasoning error, if any.")
    interaction: InteractionSummary | None = Field(
        default=None,
        description="Latest interaction summary known for the session.",
    )
    latest_analysis: CommunicationAgentAnalysis | None = Field(
        default=None,
        description="Latest structured communication-agent analysis for the session.",
    )
    assessment: FallAssessment | None = Field(
        default=None,
        description="Latest reasoning snapshot available for the session.",
    )
    execution_updates: list[ExecutionUpdate] = Field(
        default_factory=list,
        description="Operational updates such as family notification or dispatch execution state.",
    )
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        description="Full transcript accumulated on the backend for the session.",
    )
