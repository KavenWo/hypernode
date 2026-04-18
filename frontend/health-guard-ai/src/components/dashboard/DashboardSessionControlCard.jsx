function StatusTag({ active, label, danger = false }) {
  return (
    <span className={`tag ${danger ? "tag-red" : ""}`} style={{ opacity: active ? 1 : 0.65 }}>
      {active ? "Live" : "Off"} - {label}
    </span>
  );
}

export default function DashboardSessionControlCard({
  profile,
  runtimeStatus,
  motionState,
  setMotionState,
  phase,
  streamStatus,
  startSession,
  resetConversation,
}) {
  return (
    <div className="card">
      <div className="card-title">Agent Session Setup</div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        <StatusTag active={Boolean(runtimeStatus?.backend_ok)} label="Backend" danger={!runtimeStatus?.backend_ok} />
        <StatusTag active={Boolean(runtimeStatus?.gemini_configured)} label="Gemini" />
        <StatusTag active={Boolean(runtimeStatus?.vertex_search_configured)} label="Vertex Search" />
        <span className="tag">Stream - {streamStatus}</span>
      </div>

      <div className="dashboard-summary-card">
        <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
          AI Context Source
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6 }}>{profile.name}</div>
        <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
          The backend session uses this dashboard-selected profile via <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{profile.userId}</span>.
        </div>
      </div>

      <div className="form-group" style={{ marginTop: 16 }}>
        <label className="form-label">Detected Motion State</label>
        <select className="form-input" value={motionState} onChange={(event) => setMotionState(event.target.value)}>
          <option value="rapid_descent">rapid_descent</option>
          <option value="no_movement">no_movement</option>
          <option value="stumble">stumble</option>
          <option value="slow_descent">slow_descent</option>
        </select>
      </div>

      <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6, marginTop: 10 }}>
        Start a session to run the controlled fall flow: opening check, bystander check, consciousness, breathing, optional flags, reasoning, then deterministic execution.
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
        <button
          className="btn btn-primary"
          style={{ flex: 1, justifyContent: "center" }}
          onClick={startSession}
          disabled={phase === "starting" || phase === "sending"}
        >
          {phase === "starting" ? "Starting..." : "Start Session"}
        </button>
        <button
          className="btn btn-ghost"
          onClick={resetConversation}
          title="Stops the active backend session and clears the current dashboard conversation."
        >
          Reset Session
        </button>
      </div>
    </div>
  );
}
