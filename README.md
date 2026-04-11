# [Project Name Placeholder]

**Advancing Healthcare through Agentic AI for Malaysia's "Golden Hour"**

An autonomous, life-saving AI platform engineered for **Track 3: Vital Signs (Healthcare & Wellbeing)** of the Project 2030 MyAI Future Hackathon.

## 🚀 The Challenge & Our Solution

### The National Problem
As Malaysia transitions toward an "Aged Society," the public healthcare system—particularly emergency response—faces unprecedented strain. During critical events like sudden cardiac arrest or severe stroke, survival hinges on the "Golden Hour". Delays in symptom detection, chaotic bystander responses, and slow emergency dispatches cost lives.

### Our Solution
[Project Name] is a sovereign healthcare ecosystem designed to move beyond passive monitoring into **Autonomous Execution**. Harnessing the **Google AI Ecosystem Stack**, our platform automatically detects vital anomalies, triggers agentic workflows to orchestrate emergency services, sends patient profiles and precise GPS routing to nearby hospitals, and delivers localized First Aid guidance directly to bystanders—all in real-time.

---

## 🌟 Key Features

1. **Multimodal Medical Onboarding Dashboard:** 
   * Leverages **Gemini 2.0 Multimodal Capabilities** to instantly ingest medical history via documents, voice descriptions, or video uploads. Identifies key risk factors (e.g., past heart attacks) securely into a NoSQL Firebase database.
2. **Proactive Wearable & Environmental Monitoring:** 
   * Continuously retrieves heartbeat and blood pressure data from smartwatches.
   * **Vision-based Fall Detection:** Uses Gemini 2.0 Multimodal capabilities to analyze live camera feeds/video clips for behavioral anomalies like falls, providing immediate context for the medical cause.
3. **Autonomous Emergency Coordinator (Agentic Flow):** 
   * When an emergency is validated, the system triggers agentic workflows using **Firebase Genkit** and **Vertex AI Agent Builder**.
   * **User Safety Override:** Includes a "Cancel Emergency" button with a timeout period, allowing users to stop all autonomous actions in case of misjudgment or false alarms.
4. **Real-world Interventions (APIs):**
   * **Twilio API:** Instantly places synthesized VoIP voice calls to emergency contacts and local EMS, stating precise coordinates and patient conditions.
   * **Google Maps API:** Calculates routing to the nearest healthcare facility, automatically dispatching the patient's critical Firebase profile to that hospital's receiving endpoint.
5. **Contextual Bystander Guidance:**
   * Utilizes **Vertex AI Search (RAG)** grounded in national medical datasets to provide accurate, real-time CPR or medication-administration instructions to nearby caregivers via audio output.

---

## 🛠 Technology Stack & Google AI Ecosystem

We have strictly adhered to the "Build With AI" mandate to transition from Chat to Action.

### 🧠 The Intelligence (Brain)
*   **Gemini 2.0 Flash:** For high-speed, low-latency parsing of continuous wearable data streams.
*   **Gemini 2.0 Pro:** For complex clinical reasoning when a vital anomaly crosses critical thresholds, utilizing the patient's historical medical profile to avoid false positives and make dispatch decisions.

### ⚙️ The Orchestrator
*   **Vertex AI Agent Builder:** To construct specialized agents (e.g., Dispatch Agent, Reasoning Agent).
*   **Firebase Genkit:** Acts as the backend backbone managing the multi-step Agentic AI workflow sequence. Integrates seamlessly with Twilio and Google Maps tools.

### 📚 The Context
*   **Vertex AI Search (RAG):** Grounded using national Malaysian healthcare guidelines to retrieve accurate First Aid protocols for bystander instruction.

### 💻 The Development Lifecycle & Infrastructure
*   **Frontend:** React (Dashboard & UI)
*   **Backend:** Python via FastAPI
*   **Database:** Firebase NoSQL
*   **Deployment:** Google Cloud Workstations for coding, serverless deployment on Google Cloud Run.

---

## 🚀 Getting Started

### Prerequisites
* Node.js (v18+)
* Python (3.10+)
* Google Cloud Platform Account (Vertex AI, Cloud Run)
* Firebase Project Configuration
* Twilio & Google Maps API Keys

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-repo/project-name.git
   cd project-name
   ```

2. **Frontend Setup (React):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Backend Setup (Python/FastAPI):**
   ```powershell
   cd backend
   uv sync
   uv run uvicorn app.main:app --reload
   ```

4. **Environment Variables:**
   Create a `.env` file in the backend directory and populate `GEMINI_API_KEY`. The backend also accepts the older `GOOGLE_GENAI_API_KEY` name for backward compatibility.

## 📜 License
This project is open-source and submitted for the MyAI Future Hackathon 2026.
