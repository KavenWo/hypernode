function formatScore(value) {
  return typeof value === "number" ? value.toFixed(2) : value ?? "-";
}

function formatSeverity(value) {
  if (!value) {
    return "Unknown";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function toTitleCase(value) {
  return (value || "unknown")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getReasoningTone(status) {
  if (status === "pending") {
    return {
      panelClass: "dashboard-tone-pending",
      title: "Reasoning Agent Processing",
      summary: "A clinical reasoning refresh is running in the background.",
    };
  }
  if (status === "failed") {
    return {
      panelClass: "dashboard-tone-critical",
      title: "Reasoning Agent Failed",
      summary: "The background reasoning run failed and needs attention.",
    };
  }
  if (status === "completed") {
    return {
      panelClass: "dashboard-tone-success",
      title: "Reasoning Snapshot Ready",
      summary: "The latest reasoning result is available for the session.",
    };
  }
  return {
    panelClass: "dashboard-tone-neutral",
    title: "Reasoning Idle",
    summary: "No background reasoning run is active right now.",
  };
}

export default function DashboardSessionStateCard({
  sessionId,
  streamStatus,
  latestTurn,
  latestAssessment,
  error,
  historyCount,
}) {
  const reasoningTone = getReasoningTone(latestTurn?.reasoning_status);

  return (
    <div className="dashboard-stack">
      <div className="card">
        <div className="card-title">Session State</div>

        {!latestTurn && (
          <p style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
            This panel reflects what the backend currently knows about the live session once the conversation starts.
          </p>
        )}

        {latestTurn && (
          <>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
              <span className="tag">Session - {sessionId || "-"}</span>
              <span className="tag">Reasoning - {latestTurn.reasoning_status}</span>
              <span className="tag">Stream - {streamStatus}</span>
            </div>

            <div className={`dashboard-summary-card ${reasoningTone.panelClass}`}>
              <div className="form-label" style={{ marginBottom: 6 }}>{reasoningTone.title}</div>
              <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6, marginBottom: 8 }}>
                {reasoningTone.summary}
              </div>
              <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
                {latestTurn.interaction?.reasoning_refresh?.required ? "required" : "not required"} [{latestTurn.interaction?.reasoning_refresh?.priority}] - {latestTurn.reasoning_reason || latestTurn.interaction?.reasoning_refresh?.reason}
              </div>
              {latestTurn.reasoning_status === "pending" && (
                <div className="typing-dots" aria-label="Reasoning agent processing" style={{ marginTop: 10 }}>
                  <span />
                  <span />
                  <span />
                </div>
              )}
              {latestTurn.reasoning_error && (
                <div style={{ marginTop: 10, fontSize: 13, color: "var(--red)", lineHeight: 1.6 }}>
                  {latestTurn.reasoning_error}
                </div>
              )}
            </div>

            <div className="form-group" style={{ marginTop: 16 }}>
              <label className="form-label">Assistant Message</label>
              <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.7 }}>
                {latestTurn.assistant_message}
              </div>
            </div>

            {latestTurn.guidance_steps?.length > 0 && (
              <div className="form-group">
                <label className="form-label">Immediate Steps</label>
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
          </>
        )}
      </div>



      <div className="card">
        <div className="card-title">Assessment Snapshot</div>

        {!latestAssessment && (
          <p style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
            Once reasoning is invoked, the latest severity, action, and summary will appear here.
          </p>
        )}

        {latestAssessment && (
          <>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
              <span className={`tag ${latestAssessment.clinical_assessment?.severity === "critical" ? "tag-red" : ""}`}>
                Severity - {formatSeverity(latestAssessment.clinical_assessment?.severity)}
              </span>
              <span className="tag">Action - {latestAssessment.action?.recommended}</span>
              <span className="tag">Clinical - {formatScore(latestAssessment.clinical_assessment?.clinical_confidence_score)}</span>
            </div>

            <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.7 }}>
              {latestAssessment.clinical_assessment?.reasoning_summary}
            </div>
          </>
        )}
      </div>

      <div className="card">
        <div className="card-title">Dashboard Activity</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
          <span className="tag">History entries - {historyCount}</span>
          <span className="tag">Stream - {streamStatus}</span>
        </div>
        {error ? (
          <div style={{ padding: "12px 14px", background: "var(--red-subtle)", color: "var(--red)", border: "1px solid var(--red-glow)", borderRadius: "var(--radius-sm)", fontSize: 13 }}>
            {error}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.7 }}>
            Incident history is updated automatically when the backend moves into a dispatch or pending-dispatch action.
          </div>
        )}
      </div>
    </div>
  );
}
