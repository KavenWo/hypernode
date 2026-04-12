# Final Product Plan

## Product Goal

Build a trustworthy emergency-response assistant that does more than detect a fall.
The final product must:

1. Detect a possible incident.
2. Confirm whether the event is real enough to act on.
3. Ask the right person the right questions.
4. Reason with grounded medical guidance.
5. Choose a safe next action.
6. Guide the patient or bystander clearly.
7. Allow cancellation or override when appropriate.
8. Log every important decision for audit and improvement.

The final system should feel systematic, medically cautious, and explainable.

---

## What The MVP Already Does Well

- Detects a fall-like event with `motion_state` and `confidence_score`.
- Collects a small triage intake before reasoning.
- Pulls grounded guidance from Vertex AI Search when configured.
- Produces a severity, action, reasoning summary, and instructions.
- Triggers a mock dispatch flow when the action is `emergency_dispatch`.

This is a strong MVP foundation because the core loop already exists:

`detect -> ask -> reason -> act -> guide`

---

## Main Gaps To Fix Before Final Product

## 1. Confidence Score Is Not Clearly Defined

Right now `confidence_score` is treated as a general signal in the UI and backend, but it actually represents only one thing:

- how confident the detection layer is that a fall-like event happened

It should not be confused with:

- confidence that the patient is critically injured
- confidence that dispatch is medically justified
- confidence that retrieval evidence is strong

Current issue:

- the app risks making users think `confidence_score` is the AI's medical certainty, when it is only detector confidence

Final product requirement:

- separate detection confidence from clinical confidence and action certainty

---

## 2. Reasoning Is Still Too One-Shot

Current backend flow is mostly:

- vision hint
- vital hint
- question answers
- grounded snippets
- one reasoning pass

That is acceptable for MVP, but too fragile for the final product.

Final product requirement:

- split reasoning into clear stages so each stage has one responsibility

---

## 3. Vertex AI Search Is Used, But Not Yet Optimized

Current behavior is still basic:

- one query is built from a few risk signals
- top snippets are returned
- snippets are passed into reasoning
- instructions are often the snippets themselves

This is useful, but not yet reliable enough for production-like behavior.

Final product requirement:

- retrieval must be targeted, ranked, filtered, and cited so the agent uses the right protocol for the right situation

---

## 4. Response Structure Is Not Strict Enough

Current response gives useful fields, but not enough structure for a robust agent pipeline.

Missing concepts:

- evidence summary
- uncertainty summary
- red flags found
- who should answer next
- whether dispatch is pending, triggered, cancelled, or confirmed
- what facts came from user answers versus retrieval

Final product requirement:

- enforce one strict response contract used by backend, frontend, logs, and future analytics

---

## 5. Bystander Flow Is Not Yet First-Class

You already know this is needed.
If a bystander is present, the app should shift from patient-first questioning to helper-first questioning.

Final product requirement:

- the agent must detect responder availability and dynamically switch into bystander protocol mode

---

## 6. Cancellation, Override, And Audit Logging Are Incomplete

The final product must allow:

- user cancellation
- bystander cancellation
- timeout with no response
- manual override by user
- dispatch cancellation before external escalation
- logging of every decision and cancellation reason

Current issue:

- incidents can be triggered and resolved, but there is no proper cancellation state machine or audit trail for why an action was stopped

---

## 7. Metrics And Evaluation Are Not Yet Formalized

Right now it is hard to tell whether the AI is improving because there is no final evaluation framework.

Final product requirement:

- define clear metrics for detection quality, reasoning quality, retrieval quality, action quality, and UX safety

---

## Understanding Each Metric And Its Role

The final product should treat each metric as a different type of evidence.

## A. `motion_state`

Role:

- event pattern classification from the detection layer

Influence:

- changes how urgent the system should be before asking questions
- changes which triage questions are asked first
- affects fallback severity scoring

Interpretation:

- `rapid_descent` or `no_movement` should increase urgency
- `stumble` or `slow_descent` should increase verification needs before escalation

---

## B. `confidence_score`

Role:

- detector confidence that the event is truly a fall or serious fall-like event

Influence today:

- affects initial vision severity hint
- affects which third question gets selected
- contributes slightly to fallback severity logic

Important rule:

- this is not the same as medical severity

Final interpretation policy:

- low detection confidence: verify first, avoid over-escalation
- medium detection confidence: ask confirmation questions quickly
- high detection confidence: assume event is likely real, then assess injury severity

Recommended naming for clarity:

- rename display label from `Confidence Score` to `Fall Detection Confidence`

---

## C. Vital Signs

Role:

- physiological urgency signal

