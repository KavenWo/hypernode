"""Run the MVP fall workflow locally: questions first, then one reasoning pass."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from agents.orchestrator import get_fall_triage_questions, run_mvp_fall_assessment
from agents.shared.schemas import FallEvent, PatientAnswer, VitalSigns


async def main() -> None:
    print("--- [MVP FLOW TEST] ---")

    event = FallEvent(
        user_id="user_001",
        timestamp="2024-04-10T12:00:00Z",
        motion_state="rapid_descent",
        confidence_score=0.98,
    )
    vitals = VitalSigns(
        user_id="user_001",
        heart_rate=118,
        blood_pressure_systolic=92,
        blood_pressure_diastolic=58,
        blood_oxygen_sp02=91.0,
    )

    questions = get_fall_triage_questions(event, vitals)
    print("\nQuestions:")
    for question in questions.questions:
        print(f"- {question.question_id}: {question.text}")

    answers = [
        PatientAnswer(question_id="consciousness", answer="Yes, but I feel dizzy and slow to respond."),
        PatientAnswer(
            question_id="pain_mobility",
            answer="I have strong pain in my hip and I cannot stand up safely.",
        ),
        PatientAnswer(
            question_id=questions.questions[-1].question_id,
            answer="I hit my head and I take blood thinners.",
        ),
    ]

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("\nGEMINI_API_KEY is not set, so only the question step was verified.")
        return

    assessment = await run_mvp_fall_assessment(
        event=event,
        vitals=vitals,
        patient_answers=answers,
    )

    print("\nAssessment:")
    print(f"Severity: {assessment.severity}")
    print(f"Action: {assessment.action}")
    print(f"Reasoning: {assessment.reasoning}")
    print("Instructions:")
    for step in assessment.instructions:
        print(f"- {step}")


if __name__ == "__main__":
    asyncio.run(main())
