# Phase 2 Query Template Policy

Short description: this file defines the controlled query templates that turn selected retrieval intents into stable Vertex AI Search queries for the MVP and future backend use.

## Purpose

This document defines how retrieval intents become search queries for Vertex AI Search.

Phase 2 should not rely on fully freeform query generation as the default retrieval path.
Instead, the system should use controlled query templates so search behavior stays stable, testable, and explainable.

This policy gives the agent a repeatable way to turn:

- normalized case state
- selected retrieval intents
- responder context

into a small set of deliberate search queries.

---

## Core Principle

The system should use:

- template-first query construction
- modifier-based specialization
- optional constrained refinement only when needed

The system should not use:

- unrestricted model-written search queries for every run

The model may assist query refinement in limited cases, but the baseline query path must remain policy-driven.

---

## Query Design Goals

Phase 2 queries should be:

- medically focused
- stable across runs
- easy to compare in testing
- specific enough to surface actionable evidence
- short enough to avoid noisy retrieval

Each query should answer one retrieval intent, not every possible medical question at once.

---

## Query Construction Model

Each final query should be built from four parts:

1. base intent phrase
2. event anchor
3. risk or role modifiers
4. action or warning emphasis

Conceptually:

`intent template + triggered modifiers + final cleanup`

This keeps the query consistent while still allowing case-specific detail.

---

## Query Rules

### Rule 1: One Intent, One Primary Query

Each selected intent should produce one primary query by default.

Only issue a second query for the same intent if:

- the first query returns weak evidence
- a role-specific variation is required
- a critical modifier was not represented clearly enough

### Rule 2: Prefer Specific Risk Phrases Over Broad Fall Phrases

If the case includes a strong risk factor, include it directly in the query.

Examples:

- include `blood thinners`
- include `unconscious`
- include `abnormal breathing`
- include `severe bleeding`

Do not rely on a broad query and hope search ranks the high-risk case correctly.

### Rule 3: Include `fall` Only When It Improves Retrieval Focus

For most intents, `fall` should remain present because it anchors the scenario.

However, if the critical concept is primarily airway or CPR, keep the query concise and do not overload it with extra event detail.

### Rule 4: Use Role Modifiers Sparingly

Add role modifiers such as `bystander` only when:

- the guidance clearly depends on helper actions
- or the retrieved evidence needs helper-oriented wording

Do not add `bystander` to every query automatically.

### Rule 5: Do Not Pack Multiple Separate Intents Into One Query

Avoid queries such as:

- `head injury blood thinners severe bleeding CPR fall emergency`

This reduces retrieval clarity and makes debugging harder.

Instead, split into the top two or three intent-aligned queries.

---

## Base Query Templates

These are the Phase 2 default templates.

### `fall_general_first_aid`

Primary template:

- `fall first aid immediate care`

Optional anchored variant:

- `fall first aid immediate care adult`

Use when:

- broad immediate care guidance is needed

### `fall_red_flags`

Primary template:

- `fall emergency warning signs red flags`

Use when:

- escalation screening is needed

### `bystander_check_consciousness`

Primary template:

- `check responsiveness after collapse bystander`

Fallback variant:

- `how to check if person is responsive after fall`

Use when:

- a helper needs grounding for responsiveness checks

### `bystander_check_breathing`

Primary template:

- `check breathing after fall bystander`

Fallback variant:

- `how to tell if breathing is normal after collapse`

Use when:

- a helper needs grounding for breathing assessment

### `unconscious_after_fall`

Primary template:

- `unconscious after fall airway breathing emergency help`

Fallback variant:

- `unresponsive after fall what to do breathing airway`

Use when:

- consciousness is impaired or absent

### `abnormal_breathing_after_fall`

Primary template:

- `abnormal breathing after fall emergency warning signs`

Fallback variant:

- `agonal abnormal breathing emergency what to do after collapse`

Use when:

- breathing is abnormal rather than clearly absent

### `cpr_trigger_guidance`

Primary template:

- `not breathing start CPR AED emergency help`

Fallback variant:

- `when to start CPR if person not breathing normally`

Use when:

- CPR trigger evidence is needed

### `head_injury_after_fall`

Primary template:

- `head injury after fall warning signs emergency`

