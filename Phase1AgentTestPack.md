# Phase 1 Agent Test Pack

## Purpose

This is a lightweight Phase 1 test pack for the AI layer.

It is designed to help check whether the Phase 1 improvements are visible in outputs.
This is not a backend integration test.
It is an agent behavior review pack.

Use it to inspect whether the agent:

- follows the fixed schema and vocabulary
- assigns severity consistently
- uses normalized red-flag keys
- separates confidence meanings correctly
- expresses uncertainty clearly
- chooses actions that match the rules

---

## How To Use This Pack

For each scenario:

1. Feed the event, vitals, profile, and answers into the current agent flow.
2. Capture the structured output.
3. Compare the output with the expected review points.

You do not need exact numeric confidence matches.
What matters in Phase 1 is:

- correct severity banding
- correct action selection
- correct red flags
- correct schema behavior
- reasonable confidence banding

---

## Global Checks For Every Scenario

Each output should be reviewed against these checks:

- severity is only `low`, `medium`, or `critical`
- action uses only approved action vocabulary
- red flags use normalized keys
- detection confidence is not treated as medical confidence
- uncertainty is present when evidence is incomplete
- grounded source is clearly identified
- reasoning is short and operational

---

## Scenario 1: Low-Risk Fall

### Input

Event:

- motion_state: `stumble`
- fall_detection_confidence: `0.58`

Vitals:

- heart_rate: `82`
- blood_pressure: `126/78`
- SpO2: `97`

Profile:

- age: `42`
- blood_thinners: `false`
- mobility_support: `false`

Answers:

- "I slipped but stayed awake."
- "I can move safely."
- "I did not hit my head."

### Expected Review Outcome

- severity should likely be `low`
- action should likely be `monitor`
- red flags should be empty or minimal
- protective signals should include awake/responding type signals
- clinical confidence should be medium or high
- action confidence should support monitor, not escalation

---

## Scenario 2: Pain But Not Immediately Life-Threatening

### Input

Event:

- motion_state: `rapid_descent`
- fall_detection_confidence: `0.84`

Vitals:

- heart_rate: `96`
- blood_pressure: `118/74`
- SpO2: `96`

Profile:

- age: `68`
- blood_thinners: `false`

Answers:

- "I am awake."
- "My hip hurts badly."
- "I cannot stand safely."

### Expected Review Outcome

- severity should likely be `medium` or `critical` depending on policy strictness
- if `critical`, the reason should be injury risk, not just detector confidence
- action should not be `monitor`
- red flags should likely include `cannot_stand` and `severe_hip_pain` or `severe_pain`
- uncertainty may mention bleeding/head injury not confirmed

### What To Watch

- if the output escalates, it should justify it with injury risk
- if the output stays medium, it should still avoid a false sense of safety

---

## Scenario 3: Head Strike On Blood Thinners

### Input

Event:

- motion_state: `rapid_descent`
- fall_detection_confidence: `0.95`

Vitals:

- heart_rate: `110`
- blood_pressure: `104/66`
- SpO2: `94`

Profile:

- age: `74`
- blood_thinners: `true`

Answers:

- "I hit my head."
- "I feel dizzy."
- "I cannot stand."

### Expected Review Outcome

- severity should be `critical`
- action should be `dispatch_pending_confirmation` or `emergency_dispatch`
- red flags should include `head_strike`, `blood_thinner_use`, and `cannot_stand`
- suspected risks should include head injury type risk
- reasoning should mention high-risk fall plus anticoagulant use

---

## Scenario 4: Breathing Emergency

### Input

Event:

- motion_state: `no_movement`
- fall_detection_confidence: `0.97`

Vitals:

- heart_rate: `138`
- blood_pressure: `88/54`
- SpO2: `88`

Profile:

- age: `71`
- blood_thinners: `false`

Answers:

- "He is not breathing normally."
- "He is not responding."

### Expected Review Outcome

