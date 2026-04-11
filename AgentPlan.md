# AI Agents Architecture Guide

This document explains how the backend agent system is structured, what each area is responsible for, and how it should merge into the broader backend.

This is the core intelligence layer of the project.

---

# Overall Concept

Our system is designed as an agentic backend workflow:

1. Detect event
2. Analyze situation
3. Decide severity
4. Decide response
5. Trigger execution and guidance

Each step is handled by a dedicated agent role, coordinated through one orchestrator.

---

# Folder Structure

```text
backend/
  app/
    main.py

  agents/
    orchestrator.py

    shared/
      config.py
      schemas.py

    sentinel/
      vision_agent.py
      vital_agent.py
      prompts.py

    reasoning/
      clinical_agent.py
      prompts.py

    coordinator/
      dispatcher_agent.py
      prompts.py

    bystander/
      rag_agent.py
      prompts.py

    execution/
      emergency_actions.py

  db/
    firebase_client.py
    models.py

  data/
    sample_patient.json
    medical_guidance_fallback.json
```

---

# Shared Files

## `agents/shared/config.py`

Purpose:

- Configures Gemini client access
- Defines model defaults and fallbacks
- Keeps API-key wiring out of agent logic

## `db/firebase_client.py`

Purpose:

- Loads patient state from Firestore
- Seeds one sample patient for testing
- Falls back to local test data while cloud setup is incomplete

## `agents/shared/schemas.py`

Purpose:

- Defines shared Pydantic contracts used by all agents and routes

Examples:

- `FallEvent`
- `VisionAssessment`
- `ClinicalAssessment`
- `DispatchDecision`
- `BystanderInstruction`

## `agents/orchestrator.py`

Purpose:

- Controls the full workflow
- Calls agents in sequence
- Decides when to invoke execution helpers
- Keeps end-to-end flow logic in one place

---

# Agent Responsibilities

## Sentinel Layer

### `agents/sentinel/vision_agent.py`

Purpose:

- Interprets the incoming fall signal
- Produces an initial severity hint

Question it answers:

- "Did a fall likely happen?"

### `agents/sentinel/vital_agent.py`

Purpose:

- Interprets optional vital-sign input
- Produces an anomaly/risk hint

Question it answers:

- "Do vitals increase urgency?"

---

## Reasoning Layer

### `agents/reasoning/clinical_agent.py`

Purpose:

- Uses Gemini to produce the main clinical assessment
- Combines event input, patient profile, and grounded emergency knowledge

Question it answers:

- "How serious is this event?"

### `agents/reasoning/prompts.py`

Purpose:

- Stores prompt-building logic for the clinical agent

---

## Coordinator Layer

### `agents/coordinator/dispatcher_agent.py`

Purpose:

- Converts the assessment into a structured response decision

Question it answers:

- "What should the system do next?"

### `agents/coordinator/prompts.py`

Purpose:

- Stores prompt-building logic for the dispatcher agent

---

## Bystander Layer

### `agents/bystander/rag_agent.py`

Purpose:

- Produces helper instructions for nearby people
- Retrieves grounded medical guidance from Vertex AI Search when configured
- Falls back to local emergency guidance while cloud setup is incomplete

Question it answers:

- "What should people nearby do right now?"

---

# Execution Boundary

## `agents/execution/emergency_actions.py`

Purpose:

- Holds mock side-effect functions during agent development
- Represents the handoff point into real backend integrations

Examples:

- Twilio call trigger
- Nearest hospital lookup
- Ambulance dispatch helper

Important:

- This is not long-term agent logic
- When merged with the backend member's work, these functions should point to modules in:
  - `backend/integrations/twilio_caller.py`
  - `backend/integrations/maps_router.py`
  - `backend/integrations/hospital_webhook.py`

So the design principle is:

- `agents` decide
- `integrations` execute

---

# Merge Strategy

The intended merged backend structure should look like:

```text
backend/
  main.py
  routers/
  integrations/
  db/
  agents/
```

In that final structure:

- `routers/` handles frontend or device requests
- `agents/` handles reasoning and orchestration
- `integrations/` handles Twilio, Maps, hospital webhooks, and other external calls
- `db/` handles Firebase and persistence
- `Vertex AI Search` handles factual medical guidance retrieval

---

# MVP Goal

A working backend pipeline that:

- accepts a fall event
- classifies severity
- decides what action to take
- can trigger execution helpers
- can generate bystander guidance

---

# Key Design Principle

Each agent should answer one question:

- Vision Agent: "Did a fall happen?"
- Vital Agent: "Do the vitals make this worse?"
- Clinical Agent: "How serious is it?"
- Dispatcher Agent: "What should we do?"
- Bystander Agent: "What should nearby people do?"

The orchestrator combines those answers into one backend-controlled flow.
