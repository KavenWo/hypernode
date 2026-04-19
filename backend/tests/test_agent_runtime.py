import pytest

from agents.communication.session_agent import analyze_communication_turn as local_analyze_communication_turn
from agents.execution.execution_agent import requires_execution_grounding as local_requires_execution_grounding
from agents.sentinel.vital_agent import inspect_vitals as local_inspect_vitals
from agents.sentinel.vision_agent import inspect_fall_event as local_inspect_fall_event
from agents.shared.schemas import CommunicationAgentAnalysis, ConversationMessage, FallEvent, UserMedicalProfile, VitalSigns
from app.fall.agent_runtime import get_agent_backend, get_fall_agent_runtime


def test_agent_backend_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_BACKEND", raising=False)
    monkeypatch.delenv("AGENT_BACKEND_VISION", raising=False)

    assert get_agent_backend("vision") == "local"
    assert get_agent_backend("reasoning") == "local"


def test_agent_backend_honors_role_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BACKEND", "local")
    monkeypatch.setenv("AGENT_BACKEND_REASONING", "vertex")

    assert get_agent_backend("vision") == "local"
    assert get_agent_backend("reasoning") == "vertex"


def test_agent_backend_supports_genkit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BACKEND", "local")
    monkeypatch.setenv("AGENT_BACKEND_EXECUTION", "genkit")

    assert get_agent_backend("execution") == "genkit"


def test_agent_backend_supports_adk_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BACKEND", "local")
    monkeypatch.setenv("AGENT_BACKEND_EXECUTION", "adk")

    assert get_agent_backend("execution") == "adk"


@pytest.mark.asyncio
async def test_local_runtime_matches_local_signal_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BACKEND", "local")
    runtime = get_fall_agent_runtime()
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

    runtime_vision = await runtime.inspect_fall_event(event)
    direct_vision = await local_inspect_fall_event(event)
    assert runtime_vision == direct_vision

    runtime_vitals = await runtime.inspect_vitals(vitals)
    direct_vitals = await local_inspect_vitals(vitals)
    assert runtime_vitals == direct_vitals


@pytest.mark.asyncio
async def test_local_runtime_supports_demo_video_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BACKEND", "local")
    runtime = get_fall_agent_runtime()
    event = FallEvent(
        user_id="user_001",
        timestamp="2024-04-10T12:00:00Z",
        motion_state="rapid_descent",
        confidence_score=0.98,
        video_id="falling_down",
        video_source="local_demo_video",
        video_summary="Person fell and is motionless",
    )

    runtime_vision = await runtime.inspect_fall_event(event)

    assert runtime_vision.fall_detected is True
    assert runtime_vision.severity_hint == "critical"
    assert runtime_vision.reasoning == "Person fell and is motionless"


@pytest.mark.asyncio
async def test_local_runtime_matches_local_communication_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BACKEND", "local")
    runtime = get_fall_agent_runtime()
    event = FallEvent(
        user_id="user_001",
        timestamp="2024-04-10T12:00:00Z",
        motion_state="rapid_descent",
        confidence_score=0.98,
    )
    profile = UserMedicalProfile(
        user_id="user_001",
        full_name="Test User",
        age=72,
        pre_existing_conditions=["hypertension"],
        emergency_contacts=[],
        medications=["warfarin"],
        allergies=[],
        blood_thinners=True,
        mobility_support=False,
    )
    conversation_history = [ConversationMessage(role="assistant", text="A fall was detected. Are you okay?")]

    runtime_result = await runtime.analyze_communication_turn(
        client=None,
        event=event,
        vitals=None,
        patient_profile=profile,
        conversation_history=conversation_history,
        latest_message="I hit my head and feel dizzy.",
        previous_assessment=None,
        previous_analysis=None,
        pending_reasoning_context="",
        execution_plan=None,
        execution_updates=[],
        acknowledged_reasoning_triggers=set(),
    )
    direct_result = await local_analyze_communication_turn(
        client=None,
        event=event,
        vitals=None,
        patient_profile=profile,
        conversation_history=conversation_history,
        latest_message="I hit my head and feel dizzy.",
        previous_assessment=None,
        previous_analysis=None,
        pending_reasoning_context="",
        execution_plan=None,
        execution_updates=[],
        acknowledged_reasoning_triggers=set(),
    )

    assert isinstance(runtime_result, CommunicationAgentAnalysis)
    assert runtime_result == direct_result


