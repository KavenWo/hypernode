# Backend Consolidation Plan

## Why This Exists

The backend has already partially converged on one real product path, but the
repo still communicates multiple competing stories:

- a Phase 1-3 style question-first MVP flow
- a Phase 4 session-based communication flow
- legacy compatibility wrappers and older direct-dispatch experiments
- a `tests/` folder that currently mixes unit tests, smoke tests, and manual demo scripts

That makes the system feel more fragmented than it really is.

This plan turns the current backend into one coherent source-of-truth flow that:

- powers the MVP test page now
- remains usable by the final product later
- keeps deterministic assessment entrypoints for evaluation
- reduces duplicate wrappers and "test-only" product files

---

## Progress So Far

The consolidation has already started in code, not just on paper.

### Completed

- `backend/app/fall/` now exists as the active fall-domain boundary
- deterministic assessment logic now lives in `app/fall/assessment_service.py`
- session-based conversation logic now lives in `app/fall/conversation_service.py`
- emergency execution logic now lives in `app/fall/execution_service.py`
- the emergency route is now thin and service-backed
- manual runners were moved out of `backend/tests/` into `backend/evals/manual/`
- `pytest` and `pytest-asyncio` were added to the backend dev dependency group
- `pytest.ini` was added so `backend/tests/` can behave like a real automated suite
- automated tests were converted away from `main()`-style script execution
- the API smoke test was renamed from `test_api_mvp.py` to `test_api_fall.py`
- the active fall route implementation now lives in `backend/app/api/routes/fall.py`
- `FallAssessment` now exists as the primary shared-schema name

### Still In Transition

- `agents/shared/schemas.py` still owns core product contracts, even though the active backend path now imports them through `app/fall/contracts.py`
- `MvpTestPage.jsx` is correctly using the canonical session flow, but its name still reflects the prototype era

That means the behavioral source of truth is much cleaner than before, but the
repo language still partially describes the old architecture.

---

## Current Diagnosis

### 1. The real source of truth exists, but naming still hides it

The code now has a more accurate center of gravity:

- `backend/app/fall/assessment_service.py`
- `backend/app/fall/conversation_service.py`
- `backend/app/fall/execution_service.py`
- `backend/app/fall/session_store.py`

That is a major improvement.

The remaining issue is that the repo still exposes older names in enough places
that a fresh read can make the architecture feel more split than it is.

Examples:

- `app/api/routes/fall.py`
- `agents/shared/schemas.py::FallAssessment`
- `frontend/.../MvpTestPage.jsx`

### 2. The repo still presents two different "main flows"

Today, the codebase exposes both:

- question-based flow:
  - `POST /api/v1/events/fall/questions`
  - `POST /api/v1/events/fall/assess`
- session-based flow:
  - `POST /api/v1/events/fall/session-turn`
  - `GET /api/v1/events/fall/session-state/{session_id}`
  - `GET /api/v1/events/fall/session-events/{session_id}`

The Phase 4 session flow is what the frontend test page is actually using, but
the backend README and app root still present the older question-first flow as
the primary MVP path.

### 3. The tests folder currently mixes different file types

`backend/tests/` currently contains:

- proper pytest-style unit tests
- manual smoke scripts with `main()`
- end-to-end local runners
- environment-specific utilities

That makes the word "test" mean too many different things.

## Architectural Decision

The Phase 4 session-based conversation flow should become the canonical product
workflow.

The question-based flow should remain available, but only as a deterministic
assessment/evaluation path, not as a competing main architecture.

In practice, that means:

- the final product should speak to the same backend session flow as `MvpTestPage.jsx`
- the single-pass assessment route should remain for:
  - scenario evaluation
  - debugging
  - regression checks
  - controlled comparison of retrieval/reasoning behavior

---

## Target Architecture

The backend should move toward a domain-oriented `fall/` package under `app/`.

### Target layout

```text
backend/
  app/
    fall/
      contracts.py
      assessment_service.py
      conversation_service.py
      execution_service.py
      session_store.py
      scenario_service.py
      adapters/
        communication.py
        reasoning.py
        retrieval.py
        triage.py
    api/
      routes/
        fall.py
        emergency.py
```

### Responsibility split

#### `contracts.py`

Owns the shared Pydantic models currently living in `agents/shared/schemas.py`.

These are product contracts, not merely "agent" internals.

