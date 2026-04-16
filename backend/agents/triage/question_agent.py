"""Question agent: generates a small set of targeted fall-triage questions."""

from agents.shared.schemas import (
    FallEvent,
    InteractionSummary,
    TriageQuestion,
    TriageQuestionSet,
    UserMedicalProfile,
    VitalSigns,
)


def generate_triage_questions(
    *,
    event: FallEvent,
    patient_profile: UserMedicalProfile,
    vitals: VitalSigns | None,
    interaction: InteractionSummary | None = None,
) -> TriageQuestionSet:
    target = interaction.communication_target if interaction else "patient"
    if target == "bystander":
        questions = [
            TriageQuestion(
                question_id="patient_responsiveness",
                text="Is the patient responding when you speak to them or gently tap their shoulder?",
            ),
            TriageQuestion(
                question_id="breathing_observation",
                text="Is the patient breathing normally, breathing abnormally, or not breathing at all?",
            ),
        ]

        breathing_question = TriageQuestion(
            question_id="severe_bleeding_or_chest_pain",
            text="Do you see severe bleeding, chest pain, seizure activity, or new confusion?",
        )
        blood_thinner_question = TriageQuestion(
            question_id="head_strike_and_risk",
            text="Did they hit their head, are they on blood thinners, or are they trying to stand after the fall?",
        )
        brief_observation_question = TriageQuestion(
            question_id="scene_observation",
            text="What happened right before the fall, and what is the patient doing right now?",
        )
    else:
        questions = [
            TriageQuestion(
                question_id="consciousness",
                text="Are you awake and able to answer clearly right now?",
            ),
            TriageQuestion(
                question_id="pain_mobility",
                text="Do you have severe pain in your head, neck, back, or hip, or are you unable to get up safely?",
            ),
        ]

        breathing_question = TriageQuestion(
            question_id="breathing_bleeding",
            text="Are you having trouble breathing, heavy bleeding, chest pain, or new confusion?",
        )
        blood_thinner_question = TriageQuestion(
            question_id="head_injury_blood_thinner",
            text="Did you hit your head, and are you on blood thinners or feeling more dizzy than usual?",
        )
        brief_observation_question = TriageQuestion(
            question_id="observation",
            text="Can you describe what happened and whether you lost consciousness at any point?",
        )

    high_risk_event = event.motion_state in {"rapid_descent", "no_movement"} or event.confidence_score >= 0.85
    concerning_vitals = (
        vitals is not None
        and (
            vitals.heart_rate < 45
            or vitals.heart_rate > 130
            or vitals.blood_oxygen_sp02 < 92
        )
    )

    if patient_profile.blood_thinners or "warfarin" in {med.lower() for med in patient_profile.medications}:
        questions.append(blood_thinner_question)
    elif concerning_vitals or high_risk_event:
        questions.append(breathing_question)
    else:
        questions.append(brief_observation_question)

    return TriageQuestionSet(questions=questions[:3], interaction=interaction)