def test_local_runtime_matches_execution_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BACKEND", "local")
    runtime = get_fall_agent_runtime()

    assert runtime.requires_execution_grounding(
        action="dispatch_pending_confirmation",
        bystander_actions=[],
    ) == local_requires_execution_grounding(
        action="dispatch_pending_confirmation",
        bystander_actions=[],
    )


@pytest.mark.asyncio
async def test_vertex_runtime_placeholder_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BACKEND_VISION", "vertex")
    runtime = get_fall_agent_runtime()
    event = FallEvent(
        user_id="user_001",
        timestamp="2024-04-10T12:00:00Z",
        motion_state="rapid_descent",
        confidence_score=0.98,
    )

    with pytest.raises(NotImplementedError):
        await runtime.inspect_fall_event(event)


@pytest.mark.asyncio
async def test_genkit_runtime_executes_via_genkit_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    from agents.shared.schemas import ClinicalAssessmentSummary, ExecutionPlan, PatientAnswer, UserMedicalProfile

    monkeypatch.setenv("AGENT_BACKEND_EXECUTION", "genkit")
    runtime = get_fall_agent_runtime()

    async def fake_run_genkit_execution_plan(**kwargs):
        assert kwargs["action"] == "dispatch_pending_confirmation"
        return ExecutionPlan(
            steps=["Keep the patient still.", "Check breathing."],
            warnings=["Do not move the patient unless necessary."],
            escalation_triggers=["Breathing worsens."],
            quick_replies=["Done", "Need next step"],
            protocol_key="dispatch_wait",
            source="grounded",
        )

    import app.fall.genkit_execution as genkit_execution

    monkeypatch.setattr(genkit_execution, "run_genkit_execution_plan", fake_run_genkit_execution_plan)

    plan = await runtime.run_execution_grounding(
        action="dispatch_pending_confirmation",
        clinical_assessment=ClinicalAssessmentSummary(
            severity="critical",
            clinical_confidence_score=0.9,
            clinical_confidence_band="high",
            action_confidence_score=0.9,
            action_confidence_band="high",
            red_flags=["abnormal_breathing"],
            reasoning_summary="High-risk respiratory concern.",
            response_plan={},
        ),
        patient_profile=UserMedicalProfile(
            user_id="user_001",
            age=74,
            pre_existing_conditions=["hypertension"],
            emergency_contacts=[],
            medications=[],
            allergies=[],
            blood_thinners=False,
            mobility_support=False,
        ),
        patient_answers=[PatientAnswer(question_id="breathing", answer="Breathing strangely")],
    )

    assert plan.protocol_key == "dispatch_wait"
    assert plan.source == "grounded"


@pytest.mark.asyncio
async def test_adk_runtime_executes_via_adk_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    from agents.shared.schemas import ClinicalAssessmentSummary, ExecutionPlan, PatientAnswer, UserMedicalProfile

    monkeypatch.setenv("AGENT_BACKEND_EXECUTION", "adk")
    runtime = get_fall_agent_runtime()

    async def fake_run_adk_execution_plan(**kwargs):
        assert kwargs["action"] == "dispatch_pending_confirmation"
        return ExecutionPlan(
            steps=["Keep the patient still.", "Check breathing."],
            warnings=["Do not move the patient unless necessary."],
            escalation_triggers=["Breathing worsens."],
            quick_replies=["Done", "Need next step"],
            protocol_key="dispatch_wait",
            source="grounded",
        )

    import app.fall.adk_execution as adk_execution

    monkeypatch.setattr(adk_execution, "run_adk_execution_plan", fake_run_adk_execution_plan)

    plan = await runtime.run_execution_grounding(
        action="dispatch_pending_confirmation",
        clinical_assessment=ClinicalAssessmentSummary(
            severity="critical",
            clinical_confidence_score=0.9,
            clinical_confidence_band="high",
            action_confidence_score=0.9,
            action_confidence_band="high",
            red_flags=["abnormal_breathing"],
            reasoning_summary="High-risk respiratory concern.",
            response_plan={},
        ),
        patient_profile=UserMedicalProfile(
            user_id="user_001",
            age=74,
            pre_existing_conditions=["hypertension"],
            emergency_contacts=[],
            medications=[],
            allergies=[],
            blood_thinners=False,
            mobility_support=False,
        ),
        patient_answers=[PatientAnswer(question_id="breathing", answer="Breathing strangely")],
    )

    assert plan.protocol_key == "dispatch_wait"
    assert plan.source == "grounded"


