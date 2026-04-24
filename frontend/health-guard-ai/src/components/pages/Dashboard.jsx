import { useEffect, useRef, useState } from "react";
import { DEMO_PROFILES, getVitalsPreset } from "../../data/mockData";
import { PAGES } from "../../constants/pages";
import {
  createIncident,
  executeIncidentAction,
  submitIncidentAnswers,
  updateIncidentContext,
  updateIncidentStatus,
} from "../../lib/incidentApi";
import { fetchSessionIncidents } from "../../lib/patientApi";
import DashboardConversationPanel from "../dashboard/DashboardConversationPanel";
import DashboardHeader from "../dashboard/DashboardHeader";
import DashboardProfileCard from "../dashboard/DashboardProfileCard";
import DashboardSessionControlCard from "../dashboard/DashboardSessionControlCard";
import DashboardSessionStateCard from "../dashboard/DashboardSessionStateCard";
import DashboardVitalsPanel from "../dashboard/DashboardVitalsPanel";
import DashboardActionCard from "../dashboard/DashboardActionCard";
import ProfileModal from "../ui/ProfileModal";
import VideoSelectionModal from "../ui/VideoSelectionModal";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const DEFAULT_INTERACTION = {
  patient_response_status: "unknown",
  bystander_available: false,
  bystander_can_help: false,
  testing_assume_bystander: false,
  active_execution_action: "",
  responder_mode_hint: "",
  responder_mode_changed: false,
  contradiction_detected: false,
  no_response_timeout: false,
  new_fact_keys: "",
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function createVitalsState(baseVitals) {
  return {
    hr: baseVitals.hr,
    spo2: baseVitals.spo2,
    bp: baseVitals.bp,
    temp: baseVitals.temp,
  };
};

function parseBloodPressure(bp) {
  const [systolicText = "0", diastolicText = "0"] = (bp || "").split("/");
  return {
    systolic: Number(systolicText),
    diastolic: Number(diastolicText),
  };
}

function makeInteractionPayload(interaction, latestMessage) {
  return {
    patient_response_status: interaction.patient_response_status,
    bystander_available: Boolean(interaction.bystander_available),
    bystander_can_help: Boolean(interaction.bystander_can_help),
    testing_assume_bystander: Boolean(interaction.testing_assume_bystander),
    active_execution_action: interaction.active_execution_action || null,
    message_text: latestMessage,
    new_fact_keys: interaction.new_fact_keys
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    responder_mode_hint: interaction.responder_mode_hint || null,
    responder_mode_changed: Boolean(interaction.responder_mode_changed),
    contradiction_detected: Boolean(interaction.contradiction_detected),
    no_response_timeout: Boolean(interaction.no_response_timeout),
  };
}
function mapIncidentAction(latestAssessment, latestTurn) {
  const recommendedAction = latestAssessment?.action?.recommended;
  const executionUpdates = latestTurn?.execution_updates || [];

  if (executionUpdates.some((item) => item.type === "emergency_dispatch" && item.status === "completed")) {
    return "call_ambulance";
  }
  if (
    executionUpdates.some((item) =>
      ["inform_family", "family_fall_reminder"].includes(item.type) && item.status === "completed",
    )
  ) {
    return "call_family";
  }
  if (recommendedAction === "emergency_dispatch") {
    return "call_ambulance";
  }
  if (recommendedAction === "contact_family") {
    return "call_family";
  }
  return "monitor";
}

function mapIncidentSeverity(latestAssessment) {
  const severity = latestAssessment?.clinical_assessment?.severity;
  if (severity === "critical" || severity === "high") {
    return "red";
  }
  if (severity === "medium" || severity === "moderate") {
    return "amber";
  }
  return "yellow";
}

function buildTriageAnswers(messages, interaction) {
  const latestUserMessage = [...messages].reverse().find((message) => message.role !== "assistant");
  return [
    {
      question: "patient_response_status",
      answer: interaction.patient_response_status || "unknown",
    },
    {
      question: "bystander_available",
      answer: Boolean(interaction.bystander_available),
    },
    {
      question: "latest_responder_message",
      answer: latestUserMessage?.text || "",
    },
  ];
}

function buildIncidentContextPayload(messages, latestTurn) {
  return {
    conversation_history: messages || [],
    canonical_communication_state: latestTurn?.canonical_communication_state || null,
    reasoning_decision: latestTurn?.reasoning_decision || null,
    execution_state: latestTurn?.execution_state || null,
    protocol_guidance: latestTurn?.assessment?.protocol_guidance || null,
    guidance_steps: latestTurn?.guidance_steps || [],
    reasoning_runs: latestTurn?.reasoning_runs || [],
    execution_updates: latestTurn?.execution_updates || [],
    action_states: latestTurn?.action_states || [],
  };
}

function deriveIncidentState(latestAssessment, latestTurn, action, messages) {
  const executionUpdates = latestTurn?.execution_updates || [];
  const dispatchCompleted = executionUpdates.some(
    (item) => item.type === "emergency_dispatch" && item.status === "completed",
  );
  const familyCompleted = executionUpdates.some(
    (item) => ["inform_family", "family_fall_reminder"].includes(item.type) && item.status === "completed",
  );

  if (dispatchCompleted || familyCompleted) {
    return "action_taken";
  }
  if (action === "monitor" && latestAssessment) {
    return "monitoring";
  }
  if (latestAssessment?.clinical_assessment || latestAssessment?.action) {
    return "reasoning";
  }
  if ((messages || []).length > 0) {
    return "triage";
  }
  return "analyzing";
}

function deriveLiveAssistantMessage(turn) {
  const canonicalPrompt = turn?.canonical_communication_state?.latest_prompt;
  const executionState = turn?.execution_state;
  const actionStates = turn?.action_states || [];
  const dispatchState = actionStates.find((item) => item.action_type === "emergency_dispatch") || null;
  const isDispatchPending =
    turn?.state === "awaiting_dispatch_confirmation" ||
    executionState?.dispatch_status === "pending_confirmation" ||
    dispatchState?.status === "pending_confirmation";

  if (isDispatchPending && canonicalPrompt?.trim()) {
    return canonicalPrompt;
  }
  if (executionState?.phase === "guidance" && canonicalPrompt?.trim()) {
    return canonicalPrompt;
  }
  if (turn?.assistant_message?.trim()) {
    return turn.assistant_message;
  }
  if (canonicalPrompt?.trim()) {
    return canonicalPrompt;
  }
  if (turn?.communication_analysis?.followup_text?.trim()) {
    return turn.communication_analysis.followup_text;
  }
  return "";
}

export default function Dashboard({
  isActive = true,
  onNavigate,
  incidentLog,
  setIncidentLog,
  authSession,
  patientProfiles,
  currentPatientId,
}) {
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showVideoModal, setShowVideoModal] = useState(false);
  const [detectionMode, setDetectionMode] = useState("demo_video");
  const [motionState, setMotionState] = useState("rapid_descent");
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [demoVideos, setDemoVideos] = useState([]);
  const [demoVideosLoading, setDemoVideosLoading] = useState(false);
  const [demoVideosError, setDemoVideosError] = useState("");
  const [selectedVideoId, setSelectedVideoId] = useState("");
  const [latestVideoAnalysis, setLatestVideoAnalysis] = useState(null);

  const [interaction, setInteraction] = useState(DEFAULT_INTERACTION);
  const [sessionId, setSessionId] = useState("");
  const [incidentId, setIncidentId] = useState("");
  const [messages, setMessages] = useState([]);
  const [latestAssessment, setLatestAssessment] = useState(null);
  const [latestTurn, setLatestTurn] = useState(null);
  const [draftMessage, setDraftMessage] = useState("");
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState("");
  const [streamStatus, setStreamStatus] = useState("idle");

  const [sidebarWidth, setSidebarWidth] = useState(window.innerWidth * 0.26);
  const isResizing = useRef(false);
  const activeRequestControllerRef = useRef(null);
  const streamRef = useRef(null);
  const pollingRef = useRef(null);
  const sessionIdRef = useRef("");
  const incidentIdRef = useRef("");
  const incidentSyncKeyRef = useRef("");
  const executedIncidentActionsRef = useRef(new Set());

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    incidentIdRef.current = incidentId;
  }, [incidentId]);

  const profile = patientProfiles.find((item) => item.patientId === currentPatientId) || patientProfiles[0] || DEMO_PROFILES[0];
  const sessionUid = authSession?.backendSession?.session_uid || "";
  const baseVitals = getVitalsPreset(profile.userId, "normal");
  const [vitals, setVitals] = useState(() => createVitalsState(baseVitals));

  useEffect(() => {
    setVitals(createVitalsState(baseVitals));
  }, [profile.userId]);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing.current) return;
      const newWidth = window.innerWidth - e.clientX;
      const minW = window.innerWidth * 0.25;
      const maxW = window.innerWidth * 0.45;
      
      if (newWidth >= minW && newWidth <= maxW) {
        setSidebarWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      if (isResizing.current) {
        isResizing.current = false;
        document.body.style.cursor = "default";
        document.body.style.userSelect = "auto";
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setVitals((current) => {
        const hrFloor = baseVitals.hr - 4;
        const hrCeiling = baseVitals.hr + 4;
        const spo2Floor = baseVitals.spo2 - 1;
        const spo2Ceiling = baseVitals.spo2 + 1;

        const nextHr = Math.round(clamp(current.hr + (Math.random() - 0.5) * 4, hrFloor, hrCeiling));
        const nextSpo2 = Math.round(clamp(current.spo2 + (Math.random() - 0.5) * 1.5, spo2Floor, spo2Ceiling));

        const bpParts = (baseVitals.bp || "120/80").split("/");
        const targetSys = Number(bpParts[0] || 120);
        const targetDia = Number(bpParts[1] || 80);

        const currentParts = (current.bp || baseVitals.bp).split("/");
        const currentSys = Number(currentParts[0] || targetSys);
        const currentDia = Number(currentParts[1] || targetDia);

        const sysFloor = targetSys - 8;
        const sysCeiling = targetSys + 8;
        const diaFloor = targetDia - 6;
        const diaCeiling = targetDia + 6;

        const nextSys = Math.round(clamp(currentSys + (Math.random() - 0.5) * 4, sysFloor, sysCeiling));
        const nextDia = Math.round(clamp(currentDia + (Math.random() - 0.5) * 3, diaFloor, diaCeiling));
        const nextBp = `${nextSys}/${nextDia}`;

        const nextTemp = Number((current.temp + (Math.random() - 0.5) * 0.05).toFixed(1));
        const nextTempClamped = clamp(nextTemp, baseVitals.temp - 0.3, baseVitals.temp + 0.3);

        return {
          ...current,
          hr: nextHr,
          spo2: nextSpo2,
          bp: nextBp,
          temp: nextTempClamped,
        };
      });
    }, 2800);

    return () => clearInterval(interval);
  }, [baseVitals.hr, baseVitals.spo2, baseVitals.bp]);

  useEffect(() => {
    let ignore = false;

    async function loadRuntimeStatus() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/status`);
        const payload = await response.json();
        if (!ignore) {
          setRuntimeStatus(payload);
        }
      } catch {
        if (!ignore) {
          setRuntimeStatus({
            backend_ok: false,
            gemini_configured: false,
            vertex_search_configured: false,
            adk_enabled: false,
          });
        }
      }
    }

    loadRuntimeStatus();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    async function loadDemoVideos() {
      setDemoVideosLoading(true);
      setDemoVideosError("");
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/demo-videos`);
        if (!response.ok) {
          throw new Error(`Demo videos failed (${response.status})`);
        }
        const payload = await response.json();
        const videos = (payload.videos || []).map((video) => ({
          id: video.id,
          label: video.label,
          description: video.description,
          summary: video.summary,
          sourceType: video.source_type,
          available: Boolean(video.available),
          videoUrl: `${API_BASE_URL}${video.video_url}`,
        }));
        if (!ignore) {
          setDemoVideos(videos);
          setSelectedVideoId((current) => current || videos.find((item) => item.available)?.id || "");
        }
      } catch (loadError) {
        if (!ignore) {
          setDemoVideos([]);
          setDemoVideosError(loadError.message || "Unable to load demo videos.");
        }
      } finally {
        if (!ignore) {
          setDemoVideosLoading(false);
        }
      }
    }

    loadDemoVideos();
    return () => {
      ignore = true;
    };
  }, []);

  function stopSessionSync() {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }

  function clearActiveSessionState(message = "", preserveData = false) {
    stopSessionSync();
    setSessionId("");
    setStreamStatus("idle");
    setPhase("idle");
    if (!preserveData) {
      setLatestTurn(null);
      setMessages([]);
      setLatestAssessment(null);
    }
    if (message) {
      setError(message);
    }
  }

  function applySessionState(payload) {
    setMessages((currentMessages) => {
      const newHistory = payload.conversation_history || [];
      if (newHistory.length < currentMessages.length) {
        return currentMessages;
      }
      return newHistory;
    });

    setLatestAssessment(payload.assessment || null);
    setLatestTurn((current) => {
      if (!current) {
        return current;
      }
      const nextAnalysis = payload.latest_analysis || current.communication_analysis;
      const payloadAssistantMessage =
        deriveLiveAssistantMessage({
          ...current,
          ...payload,
          communication_analysis: nextAnalysis,
        }) ||
        payload.conversation_history?.filter((message) => message.role === "assistant").at(-1)?.text ||
        current.assistant_message;
      const nextGuidanceSteps = nextAnalysis?.immediate_step
        ? [nextAnalysis.immediate_step]
        : current.guidance_steps || [];
      return {
        ...current,
        state: payload.state ?? current.state,
        canonical_communication_state:
          payload.canonical_communication_state || current.canonical_communication_state,
        reasoning_decision: payload.reasoning_decision || current.reasoning_decision,
        execution_state: payload.execution_state || current.execution_state,
        interaction: payload.interaction || current.interaction,
        communication_analysis: nextAnalysis,
        reasoning_status: payload.reasoning_status,
        reasoning_run_count: payload.reasoning_run_count ?? current.reasoning_run_count ?? 0,
        reasoning_reason: payload.reasoning_reason,
        reasoning_error: payload.reasoning_error,
        reasoning_runs: payload.reasoning_runs || current.reasoning_runs || [],
        assessment: payload.assessment || current.assessment,
        assistant_message: payloadAssistantMessage,
        guidance_steps: nextGuidanceSteps,
        quick_replies: nextAnalysis?.quick_replies || current.quick_replies || [],
        execution_updates: payload.execution_updates || current.execution_updates || [],
        action_states: payload.action_states || current.action_states || [],
      };
    });
  }

  useEffect(() => {
    if (!isActive || !sessionId) {
      stopSessionSync();
      if (!isActive) {
        setStreamStatus("idle");
      }
      return undefined;
    }

    let cancelled = false;

    async function fetchSessionState() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/session-state/${sessionId}`);
        if (response.status === 404) {
          if (!cancelled) {
            clearActiveSessionState("The live session is no longer available.", true);
          }
          return;
        }
        if (!response.ok) {
          throw new Error(`Session state failed (${response.status})`);
        }
        const payload = await response.json();
        if (!cancelled) {
          applySessionState(payload);
        }
      } catch {
        if (!cancelled) {
          setStreamStatus("disconnected");
        }
      }
    }

    function startPolling() {
      if (pollingRef.current) {
        return;
      }
      setStreamStatus("polling");
      pollingRef.current = window.setInterval(() => {
        void fetchSessionState();
      }, 1500);
    }

    void fetchSessionState();

    const stream = new EventSource(`${API_BASE_URL}/api/v1/events/fall/session-events/${sessionId}`);
    streamRef.current = stream;
    setStreamStatus("connecting");

    stream.onopen = () => {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      setStreamStatus("connected");
    };

    stream.addEventListener("session_state", (event) => {
      const payload = JSON.parse(event.data);
      applySessionState(payload);
    });

    stream.addEventListener("session_closed", () => {
      if (!cancelled) {
        clearActiveSessionState("The live session has ended.", true);
      }
    });

    stream.onerror = () => {
      stream.close();
      if (streamRef.current === stream) {
        streamRef.current = null;
      }
      startPolling();
    };

    return () => {
      cancelled = true;
      stopSessionSync();
      setStreamStatus("idle");
    };
  }, [isActive, sessionId]);

  useEffect(() => {
    if (!incidentId || !sessionUid) {
      return;
    }

    const action = mapIncidentAction(latestAssessment, latestTurn);
    const state = deriveIncidentState(latestAssessment, latestTurn, action, messages);
    const triageAnswers = buildTriageAnswers(messages, interaction);
    const aiDecision = {
      action,
      reasoning: latestAssessment?.clinical_assessment?.reasoning_summary || latestAssessment?.action?.rationale || "",
      response_plan: latestAssessment?.response_plan || null,
      assessment: latestAssessment?.clinical_assessment || null,
    };
    const syncKey = JSON.stringify({
      incidentId,
      state,
      action,
      severity: mapIncidentSeverity(latestAssessment),
      triageAnswers,
      reasoning: aiDecision.reasoning,
      executionUpdates: latestTurn?.execution_updates || [],
    });

    if (incidentSyncKeyRef.current === syncKey) {
      return;
    }

    incidentSyncKeyRef.current = syncKey;

    let cancelled = false;

    async function syncIncident() {
      try {
        await submitIncidentAnswers(incidentId, {
          triage_answers: triageAnswers,
          ai_decision: aiDecision,
          severity: mapIncidentSeverity(latestAssessment),
          final_action: action,
        });
        await updateIncidentContext(incidentId, buildIncidentContextPayload(messages, latestTurn));

        await updateIncidentStatus(incidentId, { state });

        const shouldExecuteFamily = (latestTurn?.execution_updates || []).some(
          (item) => ["inform_family", "family_fall_reminder"].includes(item.type) && item.status === "completed",
        );
        const shouldExecuteDispatch = (latestTurn?.execution_updates || []).some(
          (item) => item.type === "emergency_dispatch" && item.status === "completed",
        );

        if (shouldExecuteFamily || shouldExecuteDispatch) {
          const executionKey = `${incidentId}:${action}`;
          if (!executedIncidentActionsRef.current.has(executionKey)) {
            await executeIncidentAction(incidentId, action);
            executedIncidentActionsRef.current.add(executionKey);
          }
        }

        if (!cancelled && ["action_taken", "resolved"].includes(state)) {
          const refreshedIncidents = await fetchSessionIncidents(sessionUid);
          if (!cancelled) {
            setIncidentLog(refreshedIncidents);
          }
        }
      } catch (syncError) {
        if (!cancelled) {
          setError(syncError.message || "Unable to sync incident record.");
        }
      }
    }

    syncIncident();

    return () => {
      cancelled = true;
    };
  }, [incidentId, interaction, latestAssessment, latestTurn, messages, sessionUid, setIncidentLog]);

  function resetConversationState() {
    setInteraction(DEFAULT_INTERACTION);
    setSessionId("");
    setIncidentId("");
    setMessages([]);
    setLatestAssessment(null);
    setLatestTurn(null);
    setLatestVideoAnalysis(null);
    setDraftMessage("");
    setError("");
    setStreamStatus("idle");
    setPhase("idle");
    incidentSyncKeyRef.current = "";
    executedIncidentActionsRef.current = new Set();
    stopSessionSync();
  }

  const selectedVideo = demoVideos.find((video) => video.id === selectedVideoId) || null;



  function abortActiveRequest() {
    if (activeRequestControllerRef.current) {
      activeRequestControllerRef.current.abort();
      activeRequestControllerRef.current = null;
    }
  }

  async function resetConversation() {
    const activeSessionId = sessionIdRef.current;

    abortActiveRequest();
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }

    resetConversationState();

    if (!activeSessionId) {
      return;
    }

    try {
      await fetch(`${API_BASE_URL}/api/v1/events/fall/session-reset/${activeSessionId}`, {
        method: "POST",
      });
    } catch {
      // The UI still resets locally even if the backend is already gone.
    }
  }

  async function stopSession() {
    const activeSessionId = sessionId || sessionIdRef.current;
    abortActiveRequest();
    stopSessionSync();
    clearActiveSessionState("", true);

    if (activeSessionId) {
      try {
        await fetch(`${API_BASE_URL}/api/v1/events/fall/session-stop/${activeSessionId}`, {
          method: "POST",
        });
      } catch {
        // Logging failed but we already stopped locally
      }
    }
  }

  async function startSession() {
    resetConversationState();
    abortActiveRequest();
    const controller = new AbortController();
    activeRequestControllerRef.current = controller;
    setPhase("starting");
    setError("");

    const bloodPressure = parseBloodPressure(vitals.bp);

    try {
      let videoAnalysis = null;
      let eventPayload;
      if (detectionMode === "demo_video" && selectedVideo) {
        setPhase("analyzing_video");
        const analysisResponse = await fetch(`${API_BASE_URL}/api/v1/events/fall/demo-videos/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            user_id: profile.userId,
            video_id: selectedVideo.id,
          }),
        });

        const analysisPayload = await analysisResponse.json().catch(() => ({}));
        if (!analysisResponse.ok) {
          throw new Error(analysisPayload?.detail || `Video analysis failed (${analysisResponse.status})`);
        }

        videoAnalysis = analysisPayload;
        setLatestVideoAnalysis(analysisPayload);
        if (!analysisPayload.fall_detected) {
          if (sessionUid) {
            const incident = await createIncident({
              sessionUid,
              patientId: profile.patientId,
              simulationTrigger: {
                motion_state: analysisPayload.motion_state,
                confidence_score: analysisPayload.confidence_score,
                video_id: analysisPayload.video_id,
                fall_detected: false,
              },
              videoMetadata: {
                source: analysisPayload.video_source,
                video_id: analysisPayload.video_id,
                video_label: videoAnalysis?.video_label || selectedVideo?.label || null,
                summary: analysisPayload.summary,
                analysis_model: videoAnalysis?.analysis_model || null,
                vitals_mode: "normal",
              },
            });
            setIncidentId(incident.incident_id);
            await updateIncidentStatus(incident.incident_id, {
              state: "resolved",
              summary: `Sentinel analyzed the video and detected no fall. ${analysisPayload.summary}`,
            });
          }
          setPhase("idle");
          return;
        }

        eventPayload = {
          user_id: profile.userId,
          timestamp: new Date().toISOString(),
          motion_state: analysisPayload.motion_state,
          confidence_score: Number(analysisPayload.confidence_score),
          video_id: analysisPayload.video_id,
          video_source: analysisPayload.video_source,
          video_summary: analysisPayload.summary,
        };
      } else {
        setLatestVideoAnalysis(null);
        eventPayload = {
          user_id: profile.userId,
          timestamp: new Date().toISOString(),
          motion_state: motionState,
          confidence_score: 0.98,
          video_id: null,
          video_source: "dashboard_simulation",
          video_summary: null,
        };
      }

      setPhase("starting");
      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/session-start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          event: eventPayload,
          vitals: {
            user_id: profile.userId,
            heart_rate: Number(vitals.hr),
            blood_pressure_systolic: Number(bloodPressure.systolic),
            blood_pressure_diastolic: Number(bloodPressure.diastolic),
            blood_oxygen_sp02: Number(vitals.spo2),
          },
          interaction: makeInteractionPayload(interaction, ""),
        }),
      });

      if (!response.ok) {
        throw new Error(`Session start failed (${response.status})`);
      }

      const payload = await response.json();

      if (sessionUid) {
        const incident = await createIncident({
          sessionUid,
          patientId: profile.patientId,
          simulationTrigger: {
            motion_state: eventPayload.motion_state,
            confidence_score: eventPayload.confidence_score,
            video_id: eventPayload.video_id,
            realtime_session_id: payload.session_id,
            fall_detected: true,
          },
          videoMetadata: {
            source: eventPayload.video_source,
            video_id: eventPayload.video_id,
            video_label: videoAnalysis?.video_label || selectedVideo?.label || null,
            summary: eventPayload.video_summary,
            analysis_model: videoAnalysis?.analysis_model || null,
            vitals_mode: "normal",
          },
        });
        setIncidentId(incident.incident_id);
        await updateIncidentContext(
          incident.incident_id,
          buildIncidentContextPayload(payload.transcript_append || [], payload),
        );
      }

      setSessionId(payload.session_id);
      setLatestTurn(payload);
      setLatestAssessment(payload.assessment || null);
      setMessages(payload.transcript_append || []);
      setPhase("session_ready");
    } catch (requestError) {
      if (requestError.name === "AbortError") {
        setPhase("idle");
        return;
      }
      setError(requestError.message || "Unable to start the session.");
      setPhase("error");
    } finally {
      if (activeRequestControllerRef.current === controller) {
        activeRequestControllerRef.current = null;
      }
    }
  }

  async function sendTurn(manualMessage) {
    const messageText = (manualMessage || draftMessage).trim();
    if (!messageText) {
      return;
    }

    abortActiveRequest();
    const controller = new AbortController();
    activeRequestControllerRef.current = controller;
    setDraftMessage("");
    setPhase("sending");
    setError("");

    const responderRole = latestTurn?.interaction?.communication_target || "patient";
    const optimisticVersion = (latestTurn?.reasoning_run_count ?? 0) + 1;
    const userMessage = {
      role: responderRole,
      text: messageText,
      reasoning_input_version: optimisticVersion,
      comm_reasoning_required: null,
      comm_reasoning_reason: "Waiting for communication analysis...",
    };
    const nextHistory = [...messages, userMessage];

    // Optimistically show user message
    setMessages(nextHistory);

    const bloodPressure = parseBloodPressure(vitals.bp);

    try {
      const eventPayload = {
        user_id: profile.userId,
        timestamp: new Date().toISOString(),
        motion_state: detectionMode === "demo_video" && latestVideoAnalysis ? latestVideoAnalysis.motion_state : motionState,
        confidence_score: detectionMode === "demo_video" && latestVideoAnalysis ? Number(latestVideoAnalysis.confidence_score) : 0.98,
        video_id: detectionMode === "demo_video" && latestVideoAnalysis ? latestVideoAnalysis.video_id : null,
        video_source: detectionMode === "demo_video" && latestVideoAnalysis ? latestVideoAnalysis.video_source : "dashboard_simulation",
        video_summary: detectionMode === "demo_video" && latestVideoAnalysis ? latestVideoAnalysis.summary : null,
      };
      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/session-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          event: eventPayload,
          vitals: {
            user_id: profile.userId,
            heart_rate: Number(vitals.hr),
            blood_pressure_systolic: Number(bloodPressure.systolic),
            blood_pressure_diastolic: Number(bloodPressure.diastolic),
            blood_oxygen_sp02: Number(vitals.spo2),
          },
          interaction: makeInteractionPayload(interaction, messageText),
          session_id: sessionId || null,
          latest_responder_message: messageText,
          conversation_history: messages,
          previous_assessment: latestAssessment,
        }),
      });

      if (!response.ok) {
        throw new Error(`Session turn failed (${response.status})`);
      }

      const payload = await response.json();
      setSessionId(payload.session_id);
      setLatestTurn(payload);
      setLatestAssessment(payload.assessment || latestAssessment);

      // Update messages with the real response from the backend
      const serverAppended = payload.transcript_append || [];
      setMessages(() => {
        // Find if userMessage is already in current (it should be)
        // Then append what server said.
        // We use a functional update to be safe.
        return [...nextHistory, ...serverAppended];
      });
      setPhase("session_ready");
    } catch (requestError) {
      if (requestError.name === "AbortError") {
        setPhase("idle");
        return;
      }
      setError(requestError.message || "Unable to send the turn.");
      setPhase("error");
    } finally {
      if (activeRequestControllerRef.current === controller) {
        activeRequestControllerRef.current = null;
      }
    }
  }

  async function controlAction(actionType, decision) {
    const activeSessionId =
      latestTurn?.session_id ||
      sessionIdRef.current ||
      sessionId;

    if (!activeSessionId) {
      return;
    }

    abortActiveRequest();
    const controller = new AbortController();
    activeRequestControllerRef.current = controller;
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/session-action/${activeSessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          action_type: actionType,
          decision,
        }),
      });

      if (!response.ok) {
        throw new Error(`Action control failed (${response.status})`);
      }

      const payload = await response.json();
      if (payload.session_id) {
        setSessionId(payload.session_id);
      }
      setLatestTurn((current) => {
        if (!current) {
          return current;
        }
        const nextActionStates = (current.action_states || []).map((state) =>
          state.action_type === payload.action_state.action_type ? payload.action_state : state,
        );
        if (!nextActionStates.some((state) => state.action_type === payload.action_state.action_type)) {
          nextActionStates.push(payload.action_state);
        }
        const nextTurn = {
          ...current,
          state: payload.state ?? current.state,
          canonical_communication_state:
            payload.canonical_communication_state || current.canonical_communication_state,
          reasoning_decision: payload.reasoning_decision || current.reasoning_decision,
          execution_state: payload.execution_state || current.execution_state,
          action_states: nextActionStates,
          execution_updates: payload.execution_updates || current.execution_updates || [],
        };
        return {
          ...nextTurn,
          assistant_message: deriveLiveAssistantMessage(nextTurn) || current.assistant_message,
        };
      });

      setPhase("session_ready");

      if (incidentIdRef.current) {
        try {
          if (decision === "confirm" && actionType === "emergency_dispatch") {
            await executeIncidentAction(incidentIdRef.current, "call_ambulance");
            executedIncidentActionsRef.current.add(`${incidentIdRef.current}:call_ambulance`);
            if (sessionUid) {
              const refreshedIncidents = await fetchSessionIncidents(sessionUid);
              setIncidentLog(refreshedIncidents);
            }
          }
          if (decision === "cancel") {
            await updateIncidentStatus(incidentIdRef.current, {
              state: "monitoring",
              summary: "Emergency dispatch was canceled by the responder.",
            });
          }
        } catch (syncError) {
          console.error("Incident sync failed after session action succeeded", syncError);
          setError("Dispatch decision applied, but incident history sync failed.");
        }
      }
    } catch (requestError) {
      if (requestError.name === "AbortError") {
        throw requestError;
      }
      setError(requestError.message || "Unable to control the session action.");
      throw requestError;
    } finally {
      if (activeRequestControllerRef.current === controller) {
        activeRequestControllerRef.current = null;
      }
    }
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <DashboardHeader authSession={authSession} />

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Left Main Dashboard Area */}
        <div className="page" style={{ paddingTop: 0, overflowY: "auto", flex: 1 }}>
          <div className="section-label">Patient Profile & Clinical Vitals</div>
          <div className="dash-top" style={{ marginBottom: 16 }}>
            <DashboardProfileCard
              profile={profile}
              setShowProfileModal={setShowProfileModal}
              onNavigateToProfile={() => onNavigate(PAGES.PROFILE)}
            />
            <DashboardVitalsPanel vitals={vitals} />
          </div>

          <div className="section-label">Trigger the Simulation</div>
          <div style={{ marginBottom: 16 }}>
            <DashboardSessionControlCard
              runtimeStatus={runtimeStatus}
              detectionMode={detectionMode}
              selectedVideo={selectedVideo}
              onOpenVideoSelector={() => setShowVideoModal(true)}
              phase={phase}
              streamStatus={streamStatus}
              startSession={startSession}
              stopSession={stopSession}
              resetConversation={resetConversation}
            />
          </div>

          <div className="section-label">Monitor the Agents</div>
          <div className="dashboard-stack">
            <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
              {/* Left Column: Agent Workflow */}
              <div style={{ flex: 1.35 }}>
                <DashboardSessionStateCard
                  sessionId={sessionId}
                  streamStatus={streamStatus}
                  latestTurn={latestTurn}
                  latestAssessment={latestAssessment}
                  latestVideoAnalysis={latestVideoAnalysis}
                  error={error}
                  historyCount={incidentLog.length}
                  phase={phase}
                />
              </div>

              {/* Right Column: Live Actions */}
              <div style={{ flex: 0.95, minWidth: 320 }}>
                <DashboardActionCard
                  latestAssessment={latestAssessment}
                  latestTurn={latestTurn}
                  onActionDecision={controlAction}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Resizer */}
        <div
          className="dashboard-resizer"
          onMouseDown={() => {
            isResizing.current = true;
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
          }}
        />

        {/* Right Sidebar Conversation Panel */}
        <div className="dashboard-sidebar" style={{ width: sidebarWidth }}>
          <DashboardConversationPanel
            profile={profile}
            latestTurn={latestTurn}
            messages={messages}
            draftMessage={draftMessage}
            setDraftMessage={setDraftMessage}
            phase={phase}
            sendTurn={sendTurn}
          />
        </div>
      </div>

      {showProfileModal && <ProfileModal profile={profile} onClose={() => setShowProfileModal(false)} />}
      {showVideoModal && (
        <VideoSelectionModal
          videos={demoVideos}
          selectedVideoId={selectedVideoId}
          loading={demoVideosLoading}
          error={demoVideosError}
          onClose={() => setShowVideoModal(false)}
          onSelect={(video) => {
            setSelectedVideoId(video.id);
            setMotionState(video.motionState);
            setDetectionMode("demo_video");
            setShowVideoModal(false);
          }}
        />
      )}
    </div>
  );
}
