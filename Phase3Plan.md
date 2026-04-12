# Phase 3 Plan

## Phase 3 Goal

Phase 3 is about improving the reasoning pipeline itself.

Phase 1 gave us consistency.
Phase 2 improves grounded retrieval and guidance.
Phase 3 should improve how the agent interprets signals and makes decisions.

The core objective is:

- break reasoning into clearer stages
- reduce one-shot prompt fragility
- make uncertainty handling better
- make decisions easier to debug

---

## Phase 3 Scope

Phase 3 focuses on:

- signal extraction
- evidence structuring
- clinical reasoning policy
- action policy
- uncertainty-aware decision making

This is still primarily agent work.

---

## Main Problem Before Phase 3

Even with a good schema and better retrieval, the system can still be fragile if all important judgment happens in one broad reasoning step.

Typical problems:

- symptoms are not normalized before reasoning
- incomplete answers are handled inconsistently
- severity reasoning and action reasoning are mixed together
- uncertainty is not always used properly

Phase 3 should separate these concerns.

---

## Workstreams

## 1. Signal Extraction Layer

Create a dedicated layer that converts raw answers into structured features.

### Inputs

- patient answers
- bystander answers
- profile data
- vitals
- event data

### Outputs

- red flags
- protective signals
- missing facts
- contradictions
- vulnerability modifiers

### Deliverable

- signal extraction specification and rules

---

## 2. Missing Fact Policy

The agent should explicitly identify which missing fact matters most.

Examples:

- breathing status not confirmed
- bleeding status not confirmed
- head strike not confirmed
- responsiveness unclear

### Goal

Help the agent decide when to ask one more question versus act now.

### Deliverable

- missing-fact priority rules

---

## 3. Clinical Reasoning Policy

This is where severity should be chosen using structured evidence instead of loose instinct.

### Goal

Choose `low`, `medium`, or `critical` using:

- event risk
- vitals
- profile
- extracted red flags
- grounded medical support

### Deliverable

- clinical reasoning policy doc

---

## 4. Action Policy Layer

Severity and action should not be treated as identical.

Phase 3 should define clear rules for:

- when `medium` becomes `contact_family`
- when `critical` becomes `dispatch_pending_confirmation`
- when `critical` becomes `emergency_dispatch`

### Deliverable

- action policy doc

---

## 5. Uncertainty Handling

The agent should not use uncertainty only as decoration.

Uncertainty should affect behavior.

Examples:

- ask one more question
- lower clinical confidence
- keep action at confirmation-pending instead of full dispatch
- escalate anyway if explicit danger signs exist

### Deliverable

- uncertainty behavior rules

---

## 6. Reasoning Trace For Debugging

The agent should be easier to inspect during testing.

Not full chain-of-thought.
Just structured decision support such as:

- main evidence used
- missing fact
- top red flags
- chosen severity reason
- chosen action reason

### Deliverable

- debug reasoning trace format

---

## 7. Phase 3 Scenario Review Pack

Create a focused scenario pack for reasoning decisions.

The pack should test:

- stable low-risk cases
- borderline medium vs critical cases
- explicit emergency cases
- uncertainty-heavy cases
- conflicting-signal cases

### Deliverable

- Phase 3 reasoning scenario pack

---

## Suggested Execution Order

1. Define signal extraction outputs.
2. Define missing-fact priority rules.
3. Define severity reasoning policy.
4. Define action policy.
5. Define uncertainty behavior.
6. Add reasoning trace fields for testing.
7. Build the scenario pack.

---

## What You Should Personally Own

- extraction taxonomy
- severity decision policy
- action decision policy
- uncertainty rules
- reasoning test cases

These are core AI reasoning responsibilities.

---

## What Can Be Support Work Only

- a test-only reasoning sandbox
- debug viewers for extraction output
- temporary scripts for scenario replay

These help evaluate reasoning without colliding with teammate-owned system logic.

---

## Risks To Watch

- too much logic remains hidden in one prompt
- uncertainty is ignored in hard cases
- severity and action collapse into the same decision
- extracted signals are incomplete or inconsistent
- borderline cases flip unpredictably

---

## Definition Of Done

Phase 3 is complete when:

- raw answers are converted into structured signals more reliably
- severity reasoning is more consistent
- action decisions are easier to justify
- uncertainty changes behavior, not just wording
- a scenario pack can expose reasoning weaknesses clearly
