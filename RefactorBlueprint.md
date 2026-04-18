# Emergency Fall Response Refactor Blueprint

This document is the concrete implementation blueprint for refactoring the current fall-response system into the final MVP flow described in `FinalProductPlan.md`.

This blueprint supersedes any earlier simplification idea that would remove required technologies.

## Non-Negotiable Constraints

The final implementation must preserve these technical requirements:

- `Firebase Genkit` must be used
- `Vertex AI Search` must be used
- `ADK Agent Builder` must be used
- the `15-second dispatch confirmation countdown` must remain in the execution flow

The simplification goal is:

- reduce branching
- reduce overlapping flows
- reduce migration scaffolding
- keep AI where it adds value
- keep execution reliable and deterministic

## Final Product Objective

We are building one canonical emergency flow:

1. detect fall
2. notify family immediately
3. begin monitoring
4. start controlled communication
5. collect structured state
6. run bounded reasoning
7. start 15-second dispatch confirmation if dispatch is recommended
8. execute deterministically
9. guide the responder clearly

Core principle:

- `Detection -> Decision -> Action`

## Technology Responsibility Map

To prevent cross-contamination, each required technology must have a narrow ownership boundary.

### 1. ADK Agent Builder

ADK owns the AI agents that interpret and decide:

- `Communication Agent`
- `Reasoning Agent`
- optional `Execution Guidance Formatter` only if it is formatting fixed execution output, not re-triaging

ADK is allowed to:

- analyze responder turns
- extract structured facts
- decide whether communication input is relevant or drifting
- produce the final reasoning decision object

ADK is not allowed to:

- own the overall state machine
- start arbitrary new branches
- decide execution side effects after the final decision

### 2. Vertex AI Search

Vertex AI Search owns grounding:

- `Reasoning grounding`
  - medical support for decision-making
- `Execution grounding`
  - CPR / first-aid / protocol support

Vertex AI Search is not a flow controller.
It should only provide grounded support to bounded agent calls.

### 3. Firebase Genkit

Genkit owns orchestration and integration duties required by the mandate:

- deterministic execution pipelines
- notification workflow orchestration
- dispatch confirmation workflow
- execution-stage coordination
- tool or flow wrappers where appropriate

Genkit is not allowed to become a second reasoning layer parallel to ADK.

## Canonical System Architecture

The final backend should converge on four product roles:

### 1. Sentinel Agent

Responsibility:

- inspect uploaded video
- determine `fall_detected`
- provide a simple explanation

Output:

```json
{
  "fall_detected": true,
  "explanation": "An elderly individual appears to have fallen and is not moving.",
  "confidence": 0.92
}
```

### 2. Communication Agent

Responsibility:

- handle all patient / bystander interaction
- use ADK analysis on each turn
- enforce a fixed flow
- validate inputs
- extract structured signals
- prevent drift

Communication is AI-assisted, but flow progression is controller-owned.

### 3. Reasoning Agent

Responsibility:

- consume structured state only
- use Vertex AI Search for medical grounding
- return the final decision object
- run at most 2-3 times
- stop after final output

### 4. Execution Agent

Responsibility:

- execute deterministic actions from the final decision
- handle family alerting
- handle 15-second dispatch confirmation
- handle ambulance dispatch
- handle CPR guidance

Execution may use Genkit for orchestration and Vertex AI Search for grounded protocol retrieval, but it must not re-triage.

## Canonical End-to-End Flow

## Stage 1. Sentinel Detection

Input:

- uploaded video

Output:

- `fall_detected`
- `explanation`
- `confidence`

Rule:

- if no fall is detected, stop the emergency flow
- if fall is detected, continue immediately

## Stage 2. Immediate Deterministic Actions

When a fall is detected:

- notify family immediately with an initial alert
- start monitoring immediately
- create or initialize the session state
- do not run full reasoning yet

These are deterministic actions.

## Stage 3. Controlled Communication Start

The first assistant message is:

> Are you okay?

The system enters controlled communication mode.

