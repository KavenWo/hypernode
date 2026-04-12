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

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

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

function StatusTag({ active, label, danger = false }) {
  return (
    <span className={`tag ${danger ? "tag-red" : ""}`} style={{ opacity: active ? 1 : 0.65 }}>
      {active ? "Live" : "Off"} · {label}
    </span>
  );
}

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(2) : value ?? "-";
}

export default function MvpTestPage() {
  const [event, setEvent] = useState(DEFAULT_EVENT);
  const [vitals, setVitals] = useState(DEFAULT_VITALS);
  const [status, setStatus] = useState(null);
  const [patients, setPatients] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [assessment, setAssessment] = useState(null);
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;

    async function loadStatus() {
      try {
        const [statusResponse, patientsResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/v1/events/fall/status`),
          fetch(`${API_BASE_URL}/api/v1/events/fall/patients`),
        ]);
        const payload = await statusResponse.json();
        const patientsPayload = await patientsResponse.json();
        const nextPatients = normalizePatients(patientsPayload.patients);
        if (!ignore) {
          setStatus(payload);
          setPatients(nextPatients);
          setEvent((current) => {
            if (nextPatients.length === 0) {
              return current;
            }

            if (nextPatients.some((patient) => patient.user_id === current.user_id)) {
              return current;
            }

            return {
              ...current,
              user_id: nextPatients[0].user_id,
            };
          });
        }
      } catch (err) {
        if (!ignore) {
          setStatus({
            backend_ok: false,
            gemini_configured: false,
            vertex_search_configured: false,
          });
        }
      }
    }

    loadStatus();
    return () => {
      ignore = true;
    };
  }, []);

  const eventPayload = {
    ...event,
    confidence_score: Number(event.confidence_score),
  };

  const vitalsPayload = {
    user_id: event.user_id,
    heart_rate: Number(vitals.heart_rate),
    blood_pressure_systolic: Number(vitals.blood_pressure_systolic),
    blood_pressure_diastolic: Number(vitals.blood_pressure_diastolic),
    blood_oxygen_sp02: Number(vitals.blood_oxygen_sp02),
  };

  function updateEvent(field, value) {
    setEvent((current) => ({ ...current, [field]: value }));
  }

  function updateSelectedUser(userId) {
    setEvent((current) => ({ ...current, user_id: userId }));
  }

  function updateVitals(field, value) {
    setVitals((current) => ({ ...current, [field]: value }));
  }

  function updateAnswer(questionId, value) {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  }

  async function requestQuestions() {
    setPhase("loading_questions");
    setError("");
    setAssessment(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: eventPayload,
          vitals: vitalsPayload,
        }),
      });

      if (!response.ok) {
        throw new Error(`Question request failed (${response.status})`);
      }

      const payload = await response.json();
      setQuestions(payload.questions || []);
      setAnswers({});
      setPhase("questions_ready");
    } catch (err) {
      setError(err.message || "Unable to load questions from the backend.");
      setPhase("error");
    }
  }

  async function submitAssessment() {
    setPhase("running_assessment");
    setError("");

    try {
      const patient_answers = questions.map((question) => ({
        question_id: question.question_id,
        answer: answers[question.question_id] || "",
      }));

      const response = await fetch(`${API_BASE_URL}/api/v1/events/fall/assess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: eventPayload,
          vitals: vitalsPayload,
          patient_answers,
        }),
      });

      if (!response.ok) {
        throw new Error(`Assessment request failed (${response.status})`);
      }

      const payload = await response.json();
      setAssessment(payload);
      setPhase("result_ready");
    } catch (err) {
      setError(err.message || "Unable to run the MVP assessment.");
      setPhase("error");
    }
  }

  function fillPreset(preset) {
    if (preset === "head_injury") {
      setEvent({
        user_id: "user_001",
        timestamp: "2024-04-10T12:00:00Z",
        motion_state: "rapid_descent",
        confidence_score: 0.98,
      });
      setVitals({
        heart_rate: 118,
        blood_pressure_systolic: 92,
        blood_pressure_diastolic: 58,
        blood_oxygen_sp02: 91,
      });
      setAnswers({
        consciousness: "Yes, but I feel dizzy and slow to respond.",
        pain_mobility: "I have strong pain in my hip and I cannot stand up safely.",
        head_injury_blood_thinner: "I hit my head and I take blood thinners.",
      });
      return;
    }

    setEvent({
      user_id: "user_healthy_001",
      timestamp: "2024-04-10T12:00:00Z",
      motion_state: "stumble",
      confidence_score: 0.62,
    });
    setVitals({
      heart_rate: 82,
      blood_pressure_systolic: 126,
      blood_pressure_diastolic: 78,
      blood_oxygen_sp02: 97,
    });
    setAnswers({
      consciousness: "Yes, I am awake and speaking clearly.",
      pain_mobility: "I have mild pain but I can move safely.",
      observation: "I slipped, did not hit my head, and stayed conscious.",
    });
  }

  function resetFlow() {
    setQuestions([]);
    setAnswers({});
    setAssessment(null);
    setError("");
    setPhase("idle");
  }

  const canRunAssessment =
    questions.length > 0 && questions.every((question) => (answers[question.question_id] || "").trim().length > 0);
  const selectedPatient = patients.find((patient) => patient.user_id === event.user_id);
  const debugSnapshot = assessment
    ? {
        status: assessment.status,
        responder_mode: assessment.responder_mode,
        severity: assessment.clinical_assessment?.severity,
        action: assessment.action?.recommended,
        fallback_used: assessment.audit?.fallback_used,
        grounding_source: assessment.grounding?.source,
        dispatch_triggered: assessment.audit?.dispatch_triggered,
        incident_id: assessment.incident_id,
        reasoning_summary: assessment.clinical_assessment?.reasoning_summary,
      }
    : status;

  return (
    <div>
      <div className="page-header">
        <h1>MVP Test Console</h1>
        <p>Dedicated frontend test harness for the fall triage backend flow without disturbing the existing UX pages.</p>
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
            <button className="btn btn-outline btn-sm" onClick={() => fillPreset("head_injury")}>Load High-Risk Preset</button>
            <button className="btn btn-outline btn-sm" onClick={() => fillPreset("low_risk")}>Load Low-Risk Preset</button>
            <button className="btn btn-outline btn-sm" onClick={resetFlow}>Reset Flow</button>
          </div>
        </div>

        <p style={{ fontSize: 13, color: "var(--text-sub)" }}>
          API Base: <span style={{ fontFamily: "'DM Mono', monospace" }}>{API_BASE_URL}</span>
        </p>
        {status?.vertex_project && (
          <p style={{ fontSize: 13, color: "var(--text-sub)", marginTop: 6 }}>
            Vertex Config: <span style={{ fontFamily: "'DM Mono', monospace" }}>{status.vertex_project}</span>
          </p>
        )}
      </div>

      <div className="grid-3">
        <div className="card">
          <div className="card-title">1. Event And Vitals</div>

          <div className="form-group">
            <label className="form-label">User ID</label>
            <select className="form-input" value={event.user_id} onChange={(e) => updateSelectedUser(e.target.value)}>
              {patients.length === 0 && <option value={event.user_id}>{event.user_id}</option>}
              {patients.map((patient) => (
                <option key={patient.user_id} value={patient.user_id}>
                  {patient.full_name} ({patient.user_id})
                </option>
              ))}
            </select>
            {patients.length > 0 && (
              <p style={{ fontSize: 12, color: "var(--text-sub)", marginTop: 6 }}>
                Selected profile: {selectedPatient?.age ?? "?"} years old · {selectedPatient?.blood_thinners ? "blood thinners" : "no blood thinners"}
              </p>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Timestamp</label>
            <input className="form-input" value={event.timestamp} onChange={(e) => updateEvent("timestamp", e.target.value)} />
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

          <div className="form-group">
            <label className="form-label">Fall Detection Confidence</label>
            <input className="form-input" type="number" min="0" max="1" step="0.01" value={event.confidence_score} onChange={(e) => updateEvent("confidence_score", e.target.value)} />
          </div>

          <div className="divider" />

          <div className="form-group">
            <label className="form-label">Heart Rate</label>
            <input className="form-input" type="number" value={vitals.heart_rate} onChange={(e) => updateVitals("heart_rate", e.target.value)} />
          </div>

          <div className="grid-2" style={{ marginBottom: 16 }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Systolic BP</label>
              <input className="form-input" type="number" value={vitals.blood_pressure_systolic} onChange={(e) => updateVitals("blood_pressure_systolic", e.target.value)} />
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Diastolic BP</label>
              <input className="form-input" type="number" value={vitals.blood_pressure_diastolic} onChange={(e) => updateVitals("blood_pressure_diastolic", e.target.value)} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Blood Oxygen SpO2</label>
            <input className="form-input" type="number" step="0.1" value={vitals.blood_oxygen_sp02} onChange={(e) => updateVitals("blood_oxygen_sp02", e.target.value)} />
          </div>

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={requestQuestions} disabled={phase === "loading_questions" || phase === "running_assessment"}>
            {phase === "loading_questions" ? "Requesting Questions..." : "Generate Triage Questions"}
          </button>
        </div>

        <div className="card">
          <div className="card-title">2. Triage Questions</div>

          {questions.length === 0 && (
            <p style={{ fontSize: 13, color: "var(--text-sub)" }}>
              Request questions from the backend first. This step mirrors the intended MVP frontend flow.
            </p>
          )}

          {questions.map((question, index) => (
            <div key={question.question_id} className="form-group">
              <label className="form-label">{index + 1}. {question.question_id}</label>
              <p style={{ fontSize: 13, color: "var(--text-sub)", marginBottom: 8 }}>{question.text}</p>
              <textarea
                className="form-input"
                rows="4"
                value={answers[question.question_id] || ""}
                onChange={(e) => updateAnswer(question.question_id, e.target.value)}
                placeholder="Enter the patient or bystander answer here..."
              />
            </div>
          ))}

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={submitAssessment} disabled={!canRunAssessment || phase === "running_assessment"}>
            {phase === "running_assessment" ? "Running Assessment..." : "Run Reasoning Once"}
          </button>

          {error && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--red-light)", color: "var(--red)", borderRadius: "var(--radius-sm)", fontSize: 13 }}>
              {error}
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="card">
            <div className="card-title">3. Assessment Result</div>

            {!assessment && (
              <p style={{ fontSize: 13, color: "var(--text-sub)" }}>
                The result panel will show the Phase 1 contract: severity, confidence bands, action, red flags, grounded guidance, and dispatch state.
              </p>
            )}

            {assessment && (
              <>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
                  <span className={`tag ${assessment.clinical_assessment?.severity === "critical" ? "tag-red" : ""}`}>
                    Severity · {assessment.clinical_assessment?.severity}
                  </span>
                  <span className="tag">Action · {assessment.action?.recommended}</span>
                  <span className="tag">Responder · {assessment.responder_mode}</span>
                  <span className="tag">Grounding · {assessment.grounding?.source}</span>
                </div>

                <div className="form-group">
                  <label className="form-label">Confidence</label>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <span className="tag">Detection · {assessment.detection?.fall_detection_confidence_band} ({formatScore(assessment.detection?.fall_detection_confidence_score)})</span>
                    <span className="tag">Clinical · {assessment.clinical_assessment?.clinical_confidence_band} ({formatScore(assessment.clinical_assessment?.clinical_confidence_score)})</span>
                    <span className="tag">Action · {assessment.clinical_assessment?.action_confidence_band} ({formatScore(assessment.clinical_assessment?.action_confidence_score)})</span>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Reasoning Summary</label>
                  <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>{assessment.clinical_assessment?.reasoning_summary}</div>
                </div>

                <div className="form-group">
                  <label className="form-label">Red Flags</label>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {(assessment.clinical_assessment?.red_flags || []).map((flag) => (
                      <span className="tag tag-red" key={flag}>{flag}</span>
                    ))}
                    {(assessment.clinical_assessment?.red_flags || []).length === 0 && (
                      <p style={{ fontSize: 13, color: "var(--text-sub)" }}>No normalized red flags were returned.</p>
                    )}
                  </div>
                </div>

                {assessment.clinical_assessment?.uncertainty?.length > 0 && (
                  <div className="form-group">
                    <label className="form-label">Uncertainty</label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {assessment.clinical_assessment.uncertainty.map((item, index) => (
                        <div key={`${item}-${index}`} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 12, fontSize: 13, color: "var(--text-sub)", lineHeight: 1.5 }}>
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Instructions</label>
                  <div className="instruction-box">
                    {(assessment.guidance?.steps || []).map((step, index) => (
                      <div className="instruction-step" key={`${step}-${index}`}>
                        <span className="step-num">{index + 1}</span>
                        <p>{step}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {assessment.guidance?.warnings?.length > 0 && (
                  <div className="form-group">
                    <label className="form-label">Warnings</label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {assessment.guidance.warnings.map((warning, index) => (
                        <div key={`${index}-${warning.slice(0, 20)}`} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 12, fontSize: 13, color: "var(--text-sub)", lineHeight: 1.5 }}>
                          {warning}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {assessment.grounding?.preview?.length > 0 && (
                  <div className="form-group">
                    <label className="form-label">Grounded Guidance Preview</label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {assessment.grounding.preview.map((snippet, index) => (
                        <div key={`${index}-${snippet.slice(0, 20)}`} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 12, fontSize: 13, color: "var(--text-sub)", lineHeight: 1.5 }}>
                          {snippet}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {assessment.grounding?.references?.length > 0 && (
                  <div className="form-group">
                    <label className="form-label">Guidance References</label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {assessment.grounding.references.map((reference, index) => (
                        <div
                          key={`${reference.document_id || reference.uri || reference.link || index}`}
                          style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 12, fontSize: 13, color: "var(--text-sub)", lineHeight: 1.5 }}
                        >
                          <div style={{ color: "var(--text)", marginBottom: 4 }}>
                            {reference.title || reference.document_id || `Reference ${index + 1}`}
                          </div>
                          {(reference.link || reference.uri) && (
                            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
                              {reference.link || reference.uri}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 10, fontSize: 13, color: "var(--text-sub)" }}>
                  Dispatch Triggered: <strong style={{ color: "var(--text)" }}>{assessment.audit?.dispatch_triggered ? "Yes" : "No"}</strong>
                </div>
                <div style={{ marginTop: 6, fontSize: 13, color: "var(--text-sub)" }}>
                  Status: <strong style={{ color: "var(--text)" }}>{assessment.status}</strong>
                </div>
                <div style={{ marginTop: 6, fontSize: 13, color: "var(--text-sub)" }}>
                  Event Validity: <strong style={{ color: "var(--text)" }}>{assessment.detection?.event_validity}</strong>
                </div>
                <div style={{ marginTop: 6, fontSize: 13, color: "var(--text-sub)" }}>
                  Incident ID: <span style={{ fontFamily: "'DM Mono', monospace", color: "var(--text)" }}>{assessment.incident_id || "None"}</span>
                </div>
              </>
            )}
          </div>

          <div className="card">
            <div className="card-title">Backend Debug View</div>
            <p style={{ fontSize: 13, color: "var(--text-sub)", marginBottom: 10 }}>
              Logs are still the best place to inspect internal agent details. This panel now focuses on the normalized Phase 1 fields that matter for MVP testing.
            </p>
            <pre style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 14, overflowX: "auto", whiteSpace: "pre-wrap", fontSize: 12, lineHeight: 1.5, color: "var(--text-sub)", minHeight: 140 }}>
              {JSON.stringify(debugSnapshot, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