Influence:

- should heavily affect whether the event is likely dangerous even if the fall detector is uncertain

Examples:

- low SpO2 can elevate urgency
- very high or very low heart rate can elevate urgency
- hypotension after a fall can point toward serious risk

Current limitation:

- the existing vital logic is still very coarse and only checks a few thresholds

Final product requirement:

- convert vitals into structured risk flags instead of one broad anomaly label

Examples of future flags:

- `hypoxia_risk`
- `shock_risk`
- `tachycardia_risk`
- `bradycardia_risk`
- `unstable_hemodynamics`

---

## D. Patient Profile Risk

Role:

- baseline vulnerability modifier

Influence:

- should raise caution even when answers are incomplete

Examples:

- age
- blood thinners
- mobility support needs
- cardiac history
- history of stroke
- seizure risk

Current limitation:

- profile is used, but not deeply normalized into risk categories

Final product requirement:

- map profile data into explicit risk modifiers before final reasoning

---

## E. Triage Answers

Role:

- strongest real-time human evidence in the flow

Influence:

- should override detector uncertainty when danger signs are explicitly reported

High-priority answer patterns:

- not breathing
- unconscious
- heavy bleeding
- head strike
- blood thinners
- severe pain
- cannot stand
- chest pain
- confusion
- seizure-like behavior

Final product requirement:

- extract structured red flags from free-text answers before reasoning

---

## F. Retrieval Quality

Role:

- determines whether the model is reasoning with the right grounded medical protocol

Influence:

- affects guidance quality
- affects trustworthiness of instructions
- should affect whether the system claims grounded support

Final product requirement:

- retrieval quality should be scored separately from model reasoning quality

Suggested internal retrieval metrics:

- snippet relevance
- protocol coverage
- citation completeness
- contradiction rate
- fallback rate when Vertex returns no useful result

---

## G. Clinical Confidence

This metric does not properly exist yet, but it should.

Role:

- how confident the clinical decision layer is in the chosen severity and action

This should be based on:

- number of high-risk signals
- agreement between detectors, vitals, and answers
- retrieval quality
- ambiguity in the answers

Important rule:

- low clinical confidence should usually trigger more questions, not silent certainty

---

## H. Action Confidence

This should also be separated from clinical confidence.

Role:

- confidence that the next operational action is justified now

Examples:

- calling family may need only medium action confidence
- dispatching emergency services should require stricter thresholds or explicit danger signs

---

## Final AI Architecture

The final product should move from one broad reasoning step into a staged agent pipeline.

## 1. Detection Interpreter

Inputs:

- motion event
- vision event
- event confidence
- inactivity duration if available

Output:

- `event_validity`
- `detection_confidence`
- `detection_risk_flags`
- `needs_immediate_check`

Responsibility:

- decide whether this looks like a real incident that requires interaction

---

## 2. Intake Orchestration Agent

Inputs:

- detection output
- patient profile
- vital flags

Output:

- who to address first
- next 1 to 3 questions
- whether patient mode or bystander mode is active

Responsibility:

- choose the minimum useful next questions instead of using one static triage set

Modes:

- patient mode
- bystander mode
- no-response mode

---

## 3. Signal Extraction Layer

Inputs:

- free-text answers
- patient profile
- vitals

Output:

- structured red flags
- structured protective signals
- missing facts
- contradictions

Responsibility:

- convert messy text into decision-ready features

---

## 4. Retrieval Planner

Inputs:

- extracted red flags
- patient profile risks
- event type

Output:

- targeted Vertex AI Search query set
- retrieval intent

Example retrieval intents:

- fall first aid
- head injury on blood thinners
- unconscious patient airway response
- CPR protocol
- post-fall do-not-move guidance

Responsibility:

- avoid one generic query and instead fetch the most relevant protocol

---

## 5. Clinical Reasoning Agent

Inputs:

- detection summary
- vital flags
- profile risks
- extracted answer facts
- grounded retrieval evidence

Output:

- severity
- likely risks
- recommended action
- rationale
- uncertainty
- missing critical facts

Responsibility:

- decide the safest medical interpretation without inventing facts

Key rule:

- reasoning must explicitly distinguish evidence from assumption

---

## 6. Policy And Action Agent

Inputs:

- clinical assessment
- action confidence
- user state
- cancellation state

Output:

- `monitor`
- `contact_family`
- `emergency_dispatch_pending`
- `emergency_dispatch_confirmed`
- `cancelled_by_user`
- `cancelled_by_bystander`

Responsibility:

- convert medical assessment into operational state transitions

---

## 7. Guidance Agent

Inputs:

- action
- responder type
- grounded protocol

Output:

- short immediate instruction
- step-by-step instructions
- do-not-do warnings
- escalation warning signs

Responsibility:

- produce simple instructions tailored to the person holding the phone

---

## Strict Response Contract For Final Product

Every assessment should return one strict schema.

Suggested response shape:

```json
{
  "incident_id": "INC-123",
  "status": "triage_in_progress",
  "responder_mode": "patient",
  "detection": {
    "motion_state": "rapid_descent",
    "fall_detection_confidence": 0.98,
    "event_validity": "likely_true",
    "risk_flags": ["high_impact_fall", "post_fall_immobility"]
  },
  "clinical_assessment": {
    "severity": "high",
    "clinical_confidence": "medium",
    "action_confidence": "medium_high",
    "suspected_risks": ["head_injury", "hip_injury"],
    "red_flags": ["cannot_stand", "dizziness", "blood_thinners"],
    "protective_signals": ["awake_and_responding"],
    "uncertainty": [
      "Loss of consciousness not fully confirmed",
      "Bleeding status not yet confirmed"
    ],
    "reasoning_summary": "High-risk fall with red flags and anticoagulant use."
  },
  "action": {
    "recommended": "emergency_dispatch_pending",
    "why": "High-risk fall with head injury concern on blood thinners.",
    "requires_confirmation": true,
    "countdown_seconds": 30,
    "cancel_allowed": true
  },
  "guidance": {
    "primary_message": "Stay still and do not try to stand up.",
    "steps": [
      "Check whether the patient is conscious and breathing normally.",
      "Do not move the patient if head, neck, back, or hip injury is possible.",
      "If breathing worsens or the patient becomes unresponsive, call emergency services immediately."
    ],
    "warnings": [
      "Do not give food or drink.",
      "Do not help the patient stand if severe pain or head injury is suspected."
    ]
  },
  "grounding": {
    "source": "vertex_ai_search",
    "query_intents": ["fall_red_flags", "head_injury_blood_thinners"],
    "references": []
  },
  "audit": {
    "decision_version": "v1",
    "fallback_used": false
  }
}
```

This structure keeps UI, logs, dispatch, and evaluation aligned.

---

## Confidence Strategy For Final Product

The product should use confidence in layers.

## Layer 1. Detection Confidence

Question:

- did a fall probably happen?

Used for:

- whether to enter emergency triage flow

Should not directly decide:

- ambulance dispatch on its own

---

## Layer 2. Clinical Confidence

Question:

- based on all evidence, how certain are we about the medical severity?

Used for:

- whether to ask more questions
- whether to downgrade or upgrade certainty

---

## Layer 3. Action Confidence

Question:

- are we justified to trigger the next operational step now?

Used for:

- family notification
- emergency dispatch
- countdown confirmation

---

## Recommended Operational Policy

- High detection confidence + major red flags -> urgent action path
- Low detection confidence + severe vital abnormality -> still urgent assessment path
- Medium evidence + unclear answers -> ask clarifying question before dispatch if safe to do so
- Explicit danger signs like not breathing, unconscious, heavy bleeding -> bypass extra questioning and escalate immediately

---

## Vertex AI Search Improvement Plan

## Problem Today

Current retrieval is too simple:

- one query
- top snippets
- limited ranking logic
- no contradiction check
- no protocol-specific retrieval stages

## Final Retrieval Strategy

### 1. Query By Intent, Not By Generic Summary

Instead of one broad query, build targeted queries from extracted risks.

Examples:

- `elderly fall first aid guidance`
- `head injury blood thinners emergency warning signs`
- `unconscious patient airway and breathing first aid`
- `do not move patient suspected hip fracture guidance`

### 2. Retrieve Multiple Small Evidence Sets

Use separate retrieval buckets:

- scene safety and initial check
- red flags and escalation criteria
- bystander intervention steps
- contraindications and warnings

### 3. Re-rank Before Passing To Gemini

Rank snippets by:

- direct match to current red flags
- mention of exact patient risks such as blood thinners
- actionability
- clarity

### 4. Normalize Retrieved Content

Convert snippets into:

- immediate steps
- warning signs
- escalation conditions
- do-not-do instructions

Do not pass raw snippets directly as final user instructions unless they are already clean and short.

### 5. Keep Evidence Traceable

Store:

- query used
- snippets selected
- references selected
- which instruction came from which snippet

### 6. Add Retrieval Evaluation

For each test case, verify:

- were the right protocols retrieved?
- were critical warnings present?
- did the retrieval omit a needed protocol?

---

## Bystander Flow Plan

The final product should explicitly support three responder states.

