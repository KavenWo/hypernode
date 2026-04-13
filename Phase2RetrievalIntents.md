# Phase 2 Retrieval Intent Policy

Short description: this file defines how the agent chooses the most important medical retrieval intents from a normalized fall case before any query is issued.

## Purpose

This document defines how Phase 2 chooses what medical evidence to retrieve.

Phase 1 normalized the case into fixed fields such as:

- responder mode
- severity
- red flags
- risk modifiers
- action recommendation

Phase 2 uses that normalized state to decide:

- what medical question needs to be answered first
- what evidence should be retrieved now
- which retrieval goals are higher priority than others

This is the policy that shifts the agent from broad retrieval to intent-based retrieval.

---

## Core Principle

The retrieval layer should not ask:

- what fall-related information is available?

It should ask:

- what decision-critical medical guidance is needed for this exact case?

Retrieval intents are product-controlled labels that represent those decision-critical evidence needs.

The agent may infer the active intents from the case state, but it must choose from this controlled vocabulary.

---

## Phase 2 Scope

This policy defines:

- the retrieval intent vocabulary
- what each intent means
- which normalized case signals trigger each intent
- priority rules when multiple intents apply
- how many intents should be used in one retrieval run

This policy does not define:

- the exact final query strings
- snippet ranking logic
- guidance rewriting rules

Those are covered in separate Phase 2 documents.

---

## Intent Design Goals

The retrieval intent system should make evidence selection:

- clinically focused
- operationally useful
- consistent across runs
- easy to debug

Each intent should represent one stable retrieval purpose.

Good intents are:

- specific enough to guide search quality
- broad enough to be reusable across cases
- tied to a clear product need

Bad intents are:

- overly vague
- too close to raw user wording
- too narrow to generalize

---

## Intent Families

Phase 2 groups intents into five families:

- scene and triage
- airway and CPR
- injury-specific escalation
- safe immediate care
- responder-role support

These families are organizational only.
The retrieval engine still works from the controlled intent keys below.

---

## Retrieval Intent Vocabulary

### Scene And Triage Intents

#### `fall_general_first_aid`

Use when:

- a fall likely occurred
- no more specific high-priority medical intent fully covers immediate care basics

Purpose:

- retrieve baseline fall first-aid guidance
- support low-risk or mixed-information cases

Typical evidence need:

- basic immediate care
- general safety checks
- monitoring guidance

#### `fall_red_flags`

Use when:

- the case needs escalation screening
- symptoms are incomplete or mixed
- the agent needs grounded warning-sign guidance

Purpose:

- retrieve emergency warning signs after a fall
- support escalation reasoning

Typical evidence need:

- dangerous symptoms
- warning signs that require urgent help

### Airway And CPR Intents

#### `bystander_check_consciousness`

Use when:

- responder mode is `bystander`
- responsiveness is unclear

Purpose:

- retrieve simple consciousness-check instructions for a bystander

Typical evidence need:

- how to check if the patient responds
- when lack of response is concerning

#### `bystander_check_breathing`

Use when:

- responder mode is `bystander`
- breathing status is unknown or unclear

Purpose:

- retrieve simple breathing-check guidance

Typical evidence need:

- how to check breathing safely
- what abnormal breathing means operationally

#### `unconscious_after_fall`

Use when:

- `unresponsive` or `loss_of_consciousness` is present
- or consciousness is strongly suspected to be impaired

Purpose:

- retrieve immediate guidance for an unconscious patient after a fall

Typical evidence need:

- airway and breathing priorities
- emergency escalation triggers

#### `abnormal_breathing_after_fall`

Use when:

- `abnormal_breathing` is present

Purpose:

- retrieve guidance for urgent breathing concern after a fall

Typical evidence need:

- breathing danger signs
- escalation urgency
- CPR-adjacent instructions when relevant

#### `cpr_trigger_guidance`

Use when:

- `not_breathing` is present
- breathing is absent or not normal enough that CPR guidance may be needed

Purpose:

- retrieve the evidence needed to justify and guide CPR escalation

Typical evidence need:

- when to start CPR
- AED use
- emergency help urgency

### Injury-Specific Escalation Intents

#### `head_injury_after_fall`

Use when:

- `head_strike` is present
- or head injury concern exists without a stronger risk modifier

Purpose:

- retrieve grounded warning signs and immediate cautions for head injury after a fall

Typical evidence need:

- symptoms that require urgent medical evaluation
- immediate monitoring concerns

#### `head_injury_blood_thinners`

Use when:

- `head_strike` and `blood_thinner_use` are both present

Purpose:

- retrieve the highest-priority escalation evidence for head injury with anticoagulant risk

Typical evidence need:

- why this combination is high risk
- urgent escalation warning signs

#### `severe_bleeding_after_fall`

Use when:

- `severe_bleeding` is present

Purpose:

- retrieve urgent first-aid and escalation guidance for severe bleeding

Typical evidence need:

- bleeding control
- emergency escalation urgency

#### `possible_spinal_injury`

Use when:

- `suspected_spinal_injury`
- `severe_neck_pain`
- `severe_back_pain`
- or high-risk immobility pattern strongly suggests spinal concern

