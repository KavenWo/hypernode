# Phase 1 Closeout Summary

## Phase 1 Goal

Phase 1 was about making the AI layer consistent.

It was not mainly about making the agent fully advanced yet.
It was about making sure the system has:

- fixed meanings
- fixed vocabulary
- fixed response structure
- grounded medical reasoning rules
- a stable base for Phase 2 and beyond

---

## What We Locked In

### 1. Vertex AI Search Role

Vertex AI Search remains the grounded medical source of truth.

That means:

- Vertex provides the medical references and guidance
- the agent reasons using that evidence
- the product controls the output schema and vocabulary

This is important because it prevents the system from changing its output style every time retrieval wording changes.

---

### 2. Severity Model

We simplified severity into exactly three levels:

- `low`
- `medium`
- `critical`

This makes the reasoning and UI cleaner than using too many overlapping severity labels.

---

### 3. Confidence Model

We separated confidence into three meanings:

- `fall_detection_confidence`
- `clinical_confidence`
- `action_confidence`

We also agreed that confidence should exist in two forms:

- numeric score for internal logic and tuning
- band label for readable product output

Confidence bands:

- `low`
- `medium`
- `high`

---

### 4. Fixed Action Vocabulary

We locked Phase 1 actions to:

- `monitor`
- `contact_family`
- `dispatch_pending_confirmation`
- `emergency_dispatch`
- `cancelled`
- `resolved`

This reduces prompt drift and makes downstream logic safer.

---

### 5. Responder Modes

We defined three responder modes:

- `patient`
- `bystander`
- `no_response`

This matters because the agent should not ask the same questions in every situation.

---

### 6. Red-Flag Taxonomy V1

We defined a normalized internal red-flag vocabulary instead of depending on raw Vertex wording.

Examples include:

- `not_breathing`
- `abnormal_breathing`
- `severe_bleeding`
- `head_strike`
- `confusion_after_fall`
- `cannot_stand`
- `blood_thinner_use`

This allows the agent to reason consistently while still being grounded by Vertex evidence.

---

### 7. Structured Output Contract

We aligned Phase 1 around one structured assessment shape with sections for:

- detection
- clinical assessment
- action
- guidance
- grounding
- audit

This gives the team one shared contract for the AI output.

---

## What Improved Compared To Before

Before Phase 1:

- `confidence_score` could be misunderstood as medical confidence
- severity and action semantics were looser
- red-flag handling was not normalized
- response structure was flatter and less explicit
- the relationship between Vertex and the agent output was less clearly defined

After Phase 1:

- detection confidence is clearly separated from clinical and action confidence
- severity vocabulary is simpler and more consistent
- red flags are normalized into fixed keys
- the agent contract is much clearer
- grounded retrieval and product schema now have distinct responsibilities

---

## What Phase 1 Did Not Try To Finish

These are intentionally left for later phases:

- advanced Vertex retrieval planning
- query re-ranking
- full cancellation implementation
- complete bystander flow implementation
- no-response escalation tuning
- large-scale evaluation automation
- final threshold calibration

Phase 1 is complete when the contract is stable, not when every advanced behavior is finished.

---

## Definition Of Done For Phase 1

Phase 1 should be considered complete if these are true:

- the agent uses a fixed vocabulary
- the agent uses a fixed response structure
- severity is consistently `low`, `medium`, or `critical`
- confidence meanings are separated
- red flags are normalized
- Vertex remains the grounding source
- a small scenario test pack can be used to inspect outputs

---

## Recommended Next Step

The best next step after Phase 1 is not more schema work.

The best next step is:

- test the agent on scenario cases
- inspect where outputs are still inconsistent
- use that to refine prompts, extraction, and policy in Phase 2

That is how we turn the new structure into visible quality improvements.
