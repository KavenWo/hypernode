# Phase 3 Schema Evolution Plan

## Purpose

This document proposes how the current Phase 1 response schema should evolve to support stronger reasoning in Phase 3.

The main issue is that the current schema is still too single-action-oriented.

That means it can express:

- the chosen severity
- one main action

But it still struggles to express a more realistic emergency response such as:

- dispatching emergency help
- notifying family
- instructing a bystander to check breathing
- telling someone to apply pressure to bleeding
- continuing monitoring while responders are on the way

These are not really one action.
They are multiple coordinated operational tracks.

---

## Core Problem

The current Phase 1 model assumes the response can be compressed into:

- one `recommended_action`

This becomes limiting when:

- explicit danger signs require immediate dispatch
- a bystander also needs instructions
- family should also be notified
- monitoring actions should continue after escalation
- uncertainty should influence some tracks but not block others

So the response needs to become multi-action, not single-action.

---

## Design Principle

The future schema should separate:

- what the system is escalating
- who the system is notifying
- what nearby people should do
- what follow-up monitoring should continue

This means Phase 3 should move from:

- one action label

to:

- multiple action tracks with clear responsibilities

---

## Proposed Schema Direction

## Current Phase 1 Shape

Today the action area is roughly:

```json
{
  "action": {
    "recommended": "dispatch_pending_confirmation",
    "requires_confirmation": true,
    "cancel_allowed": true,
    "countdown_seconds": 30
  }
}
```

This is still useful as a temporary v1 contract, but it is too narrow.

---

## Proposed Phase 3 Shape

The schema should evolve toward something like:

```json
{
  "response_plan": {
    "escalation_action": {
      "type": "emergency_dispatch",
      "requires_confirmation": false,
      "cancel_allowed": false,
      "reason": "Explicit life-threatening red flags present."
    },
    "notification_actions": [
      {
        "type": "inform_family",
        "priority": "secondary"
      }
    ],
    "bystander_actions": [
      {
        "type": "check_breathing",
        "priority": "immediate"
      },
      {
        "type": "start_cpr_guidance",
        "priority": "immediate"
      }
    ],
    "followup_actions": [
      {
        "type": "monitor_until_responders_arrive",
        "priority": "ongoing"
      }
    ]
  }
}
```

This gives the agent a more realistic operational structure.

---

## Recommended Multi-Action Tracks

Phase 3 should split actions into four tracks.

## 1. Escalation Action

This is the main emergency routing decision.

Suggested values:

- `none`
- `dispatch_pending_confirmation`
- `emergency_dispatch`

Questions this track answers:

- should emergency services be escalated?
- should escalation wait for a short confirmation window?
- should escalation happen immediately?

---

## 2. Notification Actions

This covers who else should be informed.

Suggested values:

- `inform_family`
- `inform_emergency_contact`
- `inform_caregiver`

Questions this track answers:

- should family be informed?
- should a caregiver be notified?

This track should not block emergency escalation.

---

## 3. Bystander Actions

This covers what nearby helpers should do immediately.

Suggested values:

- `check_consciousness`
- `check_breathing`
- `apply_pressure_to_bleeding`
- `keep_patient_still`
- `do_not_move_patient`
- `start_cpr_guidance`
- `retrieve_aed_if_available`

Questions this track answers:

- what should the bystander do right now?
- what must happen before responders arrive?

This is especially important because bystander instructions are not just “extra text.”
They are part of the operational response.

---

## 4. Follow-Up Actions

This covers ongoing behavior after the initial decision.

Suggested values:

- `monitor_for_worsening_signs`
- `stay_on_scene`
- `wait_for_responders`
- `continue_reassessment`

Questions this track answers:

- what should continue after the first action?
- what should the system keep reminding the user or bystander to do?

---

## Why This Is Better

This structure handles your concern directly.

### Example 1: Unresponsive Patient

The system may need to do all of these at once:

- escalation: `emergency_dispatch`
- bystander: `check_breathing`
- bystander: `start_cpr_guidance`
- follow-up: `wait_for_responders`

That is much more realistic than one label.

### Example 2: Head Strike On Blood Thinners

The system may need:

- escalation: `dispatch_pending_confirmation`
- notification: `inform_family`
- bystander: `keep_patient_still`
- follow-up: `monitor_for_confusion_or_vomiting`

Again, one label cannot express this cleanly.

---

## Phase 1 To Phase 3 Migration Strategy

This should be an additive transition, not a destructive rewrite.

## Step 1. Keep Phase 1 Action For Compatibility

Continue supporting:

- `action.recommended`

for compatibility with current testing and MVP flows.

## Step 2. Add New Multi-Action Section

Introduce a new section such as:

- `response_plan`

or

- `operational_actions`

without immediately removing the old field.

## Step 3. Derive Old Action From New Structure

Let the legacy single action become a simplified summary of the richer response plan.

Example:

- if escalation action is `emergency_dispatch`, then old `recommended_action` can still be `emergency_dispatch`

This avoids breaking current consumers too early.

## Step 4. Shift Testing To The New Structure

Once the team is ready, prioritize reviewing:

- escalation action
- notification actions
- bystander actions
- follow-up actions

over the single action field.

---

## Proposed Phase 3 Schema Additions

To prepare the reasoning output, these are the most useful additions.

## A. `response_plan`

Top-level structured response action plan.

## B. `hard_emergency_triggered`

Boolean:

- whether explicit life-threatening red flags override uncertainty

This helps debug why the system did not wait for more confirmation.

## C. `blocking_uncertainties`

This should only include unknowns that are still preventing a stronger action.

Examples:

- dispatch pending because responsiveness could not be confirmed

If hard emergency triggers exist, this should not block escalation.

## D. `override_policy`

This can explain whether:

- waiting is safe
- confirmation is optional
- uncertainty has been overridden by danger signs

---

## Policy Rules For The New Structure

These rules should guide the future action model.

1. Explicit life-threatening red flags can trigger immediate escalation even with incomplete information.
2. Uncertainty should not block emergency dispatch when waiting is riskier than acting.
3. Notification actions should be independent of escalation actions.
4. Bystander actions should be treated as operational output, not decorative guidance.
5. Follow-up actions should continue after the main decision.

---

## Suggested Implementation Order

To avoid clashing with teammate-owned system logic, this can be done as an AI-side planning and testing sequence first.

1. Define the multi-action schema draft.
2. Define action track vocabularies.
3. Define hard emergency trigger rules.
4. Define uncertainty override rules.
5. Define how old single-action fields map from the new structure.
6. Create a scenario pack that tests the multi-action response model.

---

## What You Should Personally Own

As the AI lead, these are the highest-value ownership areas:

- multi-action schema design
- escalation vs notification split
- bystander action vocabulary
- uncertainty override rules
- hard emergency trigger rules
- scenario review for multi-action outputs

These are core reasoning-output design decisions.

---

## Risks To Watch

- the new structure becomes too large too early
- bystander actions duplicate guidance text without adding structure
- uncertainty still blocks emergency dispatch too often
- escalation and notification logic remain entangled
- old and new action structures drift apart

---

## Definition Of Done

This schema evolution planning is ready when:

- the team agrees that one action label is not enough
- the new action tracks are clearly named
- hard emergency triggers are explicitly defined
- uncertainty override behavior is defined
- a migration path from Phase 1 schema to Phase 3 schema exists

---

## Recommended Immediate Next Step

The best next step is:

- define the multi-action response structure in detail

Specifically:

- `escalation_action`
- `notification_actions`
- `bystander_actions`
- `followup_actions`

That will give Phase 3 a much more realistic reasoning output model.
