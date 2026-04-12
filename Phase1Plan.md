# Phase 1 Plan

## Phase 1 Goal

Phase 1 is about making the AI layer consistent and stable.

This phase should answer:

- what does each field mean?
- what vocabulary is allowed?
- what should the agent always return?
- how should the team interpret severity, confidence, and actions?

Phase 1 is the semantic foundation for all later work.

---

## Main Outcome

By the end of Phase 1, the project should have:

- fixed AI vocabulary
- fixed response structure
- fixed severity model
- fixed confidence definitions
- normalized red-flag taxonomy
- clear agent-side reasoning rules

This is the phase that reduces ambiguity.

---

## Execution Focus

Phase 1 should focus on consistency, not complexity.

The most important deliverable is not better intelligence yet.
It is a stable contract that later phases can safely build on.

---

## Workstreams

## 1. Lock Core Vocabulary

Define and freeze:

- severity labels
- action labels
- responder mode labels
- incident state labels
- confidence band labels

### Deliverable

- approved enum list used by the AI layer

---

## 2. Define Confidence Semantics

Separate the meanings of:

- fall detection confidence
- clinical confidence
- action confidence

Decide:

- what each one means
- what each one does not mean
- how each one should be displayed

### Deliverable

- confidence definitions and band policy

---

## 3. Define Severity And Action Policy

Lock the decision vocabulary:

- `low`
- `medium`
- `critical`

And the action vocabulary:

- `monitor`
- `contact_family`
- `dispatch_pending_confirmation`
- `emergency_dispatch`
- `cancelled`
- `resolved`

Define how severity maps into action.

### Deliverable

- severity/action mapping rules

---

## 4. Define Red-Flag Taxonomy V1

Create the normalized red-flag vocabulary used by the agent.

Group it into:

- immediate emergency red flags
- high-risk fall red flags
- vulnerability modifiers

### Deliverable

- red-flag taxonomy list with normalized keys

---

## 5. Define Structured Output Contract

The agent must return one controlled structure.

This should include:

- detection
- clinical assessment
- action
- guidance
- grounding
- audit

### Deliverable

- structured response contract

---

## 6. Define Reasoning Rules

Document the behavior rules the agent must follow.

Examples:

- separate facts from assumptions
- do not confuse detection confidence with medical certainty
- escalate on explicit life-threatening red flags
- show uncertainty when evidence is incomplete

### Deliverable

- short reasoning policy rules

---

## 7. Create Phase 1 Test Pack

Build a small scenario set that helps check whether the new structure is visible in outputs.

### Deliverable

- manual scenario pack for agent review

---

## Suggested Execution Order

1. Lock vocabulary.
2. Lock confidence semantics.
3. Lock severity and action rules.
4. Lock red-flag taxonomy.
5. Freeze the response schema.
6. Write reasoning rules.
7. Build a small test pack.

---

## What You Should Personally Own

As the AI lead, the highest-value Phase 1 ownership areas are:

- confidence definitions
- severity definitions
- action definitions
- red-flag taxonomy
- reasoning rules
- output schema

These define how the agent thinks.

---

## What Can Be Shared Or Support-Only

These can be implementation support rather than core AI ownership:

- test harness UI for inspection
- debug display of structured output
- mock routes used for testing
- documentation cleanup

---

## Risks To Watch

- too many labels create ambiguity
- confidence is treated as fake precision
- red flags are left as free-form wording
- retrieval wording leaks directly into product schema
- action meanings remain unclear

---

## Definition Of Done

Phase 1 is complete when:

- the AI has a fixed vocabulary
- the AI has a fixed structure
- severity and action meanings are locked
- confidence meanings are separated
- red flags are normalized
- outputs can be reviewed consistently using a small test pack

---

## Phase 1 Files

The main Phase 1 artifacts should be:

- `Phase1Rules.md`
- `Phase1Summary.md`
- `Phase1AgentTestPack.md`

These together define the semantic foundation for later phases.
