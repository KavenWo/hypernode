# Backend Structure

This backend contains a small FastAPI application plus a modular Google GenAI SDK-based agent workflow.

## Run locally

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

## Run tests

```powershell
cd backend
uv run test_phase1.py
uv run test_agent.py
```

## Seed Firestore

```powershell
cd backend
uv run seed_firestore.py
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

`.\.venv\Scripts\python.exe test_vertex_search.py "fall first aid guidance"`

## Files

- `app/main.py`: FastAPI entrypoint and API route that triggers the workflow.
- `agents/orchestrator.py`: High-level flow controller that coordinates every agent.
- `agents/shared/`: Shared configuration and schemas used across all agents.
- `agents/sentinel/`: Detection agents that interpret the incoming event and vitals.
- `agents/reasoning/`: Clinical reasoning agent and its prompts.
- `agents/coordinator/`: Dispatch coordination agent and its prompts.
- `agents/bystander/`: Bystander guidance agent and prompt helpers.
- `agents/execution/`: Current mock execution boundary that later maps to backend `integrations/`.
- `db/`: Firestore models and patient profile access.
- `data/`: Local fallback records for patient state and emergency guidance.
- `test_phase1.py`: Lightweight local verification script for schemas and mock tools.
- `test_agent.py`: End-to-end local workflow runner for the Gemini-backed flow.
- `seed_firestore.py`: Helper for seeding the sample patient into Firestore.
- `pyproject.toml`: Canonical dependency manifest for `uv`.

## Architecture Notes

- `agents/` holds reasoning and orchestration only.
- `agents/execution/` is a temporary boundary for mocked side effects during development.
- `db/` holds live patient state, with a local fallback record for setup and tests.
- `Vertex AI Search` should hold emergency medical facts and procedural guidance.
- When merging with the backend member's work, functions in `agents/execution/` should move behind `integrations/` modules such as Twilio, Maps, and hospital webhook clients.
