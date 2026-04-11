# 🔥 Overall App Summary

## Core Idea

An AI-powered emergency system that detects a fall, gathers patient condition, reasons using medical knowledge, and decides the next action (monitor, call family, or call ambulance), while guiding the user or bystander.

---

## 🧠 Overall App Flow

1. User opens Dashboard
2. User uploads or triggers fall simulation
3. System detects fall
4. AI asks 2–3 triage questions
5. User answers
6. Backend gathers:

   * patient profile
   * triage answers
   * medical knowledge (Vertex AI Search)
7. Reasoning Agent evaluates situation
8. System outputs:

   * severity
   * action
   * explanation
9. Backend executes:

   * notify family OR
   * simulate ambulance call
10. Frontend displays:

* result
* action taken
* instructions

11. Incident is stored for history

---

# 🧩 Core Features

* Fall simulation (video upload)
* Patient profile system
* Live monitoring dashboard (dummy vitals)
* AI triage questions
* AI reasoning + decision making
* Medical knowledge retrieval (Vertex AI Search)
* Action execution (simulate calls/messages)
* Emergency guidance (instructions)
* Incident history tracking

---

# 🔴 Agent Responsibilities (AI)

* Reasoning Agent:

  * takes all inputs → outputs severity + action + reason
* Interaction Agent:

  * asks questions and extracts useful info
* Vertex AI integration:

  * retrieves medical context (extractive answers)
* Output formatting:

  * structured JSON for backend
  * simple message for frontend
* Script generation:

  * ambulance + family messages

---

# 🔵 Backend Responsibilities

* Anonymous login (user/session handling)
* Firestore setup (patients, incidents, history)
* Patient profile management
* Incident lifecycle management
* Store triage answers + AI results
* Dispatcher execution (simulate actions)
* Store scripts/messages
* History logging
* API endpoints for frontend
* Cloud Run deployment

---

# 🟢 Frontend Responsibilities

* Dashboard (main UI)

  * profile card
  * vitals display
  * video upload
  * emergency panel
* Triage interaction UI (buttons)
* Display results:

  * severity
  * action
  * explanation
  * instructions
* Profile view (edit patient info)
* History view (past incidents)
* Smooth UX (clear states, loading, transitions)

---

# 🏥 Medical / Knowledge Responsibilities

* Prepare structured medical knowledge files
* Cover:

  * DRABC flow
  * CPR steps
  * bleeding control
  * fall severity & red flags
  * conscious vs unconscious handling
* Ensure:

  * accuracy
  * clarity
  * structured format
* Upload to Vertex AI Search
* Serve as ground truth for AI reasoning

---

# 🚀 Final Product Goal

A clean, working prototype where:

* user triggers a fall
* AI evaluates condition using real medical knowledge
* system makes a decision
* action is executed
* user receives clear guidance

The system should feel like a **real emergency assistant**, not just a demo.
