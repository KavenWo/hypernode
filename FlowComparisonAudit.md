# Final MVP Flow vs Current Implementation Audit

This document compares the current codebase against `FinalProductPlan.md` and proposes a cleanup direction for the fall-response agent flow.

The goal is not to remove AI. The goal is to remove uncontrolled branching, migration scaffolding, and legacy paths that make the system unreliable.

## Final MVP Target

The target flow from `FinalProductPlan.md` is:

1. `Sentinel Agent`
   - detect fall from video
   - return `fall_detected` and a short explanation
2. `Immediate deterministic actions`
   - notify family immediately
   - start monitoring
   - do not trigger full reasoning yet
3. `Communication Agent`
   - own all interaction
   - still use ADK AI analysis for turn understanding
   - ask only the controlled questions in the product plan
   - extract a small set of flags such as `bleeding`, `pain`, `mobility`
   - prevent drift
4. `Reasoning Agent`
   - consume structured state only
   - use medical grounding only for decision support
   - run at most 2-3 times
   - return one terminal decision object
5. `Execution Agent`
   - deterministic only
   - execute ambulance dispatch, family notification, CPR guidance
   - no new AI reasoning after final decision

## Current State Summary

The current backend is more complex than the final MVP target in four ways:

1. It supports multiple fall entry flows at once.
   - `backend/app/api/routes/fall.py:67`
   - `backend/app/api/routes/fall.py:73`
   - `backend/app/api/routes/fall.py:89`
   - `backend/app/api/routes/fall.py:185`
   - `backend/README.md:165`

2. It still contains migration-era runtime routing across several backends.
   - `backend/app/fall/agent_runtime.py:13`
   - `backend/app/fall/agent_runtime.py:205`
   - `backend/app/fall/agent_runtime.py:265`
   - `backend/app/fall/agent_runtime.py:339`
   - `backend/app/fall/agent_runtime.py:454`

3. It duplicates reasoning and grounding responsibilities across more than one path.
   - `backend/app/fall/assessment_service.py:701`
   - `backend/app/fall/assessment_service.py:911`
   - `backend/app/fall/assessment_service.py:1012`

4. It has a fairly heavy session state machine with parallel action tracks and confirmation timers.
   - `backend/app/fall/conversation_service.py:988`
   - `backend/app/fall/conversation_service.py:994`
   - `backend/app/fall/action_runtime_service.py:30`
   - `backend/app/fall/action_runtime_service.py:31`
   - `backend/app/fall/action_runtime_service.py:379`

## What Aligns Well Already

These parts are directionally correct and should mostly be kept:

### 1. Sentinel / fall detection boundary

- `backend/agents/sentinel/vision_agent.py`
- `backend/agents/sentinel/vital_agent.py`

This matches the plan well. Sentinel should stay narrow and should not be pulled into conversation or execution behavior.

### 2. ADK communication analysis

- `backend/app/fall/adk_communication.py`

This already follows the right idea: the communication layer uses AI to analyze the latest turn, extract facts, and produce structured output, while the outer controller remains deterministic.

This should stay, but it should be constrained to the final product's fixed question sequence and approved flags only.

### 3. ADK reasoning as a bounded decision step

- `backend/app/fall/adk_reasoning.py`

This is closer to the target than the broader local/runtime-mixed path because it already frames the reasoning agent as a structured decision layer with guardrails.

### 4. ADK execution as action-to-guidance transformation

- `backend/app/fall/adk_execution.py`

This is aligned with the plan because it treats execution as downstream of an already-decided action.

### 5. Mock dispatch service

- `backend/app/fall/execution_service.py`

This can remain as the deterministic ambulance dispatch simulator, though the surrounding control flow should be simplified.

## Main Gaps Against Final MVP

### Gap 1. Two active fall flows still exist

The final plan wants one canonical product flow. The codebase still supports:

- question/assessment flow
- session conversation flow
- a legacy direct shortcut route

Evidence:

- `backend/app/api/routes/fall.py:67`
- `backend/app/api/routes/fall.py:73`
- `backend/app/api/routes/fall.py:89`
- `backend/app/api/routes/fall.py:185`
- `backend/app/main.py:32`
- `backend/app/main.py:33`

Impact:

- more code paths to test
- conflicting assumptions about when reasoning runs
- larger API surface for stale behavior to survive

Recommendation:

- keep one canonical flow centered on session/conversation control
- remove the separate `questions -> assess` product path
- remove the legacy direct POST shortcut

### Gap 2. Runtime backend routing is migration scaffolding, not product logic

The runtime supports `local`, `vertex`, `genkit`, and `adk`.

Evidence:

- `backend/app/fall/agent_runtime.py:13`
- `backend/app/fall/agent_runtime.py:205`
- `backend/app/fall/agent_runtime.py:265`
- `backend/app/fall/agent_runtime.py:339`
- `backend/tests/test_agent_runtime.py:27`
- `backend/tests/test_agent_runtime.py:153`

Impact:

- more uncertainty in active behavior
- more test surface for code we do not want in the final demo path
- placeholder runtimes invite accidental usage and configuration drift

Recommendation:

- freeze the fall product flow to ADK-backed communication, reasoning, and execution
- remove `vertex` and `genkit` fall runtime branches
- remove `local` fallback as the selectable product backend for fall flow
- if a fallback is still needed, keep fallback inside the ADK-backed module itself, not as a separate runtime family

### Gap 3. Reasoning and guidance are split across overlapping paths

There are currently two major assessment paths:

- `run_reasoning_assessment`
- `run_fall_assessment`

The second one expands into grounded guidance retrieval and protocol handling.

Evidence:

- `backend/app/fall/assessment_service.py:701`
- `backend/app/fall/assessment_service.py:911`
- `backend/app/fall/assessment_service.py:1012`
- `backend/app/fall/assessment_service.py:21`
- `backend/app/fall/assessment_service.py:364`

Impact:

- blurry separation between reasoning and execution
- reasoning can accidentally absorb responder-guidance complexity
- more opportunities for inconsistency between assessment variants

Recommendation:

- keep exactly one reasoning function for the product flow
- that function should output only the terminal decision object
- move all responder-facing protocol guidance responsibility fully into execution
- keep Vertex AI Search in reasoning only for limited medical support grounding
- keep protocol and CPR instruction grounding in execution only

### Gap 4. The session loop is more dynamic than the final plan needs

The session flow currently supports:

- selective background reasoning refreshes
- pending reasoning context handoff
- conditional phase 2 execution grounding
- action announcements
- execution-priority reply switching

Evidence:

- `backend/app/fall/conversation_service.py:750`
- `backend/app/fall/conversation_service.py:937`
- `backend/app/fall/conversation_service.py:988`
- `backend/app/fall/conversation_service.py:994`
- `backend/app/fall/session_store.py`

Impact:

- more asynchronous state behavior
- harder to guarantee the exact order of demo behavior
- larger risk of state drift between communication, reasoning, and execution

Recommendation:

- keep the session loop, but reduce it to the final MVP stages only
- communication should progress through a fixed finite sequence:
  - opening check
  - bystander check
  - consciousness
  - breathing
  - optional flag extraction
  - reasoning
  - execution guidance
- background reasoning should be limited to the specific allowed points from the final plan
- reasoning run count should be explicitly capped

### Gap 5. Execution state is modeled as a general action-track system

The action runtime currently models parallel tracks:

- `monitor`
- `contact_family`
- `emergency_dispatch`

with state transitions, notifications, deduplication, and a pending confirmation window.

Evidence:

- `backend/app/fall/action_runtime_service.py:31`
- `backend/app/fall/action_runtime_service.py:296`
- `backend/app/fall/action_runtime_service.py:313`
- `backend/app/fall/action_runtime_service.py:379`
- `backend/app/fall/action_runtime_service.py:398`

Impact:

- action-state complexity is larger than the final product plan
- confirmation-window behavior is not part of the final MVP narrative
- family reminder plus family support plus dispatch states create extra branches

Recommendation:

- replace the generic action-track state machine with a simpler deterministic execution controller
- retain only the final MVP actions:
  - `notify_family_initial`
  - `call_ambulance`
  - `start_cpr_guidance`
  - `advise_rest_and_monitor`
- remove the 15-second dispatch confirmation window unless the product plan is updated to require it
- keep family notification mandatory and deterministic

### Gap 6. The question flow is already half-deprecated but still exposed

`build_fall_questions` already returns a stub and says the legacy triage agent is deprecated, but the endpoint still exists and tests still assume a richer question flow.

Evidence:

- `backend/app/fall/assessment_service.py:239`
- `backend/app/api/routes/fall.py:67`
- `backend/tests/test_api_fall.py:13`

Impact:

- stale routes survive because tests preserve them
- developers may continue building against a path we want to retire

Recommendation:

- remove the endpoint instead of leaving a stub
- delete tests that preserve the deprecated question flow

## Recommended Keep / Simplify / Remove Map

## Keep

These should remain, though some may be slimmed down internally:

- `backend/agents/sentinel/vision_agent.py`
- `backend/agents/sentinel/vital_agent.py`
- `backend/app/fall/adk_communication.py`
- `backend/app/fall/adk_reasoning.py`
- `backend/app/fall/adk_execution.py`
- `backend/app/fall/execution_service.py`
- `backend/app/api/routes/fall.py`
  - but reduced to the canonical final-MVP endpoints only

