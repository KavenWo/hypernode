# 🤖 AI Agents Architecture Guide

This document explains how the AI agents system is structured, what each file is responsible for, and how everything connects together.

This is the **core intelligence layer** of the project.

---

# 🧠 Overall Concept

Our system is designed as an **Agentic AI workflow**:

1. Detect event (e.g. fall)
2. Analyze situation
3. Decide severity
4. Trigger actions
5. Provide guidance

Each step is handled by a **separate agent**, coordinated through an orchestrator.

---

# 📁 Folder Structure

```
agents/
  genkit.config.ts
  prompts.ts
  schemas.ts
  tools.ts
  orchestrator.ts

  sentinel/
    vital_agent.ts
    vision_agent.ts

  reasoning/
    clinical_agent.ts

  coordinator/
    dispatcher_agent.ts

  bystander/
    rag_agent.ts
    audio_stream.ts
```

---

# 🧩 Core Files (Shared)

## 1. genkit.config.ts

### Purpose:

Initializes connection to Google AI (Gemini) and Genkit.

### Responsibilities:

* Setup model (Gemini Flash / Pro)
* Configure environment
* Export model instance for agents

---

## 2. schemas.ts

### Purpose:

Defines all data structures used across the system.

### Why important:

Ensures frontend, backend, and agents all use the same format.

### Examples:

* UserProfile
* FallEvent
* ClinicalAssessment
* DispatchDecision
* BystanderInstruction

---

## 3. prompts.ts

### Purpose:

Stores all AI prompts in one place.

### Why:

* Keeps agent files clean
* Easier to update prompts
* Reusable across agents

### Examples:

* Clinical reasoning prompt
* Fall severity classification
* Bystander instructions

---

## 4. tools.ts

### Purpose:

Defines helper functions used by agents.

### Examples:

* Fetch user profile
* Send alert to family
* Trigger emergency dispatch
* Retrieve protocol

### Note:

Start with **mock functions first**.

---

## 5. orchestrator.ts

### Purpose:

Controls the full AI workflow.

### Responsibilities:

* Calls agents in correct order
* Handles decision flow
* Manages escalation logic

### Example flow:

```
Fall detected
→ Vision Agent
→ Clinical Agent
→ Dispatcher Agent
→ Bystander Agent
```

---

# 🤖 Agent Files

---

## 🟢 Sentinel Layer (Detection)

### vision_agent.ts

#### Purpose:

Detect whether a fall likely occurred.

#### Input:

* FallEvent (mocked or real)

#### Output:

```
{
  "fallDetected": true,
  "confidence": 0.92,
  "motionState": "no_movement"
}
```

---

### vital_agent.ts

#### Purpose:

Detect abnormal vitals (optional for MVP)

#### Input:

* Heart rate, SpO2, etc.

#### Output:

* anomaly detected or not

---

## 🧠 Reasoning Layer

### clinical_agent.ts

#### Purpose:

Decide how serious the situation is.

#### Input:

* User profile
* Fall event
* (optional) vitals

#### Output:

```
{
  "severity": "high",
  "recommendedAction": "emergency_dispatch"
}
```

#### Notes:

* This is the **main intelligence agent**
* Uses Gemini model

---

## 🚑 Coordinator Layer

### dispatcher_agent.ts

#### Purpose:

Convert reasoning result into actions.

#### Responsibilities:

* Decide what to do next:

  * Do nothing
  * Notify family
  * Call emergency
  * Trigger guidance

#### Output:

```
{
  "callEmergency": true,
  "callFamily": true
}
```

---

## 🧍 Bystander Layer

### rag_agent.ts

#### Purpose:

Provide grounded instructions.

#### Input:

* Scenario type (e.g. fall)

#### Output:

* Step-by-step instructions

---

### audio_stream.ts

#### Purpose:

Convert instructions into readable or spoken format.

#### Example:

* Combine steps into natural speech

---

# 🔗 How Everything Connects

## Full Flow:

```
Input Event (Fall)
↓
Vision Agent
↓
Clinical Agent
↓
Dispatcher Agent
↓
Bystander Agent
↓
Final Output (Actions + Instructions)
```

---

## Example Execution:

```
Fall detected
→ Vision confirms fall
→ Clinical agent says HIGH risk
→ Dispatcher triggers emergency
→ RAG agent provides instructions
```

---

# 🧪 Development Approach

## Phase 1 (NOW)

* Define schemas
* Create mock inputs
* Build agent structure
* Use fake data

## Phase 2

* Integrate Gemini (AI Studio / API)
* Replace mock logic with AI reasoning

## Phase 3

* Add real tools (Twilio, Maps)
* Add RAG (Vertex AI Search)

---

# ⚠️ Important Notes

* Do NOT build everything at once
* Start with **mock data**
* Ensure all agents return **structured JSON**
* Keep logic simple first

---

# 🎯 MVP Goal

A working pipeline that:

* Accepts a fall event
* Classifies severity
* Decides action
* Outputs instructions

---

# 🧠 Key Design Principle

Each agent should answer ONE question:

* Vision Agent → "Did a fall happen?"
* Clinical Agent → "How serious is it?"
* Dispatcher → "What should we do?"
* RAG Agent → "What should people do?"

---

# 🚀 Final Goal

A fully connected system where:

* AI makes decisions
* System executes actions
* Users receive real-time guidance
