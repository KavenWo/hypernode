# Phase 3 Multi-Action Spec

## Purpose

This document turns the Phase 3 multi-action idea into a concrete response design.

The goal is to make the agent capable of returning a realistic operational plan instead of one single action label.

This spec is designed to be:

- agent-first
- implementation-ready
- compatible with the current Phase 1 contract
- safe to evaluate before full backend adoption

---

## Why Multi-Action Is Needed

A real emergency response usually involves more than one action at the same time.

Examples:

- dispatch ambulance
- tell bystander to check breathing
- tell someone to apply pressure to bleeding
- notify family
- continue monitoring until responders arrive

If the agent only returns one `recommended_action`, it loses too much operational detail.

So the response must support multiple coordinated action tracks.

---

## Design Goals

The multi-action model should:

- preserve a clear primary escalation decision
- support multiple secondary actions
- distinguish scene actions from notification actions
- allow uncertainty to block some actions without blocking all actions
- allow explicit danger signs to override uncertainty
- remain compatible with the current single-action Phase 1 contract

---

## Top-Level Structure

The future response should include a new section:

```json
{
  "response_plan": {
    "escalation_action": {},
    "notification_actions": [],
    "bystander_actions": [],
    "followup_actions": []
  }
}
```

This should exist in addition to the current Phase 1 single action during migration.

---

## Response Plan Tracks

## 1. `escalation_action`

This is the main emergency escalation decision.

This track answers:

- do we escalate emergency services?
- do we wait for a short confirmation?
- do we escalate immediately?

### Proposed Shape

```json
{
  "type": "dispatch_pending_confirmation",
  "priority": "primary",
  "requires_confirmation": true,
  "cancel_allowed": true,
  "countdown_seconds": 30,
  "hard_emergency_triggered": false,
  "reason": "High-risk fall with strong injury concern."
}
```

### Allowed `type` Values

- `none`
- `dispatch_pending_confirmation`
- `emergency_dispatch`

### Allowed `priority` Values

- `primary`

### Required Fields

- `type`
- `priority`
- `requires_confirmation`
- `cancel_allowed`
- `hard_emergency_triggered`
- `reason`

### Optional Fields

- `countdown_seconds`

### Rules

- `none` means no emergency escalation action is being taken
- `dispatch_pending_confirmation` means escalation is likely appropriate, but a short confirmation window is still allowed
- `emergency_dispatch` means emergency escalation should happen immediately
- if `hard_emergency_triggered` is true, uncertainty should not keep this track at pending confirmation unless there is a very explicit policy reason

---

## 2. `notification_actions`

This covers who should be informed outside of emergency dispatch.

This track answers:

- who else should be notified?
- which notifications are immediate versus secondary?

### Proposed Shape

```json
{
  "type": "inform_family",
  "priority": "secondary",
  "reason": "Family should be aware of a critical fall and possible escalation."
}
```

### Allowed `type` Values

- `inform_family`
- `inform_emergency_contact`
- `inform_caregiver`

### Allowed `priority` Values

- `immediate`
- `secondary`

### Required Fields

- `type`
- `priority`
- `reason`

### Rules

- notification actions do not replace escalation actions
- notification actions should not delay emergency dispatch
- multiple notification actions can exist together
- if no notification is needed, return an empty list

---

## 3. `bystander_actions`

This covers what nearby people should do right now.

This track answers:

- what must a bystander do immediately?
- what scene-level action helps before responders arrive?

### Proposed Shape

```json
{
  "type": "check_breathing",
  "priority": "immediate",
  "reason": "Responsiveness is poor and breathing status is critical to determine."
}
```

### Allowed `type` Values

- `check_consciousness`
- `check_breathing`
- `apply_pressure_to_bleeding`
- `keep_patient_still`
- `do_not_move_patient`
- `start_cpr_guidance`
- `retrieve_aed_if_available`
- `clear_immediate_danger`
- `stay_with_patient`

### Allowed `priority` Values

- `immediate`
- `urgent`
- `secondary`

### Required Fields

- `type`
- `priority`
- `reason`

### Rules

- bystander actions are operational, not decorative
- bystander actions should reflect the current responder mode and scene condition
- bystander actions can exist even when escalation is `none`
- if the system is in `no_response` mode and no bystander is confirmed, return only actions that still make sense as generic scene guidance

---

## 4. `followup_actions`

This covers ongoing actions after the first response.

This track answers:

- what should continue after the initial response?
- what should the system keep telling the user or bystander to do?

### Proposed Shape

```json
{
  "type": "wait_for_responders",
  "priority": "ongoing",
  "reason": "Emergency escalation has started and the scene must remain monitored."
}
```

### Allowed `type` Values

- `monitor_for_worsening_signs`
- `stay_on_scene`
- `wait_for_responders`
- `continue_reassessment`
- `monitor_until_help_arrives`

### Allowed `priority` Values

- `ongoing`
- `secondary`

### Required Fields

- `type`
- `priority`
- `reason`

### Rules

- follow-up actions should complement, not replace, bystander or escalation actions
- follow-up actions are especially useful when the case is already escalated or still under observation

---

## Hard Emergency Trigger Rules

Some red flags should override uncertainty and move the escalation track toward immediate dispatch.

### Hard Emergency Trigger Red Flags

- `unresponsive`
- `not_breathing`
- `abnormal_breathing`
- `severe_bleeding`
- `chest_pain`
- `seizure_activity`

### Hard Trigger Rule

