# Backend Structure

This backend currently has four active layers:

- `app/`: FastAPI entrypoint, routes, runtime bootstrap, active services, and fall-domain wrappers
- `agents/`: reusable retrieval, reasoning, communication, and question logic
- `db/` and `data/`: persistence access plus local fallback policy and guidance assets
- `legacy/`: preserved older prototypes that are not part of the active product path

The practical source of truth today is:

- `app/api/routes/fall.py`
- `app/fall/*`
- `agents/*`

That source of truth works, but it is currently overloaded. The next cleanup
direction is documented in [../BackendConsolidationPlan.md](../BackendConsolidationPlan.md).

## Run locally

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

## Run backend checks

```powershell
cd backend
uv run tests/test_clinical_reasoning_policy.py
uv run tests/test_phase2_retrieval_policy.py
uv run tests/test_phase2_retrieval_engine.py
uv run tests/test_phase2_guidance_normalizer.py
```

Some files under `tests/` are still manual verification scripts rather than a
true automated pytest suite. The manual runners now live under `evals/manual/`,
and the remaining cleanup is to install the new pytest dependencies and run the
suite through pytest directly.

## Utility scripts

Helper scripts now live under `scripts/` so the backend root stays focused on
application code and project configuration.

## Seed Firestore

```powershell
cd backend
uv run scripts/seed_firestore.py
```

If `FIRESTORE_PROJECT_ID` and Google Cloud credentials are configured, the sample patient is written to Firestore.
Otherwise the backend falls back to the local sample profile in `data/sample_patient.json`.

## Vertex AI Search

The clinical and bystander flows can retrieve grounded medical guidance through `agents/bystander/knowledge_base.py`.

To use a real Vertex AI Search app, configure:

- `VERTEX_AI_SEARCH_PROJECT_ID`
- `VERTEX_AI_SEARCH_LOCATION`
- `VERTEX_AI_SEARCH_ENGINE_ID`

The runtime also needs Google Application Default Credentials so the Discovery Engine client can authenticate.

If those are not configured yet, the backend falls back to `data/medical_guidance_fallback.json`.

You can verify the live app connection with:

`.\.venv\Scripts\python.exe evals/manual/vertex_search_inspector.py "fall first aid guidance"`

## Active Product Flow

The backend currently supports two fall-flow entry styles:

### 1. Session-based conversation flow

This is the current Phase 4 product-facing path and the flow used by
`frontend/health-guard-ai/src/components/MvpTestPage.jsx`.

- `POST /api/v1/events/fall/session-turn`
- `GET /api/v1/events/fall/session-state/{session_id}`
- `GET /api/v1/events/fall/session-events/{session_id}`

This flow is intended to remain the long-term product direction because it can
support:

- patient-first interaction
- bystander takeover
- selective reasoning refresh
- execution updates
- transport-neutral progression toward future live mode

### 2. Deterministic assessment flow

These endpoints still exist and are useful for evaluation, debugging, and
deterministic backend checks:

- `POST /api/v1/events/fall/questions`
- `POST /api/v1/events/fall/assess`

The question endpoint returns 2-3 targeted questions.
The assessment endpoint runs retrieval and reasoning once, returns the current
assessment contract, and starts the mock dispatch layer when the assessed action
is `emergency_dispatch`.

## Root Layout

- `app/`: FastAPI application entrypoint, routes, fall-domain services, and runtime bootstrap.
- `agents/`: Shared agent logic used by the MVP pipeline.
- `db/`: Firestore access and patient profile loading.
- `data/`: Local fallback patient and guidance data.
- `tests/`: Automated regression-oriented checks.
- `evals/`: Manual runners and local inspection scripts that are not part of pytest collection.
- `scripts/`: Utility scripts such as seeding sample data.
- `legacy/`: Preserved older prototypes that are not part of the main MVP path.
- `.env`: Local environment configuration for development.
- `pyproject.toml`: Python dependency manifest.
- `uv.lock`: Locked dependency graph for `uv`.
- `README.md`: Backend orientation and run instructions.

## Active Layout

- `app/main.py`: FastAPI entrypoint that mounts the active routers.
- `app/core/bootstrap.py`: Shared runtime bootstrap for `.env` loading and logging.
- `app/api/routes/fall.py`: Main frontend-facing fall-flow endpoints.
- `app/fall/`: Fall-domain service boundary introduced to absorb the active product flow cleanly.
- `app/api/routes/emergency.py`: Mock emergency dispatch router and in-memory incident tracker.
- `app/fall/execution_service.py`: Domain-owned emergency execution and incident-tracking logic.
- `agents/shared/`: Shared config and schemas used across the backend.
- `agents/sentinel/`: Event and vitals inspection logic.
- `agents/triage/`: Question generation for deterministic fall intake and evaluation flows.
- `agents/reasoning/`: Clinical reasoning service and deterministic reasoning policy helpers.
- `agents/communication/`: Phase 4 interaction policy and communication analysis/render helpers.
- `agents/bystander/`: Grounded guidance retrieval and bystander instruction helpers.
- `agents/coordinator/`: Older dispatch decision logic kept for experiments.
- `db/`: Firestore access and sample patient loading.
- `data/`: Local fallback patient and medical guidance data.

## Tests And Scripts

- `tests/test_api_fall.py`: API-level verification across the current fall routes.
- `tests/test_phase2_guidance_normalizer.py`: Unit checks for guidance shaping from retrieval buckets.
- `tests/test_phase2_retrieval_engine.py`: Unit checks for bucketed retrieval output.
- `tests/test_phase2_retrieval_policy.py`: Unit checks for retrieval intent and query planning.
- `tests/test_clinical_reasoning_policy.py`: Unit checks for the deterministic reasoning policy.
- `tests/test_phase4_interaction.py`: Interaction-policy checks for target selection and refresh rules.
- `tests/test_phase4_session_turn.py`: Session-loop checks for the conversation flow.
- `evals/manual/deterministic_fall_flow_runner.py`: Manual runner for the deterministic fall evaluation flow using the active fall services.
- `evals/manual/phase1_foundation_check.py`: Manual verification for foundation stubs and schemas.
- `evals/manual/vertex_search_inspector.py`: Manual Vertex AI Search inspection utility.
- `scripts/seed_firestore.py`: Helper for seeding the sample patient into Firestore.
- `pyproject.toml`: Canonical dependency manifest for `uv`.
- `pytest.ini`: Pytest collection and asyncio configuration for the automated suite.

## Architecture Notes

- The current active fall path is: `app/api/routes/fall.py` -> `app/fall/*` -> `agents/*`.
- The Phase 4 session flow is the best candidate for the long-term canonical product workflow.
- The question/assessment flow should be preserved as a deterministic evaluation entrypoint.
- `legacy/` is for preserved prototypes that we are not deleting, but that are not part of the main MVP path.
- `Vertex AI Search` provides grounded snippets and references for medical guidance rather than whole attached documents.
- The backend cleanup roadmap now lives in `../BackendConsolidationPlan.md`.
