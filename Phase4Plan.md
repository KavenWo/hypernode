# Phase 4 Plan

## Phase 4 Goal

Phase 4 is about redesigning the responder-facing interaction loop.

Phase 3 improved structured reasoning.
Phase 4 should improve how the system communicates with the person on scene.

The main objective is to move the MVP from:

- one generic question flow

to:

- patient-first interaction
- bystander-capable action guidance
- no-response handling
- role-aware communication
- selective reasoning refresh instead of re-running reasoning on every message

This phase should be implemented text-first in the MVP, but structured so it can later plug into Gemini 3.1 Flash Live with minimal backend redesign.

---

## Product Direction For This Phase

The MVP should prioritize communication quality first.

That means:

- improve the frontend interaction flow for patient and bystander communication
- add a dedicated communication-oriented agent or policy layer
- treat the reasoning agent as the safety and decision engine, not the only conversational layer
- support text-first testing now
- preserve a clean migration path to live voice mode later

The immediate hackathon goal is not full live-AI production readiness.
The goal is to prove that the system can guide a realistic emergency conversation more clearly and more adaptively than the current triage-question flow.

---

## Core Principles

### 1. Patient First By Default

Every new incident should begin by addressing the patient first when possible.

Examples:

- "Are you okay?"
- "Can you hear me?"
- "Are you able to answer?"

This matters because the system should not prematurely assume the bystander is the main responder if the patient is still capable of self-report.

### 2. Bystander Takes Over When Action Is Needed

If:

- the patient is not responding
- the patient is confused or unable to help
- the situation becomes obviously serious
- hands-on action is required

then the communication focus should shift toward the bystander.

This shift should feel intentional and visible in both backend logic and frontend behavior.

### 3. Text First, Live Ready

The MVP should support a high-quality text-based communication flow first.

But the architecture should already assume that a future transport may be:

- text chat
- live audio
- mixed text plus live

This means Phase 4 should define interaction state, events, and guidance outputs in a transport-neutral way.

### 4. Reasoning Should Be Triggered Selectively

Not every communication turn should call the reasoning agent.

Reasoning should refresh when:

- a critical new fact appears
- a contradiction appears
- the responder role changes
- a no-response timeout is hit
- escalation eligibility changes

Reasoning should usually not refresh when:

- the system is continuing already-approved step-by-step guidance
- the user gives a non-informative acknowledgement
- the interaction is simply progressing through an execution script such as CPR guidance

This is important for speed, cost, and flow quality.

---

## Main Problem Before Phase 4

Before this phase, the MVP still behaves too much like:

- a short triage questionnaire
- one user talking to one backend pass
- one reasoning execution after answer collection

But real incidents are messier.

They often involve:

- a patient who may still answer briefly
- a bystander who can observe and act
- a responder switch mid-incident
- repeated updates while guidance is already underway
- silence or partial responses

The system should behave more like an interaction controller than a static questionnaire.

---

## Phase 4 Scope

Phase 4 should now focus on:

- patient-first opening flow
- responder-role detection and switching
- dedicated communication-agent policy for patient and bystander interactions
- bystander action-guidance flow for text MVP testing
- no-response escalation logic
- selective reasoning refresh policy
- role-aware instruction formatting
- frontend interaction changes that make text and live modes easy to compare
- a future-ready text/live transport toggle for MVP demos

---

## Updated Workstreams

## 1. Interaction State Model

Define a backend interaction state that exists separately from one-shot reasoning output.

Minimum state should include:

- current responder target
- detected responder mode
- communication mode
- current urgency band
- last confirmed critical facts
- unresolved missing facts
- whether guidance is in execution mode
- whether a reasoning refresh is required
- no-response timer state

### Deliverable

- Phase 4 interaction state contract

---

## 2. Patient-First Opening Policy

Every incident should begin with a patient-directed check unless the system already has strong evidence that the patient cannot respond.

Typical opening goals:

- confirm responsiveness
- confirm ability to speak
- quickly identify breathing or severe pain issues
- determine whether the patient can self-report at all

### Deliverable

- patient-first opening rules

---

## 3. Bystander Communication Agent Policy

The bystander flow should no longer be treated as just alternate triage answers.

It should behave like a communication-guidance layer focused on:

- rapid observation collection
- step-by-step execution guidance
- scene management
- patient safety preservation
- repeated updates from what the bystander sees

For MVP testing, we should assume a bystander is available so the communication flow can be exercised more deeply.

### Deliverable

- bystander communication policy

---

## 4. Responder Switching Rules

The system must explicitly define when it switches communication focus:

- patient to bystander
- bystander to patient
- either to no_response handling

Examples:

- patient is initially responsive but becomes confused
- patient stops responding
- bystander appears and confirms they can assist
- bystander is busy performing a guided action and the patient begins answering again

### Deliverable