If one or more hard emergency trigger red flags are present, the agent should strongly prefer:

- `escalation_action.type = emergency_dispatch`

unless there is a very explicit reason why dispatch cannot yet be immediate.

### Consequence

When `hard_emergency_triggered = true`:

- uncertainty should not be used as a reason to wait for more confirmation
- bystander actions should focus on immediate life-saving response

---

## Blocking Uncertainty Rules

Not all uncertainty should block escalation.

The agent should separate:

- normal uncertainty
- blocking uncertainty

### `blocking_uncertainties`

These are unknowns that genuinely prevent a stronger action.

Examples:

- unclear whether there was head strike
- unclear whether the patient can stand
- unclear whether anyone is available to confirm symptoms

### Rule

If hard emergency triggers are present, `blocking_uncertainties` should usually be empty or non-blocking.

If the case is concerning but not explicitly life-threatening, blocking uncertainties may justify:

- `dispatch_pending_confirmation`
- additional bystander checks
- continued reassessment

---

## Override Policy

The response should explain how uncertainty interacts with emergency triggers.

### Proposed Shape

```json
{
  "blocking_uncertainties": [
    "Head strike not fully confirmed"
  ],
  "override_policy": {
    "waiting_is_safe": false,
    "danger_overrides_uncertainty": true,
    "reason": "Breathing abnormality is an explicit life-threatening signal."
  }
}
```

### Required Fields

- `waiting_is_safe`
- `danger_overrides_uncertainty`
- `reason`

### Rule

- if `danger_overrides_uncertainty = true`, escalation should not stay blocked
- if `waiting_is_safe = true`, pending confirmation may be acceptable

---

## Compatibility With Phase 1

During migration, the current Phase 1 field should remain:

```json
{
  "action": {
    "recommended": "dispatch_pending_confirmation"
  }
}
```

### Mapping Rule

Derive the old action field from the new escalation action.

Example:

- if `escalation_action.type = none` and notification exists, old action can still be `contact_family`
- if `escalation_action.type = dispatch_pending_confirmation`, old action becomes `dispatch_pending_confirmation`
- if `escalation_action.type = emergency_dispatch`, old action becomes `emergency_dispatch`

This allows current consumers to continue functioning while the richer response plan is introduced.

---

## Example Output 1: Head Strike On Blood Thinners

```json
{
  "response_plan": {
    "escalation_action": {
      "type": "dispatch_pending_confirmation",
      "priority": "primary",
      "requires_confirmation": true,
      "cancel_allowed": true,
      "countdown_seconds": 30,
      "hard_emergency_triggered": false,
      "reason": "Head injury concern on blood thinners with inability to stand."
    },
    "notification_actions": [
      {
        "type": "inform_family",
        "priority": "secondary",
        "reason": "Family should be aware of possible emergency escalation."
      }
    ],
    "bystander_actions": [
      {
        "type": "do_not_move_patient",
        "priority": "immediate",
        "reason": "Head or spinal injury cannot be ruled out."
      },
      {
        "type": "stay_with_patient",
        "priority": "urgent",
        "reason": "The patient may worsen while waiting for help."
      }
    ],
    "followup_actions": [
      {
        "type": "monitor_for_worsening_signs",
        "priority": "ongoing",
        "reason": "Watch for confusion, vomiting, or breathing changes."
      }
    ]
  }
}
```

---

## Example Output 2: Unresponsive With Abnormal Breathing

```json
{
  "response_plan": {
    "escalation_action": {
      "type": "emergency_dispatch",
      "priority": "primary",
      "requires_confirmation": false,
      "cancel_allowed": false,
      "hard_emergency_triggered": true,
      "reason": "Unresponsiveness and abnormal breathing are explicit life-threatening signals."
    },
    "notification_actions": [
      {
        "type": "inform_emergency_contact",
        "priority": "secondary",
        "reason": "Emergency contact should be informed while responders are en route."
      }
    ],
    "bystander_actions": [
      {
        "type": "check_breathing",
        "priority": "immediate",
        "reason": "Breathing status is critical and must be reassessed immediately."
      },
      {
        "type": "start_cpr_guidance",
        "priority": "immediate",
        "reason": "If not breathing normally, CPR should begin without delay."
      },
      {
        "type": "retrieve_aed_if_available",
        "priority": "urgent",
        "reason": "AED support may be needed during resuscitation."
      }
    ],
    "followup_actions": [
      {
        "type": "wait_for_responders",
        "priority": "ongoing",
        "reason": "Continue support until emergency responders arrive."
      }
    ]
  }
}
```

---

## Review Questions For This Model

When evaluating the multi-action response, ask:

- is the escalation track correct?
- are notification actions independent and sensible?
- do bystander actions reflect the actual scene need?
- do follow-up actions continue the response logically?
- did uncertainty block the wrong thing?
- did hard emergency triggers override uncertainty when they should?

---

## Suggested Implementation Order

1. Lock allowed values for all four action tracks.
2. Lock hard emergency trigger rules.
3. Lock blocking uncertainty rules.
4. Lock compatibility mapping to the old single action field.
5. Build a multi-action test pack.
6. Use the pack to review prompt outputs before any wider integration.

---

## Definition Of Done

This multi-action spec is ready when:

- each action track has a clear purpose
- each track has approved allowed values
- emergency override behavior is explicit
- uncertainty behavior is explicit
- compatibility with the old action field is defined
- example outputs feel realistic for emergency use
