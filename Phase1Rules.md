# Phase 1 Rules Spec

## Purpose

This document locks the Phase 1 AI rules for the final product.

Phase 1 is not about making the agent maximally smart yet.
It is about making the system consistent.

The goal is to ensure:

- the AI uses stable meanings
- backend and frontend receive a fixed structure
- Vertex AI Search remains the medical grounding source
- reasoning outputs use controlled vocabulary
- future prompt improvements do not break the product contract

---

## Phase 1 Scope

Phase 1 defines:

- severity levels
- confidence model
- action vocabulary
- responder modes
- incident states
- red-flag taxonomy
- response schema contract
- reasoning output rules

Phase 1 does not yet fully define:

- advanced multi-step retrieval planning
- full evaluation suite
- complex threshold tuning from large datasets
- production dispatch integrations

---

## Core Principle

Vertex AI Search is the grounded medical source of truth.

However:

- Vertex defines the medical reference material
- the agent defines the reasoning output
- the product defines the schema and vocabulary

This means the system should work like this:

1. Retrieve grounded guidance from Vertex AI Search.
2. Use that evidence together with event data, vitals, profile, and answers.
3. Return a fixed structured output using product-controlled field names and enum values.

The agent must not return free-form labels that change from run to run.

---

## Severity Model

Phase 1 severity uses exactly three levels:

- `low`
- `medium`
- `critical`

### `low`

Definition:

- current evidence suggests the patient is likely stable
- no major emergency red flags are confirmed
- monitoring is appropriate

Typical examples:

- stumble or low-confidence fall
- patient is awake and answering clearly
- no head strike reported
- no breathing problem
- mild pain only

Typical next action:

- `monitor`

### `medium`

Definition:

- the event is concerning and needs follow-up
- risk is real, but current evidence does not clearly indicate immediate life-threatening danger

Typical examples:

- patient is conscious but in notable pain
- patient may not be safe to stand
- some uncertainty remains
- caregiver or family should be alerted

Typical next action:

- `contact_family`

### `critical`

Definition:

- current evidence suggests serious injury, strong red flags, or immediate emergency risk
- escalation should not be delayed unnecessarily

Typical examples:

- unconscious or not responding
- not breathing or abnormal breathing
- severe bleeding
- head injury with blood thinner use
- severe confusion after fall
- unable to move safely with high-risk injury concern

Typical next action:

- `dispatch_pending_confirmation`
- `emergency_dispatch`

### Severity Rule

If explicit life-threatening red flags are present, the agent must bias toward `critical`.

The agent should not keep a case in `medium` simply because uncertainty exists if the reported symptoms already indicate danger.

---

## Confidence Model

Phase 1 uses three confidence types.

Each confidence should exist as:

- a numeric score for internal logic and analytics
- a band label for UI and policy use

### 1. `fall_detection_confidence`

Definition:

- confidence that the triggering event is a real fall or clinically meaningful fall-like event

This does mean:

- the motion event is likely real
- the fall detector signal is likely trustworthy

This does not mean:

- the patient is critically injured
- emergency dispatch is automatically justified

### 2. `clinical_confidence`

Definition:

- confidence that the selected severity is appropriate given all currently available evidence

This should reflect:

- signal agreement
- red-flag strength
- completeness of answers
- ambiguity level

### 3. `action_confidence`

Definition:

- confidence that the recommended operational next step should happen now

This should reflect:

- severity
- urgency
- certainty that immediate escalation is appropriate

### Confidence Storage

Each confidence should be stored internally as a numeric value from `0.0` to `1.0`.

### Confidence Bands

For Phase 1, use this shared mapping:

- `low`: `0.00` to `0.39`
- `medium`: `0.40` to `0.74`
- `high`: `0.75` to `1.00`

### Confidence Display Rule

For production UX:

- show the confidence band, not only the raw number

For debug or test UX:

- show both score and band

Example:

- `0.78 (high)`

### Confidence Usage Rule

Confidence is not the final answer by itself.

Confidence should influence behavior like:

- verify first
- ask one more question
- escalate now

It should not replace the severity policy or red-flag policy.

---

## Action Vocabulary

Phase 1 actions are limited to this closed set:

