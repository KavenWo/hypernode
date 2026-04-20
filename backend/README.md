# ⚙️ ElderGuard AI — Backend Services

The ElderGuard backend is built with FastAPI and provides an agentic reasoning runtime powered by the Vertex AI Agent Development Kit (ADK).

## 🏗️ Core Architecture

The backend is organized into three primary layers:

- **`app/`**: FastAPI application entrypoint, REST routes, and domain-specific services (e.g., fall detection, execution).
- **`agents/`**: Reusable agent logic including Reasoning (Gemini), Communication, and grounded Retrieval (Vertex AI Search).
- **`db/` & `data/`**: persistence layer for patient profiles and incidents, including local fallbacks for medical guidance.

---

## 🚀 Run Locally

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

## 🛠️ Seed Firestore

```powershell
cd backend
uv run scripts/seed_firestore.py
```

If `FIRESTORE_PROJECT_ID` and Google Cloud credentials are configured, the sample patient is written to Firestore.
Otherwise the backend falls back to the local sample profile in `data/sample_patient.json`.

---

## 🔐 Firebase And Firestore Setup

### 1. Enable the Firebase services

In the Firebase console for your project:

- enable `Firestore Database`
- enable `Authentication`
- turn on the `Anonymous` sign-in provider

### 2. Backend credentials

Create a local `backend/.env` from `.env.example` and fill in:

- `GOOGLE_CLOUD_PROJECT`
- `FIRESTORE_PROJECT_ID`
- `FIREBASE_PROJECT_ID`
- `GOOGLE_APPLICATION_CREDENTIALS`

### 3. Frontend credentials

Create a local `frontend/health-guard-ai/.env` from `.env.example` and fill in the Firebase Web App config:

- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_API_BASE_URL`

---

## ⚡ Active Product Flow

The backend supports a stateful session-based conversation flow:

- `POST /api/v1/events/fall/session-turn`: Processes an incoming turn in the emergency conversation.
- `GET /api/v1/events/fall/session-state/{session_id}`: Retrieves the current assessed state and action decisions.
- `GET /api/v1/events/fall/session-events/{session_id}`: Retrieves the full audit log of session events.

## 📁 Project Structure

- **`app/`**: FastAPI application entrypoint, routes, and core services.
- **`agents/`**: Core agentic logic (Reasoning, Communication, Retrieval).
- **`db/`**: Persistence layer and patient profile handling.
- **`data/`**: Fallback patient data and clinical guidance local stores.
- **`experiments/`**: Research and experimental agent configurations.
- **`scripts/`**: Utility scripts (e.g., Firestore seeding).
- **`Dockerfile`**: Container definition for Google Cloud Run deployment.

## 🧠 Architecture Highlights

- **ADK Integration**: The system uses the Vertex AI Agent Development Kit for structured agent orchestration.
- **Phase 4 Session Flow**: The primary interaction path uses a stateful session model to maintain context across multi-turn emergency dialogues.
- **Grounded Reasoning**: The Reasoning Agent (Gemini) is grounded by real-time medical guidance retrieved via **Vertex AI Search**.
- **Execution Layer**: Transitions from AI reasoning to deterministic actions (Dispatch, Notifications) are handled by the `execution_service.py`.

---
*Developed by the **Hypernode Team** for Project 2030 (2026).*
