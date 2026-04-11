# Backend Structure

This backend now has a clearer split between:

- active application code under `app/`
- reusable agent logic under `agents/`
- persistence/fallback data under `db/` and `data/`
- preserved older prototypes under `legacy/`

The goal is to make the MVP path obvious without deleting older teammate files.

## Run locally

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

## Run tests

```powershell
cd backend
uv run tests/test_phase1.py
uv run tests/test_agent.py
uv run tests/test_mvp_flow.py
```

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

`.\.venv\Scripts\python.exe tests/test_vertex_search.py "fall first aid guidance"`

## MVP Flow

The backend now supports the MVP loop as a centralized two-step flow:

1. `POST /api/v1/events/fall/questions`
2. `POST /api/v1/events/fall/assess`

The first endpoint returns 2-3 questions. The second endpoint runs reasoning
once, returns the MVP result, and automatically starts the mock dispatch layer
when the assessed action is `emergency_dispatch`.

The assessment response includes:

- `severity`
- `action`
- `instructions`
- `reasoning`
- `dispatch_triggered`
- `incident_id`

## Root Layout

- `app/`: FastAPI application entrypoint, routes, services, and runtime bootstrap.
- `agents/`: Shared agent logic used by the MVP pipeline.
- `db/`: Firestore access and patient profile loading.
- `data/`: Local fallback patient and guidance data.
- `tests/`: Local verification scripts for MVP flow, agents, and Vertex search.
- `scripts/`: Utility scripts such as seeding sample data.
- `legacy/`: Preserved older prototypes that are not part of the main MVP path.
- `.env`: Local environment configuration for development.
- `pyproject.toml`: Python dependency manifest.
- `uv.lock`: Locked dependency graph for `uv`.
- `README.md`: Backend orientation and run instructions.

## Active Layout

- `app/main.py`: FastAPI entrypoint that mounts the active routers.
- `app/core/bootstrap.py`: Shared runtime bootstrap for `.env` loading and logging.
- `app/api/routes/mvp.py`: Main frontend-facing MVP endpoints.
- `app/api/routes/emergency.py`: Mock emergency dispatch router and in-memory incident tracker.
- `app/services/mvp_flow.py`: Centralized MVP flow for questions, single-pass reasoning, and optional dispatch.
- `agents/shared/`: Shared config and schemas used across the backend.
- `agents/sentinel/`: Event and vitals inspection logic.
- `agents/triage/`: Question generation for the 2-3 question MVP intake step.
- `agents/reasoning/`: Clinical reasoning agent and prompt builder.
- `agents/bystander/`: Grounded guidance retrieval and bystander instruction helpers.
- `agents/coordinator/`: Older dispatch decision logic kept for experiments.
- `db/`: Firestore access and sample patient loading.
- `data/`: Local fallback patient and medical guidance data.

## Legacy And Compatibility

- `legacy/triage_agent.py`: Preserved teammate triage prototype.
- `legacy/vitals.py`: Preserved standalone vitals router prototype.
- `agents/orchestrator.py`: Compatibility wrapper plus older direct-dispatch experiment.

## Tests And Scripts

- `tests/test_api_mvp.py`: API-level verification for the exact frontend MVP sequence.
- `tests/test_mvp_flow.py`: Direct shared-service verification for the MVP flow.
- `tests/test_phase1.py`: Lightweight schema and mock-tool verification.
- `tests/test_agent.py`: End-to-end local workflow runner for the Gemini-backed flow.
- `tests/test_vertex_search.py`: Vertex AI Search inspection utility.
- `scripts/seed_firestore.py`: Helper for seeding the sample patient into Firestore.
- `pyproject.toml`: Canonical dependency manifest for `uv`.

## Architecture Notes

- The current MVP path is: `app/api/routes/mvp.py` -> `app/services/mvp_flow.py` -> `agents/*`.
- `legacy/` is for preserved prototypes that we are not deleting, but that are not part of the main MVP path.
- `Vertex AI Search` provides grounded snippets and references for medical guidance rather than whole attached documents.