## 1. Patient Responsive

Ask:

- are you conscious?
- are you breathing normally?
- where is the pain?
- can you move safely?

## 2. Bystander Present

Ask:

- is the patient conscious?
- is the patient breathing normally?
- is there heavy bleeding?
- did they hit their head?
- are they trying to stand?

Guidance style:

- command-style
- short steps
- clear warnings

## 3. No Response

If there is no answer after a short timeout:

- switch to emergency no-response protocol
- escalate to dispatch pending or confirmed based on available evidence
- keep voice guidance extremely short

---

## Cancellation And Incident State Plan

The final product needs a real incident state machine.

Suggested states:

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

Required behaviors:

- user can cancel during countdown
- cancellation reason is captured
- cancellation does not erase the incident
- false alarms are stored for model improvement
- if user cancels but severe evidence exists, system logs the override risk

Required audit fields:

- who cancelled
- when they cancelled
- which step was active
- what action would have happened
- why the cancellation was accepted

---

## Prompting And Reasoning Rules

The final prompts should enforce these rules:

1. Separate facts from assumptions.
2. Never treat detection confidence as medical certainty.
3. Prefer asking for one missing critical fact instead of pretending certainty.
4. Escalate immediately on explicit life-threatening signs.
5. Use grounded evidence for instructions.
6. Keep actions inside a fixed action set.
7. Return short patient-safe explanations, not chain-of-thought.

The prompt should ask the model for:

- severity
- recommended action
- evidence summary
- uncertainty summary
- missing critical fact
- short reasoning

It should not ask for:

- unrestricted open-ended text
- speculative diagnoses beyond the evidence

---

## Implementation Roadmap

## Phase 1. Clean Up Semantics

Goals:

- rename and separate confidence types
- introduce richer response schema
- normalize red flags from answers
- add incident states and cancellation support

Deliverables:

- new schema definitions
- new API fields
- new frontend labels
- cancellation endpoint and audit logging

---

## Phase 2. Upgrade Retrieval And Guidance

Goals:

- move from one generic query to intent-based retrieval
- normalize snippets into protocol blocks
- attach evidence references to guidance

Deliverables:

- retrieval planner
- re-ranking logic
- protocol block formatter
- grounding trace data

---

## Phase 3. Upgrade Reasoning Pipeline

Goals:

- split intake, extraction, reasoning, and action policy
- reduce one-shot reasoning fragility
- improve explainability

Deliverables:

- signal extraction layer
- clinical reasoning layer
- policy/action layer
- uncertainty-aware responses

---

## Phase 4. Bystander And No-Response Protocols

Goals:

- fully support patient mode, bystander mode, and no-response mode
- produce role-specific instructions

Deliverables:

- responder-mode detector
- bystander question set
- no-response escalation rules
- role-aware guidance templates

---

## Phase 5. Evaluation And Safety Tuning

Goals:

- measure quality systematically
- improve thresholds with evidence

Deliverables:

- scenario test suite
- retrieval evaluation sheet
- false positive and false negative analysis
- dispatch decision review set

---

## Suggested Evaluation Metrics

Track final quality across five groups.

## 1. Detection Metrics

- fall detection precision
- fall detection recall
- false alarm rate
- missed incident rate

## 2. Triage Metrics

- question relevance
- questions needed before safe decision
- critical fact capture rate

## 3. Retrieval Metrics

- relevant snippet hit rate
- citation completeness
- protocol coverage
- fallback frequency

## 4. Reasoning Metrics

- severity correctness
- action correctness
- red-flag extraction accuracy
- uncertainty calibration

## 5. Safety And UX Metrics

- unsafe guidance rate
- unnecessary dispatch rate
- missed escalation rate
- cancellation success rate
- average time to actionable instruction

---

## Immediate Priority Recommendations

If the team wants the highest-value next steps, prioritize these first:

1. Separate `fall_detection_confidence` from future `clinical_confidence`.
2. Replace the loose reasoning response with a strict schema.
3. Add structured red-flag extraction from answers before final reasoning.
4. Build bystander mode and no-response mode into the interaction flow.
5. Add cancellation states and incident audit logging.
6. Improve Vertex AI Search by using intent-based retrieval instead of one generic query.
7. Create a scenario-based evaluation set so prompt changes can be measured instead of guessed.

---

## Final Direction

The final product should not behave like a single prompt that "decides everything."
It should behave like a layered emergency system:

- detect carefully
- verify quickly
- extract signals cleanly
- retrieve grounded protocols
- reason cautiously
- act systematically
- guide clearly
- log everything important

That is the path from a strong MVP to a credible final product.
