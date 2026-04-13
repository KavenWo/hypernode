# Phase 2 Retrieval Bucket Policy

Short description: this file defines how retrieved snippets are grouped by purpose so reasoning, guidance, warnings, and escalation cues use different evidence pools.

## Purpose

This document defines how retrieved evidence should be grouped after search and before reasoning or guidance generation.

Phase 2 should not treat all retrieved snippets as interchangeable.
Different pieces of evidence serve different product needs.

This policy ensures the system can separate:

- escalation reasoning evidence
- immediate action evidence
- safety warning evidence
- bystander instruction evidence

That separation is necessary if the agent is going to produce clearer and safer grounded outputs.

---

## Core Principle

Retrieval should collect evidence.
Bucketing should organize evidence by purpose.
Reasoning and guidance should then draw from the right bucket for the right output field.

The system should not reuse the same raw snippet for every section unless it is clearly the best evidence for multiple roles.

---

## Why Bucketing Matters

Without bucketing:

- a general snippet may dominate a high-risk case
- reasoning may cite evidence meant for user-facing instructions
- user guidance may become too technical
- do-not-do warnings may be lost inside general first-aid content

With bucketing:

- escalation logic can use escalation evidence
- user guidance can use action evidence
- warnings can use caution evidence
- bystander steps can use role-specific evidence

---

## Bucket Vocabulary

Phase 2 uses the following controlled bucket names:

- `scene_safety`
- `red_flags_and_escalation`
- `immediate_actions`
- `do_not_do_warnings`
- `bystander_instructions`
- `cpr_or_airway_steps`
- `monitoring_and_followup`

These buckets are product-controlled and should be used in debug output and evaluation.

---

## Bucket Definitions

### `scene_safety`

Purpose:

- evidence about checking surroundings, approaching safely, and establishing a safe starting point

Typical content:

- ensure scene is safe
- check before moving closer
- assess before helping the patient stand

Primary use:

- top-of-guidance context
- helper orientation

### `red_flags_and_escalation`

Purpose:

- evidence that supports urgency, escalation, and emergency warning signs

Typical content:

- symptoms that require urgent help
- when to call emergency services
- why a condition is high risk

Primary use:

- clinical reasoning
- action recommendation
- escalation triggers

### `immediate_actions`

Purpose:

- evidence for short, practical next steps that should happen now

Typical content:

- keep the patient still
- apply pressure to bleeding
- do not attempt to stand
- observe key symptoms

Primary use:

- `primary_message`
- `immediate_steps`

### `do_not_do_warnings`

Purpose:

- evidence about unsafe actions that should be explicitly avoided

Typical content:

- do not move if spinal injury is suspected
- do not delay emergency help
- do not give unsafe assistance

Primary use:

- warnings section
- risk-reduction messaging

### `bystander_instructions`

Purpose:

- helper-oriented evidence that is specifically phrased for a nearby responder

Typical content:

- what a bystander should check
- how to assist safely
- what to report

Primary use:

- bystander-mode guidance
- question framing for helper interaction

### `cpr_or_airway_steps`

Purpose:

- evidence related to breathing assessment, airway priorities, CPR initiation, and AED use

Typical content:

- check breathing immediately
- start CPR if not breathing normally
- use an AED if available

Primary use:

- urgent instructions
- highest-priority guidance in breathing emergencies

### `monitoring_and_followup`

Purpose:

- evidence for observation, delayed warning signs, and what to watch after the immediate event

Typical content:

- monitor symptoms
- watch for worsening confusion
- seek help if symptoms develop later

Primary use:

- low-risk guidance
- delayed escalation triggers

---

## Intent-To-Bucket Mapping

The following mapping defines where evidence from each retrieval intent should usually land.

### `fall_general_first_aid`

Primary buckets:

- `immediate_actions`
- `scene_safety`

Secondary bucket:

- `monitoring_and_followup`

### `fall_red_flags`

Primary bucket:

- `red_flags_and_escalation`

Secondary bucket:

- `monitoring_and_followup`

### `bystander_check_consciousness`

Primary bucket:

- `bystander_instructions`

Secondary bucket:

- `red_flags_and_escalation`

### `bystander_check_breathing`

Primary buckets:

- `bystander_instructions`
- `cpr_or_airway_steps`

### `unconscious_after_fall`

Primary buckets:

- `red_flags_and_escalation`
- `cpr_or_airway_steps`

Secondary bucket:

- `bystander_instructions`

### `abnormal_breathing_after_fall`

Primary buckets:

- `red_flags_and_escalation`
- `cpr_or_airway_steps`

### `cpr_trigger_guidance`

Primary bucket:

- `cpr_or_airway_steps`

Secondary bucket:

- `red_flags_and_escalation`

### `head_injury_after_fall`

Primary bucket:

- `red_flags_and_escalation`

Secondary buckets:

- `immediate_actions`
- `monitoring_and_followup`

### `head_injury_blood_thinners`

Primary bucket:

- `red_flags_and_escalation`

Secondary bucket:

- `immediate_actions`

### `severe_bleeding_after_fall`

Primary buckets:

- `immediate_actions`
- `red_flags_and_escalation`

Secondary bucket:

- `do_not_do_warnings`

### `possible_spinal_injury`

Primary buckets:

- `do_not_do_warnings`
- `immediate_actions`

Secondary bucket:

- `red_flags_and_escalation`

### `fracture_or_cannot_stand`

Primary buckets:

- `immediate_actions`
- `do_not_do_warnings`

Secondary bucket:

- `red_flags_and_escalation`

### `do_not_move_possible_injury`

Primary bucket:

- `do_not_do_warnings`

Secondary bucket:

- `immediate_actions`

### `monitor_low_risk_fall`

Primary bucket:

- `monitoring_and_followup`

Secondary bucket:

- `immediate_actions`

### `bystander_instruction_mode`

Primary bucket:

- `bystander_instructions`

Secondary buckets:

- `scene_safety`
- `immediate_actions`

---

## Bucket Capacity Rules

Each bucket should keep only a small number of high-utility snippets.

Recommended Phase 2 limits:

- `scene_safety`: up to `2`
- `red_flags_and_escalation`: up to `3`
- `immediate_actions`: up to `3`
- `do_not_do_warnings`: up to `2`
- `bystander_instructions`: up to `3`
- `cpr_or_airway_steps`: up to `3`
- `monitoring_and_followup`: up to `2`

### Capacity Rule

If more snippets qualify than the bucket limit allows, the ranking policy should choose the most:

- case-specific
- actionable
- clearly worded

Do not keep extra snippets simply because they are available.

---

## Bucket Usage Rules

### Reasoning Usage

The reasoning layer should primarily use:

- `red_flags_and_escalation`
- `cpr_or_airway_steps`

Reasoning may also use:

- `do_not_do_warnings`

when movement or unsafe action risk materially affects escalation.

### Guidance Usage

The user-facing guidance layer should primarily use:

- `immediate_actions`
- `do_not_do_warnings`
- `bystander_instructions`
- `cpr_or_airway_steps`

### Low-Risk Guidance Usage

For low-risk or monitoring cases, the guidance layer should additionally use:

- `monitoring_and_followup`

### Scene Framing Usage

Use `scene_safety` sparingly.
It should support orientation, not crowd out more urgent medical guidance.

---

## Cross-Bucket Rules

### Rule 1: Avoid Duplicate Evidence Flooding

The same snippet should not be copied into many buckets unless it truly serves multiple purposes.

If reused across buckets, that should be visible in debug output.

### Rule 2: Prefer Function Over Source Order

Bucket placement should depend on what the snippet helps with, not only where it appeared in retrieval results.

### Rule 3: Specific Buckets Beat General Buckets

If a snippet clearly belongs in `cpr_or_airway_steps`, do not store it only in `immediate_actions`.

If a snippet clearly expresses a warning, do not hide it inside `fall_general_first_aid` handling.

### Rule 4: Buckets Support Output Separation

Output sections should be filled from the most appropriate buckets:

- `primary_message` from `immediate_actions` or `cpr_or_airway_steps`
- `immediate_steps` from `immediate_actions`, `bystander_instructions`, or `cpr_or_airway_steps`
- `warnings` from `do_not_do_warnings`
- `escalation_triggers` from `red_flags_and_escalation`

---

## Minimal Debug Expectations

Phase 2 debug output should show:

- which snippets entered each bucket
- which intent produced each snippet
- which bucket items were selected for final guidance
- which bucket items were discarded due to capacity or low utility

This is necessary to diagnose whether issues come from:

- retrieval quality
- bad bucket assignment
- bad ranking
- weak normalization

---

## Locked Decisions Summary

Phase 2 evidence bucketing uses:

- a fixed bucket vocabulary
- intent-to-bucket routing
- small capacity limits
- different evidence pools for reasoning and guidance
- explicit mapping from buckets to output sections

This policy is what turns retrieval from a flat snippet list into a usable grounded evidence pipeline.
