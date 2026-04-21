# 🚑 ElderGuard — Intelligent Emergency Fall Response System

## 🔗 Project Links

* **Live Demo**: [https://elder-guard-web-848039689147.us-central1.run.app]
* **Live Backend**: [https://elder-guard-api-848039689147.us-central1.run.app/]
* **GitHub**: [https://github.com/KavenWo/hypernode]
* **Demo Video**: [https://drive.google.com/file/d/1IWPZKLI9tv-YwZMn4xhD0I4PxLt1Yi8V/view]
* **Submission Slides**: [https://docs.google.com/presentation/d/1p5mnrbgPwq01if81_ZVz5XyvpN-q9IYicVPZ5zNyvqs/edit?usp=sharing]

> The system is fully deployed on Google Cloud Run. Local setup is optional for evaluation.

---

## 🧠 Overview

**ElderGuard** is an AI-powered emergency response system designed to detect falls, understand real-world situations, and execute appropriate actions in real time.

Unlike traditional fall detection systems that only alert, ElderGuard:

* Communicates with patients or bystanders
* Performs intelligent reasoning
* Guides emergency response (e.g. CPR)
* Executes critical actions such as dispatch and notifications

---

## ❗ Problem

Falls among elderly individuals are a major healthcare concern, especially in home environments where immediate assistance is unavailable.

Delayed response can lead to:

* Severe injury
* Long-term complications
* Increased mortality risk

Existing systems lack:

* Real-time understanding
* Decision-making capability
* Guided intervention

---

## 💡 Solution

ElderGuard provides an end-to-end intelligent response system:

1. Detects fall using vision AI
2. Initiates communication with patient or bystander
3. Collects structured medical signals
4. Uses AI reasoning to assess severity
5. Executes appropriate emergency actions

---

## ⚙️ Key Features

* Fall detection from video input
* Real-time communication with patient or bystander
* AI-driven reasoning for severity assessment
* CPR guidance system (step-by-step)
* Emergency dispatch simulation
* Family notification system
* Controlled multi-agent workflow for reliability
* Dashboard for monitoring and interaction

---

## 🧠 System Architecture

ElderGuard is built using a multi-agent architecture:

### Core Agents

* **Sentinel Agent** — Detects fall events from video input
* **Communication Agent** — Handles structured interaction with patient or bystander
* **Reasoning Agent** — Performs AI-based decision making using medical context
* **Execution Agent** — Executes deterministic actions such as dispatch and guidance

---

### Supporting Technologies

* Vertex AI Agent Development Kit (ADK)
* Gemini 2.5 Flash and Gemini 2.5 Pro
* Vertex AI Search for grounded knowledge
* Google Cloud Run for deployment

---

## 🔁 System Flow

1. Fall detected via video
2. System initiates communication
3. Collects patient or bystander input
4. AI evaluates situation using reasoning
5. System executes appropriate action:

   * CPR guidance
   * Emergency dispatch
   * Family notification

---

## 🚀 Setup Instructions

For a detailed guide on how to configure and run each component, please refer to the specific README files in the subdirectories:

### Backend (FastAPI + Agentic Runtime)
Located in [`/backend`]
* Uses `uv` for dependency management
* Requires Google Cloud credentials for Vertex AI
* Handles the reasoning and execution logic

### Frontend (React + Vite)
Located in [`/frontend/health-guard-ai`]
* Built with React and Framer Motion
* Connects to the backend via REST API
* Real-time dashboard for monitoring fall events

---

## ☁️ Deployment

The system is deployed on Google Cloud Run for scalable and serverless execution.

---

## 🤖 AI Usage Disclosure

This project uses the Google AI Ecosystem Stack as part of its core system:

* Google AI Studio or Antigravity was used as the starting point for development and prototyping
* Gemini models (2.5 Flash and 2.5 Pro) are used for system intelligence, interaction, and reasoning
* Vertex AI (Agent Development Kit and Vertex AI Search) is used for orchestration and grounded knowledge retrieval
* Google Cloud Run is used for deployment

Additional AI-assisted tools may have been used to support development efficiency such as code suggestions, debugging, or refactoring.

All generated or assisted code has been reviewed, validated, and understood by the team, and can be fully explained during judging.

---

## 🇲🇾 Impact & Alignment

ElderGuard aligns with Malaysia’s Healthcare and Wellbeing track by:

* Improving emergency response time
* Supporting elderly care in home environments
* Reducing strain on healthcare systems
* Enabling safer, AI-assisted living environments

It also contributes to Smart Cities through intelligent home monitoring and has potential integration with public emergency systems.

---

## 🧩 Future Improvements

* Integration with real emergency services
* Wearable device compatibility
* Expanded medical scenario handling
* Enhanced multimodal detection

---

## 🛠️ Development Timeline

This project was developed during the Project 2030: MyAI Future Hackathon period (15 March 2026 – 21 April 2026), in accordance with competition rules.

---

## 👥 Team

* KAVEN WONG XIEN HEAN — Agentic System Architecture & Development
* LOH ZHI FONG — Frontend Engineering
* LEE POH SIANG — Backend Systems Support
* JAZMYN WONG YUIT WEN — Research & Vertex AI Integration

---

## 📌 Final Note

From detection to decision to action, ElderGuard demonstrates how AI can move beyond passive monitoring into active, intelligent intervention.

---

*Developed by the **Hypernode Team** for Project 2030 (2026).*