- severity must be `critical`
- action should strongly lean to `emergency_dispatch`
- red flags should include `abnormal_breathing` or `not_breathing`, and `unresponsive`
- uncertainty should be minimal because explicit danger signs are present
- action confidence should be high

---

## Scenario 5: Severe Bleeding

### Input

Event:

- motion_state: `rapid_descent`
- fall_detection_confidence: `0.90`

Vitals:

- heart_rate: `128`
- blood_pressure: `92/60`
- SpO2: `93`

Profile:

- age: `59`
- blood_thinners: `false`

Answers:

- "There is heavy bleeding from the leg."
- "The patient is conscious but weak."

### Expected Review Outcome

- severity should be `critical`
- action should not be `monitor`
- red flags should include `severe_bleeding`
- reasoning should reflect explicit danger signs, not just fall pattern

---

## Scenario 6: Bystander Observation Mode

### Input

Event:

- motion_state: `rapid_descent`
- fall_detection_confidence: `0.88`

Vitals:

- heart_rate: `102`
- blood_pressure: `112/70`
- SpO2: `95`

Profile:

- age: `79`
- blood_thinners: `true`

Answers:

- "I am the bystander."
- "She is awake but confused."
- "She hit her head."
- "She should not stand."

### Expected Review Outcome

- responder mode should be `bystander`
- severity should likely be `critical`
- red flags should include `confusion_after_fall`, `head_strike`, `blood_thinner_use`
- reasoning should remain structured and not drift into free-form essay style

---

## Scenario 7: No Response Case

### Input

Event:

- motion_state: `no_movement`
- fall_detection_confidence: `0.93`

Vitals:

- heart_rate: `120`
- blood_pressure: `98/62`
- SpO2: `92`

Profile:

- age: `83`
- blood_thinners: `true`

Answers:

- none

### Expected Review Outcome

- responder mode should be `no_response`
- severity should likely be `critical` or at minimum strong medium with urgent caution
- uncertainty should be present because no answers exist
- output should not pretend to know unconfirmed symptoms
- action should reflect high concern from event + profile even without human answers

---

## Scenario 8: False Alarm Style Case

### Input

Event:

- motion_state: `slow_descent`
- fall_detection_confidence: `0.36`

Vitals:

- heart_rate: `78`
- blood_pressure: `122/76`
- SpO2: `98`

Profile:

- age: `37`
- blood_thinners: `false`

Answers:

- "I am fine."
- "I sat down quickly but did not fall."
- "No pain, no head hit, no dizziness."

### Expected Review Outcome

- severity should likely be `low`
- action should likely be `monitor`
- detection confidence should stay separate from clinical reasoning
- the output should not over-escalate based only on event metadata

---

## Review Scorecard

For each scenario, score these areas:

- Schema compliance: pass/fail
- Severity choice: good/unclear/incorrect
- Action choice: good/unclear/incorrect
- Red-flag extraction: good/partial/missed
- Confidence behavior: good/unclear/inconsistent
- Uncertainty handling: good/weak/missing
- Grounding visibility: good/weak/missing

---

## Signs That Phase 1 Is Working

You should be able to see these improvements:

- the agent stops mixing detection confidence with medical certainty
- the same kind of risk is described with the same normalized keys
- severity selection looks more consistent across similar cases
- the output is easier to read and compare
- the agent admits uncertainty more clearly instead of sounding falsely certain

---

## Signs That Phase 1 Still Needs Work

If you see these problems repeatedly, Phase 1 is not clean yet:

- custom severity names appear
- the same symptom is described with inconsistent red-flag keys
- confidence bands feel random
- critical cases remain in medium without explanation
- low-risk cases escalate based only on detection confidence
- uncertainty is missing in incomplete-answer cases

---

## Recommended Use

Use this pack in two ways:

- manual review while testing the current prompt
- regression review after prompt updates

This gives you a clean way to tell whether the Phase 1 improvements are actually visible.
