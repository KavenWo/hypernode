import { useEffect, useState } from "react";

const DEFAULT_EVENT = {
  user_id: "user_001",
  timestamp: "2024-04-10T12:00:00Z",
  motion_state: "rapid_descent",
  confidence_score: 0.98,
};

const DEFAULT_VITALS = {
  heart_rate: 118,
  blood_pressure_systolic: 92,
  blood_pressure_diastolic: 58,
  blood_oxygen_sp02: 91,
};

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

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function StatusTag({ active, label, danger = false }) {
  return (
    <span className={`tag ${danger ? "tag-red" : ""}`} style={{ opacity: active ? 1 : 0.65 }}>
      {active ? "Live" : "Off"} - {label}
    </span>
  );
}

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(2) : value ?? "-";
}

function normalizePatients(patients) {
  const seen = new Set();
  return (patients || [])
    .filter((patient) => patient?.user_id)
    .filter((patient) => {
      if (seen.has(patient.user_id)) {
        return false;
      }
      seen.add(patient.user_id);
      return true;
    });
}

function ChatBubble({ role, text }) {
  const isAssistant = role === "assistant";
  return (
    <div
      style={{
        display: "flex",
        justifyContent: isAssistant ? "flex-start" : "flex-end",
      }}
    >
      <div
        style={{
          maxWidth: "88%",
          background: isAssistant ? "linear-gradient(135deg, #fff4dd 0%, #ffe4ba 100%)" : "linear-gradient(135deg, #f5f7fb 0%, #e5ebf5 100%)",
          border: "1px solid var(--border)",
          borderRadius: 18,
          padding: "12px 14px",
          boxShadow: "0 10px 24px rgba(15, 23, 42, 0.06)",
        }}
      >
        <div style={{ fontSize: 11, color: "var(--text-sub)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {isAssistant ? "Communication Agent" : role}
        </div>
        <div style={{ fontSize: 14, color: "var(--text)", lineHeight: 1.6 }}>{text}</div>
      </div>
    </div>
  );
}

function makeInteractionPayload(interaction, latestMessage) {
  return {
    patient_response_status: interaction.patient_response_status,
    bystander_available: Boolean(interaction.bystander_available),
    bystander_can_help: Boolean(interaction.bystander_can_help),
    testing_assume_bystander: Boolean(interaction.testing_assume_bystander),
    active_execution_action: interaction.active_execution_action || null,
    message_text: latestMessage,
    new_fact_keys: interaction.new_fact_keys.split(",").map((item) => item.trim()).filter(Boolean),
    responder_mode_hint: interaction.responder_mode_hint || null,
    responder_mode_changed: Boolean(interaction.responder_mode_changed),
    contradiction_detected: Boolean(interaction.contradiction_detected),
    no_response_timeout: Boolean(interaction.no_response_timeout),
  };
}

export default function MvpTestPage() {
  const [event, setEvent] = useState(DEFAULT_EVENT);
  const [vitals, setVitals] = useState(DEFAULT_VITALS);
  const [interaction, setInteraction] = useState(DEFAULT_INTERACTION);
  const [sessionId, setSessionId] = useState("");
  const [status, setStatus] = useState(null);
  const [patients, setPatients] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [messages, setMessages] = useState([]);
  const [latestAssessment, setLatestAssessment] = useState(null);
  const [latestTurn, setLatestTurn] = useState(null);
  const [draftMessage, setDraftMessage] = useState("");
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState("");
  const [streamStatus, setStreamStatus] = useState("idle");

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
    let ignore = false;

    async function loadData() {
      try {
        const [statusResponse, patientsResponse, scenariosResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/v1/events/fall/status`),
          fetch(`${API_BASE_URL}/api/v1/events/fall/patients`),
          fetch(`${API_BASE_URL}/api/v1/events/fall/phase4-scenarios`),
        ]);
        const statusPayload = await statusResponse.json();
        const patientsPayload = await patientsResponse.json();
        const scenariosPayload = await scenariosResponse.json();
        const nextPatients = normalizePatients(patientsPayload.patients);

        if (!ignore) {
          setStatus(statusPayload);
          setPatients(nextPatients);
          setScenarios(scenariosPayload.scenarios || []);
          if (nextPatients.length > 0) {
            setEvent((current) => ({ ...current, user_id: nextPatients[0].user_id }));
          }
        }
      } catch (_err) {
        if (!ignore) {
          setStatus({
            backend_ok: false,
            gemini_configured: false,
            vertex_search_configured: false,
          });
        }
      }
    }

    loadData();
    return () => {
      ignore = true;
    };
  }, []);

  function updateEvent(field, value) {
    setEvent((current) => ({ ...current, [field]: value }));
  }

  function updateVitals(field, value) {
    setVitals((current) => ({ ...current, [field]: value }));
  }

  function updateInteraction(field, value) {
    setInteraction((current) => ({ ...current, [field]: value }));
  }

  function resetConversation() {
    setSessionId("");
    setMessages([]);
    setLatestAssessment(null);
    setLatestTurn(null);
    setDraftMessage("");
    setError("");
    setStreamStatus("idle");
    setPhase("idle");
  }

  function fillScenario(scenarioId) {
    const scenario = scenarios.find((item) => item.id === scenarioId);
    if (!scenario) {
      return;
    }
    setSelectedScenarioId(scenario.id);
    setInteraction({
      ...DEFAULT_INTERACTION,
      ...(scenario.interaction_context || {}),
      new_fact_keys: (scenario.new_fact_keys || []).join(", "),
    });
    setDraftMessage(scenario.message_text || "");
    resetConversation();
  }

  async function startSession() {
    setPhase("starting");
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/session-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: {
            ...event,
            confidence_score: Number(event.confidence_score),
          },
          vitals: {
            user_id: event.user_id,
            heart_rate: Number(vitals.heart_rate),
            blood_pressure_systolic: Number(vitals.blood_pressure_systolic),
            blood_pressure_diastolic: Number(vitals.blood_pressure_diastolic),
            blood_oxygen_sp02: Number(vitals.blood_oxygen_sp02),
          },
          interaction: makeInteractionPayload(interaction, ""),
          session_id: sessionId || null,
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
    } catch (err) {
      setError(err.message || "Unable to start the session.");
      setPhase("error");
    }
  }

  async function sendTurn() {
    if (!draftMessage.trim()) {
      return;
    }

    setPhase("sending");
    setError("");

    const responderRole = latestTurn?.interaction?.communication_target || "patient";
    const nextHistory = [
      ...messages,
      { role: responderRole, text: draftMessage.trim() },
    ];

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/session-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: {
            ...event,
            confidence_score: Number(event.confidence_score),
          },
          vitals: {
            user_id: event.user_id,
            heart_rate: Number(vitals.heart_rate),
            blood_pressure_systolic: Number(vitals.blood_pressure_systolic),
            blood_pressure_diastolic: Number(vitals.blood_pressure_diastolic),
            blood_oxygen_sp02: Number(vitals.blood_oxygen_sp02),
          },
          interaction: makeInteractionPayload(interaction, draftMessage.trim()),
          session_id: sessionId || null,
          latest_responder_message: draftMessage.trim(),
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
      setDraftMessage("");
      setPhase("session_ready");
    } catch (err) {
      setError(err.message || "Unable to send the turn.");
      setPhase("error");
    }
  }

  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedScenarioId);
  const selectedPatient = patients.find((patient) => patient.user_id === event.user_id);
  const interactionSummary = latestTurn?.interaction;
  const debugSnapshot = {
    session_id: sessionId,
    stream_status: streamStatus,
    latest_turn: latestTurn,
    latest_assessment: latestAssessment,
    execution_updates: latestTurn?.execution_updates || [],
    message_count: messages.length,
    runtime: status,
  };

  return (
    <div>
      <div className="page-header">
        <h1>MVP Test Console</h1>
        <p>Session-based Phase 4 tester for conversational patient and bystander guidance.</p>
      </div>

      <div className="card section-gap">
        <div className="status-row" style={{ marginBottom: 16, alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
          <div>
            <div className="card-title" style={{ marginBottom: 8 }}>Runtime Status</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <StatusTag active={Boolean(status?.backend_ok)} label="Backend API" danger={!status?.backend_ok} />
              <StatusTag active={Boolean(status?.gemini_configured)} label="AI Model" />
              <StatusTag active={Boolean(status?.vertex_search_configured)} label="Vertex Search" />
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {scenarios.slice(0, 5).map((scenario) => (
              <button key={scenario.id} className="btn btn-outline btn-sm" onClick={() => fillScenario(scenario.id)}>
                {scenario.label}
              </button>
            ))}
            <button className="btn btn-outline btn-sm" onClick={resetConversation}>Reset Session</button>
          </div>
        </div>

        <p style={{ fontSize: 13, color: "var(--text-sub)" }}>
          API Base: <span style={{ fontFamily: "'DM Mono', monospace" }}>{API_BASE_URL}</span>
        </p>
        {selectedScenario?.expected_focus && (
          <p style={{ fontSize: 13, color: "var(--text-sub)", marginTop: 6 }}>
            Scenario focus: {selectedScenario.expected_focus}
          </p>
        )}
      </div>

      <div className="grid-3">
        <div className="card">
          <div className="card-title">1. Session Setup</div>

          <div className="form-group">
            <label className="form-label">User ID</label>
            <select className="form-input" value={event.user_id} onChange={(e) => updateEvent("user_id", e.target.value)}>
              {patients.length === 0 && <option value={event.user_id}>{event.user_id}</option>}
              {patients.map((patient) => (
                <option key={patient.user_id} value={patient.user_id}>
                  {patient.full_name} ({patient.user_id})
                </option>
              ))}
            </select>
            {selectedPatient && (
              <p style={{ fontSize: 12, color: "var(--text-sub)", marginTop: 6 }}>
                Selected profile: {selectedPatient.age} years old - {selectedPatient.blood_thinners ? "blood thinners" : "no blood thinners"}
              </p>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Motion State</label>
            <select className="form-input" value={event.motion_state} onChange={(e) => updateEvent("motion_state", e.target.value)}>
              <option value="rapid_descent">rapid_descent</option>
              <option value="no_movement">no_movement</option>
              <option value="stumble">stumble</option>
              <option value="slow_descent">slow_descent</option>
            </select>
          </div>

          <div className="divider" />

          <div className="form-group">
            <label className="form-label">Heart Rate</label>
            <input className="form-input" type="number" value={vitals.heart_rate} onChange={(e) => updateVitals("heart_rate", e.target.value)} />
          </div>

          <div className="form-group">
            <label className="form-label">SpO2</label>
            <input className="form-input" type="number" step="0.1" value={vitals.blood_oxygen_sp02} onChange={(e) => updateVitals("blood_oxygen_sp02", e.target.value)} />
          </div>

          <p style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
            The communication agent starts only with the fall, profile, and vitals. It should discover responsiveness, bystander presence, and next steps through the conversation.
          </p>

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={startSession} disabled={phase === "starting" || phase === "sending"}>
            {phase === "starting" ? "Starting..." : "Start Session"}
          </button>
        </div>

        <div className="card" style={{ display: "flex", flexDirection: "column", minHeight: 720 }}>
          <div className="card-title">2. Conversation</div>

          {interactionSummary && (
            <div style={{ marginBottom: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span className="tag">Target - {interactionSummary.communication_target}</span>
              <span className="tag">Mode - {interactionSummary.interaction_mode}</span>
              <span className="tag">Style - {interactionSummary.guidance_style}</span>
              <span className="tag">Reasoning - {latestTurn?.reasoning_status || "idle"}</span>
              <span className="tag">Stream - {streamStatus}</span>
            </div>
          )}

          {messages.length === 0 && (
            <p style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
              Start a session first. The communication agent will reply, then you can type the next patient or bystander message turn by turn.
            </p>
          )}

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              flex: 1,
              minHeight: 360,
              maxHeight: 460,
              overflowY: "auto",
              marginBottom: 14,
              padding: 12,
              borderRadius: 20,
              border: "1px solid var(--border)",
              background: "linear-gradient(180deg, #fffdf8 0%, #f7f1e6 100%)",
            }}
          >
            {messages.map((message, index) => (
              <ChatBubble key={`${message.role}-${index}`} role={message.role} text={message.text} />
            ))}
          </div>

          <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
            <div className="form-group">
              <label className="form-label">Next Responder Message</label>
              <textarea
                className="form-input"
                rows="3"
                value={draftMessage}
                onChange={(e) => setDraftMessage(e.target.value)}
                placeholder="Type what the patient or bystander says next..."
              />
            </div>

            {latestTurn?.quick_replies?.length > 0 && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                {latestTurn.quick_replies.map((reply) => (
                  <button key={reply} className="btn btn-outline btn-sm" onClick={() => setDraftMessage(reply)}>
                    {reply}
                  </button>
                ))}
              </div>
            )}

            <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={sendTurn} disabled={!draftMessage.trim() || phase === "sending" || !latestTurn}>
              {phase === "sending" ? "Sending..." : "Send Turn"}
            </button>
          </div>

          {latestTurn?.guidance_steps?.length > 0 && (
            <div className="form-group" style={{ marginTop: 16 }}>
              <label className="form-label">Immediate Step</label>
              <div className="instruction-box">
                {latestTurn.guidance_steps.map((step, index) => (
                  <div className="instruction-step" key={`${step}-${index}`}>
                    <span className="step-num">{index + 1}</span>
                    <p>{step}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--red-light)", color: "var(--red)", borderRadius: "var(--radius-sm)", fontSize: 13 }}>
              {error}
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="card">
            <div className="card-title">3. Session State</div>

            {!latestTurn && (
              <p style={{ fontSize: 13, color: "var(--text-sub)" }}>
                This panel will show whether the communication agent invoked reasoning or continued guidance directly.
              </p>
            )}

            {latestTurn && (
              <>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
                  <span className="tag">Reasoning - {latestTurn.reasoning_status}</span>
                  <span className="tag">Target - {latestTurn.interaction?.communication_target}</span>
                </div>

                <div className="form-group">
                  <label className="form-label">Session ID</label>
                  <div style={{ fontSize: 12, color: "var(--text-sub)", fontFamily: "'DM Mono', monospace" }}>
                    {sessionId || "-"}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Reasoning Refresh</label>
                  <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 12, fontSize: 13, color: "var(--text-sub)", lineHeight: 1.5 }}>
                    {latestTurn.interaction?.reasoning_refresh?.required ? "required" : "not required"} [{latestTurn.interaction?.reasoning_refresh?.priority}] - {latestTurn.reasoning_reason || latestTurn.interaction?.reasoning_refresh?.reason}
                  </div>
                </div>

                {latestTurn.reasoning_error && (
                  <div className="form-group">
                    <label className="form-label">Reasoning Error</label>
                    <div style={{ fontSize: 13, color: "var(--red)", lineHeight: 1.6 }}>{latestTurn.reasoning_error}</div>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Assistant Message</label>
                  <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>{latestTurn.assistant_message}</div>
                </div>

                {latestTurn.execution_updates?.length > 0 && (
                  <div className="form-group">
                    <label className="form-label">Execution Updates</label>
                    {latestTurn.execution_updates.some((item) => item.type === "inform_family") && (
                      <div
                        style={{
                          marginBottom: 10,
                          background: "linear-gradient(135deg, #eef7ea 0%, #dff0d6 100%)",
                          border: "1px solid #b8d7ad",
                          borderRadius: "var(--radius-sm)",
                          padding: 12,
                          fontSize: 13,
                          color: "#345b2c",
                          lineHeight: 1.5,
                        }}
                      >
                        Family notification is active in this session.
                      </div>
                    )}
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {latestTurn.execution_updates.map((item, index) => (
                        <div
                          key={`${item.type}-${index}`}
                          style={{
                            background: "var(--surface2)",
                            border: "1px solid var(--border)",
                            borderRadius: "var(--radius-sm)",
                            padding: 12,
                            fontSize: 13,
                            color: "var(--text-sub)",
                            lineHeight: 1.5,
                          }}
                        >
                          <div style={{ fontWeight: 600, color: "var(--text)" }}>
                            {item.type} [{item.status}]
                          </div>
                          <div>{item.detail}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {latestAssessment && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Assessment Snapshot</label>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <span className={`tag ${latestAssessment.clinical_assessment?.severity === "critical" ? "tag-red" : ""}`}>
                          Severity - {latestAssessment.clinical_assessment?.severity}
                        </span>
                        <span className="tag">Action - {latestAssessment.action?.recommended}</span>
                        <span className="tag">Clinical - {formatScore(latestAssessment.clinical_assessment?.clinical_confidence_score)}</span>
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Reasoning Summary</label>
                      <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
                        {latestAssessment.clinical_assessment?.reasoning_summary}
                      </div>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          <div className="card">
            <div className="card-title">Backend Debug View</div>
            <pre style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 14, overflowX: "auto", whiteSpace: "pre-wrap", fontSize: 12, lineHeight: 1.5, color: "var(--text-sub)", minHeight: 140 }}>
              {JSON.stringify(debugSnapshot, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
