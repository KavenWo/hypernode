# Phase 5 Plan

## Phase 5 Goal

Phase 5 is about evaluation, tuning, and safety refinement.

By this point, the system should already have:

- a stable contract
- stronger retrieval behavior
- better reasoning structure
- better interaction modes

Phase 5 turns that into a measurable improvement process.

---

## Phase 5 Scope

Phase 5 focuses on:

- evaluation design
- scenario scoring
- threshold review
- false positive and false negative analysis
- safety tuning
- regression tracking

This phase is where the team stops changing the AI only by intuition.

---

## Main Problem Before Phase 5

Without a proper evaluation phase, it becomes hard to tell:

- whether prompt changes really helped
- whether retrieval changes improved grounding
- whether new behavior made some cases worse
- whether the system is becoming safer or just more complex

Phase 5 solves that by making quality measurable.

---

## Workstreams

## 1. Evaluation Framework

Build a consistent framework for reviewing outputs.

Review categories should include:

- schema compliance
- severity correctness
- action correctness
- red-flag extraction quality
- confidence consistency
- uncertainty handling
- grounding usefulness
- guidance safety

### Deliverable

- Phase 5 evaluation rubric

---

## 2. Scenario Library

Build a more complete scenario library covering:

- low-risk cases
- medium-risk cases
- critical cases
- bystander cases
- no-response cases
- false alarm cases
- conflicting-signal cases

### Deliverable

- consolidated scenario library

---

## 3. Threshold Review

Review the practical behavior of:

- confidence bands
- severity thresholds
- dispatch vs confirmation boundaries
- low-risk monitoring boundaries

### Goal

Check whether the current policy is too aggressive or too passive.

### Deliverable

- threshold review notes and adjustment proposals

---

## 4. False Positive Analysis

Identify cases where the system escalates too much.

Examples:

- false alarm from motion data
- medium-risk case wrongly moved to critical
- low-risk patient over-escalated because of event metadata

### Deliverable

- false positive review set

---

## 5. False Negative Analysis

Identify cases where the system misses urgency.

Examples:

- breathing problem not escalated fast enough
- head injury on blood thinners under-classified
- severe bleeding not prioritized enough
- no-response case treated too passively

### Deliverable

- false negative review set

---

## 6. Safety Review

Inspect whether the guidance or action output ever becomes unsafe.

Review areas:

- dangerous calmness in critical cases
- missing warnings
- unclear or contradictory instructions
- role mismatch in bystander/patient guidance

### Deliverable

- safety review checklist

---

## 7. Regression Tracking

Every major prompt or policy change should be compared against previous results.

### Goal

Prevent improvements in one area from silently damaging another.

### Deliverable

- regression tracking template

---

## Suggested Execution Order

1. Define the evaluation rubric.
2. Consolidate scenario library.
3. Run initial evaluation pass.
4. Review thresholds and boundaries.
5. Separate false positives and false negatives.
6. Run safety review.
7. Track regressions across updates.

---

## What You Should Personally Own

- evaluation rubric
- scenario library structure
- threshold review interpretation
- false positive and false negative analysis
- safety judgment on prompt and reasoning behavior

These are core AI quality responsibilities.

---

## What Can Be Support Work Only

- scripts for recording results
- spreadsheets or markdown score tables
- dashboards for internal review
- scenario replay helpers

These help evaluation without changing teammate-owned logic.

---

## Risks To Watch

- prompts are tuned based on a few memorable cases only
- improvements are not tracked over time
- confidence looks neat but is poorly calibrated
- unsafe guidance slips through because outputs “look structured”
- retrieval quality and reasoning quality get mixed together in analysis

---

## Definition Of Done

Phase 5 is complete when:

- the project has a repeatable evaluation rubric
- scenario reviews are structured and comparable
- false positives and false negatives are being tracked
- safety review is explicit
- regression checks exist for important prompt or policy changes
- the team can justify future improvements with evidence, not only instinct

---

## Recommended Immediate Next Step

The best first action for Phase 5 is:

- create the evaluation rubric and consolidated scenario library

That becomes the backbone for all later tuning work.
