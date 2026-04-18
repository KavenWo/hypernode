# 🚑 AI Emergency Fall Response System — Final MVP Flow

## 🎯 Objective

Build a **reliable, controlled, and intelligent emergency response system** that demonstrates:

* Fall detection from video
* Structured communication with patient / bystander
* AI-powered reasoning for decision making
* Deterministic execution of emergency actions
* Clear and guided emergency assistance (e.g. CPR)

The system must prioritize:

* **Reliability over complexity**
* **Clarity over flexibility**
* **Controlled scenarios over open-ended behavior**

---

# 🧠 System Architecture Overview

The system consists of 3 main agents:

## 1. Sentinel Agent (Detection)

* Analyzes video input
* Detects whether a fall has occurred
* Outputs a simple explanation of the event

---

## 2. Communication Agent (Control Flow)

* Handles ALL interaction with patient or bystander
* Asks structured questions
* Collects inputs
* Enforces flow (prevents drift)
* Performs input validation and signal extraction
* Maintains structured state

---

## 3. Reasoning Agent (Decision Engine)

* Receives structured state from Communication Agent
* Uses Vertex AI Search for medical grounding
* Produces FINAL decision output:

  * scenario
  * severity
  * action
  * reason
  * instructions
  * confidence
* Runs at most **2–3 times**
* **Stops completely after final output**

---

## 4. Execution Agent (Deterministic)

* Executes actions based on reasoning output
* Handles:

  * ambulance dispatch (simulated)
  * family notification
  * CPR flow
* Uses Communication Agent to deliver instructions
* No AI decision-making

---

# 🔁 End-to-End System Flow

## STEP 1 — Sentinel Agent (Video Input)

Input:

* Uploaded video

Output:

* Fall detected (true/false)
* Explanation:

  > “An elderly individual appears to have fallen and is not moving.”

---

## STEP 2 — Immediate Actions

Once fall is detected:

* 📞 Notify family (initial alert)
* 🟡 Start monitoring
* ❌ Do NOT trigger reasoning yet

---

## STEP 3 — Communication Agent Starts

> “Are you okay?”

---

## STEP 4 — Response Handling

### Case A — No response

* Wait ~10 seconds
* Send minimal state to Reasoning Agent

---

### Case B — Response exists

Communication Agent:

* validates input
* extracts signals
* stores flags

---

## STEP 5 — Bystander Check

> “Is anyone nearby who can assist?”

UI:

* Button: “I am here (Bystander)”

Logic:

```
if button_clicked:
    mode = "bystander"
else:
    mode = "patient_only"
```

---

## STEP 6 — Critical Questions

Communication Agent asks:

* “Is the patient conscious?”
* “Is the patient breathing normally?”

Optional extracted signals:

* bleeding
* pain
* mobility

---

# 🧠 Reasoning Flow

## Reasoning Call 1 — Initial Check

Triggered when:

* no response

Input:

```
{
  "response": "none",
  "bystander": false,
  "flags": []
}
```

---

## Reasoning Call 2 — Main Decision (CORE)

Input:

```
{
  "conscious": false,
  "breathing": false,
  "bystander": true,
  "flags": ["bleeding"]
}
```

Output:

```
{
  "scenario": "CPR",
  "severity": "critical",
  "action": "call_ambulance",
  "instructions": "Start CPR immediately",
  "confidence": 0.95
}
```

---

## Reasoning Call 3 — Optional

Only if:

```
confidence < 0.8
```

---

# 🎯 Scenario Control

## Scenario 1 — CPR (Critical)

* unconscious
* not breathing
* bystander present

→ call ambulance
→ start CPR

---

## Scenario 2 — No Response

* no interaction

→ timeout
→ auto dispatch

---

## Scenario 3 — Non-Critical

* conscious
* breathing normal

→ notify family
→ advise rest

---

# 🫀 CPR Flow (Execution Phase)

* Reasoning stops
* Execution Agent controls flow
* Communication Agent delivers steps

Steps:

1. Check airway
2. Chest compressions
3. Maintain rhythm

User responses:

* OK
* Can’t follow

---

# 🧱 Communication Agent Input Rules

## Rule 1 — Must answer

If irrelevant input:

> “I understand, but I need to confirm: is the patient conscious?”

---

## Rule 2 — Extract signals

Input:

> “He’s bleeding”

→ store flag

---

## Rule 3 — No drift

* extra info does NOT change scenario

---

# 🧾 Final Output (Terminal)

This output ENDS reasoning.

```
{
  "scenario": "CPR",
  "severity": "critical",
  "action": "call_ambulance",
  "confidence": 0.95,
  "reason": "Patient is unconscious and not breathing",
  "instructions": "Start CPR immediately",
  "flags_used": ["bleeding"]
}
```

---

# 🔒 Constraints

* Max 2–3 reasoning calls
* No open-ended chat
* No uncontrolled branching
* Execution always deterministic
* Always notify family

---

# 🚀 Final Behavior

1. Detect fall
2. Communicate
3. Collect structured input
4. Reason once
5. Execute
6. Guide

---

# 🧠 Philosophy

Not a full medical system.

A **reliable emergency decision system**.

---

# ✅ Success Criteria

* Works consistently
* No demo failure
* Clear reasoning
* Smooth UX

---

# 🔥 Core Narrative

“Detection → Decision → Action”