#### `assessment_service.py`

Owns the deterministic single-pass backend path:

1. load profile
2. inspect event and vitals
3. run retrieval
4. run reasoning
5. normalize guidance
6. return `FallAssessment`

This is the reusable engine for both evaluation and conversation refresh.

#### `conversation_service.py`

Owns the Phase 4 session loop:

- turn intake
- communication analysis
- interaction target selection
- selective reasoning refresh decision
- transcript handling
- response shaping
- background reasoning coordination

This becomes the canonical product-facing workflow.

#### `execution_service.py`

Owns dispatch and other operational side effects:

- emergency trigger bridge
- execution update construction
- family notification shaping
- future downstream product integrations

This removes the current service-to-route dependency.

#### `session_store.py`

Owns the session record lifecycle only.

This file already exists in spirit and should remain small and isolated.

#### `scenario_service.py`

Owns scenario-pack loading from `backend/data/`:

- phase 2 retrieval scenarios
- phase 3 reasoning scenarios
- phase 4 interaction scenarios

Later, this can evolve into a unified evaluation library.

#### `adapters/*`

Wrap the existing `agents/*` modules without forcing an immediate rewrite.

This allows the refactor to happen safely in layers.

---

## Naming Direction

The backend should stop treating "MVP" as the core identity of product code.

Use "fall", "incident", "assessment", and "conversation" for durable names.

### Rename direction

- `MvpAssessment` -> `FallAssessment`
- `mvp_flow.py` -> split into `assessment_service.py` and `conversation_service.py`
- `mvp_router` -> `fall_router`
- `get_mvp_fall_questions` -> `build_fall_questions`
- `run_mvp_fall_assessment` -> `run_fall_assessment`
- `run_mvp_conversation_turn` -> `run_fall_conversation_turn`

### What can keep MVP naming temporarily

- `frontend/health-guard-ai/src/components/MvpTestPage.jsx`

That file is clearly a testing console, so the name is acceptable until the
final product surfaces are more stable.

---

## Test Taxonomy Cleanup

The test cleanup should not be "delete tests".
It should be "separate automated tests from manual evaluators".

### Keep under `backend/tests/`

These should become the real automated suite:

- `test_phase2_guidance_normalizer.py`
- `test_phase2_retrieval_engine.py`
- `test_phase2_retrieval_policy.py`
- `test_phase3_reasoning.py`
- `test_phase4_interaction.py`
- `test_phase4_session_turn.py`
- `test_api_mvp.py`

### Move out of `backend/tests/`

These are better treated as evaluation/demo scripts:

- `test_mvp_flow.py`
- `test_agent.py`
- `test_phase1.py`
- `test_vertex_search.py`

Suggested destination:

```text
backend/
  evals/
    smoke/
    manual/
    integration/
```

### Dependency cleanup

Add a real test dependency set to `backend/pyproject.toml`, including at least:

- `pytest`
- `pytest-asyncio`

This makes `backend/tests/` a real regression suite instead of a mixed folder of
Python entrypoints.

---

## Migration Strategy

This should be done as a staged refactor, not a big-bang rewrite.

### Stage 1. Establish new source-of-truth boundaries

Goal:
Create the new modules without changing behavior.

Actions:

- add `app/fall/assessment_service.py`
- add `app/fall/conversation_service.py`
- add `app/fall/execution_service.py`
- add `app/fall/session_store.py`
- add `app/fall/scenario_service.py`
- initially delegate to the current implementations

Result:
Routes stop importing `app.services.mvp_flow` directly.

Status:
Completed.

### Stage 2. Remove service/API inversion

Goal:
Move dispatch logic out of route-owned modules.

Actions:

- extract `trigger_emergency` and related execution types from `app/api/routes/emergency.py`
- move them into `app/fall/execution_service.py` or `app/services/emergency_dispatch.py`
- let the route call the service
- let assessment/conversation services call the service directly

Result:
API routes become thin again.

Status:
Completed.

### Stage 3. Split deterministic assessment from conversation flow

Goal:
Make the architecture easier to reason about.

Actions:

- move single-pass assessment functions into `assessment_service.py`
- move session turn and refresh orchestration into `conversation_service.py`
- keep `session_store.py` isolated

Result:
The repo has two clear workflows:

- deterministic assessment
- session-based conversation

without mixing both into one huge file.