Purpose:

- retrieve movement restrictions and escalation guidance for possible spinal injury

Typical evidence need:

- do-not-move warnings
- neck and spine precautions

#### `fracture_or_cannot_stand`

Use when:

- `cannot_stand`
- `suspected_fracture`
- `severe_hip_pain`
- or other major weight-bearing concern is present

Purpose:

- retrieve safe handling and escalation guidance for likely fracture or inability to stand

Typical evidence need:

- movement caution
- immediate care steps
- when not to help the patient stand

### Safe Immediate Care Intents

#### `do_not_move_possible_injury`

Use when:

- movement may worsen injury
- but the more specific spinal/fracture intent is not the only priority

Purpose:

- retrieve safe immobility guidance and movement warnings

Typical evidence need:

- when to keep the patient still
- what not to do

#### `monitor_low_risk_fall`

Use when:

- severity is currently `low`
- no major emergency red flags are present
- grounded monitoring guidance is still useful

Purpose:

- retrieve appropriate observation and follow-up guidance for a lower-risk case

Typical evidence need:

- symptom monitoring
- delayed warning signs
- when to escalate later

### Responder-Role Support Intents

#### `bystander_instruction_mode`

Use when:

- responder mode is `bystander`
- guidance needs to be phrased around what the bystander should do

Purpose:

- retrieve instruction wording and action framing suitable for a helper on scene

Typical evidence need:

- concise helper actions
- short observation prompts
- safe assistance steps

---

## Trigger Rules

The intent planner should derive intents from normalized case fields, not from raw text alone.

Primary inputs:

- responder mode
- normalized red flags
- severity
- suspected risks
- protective signals
- known profile modifiers

### Trigger Precedence

Use this precedence when multiple triggers exist:

1. airway and life-threat intents
2. severe bleeding intents
3. head injury and anticoagulant intents
4. spinal or fracture movement-restriction intents
5. general red-flag intents
6. low-risk monitoring intents

This means specific high-risk intents should outrank generic fall intents.

### Trigger Examples

- `not_breathing` -> `cpr_trigger_guidance`
- `abnormal_breathing` -> `abnormal_breathing_after_fall`
- `unresponsive` -> `unconscious_after_fall`
- `head_strike` + `blood_thinner_use` -> `head_injury_blood_thinners`
- `severe_bleeding` -> `severe_bleeding_after_fall`
- `suspected_spinal_injury` -> `possible_spinal_injury`
- `cannot_stand` + `suspected_fracture` -> `fracture_or_cannot_stand`
- `bystander` mode + breathing unknown -> `bystander_check_breathing`
- low-risk case with no emergency red flags -> `monitor_low_risk_fall`

---

## Priority Policy

When multiple intents are active, the planner should rank them by:

1. life-saving urgency
2. injury worsening risk
3. action specificity
4. responder usefulness
5. general fallback value

### Priority Tiers

#### Tier 1: Immediate Life Threat

- `cpr_trigger_guidance`
- `abnormal_breathing_after_fall`
- `unconscious_after_fall`
- `severe_bleeding_after_fall`

#### Tier 2: High-Risk Escalation

- `head_injury_blood_thinners`
- `possible_spinal_injury`
- `head_injury_after_fall`

#### Tier 3: Safe Handling And Focused Care

- `fracture_or_cannot_stand`
- `do_not_move_possible_injury`
- `bystander_check_breathing`
- `bystander_check_consciousness`

#### Tier 4: Broad Triage Support

- `fall_red_flags`
- `bystander_instruction_mode`
- `fall_general_first_aid`
- `monitor_low_risk_fall`

### Priority Rule

If a Tier 1 intent is active, the planner should not spend most of the retrieval budget on Tier 4 intents.

Broad intents can still be added as support, but only after immediate needs are covered.

---

## Intent Count Limits

Phase 2 should keep retrieval focused.

Recommended limits:

- default target: `2` intents
- normal maximum: `3` intents
- emergency maximum: `4` intents only when one life-threat intent and one or more specific injury intents are both active

### Intent Selection Rule

Do not include multiple intents that answer the same question unless there is a clear reason.

For example:

- use `head_injury_blood_thinners` instead of both `head_injury_after_fall` and `fall_red_flags` if retrieval budget is tight

---

## Fallback Policy

If the planner cannot confidently select a highly specific intent:

1. include `fall_red_flags`
2. include `fall_general_first_aid`
3. include role-specific helper intents if responder mode is `bystander`

This ensures the system still retrieves broadly useful, grounded evidence without pretending to be more specific than the case allows.

---

## Audit Expectations

Every retrieval run should record:

- active normalized triggers
- selected intents
- skipped candidate intents
- final priority order
- whether fallback logic was used

This is required for Phase 2 debugging and evaluation.

---

## Locked Decisions Summary

Phase 2 retrieval intent planning uses:

- a controlled intent vocabulary
- normalized Phase 1 fields as inputs
- deterministic priority tiers
- a small retrieval budget
- specific intents before broad intents
- explicit fallback behavior

The main design goal is to retrieve the most decision-relevant evidence first, not the most generic fall content.
