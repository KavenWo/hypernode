# Phase 3 Closeout Summary

Short description: this file summarizes what Phase 3 improved in the reasoning and action-execution layers, what was added to the MVP, and what remains for later iterations.

## Phase 3 Goal

Phase 3 was about improving the reasoning pipeline itself.

Phase 1 gave us a stable contract.
Phase 2 made retrieval and grounding more deliberate.
Phase 3 focused on making the system interpret evidence more clearly, handle uncertainty more deliberately, and produce more realistic operational output.

The main objective was to improve:

- signal extraction
- missing-fact handling
- severity reasoning
- action reasoning
- uncertainty override behavior
- debug visibility for reasoning decisions
- multi-action execution planning

This phase was mainly about making the decision layer more structured and inspectable.

---

## What We Locked In

### 1. Structured Signal Extraction

We added a dedicated Phase 3 reasoning helper in the backend:

- `backend/agents/reasoning/phase3_reasoning.py`

This means raw answers are no longer treated as one broad text blob before all reasoning happens.

The system now extracts structured reasoning features such as:

- `red_flags`
- `protective_signals`
- `suspected_risks`
- `vulnerability_modifiers`
- `missing_facts`
- `contradictions`
- `uncertainty`

This matters because reasoning becomes less dependent on one broad prompt step.

---

### 2. Missing-Fact Priority Logic

Phase 3 now explicitly identifies which missing fact matters most.

Examples include:

- `breathing_status_unconfirmed`
- `bleeding_status_unconfirmed`
- `responsiveness_unconfirmed`
- `head_strike_unconfirmed`

The system can now expose:

- the list of missing facts
- the single highest-priority missing fact
- whether that uncertainty is still blocking stronger action

This matters because uncertainty is no longer just wording.
It now affects execution behavior more directly.

---

### 3. Staged Severity And Action Reasoning

We separated severity reasoning from action reasoning more clearly.

The staged reasoning flow now works more like:

1. extract structured signals
2. review missing facts and contradictions
3. choose severity
4. choose escalation behavior
5. build the operational response plan

This matters because:

- `critical` does not automatically mean one specific action
- missing information can lower confidence without always blocking escalation
- action logic is easier to inspect and improve

---

### 4. Uncertainty Override Behavior

Phase 3 now treats explicit danger signs as override-capable signals instead of letting missing facts block action too easily.

That means the system can now expose:

- `hard_emergency_triggered`
- `blocking_uncertainties`
- `override_policy`

This matters because the system can now explain when:

- uncertainty still blocks a stronger action
- uncertainty only lowers confidence
- explicit danger signs override uncertainty and trigger immediate escalation

This is especially important for cases such as:

- unconscious after a fall
- abnormal breathing
- not breathing
- severe bleeding

---

### 5. Multi-Action Response Plan

Phase 3 evolved the output beyond one single action label.

We added a structured response plan that can express multiple coordinated operational tracks:

- `escalation_action`
- `notification_actions`
- `bystander_actions`
- `followup_actions`

This means the system can now represent more realistic behavior such as:

- dispatching emergency help
- informing family
- instructing a bystander to check breathing
- keeping the patient still
- continuing monitoring until responders arrive

This matters because emergency response is not really one action.

---

### 6. Legacy Compatibility Preserved

Even though Phase 3 added the richer response plan, we kept the earlier MVP action contract for compatibility:

- `action.recommended`
- `requires_confirmation`
- `cancel_allowed`
- `countdown_seconds`

The old single-action view is now effectively a simplified summary of the richer Phase 3 response plan.

This matters because the MVP and existing flows can continue working while the new structure is introduced gradually.

---

### 7. Phase 3 Policy Asset

We added a machine-readable Phase 3 policy asset in the backend:

- `backend/data/phase3_reasoning_policy.json`

This means the Phase 3 reasoning behavior is no longer only implied by code or `.md` notes.

The backend can now reference a structured policy for:

- signal outputs
- missing-fact priority
- action tracks
- uncertainty behavior
- debug trace expectations

---

### 8. Phase 3 Scenario Pack

We added a focused Phase 3 scenario pack for reasoning evaluation:

- `backend/data/phase3_test_scenarios.json`

This allows the MVP to quickly test reasoning-focused cases such as:

- explicit airway emergencies
- critical but still uncertainty-heavy cases
- conflicting-signal cases

