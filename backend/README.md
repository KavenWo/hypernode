# Backend Structure

This backend contains a small FastAPI application plus Genkit-based agent flow logic.

## Run locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Files

- `app/main.py`: FastAPI entrypoint and flow import hook.
- `app/agents/config.py`: Genkit configuration and model setup.
- `app/agents/schemas.py`: Pydantic data models used across the flow.
- `app/agents/tools.py`: Mock integration functions for dispatch actions.
- `app/agents/flows.py`: Main agent orchestration flow.
- `test_phase1.py`: Lightweight local verification script for schemas and mock tools.
- `requirements.txt`: Python dependencies for the backend.