@pytest.mark.asyncio
async def test_adk_runtime_reasoning_executes_via_adk_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    from agents.shared.schemas import ClinicalAssessment, FallEvent, UserMedicalProfile, VisionAssessment, VitalAssessment

    monkeypatch.setenv("AGENT_BACKEND_REASONING", "adk")
    runtime = get_fall_agent_runtime()

    async def fake_assess_clinical_severity_with_adk(**kwargs):
        assert kwargs["event"].user_id == "user_001"
        return ClinicalAssessment(
            severity="critical",
            clinical_confidence_score=0.9,
            clinical_confidence_band="high",
            action_confidence_score=0.88,
            action_confidence_band="high",
            red_flags=["abnormal_breathing"],
            protective_signals=[],
            suspected_risks=["respiratory_distress"],
            vulnerability_modifiers=["older_adult"],
            missing_facts=[],
            contradictions=[],
            uncertainty=[],
            hard_emergency_triggered=False,
            blocking_uncertainties=[],
            override_policy="",
            reasoning_summary="Critical respiratory concern.",
            recommended_action="dispatch_pending_confirmation",
            response_plan={},
            reasoning_trace={},
        )

    import app.fall.adk_reasoning as adk_reasoning

    monkeypatch.setattr(adk_reasoning, "assess_clinical_severity_with_adk", fake_assess_clinical_severity_with_adk)

    assessment = await runtime.assess_clinical_severity(
        client=None,
        event=FallEvent(
            user_id="user_001",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="rapid_descent",
            confidence_score=0.98,
        ),
        patient_profile=UserMedicalProfile(user_id="user_001", age=72),
        vision_assessment=VisionAssessment(
            fall_detected=True,
            severity_hint="critical",
            reasoning="Rapid descent and no movement.",
        ),
        vital_assessment=VitalAssessment(
            anomaly_detected=True,
            severity_hint="critical",
            reasoning="SpO2 low.",
        ),
        grounded_medical_guidance=None,
        patient_answers=[],
    )

    assert assessment.recommended_action == "dispatch_pending_confirmation"
    assert assessment.severity == "critical"


@pytest.mark.asyncio
async def test_adk_runtime_communication_executes_via_adk_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    from agents.shared.schemas import FallEvent, UserMedicalProfile

    monkeypatch.setenv("AGENT_BACKEND_COMMUNICATION", "adk")
    runtime = get_fall_agent_runtime()

    async def fake_analyze_communication_turn_with_adk(**kwargs):
        assert kwargs["latest_message"] == "I can breathe but my head hurts."
        return CommunicationAgentAnalysis(
            followup_text="Okay. Stay still and tell me if breathing changes.",
            responder_role="patient",
            communication_target="patient",
            patient_responded=True,
            bystander_present=False,
            bystander_can_help=False,
            extracted_facts=["responsive", "pain_present", "patient_speaking"],
            resolved_fact_keys=["stable_speaking"],
            open_question_key="head_injury",
            open_question_resolved=False,
            conversation_state_summary="Resolved: stable_speaking. Open question: head_injury. Next focus: head_injury.",
            reasoning_needed=False,
            reasoning_reason="No new escalation reason was detected beyond what reasoning already knows.",
            should_surface_execution_update=False,
            guidance_intent="question",
            next_focus="head_injury",
            immediate_step="Stay still.",
            quick_replies=["Breathing okay", "Head hurts", "Need help"],
        )

    import app.fall.adk_communication as adk_communication

    monkeypatch.setattr(adk_communication, "analyze_communication_turn_with_adk", fake_analyze_communication_turn_with_adk)

    analysis = await runtime.analyze_communication_turn(
        client=None,
        event=FallEvent(
            user_id="user_001",
            timestamp="2024-04-10T12:00:00Z",
            motion_state="rapid_descent",
            confidence_score=0.98,
        ),
        vitals=None,
        patient_profile=UserMedicalProfile(
            user_id="user_001",
            full_name="Test User",
            age=72,
            pre_existing_conditions=["hypertension"],
            emergency_contacts=[],
            medications=["warfarin"],
            allergies=[],
            blood_thinners=True,
            mobility_support=False,
        ),
        conversation_history=[ConversationMessage(role="assistant", text="A fall was detected. Are you okay?")],
        latest_message="I can breathe but my head hurts.",
        previous_assessment=None,
        previous_analysis=None,
        pending_reasoning_context="",
        execution_plan=None,
        execution_updates=[],
        acknowledged_reasoning_triggers=set(),
    )

    assert analysis.communication_target == "patient"
    assert analysis.next_focus == "head_injury"
    assert analysis.immediate_step == "Stay still."