Fallback variant:

- `head injury fall when to seek urgent help`

Use when:

- head injury is a concern without anticoagulant modifier

### `head_injury_blood_thinners`

Primary template:

- `head injury blood thinners fall emergency warning signs`

Fallback variant:

- `head hit on blood thinners after fall urgent evaluation`

Use when:

- head injury and anticoagulant risk are both present

### `severe_bleeding_after_fall`

Primary template:

- `severe bleeding after fall first aid emergency`

Fallback variant:

- `how to stop severe bleeding emergency help`

Use when:

- urgent bleeding control guidance is needed

### `possible_spinal_injury`

Primary template:

- `suspected spinal injury after fall do not move first aid`

Fallback variant:

- `neck back injury after fall keep still emergency`

Use when:

- spinal precautions are needed

### `fracture_or_cannot_stand`

Primary template:

- `cannot stand after fall possible fracture what to do`

Fallback variant:

- `hip fracture after fall do not help stand`

Use when:

- fracture or unsafe weight-bearing is likely

### `do_not_move_possible_injury`

Primary template:

- `after fall when not to move injured person`

Fallback variant:

- `keep still after fall possible serious injury`

Use when:

- movement warnings are more important than diagnosis-specific retrieval

### `monitor_low_risk_fall`

Primary template:

- `mild fall home monitoring warning signs`

Fallback variant:

- `after minor fall symptoms to watch for`

Use when:

- low-risk monitoring advice is needed

### `bystander_instruction_mode`

Primary template:

- `bystander first aid after fall what to do`

Fallback variant:

- `helping someone after a fall immediate steps`

Use when:

- helper-oriented phrasing is useful across a mixed case

---

## Modifier Rules

Modifiers should be added only when they materially change retrieval quality.

### Risk Modifiers

Allowed examples:

- `blood thinners`
- `older adult`
- `unconscious`
- `not breathing`
- `abnormal breathing`
- `severe bleeding`
- `head injury`
- `spinal injury`

Use when:

- the modifier is present in normalized state
- the modifier changes urgency or expected advice

### Role Modifiers

Allowed examples:

- `bystander`
- `caregiver`

Use when:

- the instructions should be phrased for the helper rather than the patient

### Context Modifiers

Allowed examples:

- `after fall`
- `after collapse`
- `adult`
- `older adult`

Use when:

- they improve relevance without making the query too long

### Modifier Rule

No more than `2` modifiers should usually be appended to one base query.

If more context is needed, prefer a second intent query instead of one overloaded query.

---

## Query Budget Policy

To reduce noise, Phase 2 should keep a small query budget.

Recommended defaults:

- low-risk case: `1-2` queries
- normal concerning case: `2-3` queries
- critical mixed case: `3-4` queries

### Query Ordering

Always issue the highest-priority intent query first.

Recommended ordering:

1. immediate life-threat query
2. injury-specific escalation query
3. safe-handling or helper query
4. broad fallback query

### Broad Query Rule

Do not spend query budget on `fall_general_first_aid` if:

- a Tier 1 life-threat query and a highly specific Tier 2 injury query already fully consume the useful budget

---

## Constrained AI Refinement

AI assistance is allowed only as a secondary refinement step.

It may be used to:

- choose between a primary and fallback template variant
- add one missing modifier
- generate one alternate wording if retrieval quality is weak

It should not be used to:

- invent the initial query strategy from scratch
- replace the intent mapping policy
- generate many uncontrolled query variants

### Refinement Trigger

Refinement should happen only if:

- retrieved snippets are too generic
- the top results miss an obvious case modifier
- the returned evidence is not actionable enough

### Refinement Limit

Allow at most one refinement round per intent in Phase 2.

This prevents uncontrolled search expansion.

---

## Audit Expectations

Every retrieval run should record:

- selected intent
- primary template used
- modifiers applied
- whether a fallback template was used
- whether AI refinement was used
- final issued queries in order

This is required for grounding inspection and query evaluation.

---

## Locked Decisions Summary

Phase 2 query generation is:

- template-first
- modifier-based
- budget-limited
- specific before broad
- optionally AI-refined only when needed

This keeps retrieval consistent enough for testing while preserving room for controlled improvement.
