import { useEffect, useRef, useState } from "react";
import { DEMO_PROFILES, getVitalsPreset } from "../../data/mockData";
import { PAGES } from "../../constants/pages";
import DashboardConversationPanel from "../dashboard/DashboardConversationPanel";
import DashboardHeader from "../dashboard/DashboardHeader";
import DashboardProfileCard from "../dashboard/DashboardProfileCard";
import DashboardSessionControlCard from "../dashboard/DashboardSessionControlCard";
import DashboardSessionStateCard from "../dashboard/DashboardSessionStateCard";
import DashboardVitalsPanel from "../dashboard/DashboardVitalsPanel";
import DashboardActionCard from "../dashboard/DashboardActionCard";
import ProfileModal from "../ui/ProfileModal";

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

function createHistorySeries(value, variance, min, max) {
  return Array.from({ length: 10 }, () => Math.round(clamp(value + (Math.random() - 0.5) * variance, min, max)));
}

function createVitalsState(baseVitals) {
  return {
    hr: baseVitals.hr,
    spo2: baseVitals.spo2,
    bp: baseVitals.bp,
    temp: baseVitals.temp,
    hrHistory: createHistorySeries(baseVitals.hr, 8, 45, 160),
    spo2History: createHistorySeries(baseVitals.spo2, 3, 84, 100),
  };
}

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

function mapAssessmentSeverity(severity) {
  if (severity === "critical") {
    return "Critical";
  }
  if (severity === "medium") {
    return "Medium";
  }
  return "Low";
}

function buildHistoryEntry(profileName, latestAssessment, executionUpdate) {
  const recommendedAction = latestAssessment?.action?.recommended;
  const event =
    recommendedAction === "emergency_dispatch"
      ? "Emergency Dispatch Triggered"
      : "Dispatch Pending Confirmation";

  const action = executionUpdate.status === "completed" ? "EMS Dispatched" : "Awaiting Confirmation";

  return {
    id: `h${Date.now()}`,
    timestamp: new Date().toLocaleString("en-MY", { hour12: false }).slice(0, 16),
    profile: profileName,
    event,
    severity: mapAssessmentSeverity(latestAssessment?.clinical_assessment?.severity),
    action,
    summary: latestAssessment?.clinical_assessment?.reasoning_summary || executionUpdate.detail,
  };
}