- `monitor`
- `contact_family`
- `dispatch_pending_confirmation`
- `emergency_dispatch`
- `cancelled`
- `resolved`

### `monitor`

Use when:

- severity is `low`
- no major red flags are confirmed
- observation is appropriate

### `contact_family`

Use when:

- severity is `medium`
- a caregiver or family member should be informed
- dispatch is not yet clearly required

### `dispatch_pending_confirmation`

Use when:

- severity is `critical`
- escalation is likely needed
- the product flow still allows a short confirm/cancel window

### `emergency_dispatch`

Use when:

- severity is `critical`
- immediate escalation is justified now
- no further confirmation should delay action

### `cancelled`

Use when:

- the user or bystander cancels the current escalation flow

### `resolved`

Use when:

- the incident is closed after monitoring or escalation flow ends

### Action Rule

The model must only emit values from this fixed list.

---

## Responder Modes

Phase 1 supports exactly three responder modes:

- `patient`
- `bystander`
- `no_response`

### `patient`

Meaning:

- the patient is responsive enough to answer directly

Question style:

- short direct questions
- symptom-focused

### `bystander`

Meaning:

- another person is present and providing information or assistance

Question style:

- observational and instruction-oriented
- asks what the bystander sees

### `no_response`

Meaning:

- no one is answering within the expected window

Behavior:

- switch to no-response policy
- rely more on event, vitals, and known risk factors

### Responder Mode Rule

The mode must be explicit in the assessment output.

---

## Incident State Vocabulary

Phase 1 incident states are:

- `detected`
- `verification_in_progress`
- `triage_in_progress`
- `dispatch_pending_confirmation`
- `dispatch_confirmed`
- `guidance_active`
- `cancelled_by_user`
- `cancelled_by_bystander`
- `false_alarm_confirmed`
- `resolved`

### State Rules

- incidents are never silently discarded
- cancellation does not erase the record
- false alarms must still be logged
- every transition should be auditable

---

## Red-Flag Taxonomy V1

This taxonomy is product-controlled.

Vertex AI Search may provide the evidence and wording, but the agent must normalize evidence into these keys.

### Immediate Emergency Red Flags

- `unresponsive`
- `loss_of_consciousness`
- `not_breathing`
- `abnormal_breathing`
- `severe_bleeding`
- `chest_pain`
- `seizure_activity`

### High-Risk Fall Red Flags

- `head_strike`
- `vomiting_after_head_injury`
- `confusion_after_fall`
- `sudden_collapse`
- `cannot_stand`
- `severe_pain`
- `severe_hip_pain`
- `severe_back_pain`
- `severe_neck_pain`
- `suspected_fracture`
- `suspected_spinal_injury`

### Vulnerability Modifiers

- `blood_thinner_use`
- `older_adult`
- `known_heart_disease`
- `known_neurological_disease`
- `mobility_support_user`
- `recurrent_falls`

### Red-Flag Interpretation Rule

Immediate emergency red flags should strongly bias severity toward `critical`.

High-risk fall red flags should raise severity and action confidence, especially when multiple are present.

Vulnerability modifiers do not always trigger escalation by themselves, but they increase caution.

---

## Evidence Categories

Phase 1 recognizes five evidence categories:

- `detector_evidence`
- `vital_evidence`
- `profile_evidence`
- `answer_evidence`
- `retrieval_evidence`

### `detector_evidence`

Examples:

- motion state
- fall detection confidence
- inactivity after event

### `vital_evidence`

Examples:

- SpO2
- heart rate
- blood pressure

### `profile_evidence`

Examples:

- age
- blood thinner usage
- chronic disease
- mobility support

### `answer_evidence`

Examples:

- patient says they hit their head
- bystander says patient is not responding
- patient says they cannot stand

### `retrieval_evidence`

Examples:

- Vertex snippet indicates head injury on blood thinners is high risk
- Vertex snippet indicates not breathing should trigger CPR

### Evidence Rule

The reasoning layer should distinguish evidence from assumptions.

The system should be able to say:

- what was observed
- what was reported
- what was grounded from Vertex
- what remains uncertain

---

## Response Schema Contract