## Stage 4. Response Handling

### Case A. No response

- wait about 10 seconds
- mark `response = none`
- run `Reasoning Call 1`

### Case B. Response exists

Communication Agent:

- validates the message
- identifies whether responder is patient or bystander
- extracts allowed signals
- advances through the fixed question sequence

## Stage 5. Bystander Check

Prompt:

> Is anyone nearby who can assist?

Possible frontend signal:

- `I am here (Bystander)`

State update:

- `mode = bystander`
- or `mode = patient_only`

## Stage 6. Critical Questions

Required questions:

- Is the patient conscious?
- Is the patient breathing normally?

Optional extracted signals:

- bleeding
- pain
- mobility

No other open-ended triage branches should be introduced.

## Stage 7. Reasoning

### Reasoning Call 1

Triggered only when:

- no response after timeout

Example input:

```json
{
  "response": "none",
  "bystander": false,
  "conscious": null,
  "breathing": null,
  "flags": []
}
```

### Reasoning Call 2

Triggered when the critical structured state is ready.

Example input:

```json
{
  "response": "present",
  "bystander": true,
  "conscious": false,
  "breathing": false,
  "flags": ["bleeding"]
}
```

### Reasoning Call 3

Allowed only if:

- confidence is below threshold
- a specific bounded clarification is required

Hard cap:

- max 3 reasoning calls total

## Stage 8. Dispatch Confirmation

If the reasoning decision recommends ambulance dispatch:

- start a 15-second confirmation countdown
- communicate clearly that emergency dispatch is about to happen
- allow cancellation if the flow rules permit it
- auto-dispatch if the countdown completes without cancellation

This countdown is execution-owned, not reasoning-owned.

## Stage 9. Deterministic Execution

Once the final decision is reached:

- reasoning is closed
- execution proceeds deterministically

Examples:

- `CPR scenario`
  - dispatch flow
  - grounded CPR guidance
- `No response scenario`
  - dispatch flow
  - waiting guidance
- `Non-critical scenario`
  - family support update
  - rest / monitoring guidance

## State Machine Blueprint

The communication and orchestration layer should be implemented as a finite-state machine.

## Core Session States

- `idle`
- `fall_detected`
- `initial_actions_started`
- `opening_check`
- `awaiting_opening_response`
- `bystander_check`
- `consciousness_check`
- `breathing_check`
- `optional_flags_check`
- `ready_for_reasoning`
- `reasoning_in_progress`
- `awaiting_dispatch_confirmation`
- `execution_in_progress`
- `completed`

## State Rules

### `fall_detected`

Entry conditions:

- Sentinel returns `fall_detected = true`

Actions:

- initialize session
- record sentinel summary

### `initial_actions_started`

Actions:

- send initial family notification
- start monitoring

Next state:

- `opening_check`

### `opening_check`

Assistant prompt:

- Are you okay?

Next state:

- `awaiting_opening_response`

### `awaiting_opening_response`

Possible transitions:

- human response -> `bystander_check`
- 10s timeout -> `ready_for_reasoning`

### `bystander_check`

Assistant prompt:

- Is anyone nearby who can assist?

Possible transitions:

- bystander confirmed -> `consciousness_check`
- no bystander -> `consciousness_check`

### `consciousness_check`

Assistant prompt:

- Is the patient conscious?

Possible transitions:

- valid answer -> `breathing_check`
- irrelevant answer -> stay and re-ask

### `breathing_check`

Assistant prompt:

- Is the patient breathing normally?

Possible transitions:

- valid answer -> `optional_flags_check`
- irrelevant answer -> stay and re-ask

### `optional_flags_check`

Goal:

- extract optional allowed signals from any latest turn

Allowed flags:

- bleeding
- pain
- mobility

Next state:

- `ready_for_reasoning`

### `ready_for_reasoning`

Rules:

- build structured reasoning input
- enforce reasoning call cap

Next state:

- `reasoning_in_progress`

### `reasoning_in_progress`

Actions:

