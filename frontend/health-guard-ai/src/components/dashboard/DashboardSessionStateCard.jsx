import { MessageSquare, Users, BrainCircuit, Zap, Shield } from "lucide-react";

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

export default function DashboardSessionStateCard({
  sessionId,
  streamStatus,
  latestTurn,
  latestAssessment,
  error,
  historyCount,
  phase,
}) {
  // Communication Agent Logic
  const isCommRunning = phase === "sending" || phase === "starting";
  const commStatus = isCommRunning ? "pending" : (latestTurn ? "active" : "idle");
  let commStatusText = latestTurn ? "Listening" : "Standby";
  if (isCommRunning) commStatusText = "Thinking";
  if (streamStatus === "connecting") commStatusText = "Connecting";
  
  // Bystander Agent Logic
  const bystanderAvailable = latestTurn?.interaction?.bystander_available;
  const bystanderCanHelp = latestTurn?.interaction?.bystander_can_help;
  const guidanceSteps = latestTurn?.guidance_steps || [];
  let bystanderStatus = "idle";
  let bystanderStatusText = "Standby";
  
  if (bystanderAvailable) {
    bystanderStatus = "active";
    bystanderStatusText = "Engaged";
  } else if (bystanderAvailable === false) {
    bystanderStatus = "idle";
    bystanderStatusText = "No Bystander";
  }

  // Reasoning Agent Logic
  const reasoningState = latestTurn?.reasoning_status;
  let reasoningStatus = "idle";
  let reasoningStatusText = "Standby";
  let reasoningPulsing = false;
  
  if (reasoningState === "pending") {
    reasoningStatus = "pending";
    reasoningStatusText = "Analyzing";
    reasoningPulsing = true;
  } else if (reasoningState === "completed") {
    reasoningStatus = "success";
    reasoningStatusText = "Completed";
  } else if (reasoningState === "failed") {
    reasoningStatus = "pending"; 
    reasoningStatusText = "Failed";
  }

  // Execution Agent Logic
  const executionUpdates = latestTurn?.execution_updates || [];
  const actionStates = latestTurn?.action_states || [];
  
  let executionStatus = "idle";
  let executionStatusText = "Standby";
  let executionActivity = latestTurn 
    ? "Awaiting actionable triggers from the reasoning engine." 
    : "Standing by for emergency action triggers.";
  
  if (executionUpdates.length > 0 || actionStates.length > 0) {
    const hasPending = executionUpdates.some(u => ["pending_confirmation", "queued"].includes(u.status));
    const hasActive = executionUpdates.some(u => u.status === "active");
    
    if (hasActive || hasPending) {
      executionStatus = "active";
      executionStatusText = "Running";
      executionActivity = "Executing prioritized response protocol steps or dispatch sequences.";
    } else {
      executionStatus = "success";
      executionStatusText = "Executed";
      executionActivity = "Response plan actions completed successfully.";
    }
  }

  // Sentinel Agent Logic
  const sentinelStatus = "idle";
  const sentinelStatusText = "Unavailable";

  return (
    <div className="card" style={{ padding: "18px 20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div className="card-title" style={{ marginBottom: 0 }}>Agentic Workflow Monitor</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <span className="tag">Session - {sessionId || "-"}</span>
          <span className="tag">Stream - {streamStatus}</span>
          <span className="tag">History - {historyCount}</span>
        </div>
      </div>

      {error && (
        <div style={{ padding: "12px 14px", background: "var(--red-subtle)", color: "var(--red)", border: "1px solid var(--red-glow)", borderRadius: "var(--radius-sm)", fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Communication Agent */}
      <div className={`agent-card ${isCommRunning ? 'reasoning-pulse-border' : ''}`}>
        <div className="agent-header">
          <div className="agent-title-group">
            <div className={`agent-icon-box ${commStatus} ${isCommRunning ? 'pulsing' : ''}`}>
              <MessageSquare size={16} />
            </div>
            <span>Communication Agent</span>
          </div>
          <div className={`agent-status-tag ${commStatus}`}>
            {commStatusText}
          </div>
        </div>
        <div className="agent-detail">
          <div style={{ marginBottom: 4, fontWeight: 600, color: "var(--text)" }}>Interaction Analysis:</div>
          <div style={{ marginBottom: 10 }}>Extracting intent, responder availability, and mapping clinical facts.</div>
          
          <div className="agent-meta-row">
            {latestTurn ? (
              <>
                <span className="tag">Patient Status - {toTitleCase(latestTurn.interaction?.patient_response_status)}</span>
                {latestTurn.interaction?.new_fact_keys && latestTurn.interaction.new_fact_keys.length > 0 && (
                   <span className="tag tag-green">New Facts Logged</span>
                )}
              </>
            ) : (
                <span className="tag">Awaiting Dialogue</span>
            )}
          </div>
          {latestTurn?.communication_analysis?.ai_server_error && (
            <div style={{ marginTop: 10, padding: "8px 12px", background: "var(--red-subtle)", color: "var(--red)", border: "1px solid var(--red-glow)", borderRadius: 6, fontSize: 13, lineHeight: 1.5 }}>
              <strong style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.5px" }}>AI Server Fallback</strong>
              <div style={{ marginTop: 2, opacity: 0.9 }}>{latestTurn.communication_analysis.ai_server_error}</div>
            </div>
          )}
        </div>
      </div>

      {/* Bystander Agent */}
      <div className="agent-card">
        <div className="agent-header">
          <div className="agent-title-group">
            <div className={`agent-icon-box ${bystanderStatus}`}>
              <Users size={16} />
            </div>
            <span>Bystander Agent</span>
          </div>
          <div className={`agent-status-tag ${bystanderStatus}`}>
            {bystanderStatusText}
          </div>
        </div>
        <div className="agent-detail">
          <div style={{ marginBottom: 4, fontWeight: 600, color: "var(--text)" }}>Scene Evaluation:</div>
          <div style={{ marginBottom: guidanceSteps.length > 0 ? 10 : 0 }}>
            {!latestTurn ? "Standing by to evaluate scene dynamics." :
              (bystanderAvailable ? 
                (bystanderCanHelp ? "Bystander confirmed and capable of providing assistance." : "Bystander present but unable to help.") : 
                "No capable bystander identified at the scene.")}
          </div>
          
          {guidanceSteps.length > 0 && (
            <div style={{ marginTop: 10, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "6px", padding: "12px" }}>
              <div style={{ fontSize: 10, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 8, letterSpacing: "0.5px" }}>
                Immediate Instructions Provided
              </div>
              <ul style={{ paddingLeft: 18, margin: 0, fontSize: 13, lineHeight: 1.5, color: "var(--text-sub)" }}>
                {guidanceSteps.map((step, idx) => (
                  <li key={idx} style={{ marginBottom: 4 }}>{step}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Reasoning Agent */}
      <div className={`agent-card ${reasoningPulsing ? 'reasoning-pulse-border' : ''}`}>
        <div className="agent-header">
          <div className="agent-title-group">
            <div className={`agent-icon-box ${reasoningStatus} ${reasoningPulsing ? 'pulsing' : ''}`}>
              <BrainCircuit size={16} />
            </div>
            <span>Reasoning Agent</span>
          </div>
          <div className={`agent-status-tag ${reasoningStatus}`}>
            {reasoningStatusText}
          </div>
        </div>
        
        <div className="agent-detail">
          <div style={{ marginBottom: 4, fontWeight: 600, color: "var(--text)" }}>Clinical Justification:</div>
          <div style={{ marginBottom: 12 }}>
            {!latestTurn ? "Standing by to monitor vitals and evaluate clinical severity." :
              (latestTurn.reasoning_status === "pending" ? (
                 <>
                   <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, color: "var(--amber)" }}>
                     <div className="typing-dots"><span></span><span></span><span></span></div>
                     Evaluating latest vitals and context...
                   </div>
                   {latestAssessment?.clinical_assessment?.reasoning_summary && (
                     <div style={{ opacity: 0.65, borderLeft: "2px solid var(--border)", paddingLeft: 8, fontSize: 13 }}>
                       <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", marginBottom: 2 }}>Previous Run:</div>
                       {latestAssessment.clinical_assessment.reasoning_summary}
                     </div>
                   )}
                 </>
              ) : (
                 latestAssessment?.clinical_assessment?.reasoning_summary || "Awaiting significant changes in state or vital signs to run full reasoning refresh."
              ))
            }
            
            {/* Show why it triggered if running/completed just now */}
            {latestTurn?.reasoning_reason && latestTurn.reasoning_status === "pending" && (
              <div style={{ marginTop: 6, fontSize: 12, fontStyle: "italic", opacity: 0.8 }}>
                Trigger: {latestTurn.reasoning_reason}
              </div>
            )}
          </div>
          
          {latestAssessment && (
            <div className="agent-meta-row" style={{ marginTop: 12 }}>
              <span className={`tag ${latestAssessment.clinical_assessment?.severity === "critical" ? "tag-red" : ""}`}>
                Severity - {formatSeverity(latestAssessment.clinical_assessment?.severity)}
              </span>
              <span className="tag">Confidence - {formatScore(latestAssessment.clinical_assessment?.clinical_confidence_score)}</span>
              {latestTurn.reasoning_run_count > 0 && (
                <span className="tag">Runs: {latestTurn.reasoning_run_count}</span>
              )}
              {latestTurn?.interaction?.reasoning_refresh?.required && (
                <span className="tag tag-orange">Rerun Queued</span>
              )}
            </div>
          )}

          {(latestTurn?.reasoning_error || latestAssessment?.clinical_assessment?.ai_server_error) && (
            <div style={{ marginTop: 10, padding: "8px 12px", background: "var(--red-subtle)", color: "var(--red)", border: "1px solid var(--red-glow)", borderRadius: 6, fontSize: 13, lineHeight: 1.5 }}>
              <strong style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.5px" }}>AI Server Fallback</strong>
              <div style={{ marginTop: 2, opacity: 0.9 }}>
                {latestTurn?.reasoning_error || latestAssessment?.clinical_assessment?.ai_server_error}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Execution Agent */}
      <div className="agent-card">
        <div className="agent-header">
          <div className="agent-title-group">
            <div className={`agent-icon-box ${executionStatus}`}>
              <Zap size={16} />
            </div>
            <span>Execution Agent</span>
          </div>
          <div className={`agent-status-tag ${executionStatus}`}>
            {executionStatusText}
          </div>
        </div>
        <div className="agent-detail">
          <div style={{ marginBottom: 4, fontWeight: 600, color: "var(--text)" }}>Action Dispatcher:</div>
          <div style={{ marginBottom: executionUpdates.length > 0 ? 10 : 0 }}>{executionActivity}</div>
          
          {executionUpdates.length > 0 && (
            <div className="agent-meta-row" style={{ marginTop: 6, gap: 6 }}>
              {executionUpdates.map((update, idx) => (
                <span key={idx} className={`tag ${update.status === "completed" ? "tag-green" : update.status === "active" ? "tag-blue" : ""}`}>
                  {toTitleCase(update.type)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Sentinel Agent */}
      <div className="agent-card" style={{ opacity: 0.6 }}>
        <div className="agent-header">
          <div className="agent-title-group">
            <div className={`agent-icon-box ${sentinelStatus}`}>
              <Shield size={16} />
            </div>
            <span>Sentinel Agent</span>
          </div>
          <div className={`agent-status-tag ${sentinelStatus}`}>
            {sentinelStatusText}
          </div>
        </div>
        <div className="agent-detail">
          <div style={{ marginBottom: 4, fontWeight: 600, color: "var(--text)" }}>Safety Guardrails:</div>
          <div>Agent is currently deactivated. Safety protocols are intrinsically handled by the base reasoning pipeline.</div>
        </div>
      </div>

    </div>
  );
}