export default function Dashboard({ onNavigate, historyLog, setHistoryLog }) {
  const [profileIdx, setProfileIdx] = useState(0);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showProfileSelector, setShowProfileSelector] = useState(false);
  const [vitalsMode, setVitalsMode] = useState("normal");
  const [motionState, setMotionState] = useState("rapid_descent");
  const [runtimeStatus, setRuntimeStatus] = useState(null);

  const [interaction, setInteraction] = useState(DEFAULT_INTERACTION);
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState([]);
  const [latestAssessment, setLatestAssessment] = useState(null);
  const [latestTurn, setLatestTurn] = useState(null);
  const [draftMessage, setDraftMessage] = useState("");
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState("");
  const [streamStatus, setStreamStatus] = useState("idle");

  const [sidebarWidth, setSidebarWidth] = useState(500);
  const isResizing = useRef(false);

  const profile = DEMO_PROFILES[profileIdx];
  const baseVitals = getVitalsPreset(profile.userId, vitalsMode);
  const [vitals, setVitals] = useState(() => createVitalsState(baseVitals));

  const lastHistoryKeyRef = useRef("");

  useEffect(() => {
    function handleMouseMove(e) {
      if (!isResizing.current) return;
      const newWidth = document.body.clientWidth - e.clientX;
      setSidebarWidth(Math.max(300, Math.min(800, newWidth)));
    }
    function handleMouseUp() {
      if (isResizing.current) {
        isResizing.current = false;
        document.body.style.cursor = "default";
      }
    }
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  useEffect(() => {
    setVitals(createVitalsState(baseVitals));
    setMotionState(vitalsMode === "abnormal" ? "rapid_descent" : "stumble");
    setInteraction(DEFAULT_INTERACTION);
    setSessionId("");
    setMessages([]);
    setLatestAssessment(null);
    setLatestTurn(null);
    setDraftMessage("");
    setError("");
    setStreamStatus("idle");
    setPhase("idle");
  }, [baseVitals, profile.userId, vitalsMode]);

  useEffect(() => {
    const interval = setInterval(() => {
      setVitals((current) => {
        const hrFloor = vitalsMode === "abnormal" ? baseVitals.hr - 10 : baseVitals.hr - 6;
        const hrCeiling = vitalsMode === "abnormal" ? baseVitals.hr + 10 : baseVitals.hr + 6;
        const spo2Floor = vitalsMode === "abnormal" ? baseVitals.spo2 - 2 : baseVitals.spo2 - 1;
        const spo2Ceiling = vitalsMode === "abnormal" ? baseVitals.spo2 + 2 : baseVitals.spo2 + 1;

        const nextHr = Math.round(clamp(current.hr + (Math.random() - 0.5) * 4, hrFloor, hrCeiling));
        const nextSpo2 = Math.round(clamp(current.spo2 + (Math.random() - 0.5) * 2, spo2Floor, spo2Ceiling));

        return {
          ...current,
          hr: nextHr,
          spo2: nextSpo2,
          hrHistory: [...current.hrHistory.slice(1), nextHr],
          spo2History: [...current.spo2History.slice(1), nextSpo2],
        };
      });
    }, 2500);

    return () => clearInterval(interval);
  }, [baseVitals.hr, baseVitals.spo2, vitalsMode]);

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
    if (!sessionId) {
      return undefined;
    }

    const stream = new EventSource(`${API_BASE_URL}/api/v1/events/fall/session-events/${sessionId}`);
    setStreamStatus("connecting");

    stream.onopen = () => {
      setStreamStatus("connected");
    };

    stream.addEventListener("session_state", (event) => {
      const payload = JSON.parse(event.data);
      setMessages(payload.conversation_history || []);
      setLatestAssessment(payload.assessment || null);
      setLatestTurn((current) => {
        if (!current) {
          return current;
        }
        const nextAnalysis = payload.latest_analysis || current.communication_analysis;
        return {
          ...current,
          interaction: payload.interaction || current.interaction,
          communication_analysis: nextAnalysis,
          reasoning_status: payload.reasoning_status,
          reasoning_reason: payload.reasoning_reason,
          reasoning_error: payload.reasoning_error,
          assessment: payload.assessment || current.assessment,
          execution_updates: payload.execution_updates || current.execution_updates || [],
        };
      });
    });

    stream.onerror = () => {
      setStreamStatus("disconnected");
      stream.close();
    };

    return () => {
      stream.close();
      setStreamStatus("idle");
    };
  }, [sessionId]);

  useEffect(() => {
    const executionUpdate = latestTurn?.execution_updates?.find(
      (item) => item.type === "emergency_dispatch" && ["completed", "pending_confirmation"].includes(item.status),
    );

    if (!executionUpdate || !latestAssessment || !sessionId) {
      return;
    }

    const historyKey = `${sessionId}:${executionUpdate.type}:${executionUpdate.status}:${latestAssessment.action?.recommended}`;
    if (lastHistoryKeyRef.current === historyKey) {
      return;
    }

    lastHistoryKeyRef.current = historyKey;
    setHistoryLog((current) => [buildHistoryEntry(profile.name, latestAssessment, executionUpdate), ...current]);
  }, [latestAssessment, latestTurn, profile.name, sessionId, setHistoryLog]);

  function resetConversation() {
    setInteraction(DEFAULT_INTERACTION);
    setSessionId("");
    setMessages([]);
    setLatestAssessment(null);
    setLatestTurn(null);
    setDraftMessage("");
    setError("");
    setStreamStatus("idle");
    setPhase("idle");
  }

  async function startSession() {
    setPhase("starting");
    setError("");

    const bloodPressure = parseBloodPressure(vitals.bp);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/session-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: {
            user_id: profile.userId,
            timestamp: new Date().toISOString(),
            motion_state: motionState,
            confidence_score: 0.98,
          },
          vitals: {
            user_id: profile.userId,
            heart_rate: Number(vitals.hr),
            blood_pressure_systolic: Number(bloodPressure.systolic),
            blood_pressure_diastolic: Number(bloodPressure.diastolic),
            blood_oxygen_sp02: Number(vitals.spo2),
          },
          interaction: makeInteractionPayload(interaction, ""),
          session_id: null,
          latest_responder_message: "",
          conversation_history: [],
          previous_assessment: null,
        }),
      });

      if (!response.ok) {
        throw new Error(`Session start failed (${response.status})`);
      }

      const payload = await response.json();
      setSessionId(payload.session_id);
      setLatestTurn(payload);
      setLatestAssessment(payload.assessment || null);
      setMessages(payload.transcript_append || []);
      setPhase("session_ready");
    } catch (requestError) {
      setError(requestError.message || "Unable to start the session.");
      setPhase("error");
    }
  }

  async function sendTurn() {
    if (!draftMessage.trim()) {
      return;
    }

    const messageText = draftMessage.trim();
    setDraftMessage("");
    setPhase("sending");
    setError("");

    const responderRole = latestTurn?.interaction?.communication_target || "patient";
    const userMessage = { role: responderRole, text: messageText };
    const nextHistory = [...messages, userMessage];

    // Optimistically show user message
    setMessages(nextHistory);

    const bloodPressure = parseBloodPressure(vitals.bp);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/session-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: {
            user_id: profile.userId,
            timestamp: new Date().toISOString(),
            motion_state: motionState,
            confidence_score: 0.98,
          },
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
      setMessages([...nextHistory, ...(payload.transcript_append || [])]);
      setPhase("session_ready");
    } catch (requestError) {
      setError(requestError.message || "Unable to send the turn.");
      setPhase("error");
    }
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <DashboardHeader runtimeStatus={runtimeStatus} />

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        
        {/* Left Main Dashboard Area */}
        <div className="page" style={{ paddingTop: 0, overflowY: "auto", flex: 1 }}>
          <div className="dash-top">
            <DashboardProfileCard
              profile={profile}
              profileIdx={profileIdx}
              showProfileSelector={showProfileSelector}
              setShowProfileModal={setShowProfileModal}
              setShowProfileSelector={setShowProfileSelector}
              setProfileIdx={setProfileIdx}
              onNavigateToProfile={() => onNavigate(PAGES.PROFILE)}
            />
            <DashboardVitalsPanel vitals={vitals} vitalsMode={vitalsMode} setVitalsMode={setVitalsMode} />
          </div>

          <div className="section-label">Communication Agent - real dashboard session flow</div>

          <div className="dashboard-stack">
            <div className="grid-2">
              <DashboardSessionControlCard
                profile={profile}
                runtimeStatus={runtimeStatus}
                motionState={motionState}
                setMotionState={setMotionState}
                phase={phase}
                streamStatus={streamStatus}
                startSession={startSession}
                resetConversation={resetConversation}
              />
              <DashboardActionCard
                latestAssessment={latestAssessment}
                latestTurn={latestTurn}
              />
            </div>
            <DashboardSessionStateCard
              sessionId={sessionId}
              streamStatus={streamStatus}
              latestTurn={latestTurn}
              latestAssessment={latestAssessment}
              error={error}
              historyCount={historyLog.length}
            />
          </div>
        </div>

        {/* Resizer */}
        <div 
          className="dashboard-resizer"
          onMouseDown={() => {
            isResizing.current = true;
            document.body.style.cursor = "col-resize";
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
    </div>
  );
}