- run bounded ADK reasoning with Vertex AI Search grounding

Possible transitions:

- decision says dispatch -> `awaiting_dispatch_confirmation`
- decision says non-critical rest/monitor -> `execution_in_progress`
- decision says CPR guidance -> `awaiting_dispatch_confirmation`

### `awaiting_dispatch_confirmation`

Actions:

- start 15-second countdown
- tell responder dispatch is preparing
- allow cancel or confirm control

Possible transitions:

- confirm -> `execution_in_progress`
- timeout -> `execution_in_progress`
- cancel -> `execution_in_progress`

### `execution_in_progress`

Actions:

- run deterministic Genkit execution workflow
- start guidance delivery through communication

Possible transitions:

- execution finished or stable monitor path active -> `completed`

## Contract Blueprint

The current schema layer is too broad. We should introduce a narrower final-MVP contract set.

## 1. Sentinel Result

```json
{
  "fall_detected": true,
  "explanation": "string",
  "confidence": 0.0
}
```

## 2. Communication State

```json
{
  "session_id": "string",
  "state": "opening_check",
  "mode": "patient_only",
  "responder_role": "patient",
  "patient_responded": true,
  "bystander_present": false,
  "conscious": null,
  "breathing_normal": null,
  "flags": [],
  "latest_prompt": "Are you okay?",
  "latest_message": "",
  "reasoning_call_count": 0
}
```

## 3. Communication Analysis Output

This is the ADK output for a single turn.

```json
{
  "responder_role": "patient",
  "patient_responded": true,
  "bystander_present": false,
  "answer_relevance": "valid",
  "conscious": null,
  "breathing_normal": null,
  "flags": ["pain"],
  "needs_reask": false,
  "reask_for": null,
  "followup_text": "string"
}
```

## 4. Reasoning Input

```json
{
  "response": "present",
  "bystander": true,
  "conscious": false,
  "breathing": false,
  "flags": ["bleeding"],
  "reasoning_call_count": 2
}
```

## 5. Reasoning Decision

```json
{
  "scenario": "CPR",
  "severity": "critical",
  "action": "call_ambulance",
  "reason": "Patient is unconscious and not breathing",
  "instructions": "Start CPR immediately",
  "confidence": 0.95,
  "flags_used": ["bleeding"]
}
```

## 6. Execution State

```json
{
  "phase": "dispatch_countdown",
  "countdown_seconds": 15,
  "family_notified_initial": true,
  "family_notified_update": false,
  "dispatch_status": "pending_confirmation",
  "guidance_protocol": "",
  "guidance_step_index": 0
}
```

## 7. Session Response

This is the main frontend payload for the canonical session flow.

```json
{
  "session_id": "string",
  "state": "breathing_check",
  "assistant_message": "Is the patient breathing normally?",
  "communication_state": {},
  "reasoning_decision": null,
  "execution_state": {},
  "quick_replies": []
}
```

## Module Ownership Blueprint

## Keep and Refactor

### `backend/agents/sentinel/*`

Keep:

- `vision_agent.py`
- `vital_agent.py`

Refactor goal:

- ensure they only produce detection-oriented outputs

### `backend/app/fall/adk_communication.py`

Keep.

Refactor goal:

- constrain prompt and output schema to the final fixed question flow
- remove broad conversational flexibility
- keep signal extraction narrow and explicit

### `backend/app/fall/adk_reasoning.py`

Keep.

Refactor goal:

- accept only final structured state input
- preserve Vertex AI Search support grounding
- return only final decision contract

### `backend/app/fall/adk_execution.py`

Keep.

Refactor goal:

- only format and ground protocol execution
- no triage logic

### `backend/app/fall/execution_service.py`

Keep.

Refactor goal:

- remain the deterministic mock dispatch layer
- integrate cleanly with countdown and final execution states

### `backend/app/fall/conversation_service.py`

Keep, but heavily rewrite.

Refactor goal:

- become the canonical session state controller
- own state transitions
- invoke ADK communication only for turn analysis
- invoke reasoning only at approved checkpoints

