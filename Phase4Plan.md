# Phase 4 Plan

## Phase 4 Goal

Phase 4 is about making the interaction flow smarter for real emergency situations.

The focus is:

- patient mode
- bystander mode
- no-response mode
- role-specific guidance

This is the phase where the agent becomes more adaptive to who is actually present and able to help.

---

## Phase 4 Scope

Phase 4 focuses on:

- responder mode detection
- mode-specific questioning
- bystander-first guidance flow
- no-response escalation logic
- role-aware instruction formatting

This phase is strongly agent-centered, though some support UI or test flow work may help.

---

## Main Problem Before Phase 4

Before this phase, the system may still behave too much like a single-user questionnaire.

But real incidents often involve:

- a responsive patient
- a bystander reporting what they see
- nobody responding at all

The agent should not use one interaction pattern for all of them.

---

## Workstreams

## 1. Responder Mode Detection

The agent should detect who is currently interacting.

Supported modes:

- `patient`
- `bystander`
- `no_response`

### Goal

Decide who the app should address before asking or guiding.

### Deliverable

- responder-mode detection policy

---

## 2. Patient Mode Question Strategy

Patient mode should prioritize short direct self-report questions.

Typical focus:

- consciousness
- breathing
- pain location
- movement ability
- head strike

### Deliverable

- patient mode question policy

---

## 3. Bystander Mode Question Strategy

Bystander mode should prioritize observation and action.

Typical focus:

- is the patient responding?
- is the patient breathing normally?
- is there severe bleeding?
- did they hit their head?
- are they trying to stand?

### Deliverable

- bystander mode question policy

---

## 4. No-Response Policy

If nobody answers, the agent must stop assuming it can keep asking indefinitely.

### Goal

Define when the system should:

- continue waiting
- escalate concern
- switch to urgent guidance mode
- move toward dispatch policy

### Deliverable

- no-response escalation rules

---

## 5. Role-Specific Guidance

Guidance should be tailored to the responder.

Patient guidance should be:

- calm
- direct
- self-protective

Bystander guidance should be:

- command-style
- observational
- step-based

No-response output should be:

- short
- urgent
- minimal

### Deliverable

- role-aware guidance rules

---

## 6. Escalation Timing Rules

The agent should define when it is safe to ask another question and when it is not.

This is especially important in:

- breathing emergencies
- unconscious cases
- heavy bleeding cases
- no-response cases

### Deliverable

- escalation timing policy

---

## 7. Phase 4 Interaction Test Pack

Create a scenario pack specifically for interaction modes.

Scenarios should include:

- patient responsive and calm
- patient responsive but confused
- bystander reporting a severe fall
- bystander reporting abnormal breathing
- no-response after high-risk event

### Deliverable

- Phase 4 interaction scenario pack

---

## Suggested Execution Order

1. Define responder mode detection.
2. Define patient mode questioning.
3. Define bystander mode questioning.
4. Define no-response policy.
5. Define role-aware guidance style.
6. Define escalation timing rules.
7. Build interaction test pack.

---

## What You Should Personally Own

- responder mode definitions
- mode-specific question strategy
- no-response policy
- role-aware guidance style
- interaction scenario design

These define how the agent behaves during real use.

---

## What Can Be Support Work Only

- test-only mock interfaces
- timer or state demos for review
- scripts to replay interaction scenarios

These can help evaluation without stepping on teammate-owned production logic.

---

## Risks To Watch

- patient and bystander guidance get mixed together
- no-response cases stay stuck in questioning mode
- questions are too long or too many
- role switching is inconsistent
- urgent cases are delayed by unnecessary confirmation questions

---

## Definition Of Done

Phase 4 is complete when:

- responder mode is more reliably identified
- question strategy changes by role
- bystander flows feel meaningfully different from patient flows
- no-response logic is clearly defined
- guidance tone matches the current responder role
- an interaction test pack shows visible improvements