## Simplify Heavily

These should stay in concept but be narrowed to the final plan:

- `backend/app/fall/conversation_service.py`
  - reduce to fixed-state conversation control
  - hard-cap reasoning runs
  - remove broad selective refresh behavior
- `backend/app/fall/session_store.py`
  - keep only the state needed for one active canonical session flow
  - remove surplus reasoning/debug/version fields where possible
- `backend/app/fall/contracts.py`
- `backend/agents/shared/schemas.py`
  - shrink toward final MVP contracts instead of migration-era wide schemas
- `backend/app/fall/assessment_service.py`
  - collapse to one reasoning path
  - remove responder-guidance ownership from reasoning

## Remove From Product Flow

These should be removed or retired from the active fall-response path:

- `backend/app/fall/agent_runtime.py`
  - replace with a direct final-MVP runtime binding instead of multi-backend routing
- `backend/app/fall/genkit_execution.py`
- `backend/app/api/routes/fall.py` routes:
  - `/questions`
  - `/assess`
  - direct legacy `/`
- question-flow logic and related expectations
- generic dispatch confirmation window behavior
- broad `communication_handoff` contract features not required by final MVP
- guidance retrieval inside the main reasoning path

## Strong Removal Candidates

These look like legacy or migration leftovers and should be proposed for deletion once references are removed:

- `backend/legacy/triage_agent.py`
- `backend/legacy/vitals.py`
- `backend/experiments/adk_vertex_search_smoke_test.py`
- `backend/emergency.py`
  - only after verifying no remaining support APIs still need compatibility with it

## Tests To Remove Or Rewrite

Several tests currently preserve complexity we do not want in the final MVP.

### Remove or replace

- `backend/tests/test_agent_runtime.py`
  - this exists largely to validate runtime backend switching
- `backend/tests/test_phase2_guidance_normalizer.py`
- `backend/tests/test_phase2_retrieval_engine.py`
- `backend/tests/test_phase2_retrieval_policy.py`
- `backend/tests/test_grounded_guidance_trigger.py`
- `backend/tests/test_protocol_grounding.py`
- `backend/tests/test_reasoning_support_grounding.py`
  - keep only the parts still needed by the final MVP reasoning/execution split

### Rewrite around the final product path

- `backend/tests/test_api_fall.py`
- `backend/tests/test_phase4_session_turn.py`
- `backend/tests/test_runtime_status.py`

New tests should be scenario-driven around the final plan:

1. fall detected -> family notified -> patient asked "Are you okay?"
2. no response after timeout -> reasoning -> auto dispatch
3. bystander present + unconscious + not breathing -> reasoning -> CPR scenario
4. conscious + breathing normal -> non-critical scenario -> notify family + advise rest
5. communication drift input -> agent re-asks required structured question
6. reasoning stops after final decision
7. execution stays deterministic after final decision

## Proposed Canonical Backend Shape

The final MVP backend should converge toward this simpler shape:

- `sentinel_service`
  - detect fall only
- `communication_service`
  - fixed flow controller
  - ADK AI turn analysis
  - extract structured state
- `reasoning_service`
  - one bounded decision call
  - optional second call only when confidence is low or no-response escalation requires it
- `execution_service`
  - deterministic final action runner
  - family alert
  - ambulance dispatch
  - CPR guidance

In practice, this means the current session route can remain, but the internals should act like a small finite-state machine rather than a broad adaptive orchestration layer.

## Safe Cleanup Sequence

Recommended order to avoid breakage:

1. Freeze the desired API and session shape around the final MVP only.
2. Remove the question/assessment endpoints and their tests.
3. Replace runtime backend switching with a direct ADK final-MVP runtime.
4. Collapse reasoning to one bounded assessment path.
5. Move all protocol/guidance ownership fully into execution.
6. Replace `action_runtime_service` with a smaller deterministic execution controller.
7. Delete legacy and experiment files after imports are gone.
8. Rewrite docs and health/status responses so they describe only one flow.

## Bottom Line

The codebase already contains the right ingredients for the final MVP:

- sentinel separation
- ADK communication analysis
- ADK reasoning
- deterministic execution concepts

What is hurting reliability is not missing capability. It is overlapping flow styles, migration backends, wide schemas, and state machinery that is broader than the final product narrative.

The best implementation direction is:

- keep AI inside communication and reasoning
- keep execution deterministic
- reduce the system to one canonical fall-response flow
- delete legacy files and migration scaffolding once the direct path is in place