### `backend/app/fall/session_store.py`

Keep, but simplify.

Refactor goal:

- store only the state machine data needed by the final flow
- remove migration/debug-only complexity where possible

### `backend/app/fall/action_runtime_service.py`

Keep conceptually, but rewrite around final execution state vocabulary.

Refactor goal:

- own family notification states
- own 15s dispatch countdown
- own dispatch execution trigger
- own deterministic CPR or rest guidance progression

### `backend/app/api/routes/fall.py`

Keep, but reduce to the canonical session flow endpoints only.

Recommended final routes:

- `POST /api/v1/events/fall/session-start`
- `POST /api/v1/events/fall/session-turn`
- `GET /api/v1/events/fall/session-state/{session_id}`
- `POST /api/v1/events/fall/session-action/{session_id}`
- `GET /api/v1/events/fall/session-events/{session_id}`

## Preserve Required Genkit Integration

### `backend/app/fall/genkit_execution.py`

Do not remove outright because Genkit is mandatory.

Refactor goal:

- turn it into the required execution orchestration layer
- remove any role that looks like alternative reasoning
- ensure it only consumes fixed execution input

Recommended Genkit responsibilities:

- family notification workflow orchestration
- dispatch confirmation workflow orchestration
- grounded CPR execution workflow handoff
- execution event publication or status fan-out if needed

## Remove or Retire From Active Product Flow

These should no longer define the product path once the refactor is complete:

- question/assessment dual flow in `backend/app/api/routes/fall.py`
- question stub flow in `backend/app/fall/assessment_service.py`
- multi-runtime product switching in `backend/app/fall/agent_runtime.py`
- broad migration contracts that are not needed by final MVP

## Legacy Removal Candidates

These should be deleted once references are gone:

- `backend/legacy/triage_agent.py`
- `backend/legacy/vitals.py`
- `backend/experiments/adk_vertex_search_smoke_test.py`

`backend/emergency.py` should be kept only until compatibility references are removed, then deleted.

## Concrete Refactor Tasks

## Workstream 1. Final Contract Definitions

Deliverables:

- new final MVP schemas
- reduced session response contract
- reduced reasoning input/output contract
- reduced execution state contract

Files to update:

- `backend/agents/shared/schemas.py`
- `backend/app/fall/contracts.py`

Success criteria:

- frontend and backend speak one canonical schema family
- no product-facing response depends on migration-era wide contracts

## Workstream 2. Canonical Session State Machine

Deliverables:

- state enum
- transition rules
- timeout handling
- bystander/patient mode rules

Files to update:

- `backend/app/fall/conversation_service.py`
- `backend/app/fall/session_store.py`

Success criteria:

- every session is always in one explicit state
- communication cannot drift outside the fixed flow
- reasoning can only trigger from approved states

## Workstream 3. ADK Communication Narrowing

Deliverables:

- updated prompt
- updated response schema
- narrow signal vocabulary
- re-ask rules for irrelevant answers

Files to update:

- `backend/app/fall/adk_communication.py`

Success criteria:

- communication analysis remains AI-based
- controller remains deterministic
- extra user input cannot create new scenarios

## Workstream 4. Reasoning Simplification

Deliverables:

- one bounded reasoning entrypoint
- max 3 call guard
- final decision contract
- Vertex AI Search medical support grounding

Files to update:

- `backend/app/fall/adk_reasoning.py`
- `backend/app/fall/assessment_service.py`

Success criteria:

- no duplicate reasoning paths
- reasoning stops after final decision
- no responder-facing protocol logic remains in reasoning

## Workstream 5. Execution and Countdown

Deliverables:

- deterministic execution controller
- family initial alert
- family update behavior
- 15-second dispatch countdown
- ambulance dispatch
- CPR guidance progression
- non-critical guidance progression

Files to update:

- `backend/app/fall/action_runtime_service.py`
- `backend/app/fall/execution_service.py`
- `backend/app/fall/genkit_execution.py`
- `backend/app/fall/adk_execution.py`