Status:
Completed structurally, but still carrying compatibility naming.

### Stage 4. Reclassify tests and scripts

Goal:
Make the testing strategy legible.

Actions:

- convert manual scripts into `backend/evals/`
- keep only automated regression tests in `backend/tests/`
- add pytest dependencies
- normalize test naming and async usage

Result:
The project gains a real regression suite while preserving manual inspection
tools.

Status:
Mostly completed. Remaining work is to install the dev dependencies into the
active environment and run the suite through `pytest` directly.

### Stage 5. Rename contracts and routes

Goal:
Remove leftover "MVP" naming from product code.

Actions:

- rename central models and services to `fall_*`
- keep compatibility aliases temporarily where needed
- update frontend API usage only after backend aliases exist

Result:
The codebase becomes easier to understand as product code rather than prototype
glue.

Status:
Started, not finished.

---

## Proposed Canonical Flow

### Product flow

This is the final product-facing source of truth:

1. client starts or resumes a fall conversation session
2. communication service analyzes the latest turn
3. interaction policy decides the current target and mode
4. reasoning refresh runs only when needed
5. assessment service produces the latest grounded reasoning snapshot
6. execution service applies dispatch/notification side effects
7. conversation service returns transport-neutral session state

### Evaluation flow

This remains available for direct testing:

1. submit event, vitals, answers, and optional interaction hints
2. run deterministic retrieval + reasoning once
3. inspect the output contract and debug metadata

---

## File-by-File Recommendation

### Keep and promote

- `backend/app/api/routes/mvp.py`
  - keep behavior, but eventually rename to `fall.py`
- `backend/app/services/session_store.py`
  - move into the new `app/fall/` package
- `backend/agents/reasoning/phase3_reasoning.py`
  - keep as the core staged reasoning engine
- `backend/agents/reasoning/clinical_agent.py`
  - keep as live/fallback reasoning adapter
- `backend/agents/communication/interaction_policy.py`
  - keep as core Phase 4 policy logic
- `backend/agents/communication/session_agent.py`
  - keep as communication analysis/render adapter
- `backend/agents/bystander/retrieval_policy.py`
  - keep as retrieval planner
- `backend/agents/bystander/retrieval_engine.py`
  - keep as retrieval adapter
- `backend/agents/bystander/guidance_normalizer.py`
  - keep as guidance-shaping utility

### Split or demote

- `backend/app/services/mvp_flow.py`
  - split into dedicated fall-domain services
- `backend/agents/orchestrator.py`
  - demote to compatibility-only import surface
- `backend/tests/test_mvp_flow.py`
  - move to eval/manual coverage
- `backend/tests/test_agent.py`
  - move to eval/manual coverage
- `backend/tests/test_phase1.py`
  - move to eval/manual coverage or archive
- `backend/tests/test_vertex_search.py`
  - move to eval/manual coverage

### Keep as legacy or archive

- `backend/legacy/*`
  - keep preserved, but do not let it shape active architecture decisions

---

## Success Criteria

This consolidation is complete when:

- the backend has one clearly documented canonical product flow
- `MvpTestPage.jsx` exercises the same services the final product will use
- deterministic assessment remains available without becoming a competing flow
- API routes are thin and do not contain domain logic
- service modules do not import route modules
- `backend/tests/` contains only automated regression tests
- manual verification scripts live outside `backend/tests/`
- the architecture reads as durable product code, not phase-by-phase scaffolding

---

## Recommended Immediate Next Slice

The best next implementation slice is now:

1. keep `backend/app/api/routes/fall.py` as the active route module and preserve `mvp.py` only as a compatibility shim
2. keep `FallAssessment` as the primary schema name and migrate remaining active code type hints away from `MvpAssessment`
3. update route/test/doc references so `fall` is the visible product vocabulary
4. optionally move `backend/agents/orchestrator.py` under a clearer `legacy/` or `compat/` surface once the team is ready to break the old import path
5. install backend dev dependencies and run `pytest` as the canonical automated test entrypoint

This is the point where the refactor should switch from structural extraction to
language cleanup and final source-of-truth signaling.

### Suggested execution order

If we want the least risky order, do it like this:

1. route/module rename pass
2. contract rename pass with compatibility aliases
3. doc and test naming pass
4. pytest execution pass
5. optional orchestrator demotion or relocation
This keeps behavior stable while making the architecture much easier to read.