This matters because Phase 3 needed a faster loop for testing judgment quality, not only retrieval quality.

---

### 9. MVP Debug Visibility For Phase 3

We extended the MVP backend and frontend so the new reasoning structure can be inspected during testing.

The MVP now shows:

- missing facts
- contradictions
- vulnerability modifiers
- hard emergency override state
- blocking uncertainties
- override policy
- reasoning trace
- multi-track response plan

This makes the MVP much more useful for comparing why the system escalated, delayed, or chose additional operational actions.

---

## How Phase 2 And Phase 3 Now Work Together

Phase 2 and Phase 3 now play different but complementary roles.

### Phase 2

Phase 2 is still the grounded evidence layer.

It is responsible for:

- retrieval intent selection
- controlled query construction
- bucket-aware retrieval
- grounded guidance snippets
- bucket-specific references and sources

### Phase 3

Phase 3 is now the structured reasoning and execution layer.

It is responsible for:

- normalizing signals from answers and profile data
- deciding which uncertainty matters most
- selecting severity
- deciding whether uncertainty blocks or is overridden
- building the response plan
- exposing the reasoning trace

### Combined Flow

The current MVP flow now works like this:

1. Phase 2 retrieves focused grounded evidence using intents and bucket-aware queries.
2. Phase 3 uses the event, vitals, answers, profile, and grounded evidence context to perform staged reasoning.
3. The MVP returns both:
   - retrieval debug information from Phase 2
   - reasoning and response-plan debug information from Phase 3

This is important because the system is now less like one broad AI judgment and more like:

- evidence retrieval first
- structured reasoning second
- operational planning after that

---

## What Improved Compared To Before

Before Phase 3:

- raw answers fed more directly into one broader reasoning step
- missing information was less explicit
- severity and action were more tightly coupled
- uncertainty was often descriptive rather than behavior-changing
- the MVP had less visibility into why the system chose a decision
- one action label tried to compress too much operational meaning

After Phase 3:

- answers are normalized into structured signals
- missing facts are surfaced explicitly
- severity and action are more clearly separated
- uncertainty can either block or be overridden depending on danger signs
- the system can produce a multi-track response plan
- reasoning decisions are easier to inspect in the MVP
- explicit emergencies can trigger faster escalation even with incomplete information

---

## What Phase 3 Did Not Try To Finish

These are intentionally left for later work:

- a full multi-round reasoning loop with repeated follow-up questions
- conversation-state orchestration across multiple reasoning passes
- timeout-aware escalation after failed confirmation attempts
- production calibration for action vocabularies across live model outputs
- stronger normalization of live model-generated action labels into a stricter fixed execution vocabulary
- final production integration of richer multi-action behavior with downstream execution systems

Phase 3 is complete when reasoning is more structured, uncertainty is more behavior-aware, and the MVP can inspect the new execution model.
It is not yet the final multi-round orchestration system.

---

## Definition Of Done For Phase 3

Phase 3 should be considered complete if these are true:

- raw answers are converted into structured signals more reliably
- severity reasoning is more consistent
- uncertainty changes behavior instead of only wording
- explicit danger signs can override uncertainty when necessary
- the system can express multi-track operational actions
- the MVP can inspect the Phase 3 reasoning trace and response plan
- a Phase 3 scenario pack can expose reasoning weaknesses clearly

---

## Verification Completed

Phase 3 verification included:

- backend compile checks for the updated reasoning and schema modules
- local smoke verification for the Phase 3 reasoning helper
- API verification for the MVP route and Phase 3 scenario route
- frontend production build verification for the updated MVP tester

Local MVP/API verification also showed that:

- the new `response_plan` is returned alongside the legacy action summary
- explicit danger signs can trigger immediate `emergency_dispatch`
- blocking uncertainty is now visible separately from general uncertainty
- when Vertex AI Search is available, Phase 2 grounding can support the Phase 3 reasoning and override logic

---

## Recommended Next Step

The best next step after Phase 3 is not another one-pass reasoning tweak.

The best next step is:

- design a multi-round reasoning and follow-up loop
- let the system ask or request one more critical fact when uncertainty truly matters
- define timeout and no-response escalation rules
- tighten the operational action vocabulary for more consistent live outputs
- evaluate how the richer response plan should integrate with downstream backend and frontend execution logic

That is how we move from a stronger one-pass reasoning pipeline to a more adaptive emergency-response orchestration flow.