Success criteria:

- countdown always works consistently
- execution never re-triages
- CPR guidance is deterministic after the final decision

## Workstream 6. Route and API Cleanup

Deliverables:

- canonical route set only
- docs aligned to one flow
- health endpoint aligned to one flow

Files to update:

- `backend/app/api/routes/fall.py`
- `backend/app/main.py`
- `backend/README.md`

Success criteria:

- backend no longer advertises multiple fall-flow styles

## Workstream 7. Legacy Cleanup

Deliverables:

- delete inactive legacy files
- delete experiments not used
- remove compatibility shims when safe

Files to remove after cutover:

- `backend/legacy/triage_agent.py`
- `backend/legacy/vitals.py`
- `backend/experiments/adk_vertex_search_smoke_test.py`
- `backend/emergency.py`

Success criteria:

- no stale fall-flow implementation remains available to confuse future work

## Rollout Phases

## Phase 1. Blueprint Lock

Goal:

- freeze target architecture and contracts before heavy code changes

Outputs:

- this blueprint
- approved route set
- approved state machine
- approved contract shapes

## Phase 2. Contract and Controller Refactor

Goal:

- implement the canonical state machine and contract layer

Changes:

- update schemas
- update session store
- update conversation controller

## Phase 3. Reasoning and Execution Refactor

Goal:

- implement the final bounded reasoning and deterministic execution split

Changes:

- collapse assessment logic
- add final reasoning contract
- refactor countdown and execution
- integrate Genkit execution orchestration cleanly

## Phase 4. Route Cutover

Goal:

- move the product path fully to canonical session flow

Changes:

- deprecate and remove old question/assessment flow
- update docs
- update health endpoint

## Phase 5. Legacy Deletion and Test Rewrite

Goal:

- remove stale code and lock reliability through scenario tests

Changes:

- delete legacy files
- rewrite tests around final scenarios

## Test Blueprint

The final tests should be scenario-driven and aligned to the final product plan.

## Required scenarios

1. Fall detected
   - family initial alert is sent
   - monitoring starts
   - first prompt is "Are you okay?"

2. No response scenario
   - 10-second timeout occurs
   - Reasoning Call 1 runs
   - dispatch countdown starts
   - auto-dispatch occurs after 15 seconds if not cancelled

3. CPR scenario
   - bystander present
   - patient unconscious
   - patient not breathing normally
   - final decision is CPR
   - dispatch countdown occurs
   - CPR execution guidance starts

4. Non-critical scenario
   - patient conscious
   - breathing normal
   - family remains notified
   - rest and monitoring guidance is delivered

5. Drift resistance
   - irrelevant user input
   - communication agent re-asks the required controlled question

6. Reasoning call cap
   - reasoning never exceeds max allowed calls

7. Execution determinism
   - after final decision, execution does not reopen triage

8. Technology mandate coverage
   - ADK communication path is exercised
   - ADK reasoning path is exercised
   - Vertex AI Search grounding is exercised or safely stubbed
   - Genkit execution orchestration is exercised or safely stubbed

## Immediate Next Implementation Order

The recommended coding order is:

1. define final contract models
2. define explicit session state enum and transitions
3. refactor `conversation_service` around the finite-state machine
4. refactor `assessment_service` into one bounded reasoning path
5. refactor `action_runtime_service` for countdown plus deterministic execution
6. reposition `genkit_execution.py` as mandated execution orchestration
7. cut old routes
8. rewrite tests
9. delete legacy files

## Bottom Line

The final system should not be a broad agentic playground.
It should be a tightly controlled emergency pipeline that still uses the mandated stack:

- `ADK` for communication and reasoning intelligence
- `Vertex AI Search` for grounding
- `Firebase Genkit` for execution orchestration

The simplification is in control flow, not in removing AI.
The result should be one reliable, safe, demo-ready path with explicit state transitions, bounded reasoning, a preserved 15-second dispatch confirmation, and deterministic execution after the final decision.