Phase 1 target response structure:

```json
{
  "incident_id": "INC-123",
  "status": "triage_in_progress",
  "responder_mode": "patient",
  "detection": {
    "motion_state": "rapid_descent",
    "fall_detection_confidence_score": 0.91,
    "fall_detection_confidence_band": "high",
    "event_validity": "likely_true"
  },
  "clinical_assessment": {
    "severity": "critical",
    "clinical_confidence_score": 0.73,
    "clinical_confidence_band": "medium",
    "action_confidence_score": 0.88,
    "action_confidence_band": "high",
    "red_flags": ["head_strike", "blood_thinner_use", "cannot_stand"],
    "protective_signals": ["awake_and_answering"],
    "suspected_risks": ["head_injury", "fracture_risk"],
    "uncertainty": ["Bleeding not yet confirmed"],
    "reasoning_summary": "High-risk fall with injury concern and anticoagulant use."
  },
  "action": {
    "recommended": "dispatch_pending_confirmation",
    "requires_confirmation": true,
    "cancel_allowed": true,
    "countdown_seconds": 30
  },
  "guidance": {
    "primary_message": "Stay still and do not try to stand.",
    "steps": [],
    "warnings": []
  },
  "grounding": {
    "source": "vertex_ai_search",
    "references": []
  },
  "audit": {
    "fallback_used": false,
    "policy_version": "phase1_v1"
  }
}
```

### Schema Rules

- the model must not invent extra top-level sections
- enums must come from controlled values
- red flags must use normalized taxonomy keys
- confidence must include score and band
- reasoning must be short and operational

### Schema Evolution Note

This Phase 1 schema should be treated as the stable `v1` contract.

However, it should not be treated as the final long-term action structure.

Phase 3 is expected to evolve the action model from:

- one primary recommended action

into a richer operational structure such as:

- primary escalation action
- notification actions
- bystander actions
- follow-up actions

So the Phase 1 schema should be considered:

- stable enough for consistency
- simple enough for MVP use
- intentionally evolvable for later multi-action reasoning

---

## Reasoning Output Rules

The model output must follow these rules:

1. Separate facts from assumptions.
2. Do not treat fall detection confidence as medical severity.
3. Use Vertex-grounded evidence for medical instructions when available.
4. If explicit life-threatening red flags are present, escalate without unnecessary delay.
5. If evidence is incomplete but concerning, say what is uncertain.
6. Use only the approved severity and action vocabulary.
7. Keep `reasoning_summary` short.
8. Do not output hidden chain-of-thought.

---

## Phase 1 Prompt Expectations

The reasoning prompt should require the model to return:

- severity
- confidence fields
- red flags
- suspected risks
- uncertainty
- recommended action
- short reasoning summary

The prompt should explicitly forbid:

- unsupported diagnosis claims
- unstructured essay output
- custom severity names
- custom action names

---

## Phase 1 Backend Expectations

Backend implementation should:

- update schemas to match this contract
- rename current event confidence semantics to fall detection confidence
- support incident status transitions
- preserve structured red-flag fields
- attach grounding metadata and references

---

## Phase 1 Frontend Expectations

Frontend implementation should:

- display severity using `low`, `medium`, `critical`
- display confidence as band-first
- clearly label fall detector confidence as detection confidence
- support new incident statuses
- prepare UI for cancellation and confirmation flow

---

## Phase 1 Open Items

These items are intentionally left tunable after implementation:

- exact confidence score calculation logic
- exact cutoff tuning for confidence bands
- exact countdown duration
- exact trigger threshold for automatic dispatch without confirmation
- expanded red-flag coverage for future scenarios
- evolution path from single-action output to multi-action operational output

These should be refined in later phases using scenario testing and evaluation.

---

## Locked Decisions Summary

Phase 1 locks in these decisions:

- Vertex AI Search is the medical grounding source of truth
- the product controls schema and vocabulary
- severity is `low`, `medium`, `critical`
- confidence is stored as score plus band
- confidence bands are `low`, `medium`, `high`
- action vocabulary is closed and fixed
- responder mode is explicit
- incident states are explicit
- red flags use normalized taxonomy keys
- reasoning output must be structured and short