- responder-switching policy

---

## 5. Selective Reasoning Refresh Policy

Define exactly when a new interaction turn should trigger the reasoning agent.

High-priority refresh triggers:

- new abnormal breathing report
- severe bleeding report
- loss of responsiveness
- head strike newly confirmed
- new contradiction against previous facts
- escalation timeout or no-response timeout
- patient or bystander reports a major state change

Low-priority or no-refresh examples:

- "okay"
- "done"
- "I am checking now"
- repeated execution updates that do not change risk
- continuing CPR cadence guidance after escalation is already decided

### Deliverable

- reasoning-refresh trigger rules

---

## 6. No-Response Policy

If nobody answers, the system must stop assuming the conversation can continue indefinitely.

The policy should define when to:

- keep waiting briefly
- repeat a short urgent prompt
- shift to bystander-directed instructions
- move toward escalation or dispatch logic

### Deliverable

- no-response escalation rules

---

## 7. Role-Specific Guidance Formatting

Guidance should be formatted for the current communication target.

Patient guidance should be:

- calm
- direct
- short
- self-protective

Bystander guidance should be:

- command-style
- step-based
- observational
- action-oriented

No-response output should be:

- minimal
- urgent
- repetitive only when useful

### Deliverable

- role-aware guidance style rules

---

## 8. MVP Frontend Communication Flow

The MVP frontend should evolve from "generate triage questions then assess once" into a communication-focused console.

The MVP should support:

- text interaction mode
- live-preview mode placeholder or toggle
- visible responder target
- visible current urgency
- visible execution-guidance state
- visible reasoning-refresh events for testers

For hackathon judging, this is valuable because it makes the system behavior understandable during demos.

### Deliverable

- Phase 4 MVP frontend communication spec

---

## 9. Live-Ready Transport Abstraction

Even if live mode is not fully implemented yet, the Phase 4 backend should be shaped so that Gemini 3.1 Flash Live can plug in later.

That means backend outputs should not only be plain free-form chat text.

They should include structured communication artifacts such as:

- next target
- message text
- guidance mode
- urgency mode
- whether reasoning refresh is required
- whether this is guidance continuation or fresh evaluation

### Deliverable

- live-ready communication event contract

---

## 10. Phase 4 Interaction Test Pack

Create a scenario pack focused on communication behavior, not just severity correctness.

Scenarios should include:

- patient responsive and calm
- patient responsive but confused
- patient initially responsive then silent
- bystander present with severe fall
- bystander reporting abnormal breathing
- bystander performing guided CPR
- no-response after high-risk event
- guidance continuation without reasoning refresh

### Deliverable

- Phase 4 interaction scenario pack

---

## Suggested Execution Order

1. Define the Phase 4 interaction state model.
2. Define patient-first opening rules.
3. Define the bystander communication policy.
4. Define responder switching rules.
5. Define selective reasoning refresh triggers.
6. Define no-response policy.
7. Define role-aware guidance formatting.
8. Add the Phase 4 scenario pack.
9. Upgrade the MVP frontend to use the new communication flow.
10. Add a text/live mode toggle for evaluation readiness.

---

## Immediate Implementation Priority

For the current MVP cycle, the best near-term execution order is:

1. text-first bystander communication flow
2. patient-first opening policy
3. selective reasoning refresh rules
4. backend interaction-state support
5. frontend communication console upgrades
6. live-mode compatibility hooks

This keeps the prototype useful now while protecting the migration path to Gemini Live later.

---

## What You Should Personally Own

- interaction-state definitions
- patient-first communication rules
- bystander communication rules
- responder-switching logic
- selective reasoning refresh policy
- role-aware guidance style
- interaction scenario design
- text/live MVP interaction framing

These are the pieces that determine whether the product feels coherent during a real responder-facing demo.

---

## What Can Be Support Work Only

- test-only mock interfaces
- websocket or timer demos
- replay scripts for interaction scenarios
- audio transport experiments
- live-preview shell integrations

These can support evaluation without forcing the full live architecture too early.

---

## Risks To Watch

- bystander mode remains just a renamed triage questionnaire
- the system forgets to address the patient first
- reasoning gets re-run too often and slows communication
- important state changes fail to trigger reasoning refresh
- patient and bystander guidance mix together
- no-response cases remain stuck in questioning mode
- live mode is introduced before the text interaction policy is stable
- frontend becomes chat-only instead of interaction-state aware

---

## Definition Of Done

Phase 4 is complete when:

- the system starts with a patient-first interaction by default
- bystander flows feel meaningfully different from patient flows
- responder switching behavior is explicit and testable
- reasoning refresh happens selectively rather than every turn
- no-response logic is clearly defined
- guidance tone matches the active communication target
- the text MVP demonstrates a realistic guided interaction flow
- the architecture is clearly prepared for a later Gemini Live adapter
