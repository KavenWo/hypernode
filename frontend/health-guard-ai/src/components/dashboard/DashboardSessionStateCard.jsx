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
  if (!value) return "Unknown";
  const str = String(value);
  return str
    .split("_")
    .map((part) => (part ? part.charAt(0).toUpperCase() + part.slice(1) : ""))
    .join(" ");
}

function formatFlags(flags) {
  if (!Array.isArray(flags) || flags.length === 0) {
    return "None";
  }
  return flags.filter(Boolean).map((flag) => toTitleCase(flag)).join(", ");
}

function formatBooleanLabel(value, positiveLabel, negativeLabel = "Unknown") {
  if (value === true) {
    return positiveLabel;
  }
  if (value === false) {
    return negativeLabel;
  }
  return "Unknown";
}

export default function DashboardSessionStateCard({
  sessionId,
  streamStatus,
  latestTurn,
  latestAssessment,
  latestVideoAnalysis,
  error,
  historyCount,
  phase,
}) {
  const canonicalState = latestTurn?.state;
  const canonicalCommunication = latestTurn?.canonical_communication_state;
  const canonicalExecution = latestTurn?.execution_state;
  const executionPlan = latestTurn?.execution_analysis;
  const grounding = latestAssessment?.protocol_guidance;
  const reasoningDecision = latestTurn?.reasoning_decision;
  const reasoningRuns = latestTurn?.reasoning_runs || [];
  const latestReasoningRun = reasoningRuns.at?.(-1) || null;
  const detection = latestAssessment?.detection;
  const protocolGuidance = latestAssessment?.protocol_guidance;
  const isSentinelAnalyzing = phase === "analyzing_video";
  const sentinelDetection = detection || (latestVideoAnalysis
    ? {
        severity: latestVideoAnalysis?.severity || 'low',
        motion_state: latestVideoAnalysis?.motion_state,
        fall_detection_confidence_score: latestVideoAnalysis?.confidence_score,
        event_validity: latestVideoAnalysis?.fall_detected ? "likely_true" : "unlikely_false",
        video_id: latestVideoAnalysis?.video_id,
        video_source: latestVideoAnalysis?.video_source,
        video_summary: latestVideoAnalysis?.summary,
        fall_detected: latestVideoAnalysis?.fall_detected
      }
    : null);

  // Communication Agent Logic
  const isCommRunning = phase === "sending" || phase === "starting";
  const commStatus = isCommRunning ? "pending" : (latestTurn ? "active" : "idle");
  let commStatusText = latestTurn ? "Listening" : "Standby";
  if (isCommRunning) commStatusText = "Thinking";
  if (streamStatus === "connecting") commStatusText = "Connecting";

  // Bystander Agent Logic
  const bystanderAvailable = canonicalCommunication?.bystander_present ?? latestTurn?.interaction?.bystander_available;
  const bystanderCanHelp = latestTurn?.interaction?.bystander_can_help;
  const protocolSteps = protocolGuidance?.steps || [];
  const guidanceSteps = protocolSteps.length > 0 ? protocolSteps : (latestTurn?.guidance_steps || []);
  const currentGuidanceStepIndex = canonicalExecution?.guidance_step_index ?? 0;
  const currentGuidanceStep =
    guidanceSteps.length > 0
      ? guidanceSteps[Math.min(currentGuidanceStepIndex, guidanceSteps.length - 1)]
      : "";
  const protocolKey = protocolGuidance?.protocol_key || canonicalExecution?.guidance_protocol || "";
  const protocolTitle = protocolGuidance?.title || (protocolKey ? toTitleCase(protocolKey) : "");
  const groundingStatus = protocolGuidance?.grounding_status || "not_needed";
  const protocolReady = Boolean(protocolGuidance?.ready_for_communication && guidanceSteps.length > 0);
  const groundingRequired = Boolean(protocolGuidance?.grounding_required || protocolKey);
  const bystanderGroundingActive = Boolean(bystanderAvailable && bystanderCanHelp && groundingRequired);
  let bystanderStatus = "idle";
  let bystanderStatusText = "Standby";

  if (!latestTurn) {
    bystanderStatus = "idle";
    bystanderStatusText = "Standby";
  } else if (groundingStatus === "pending") {
    bystanderStatus = "pending";
    bystanderStatusText = "Grounding";
  } else if (protocolReady) {
    bystanderStatus = "success";
    bystanderStatusText = "Grounded";
  } else if (bystanderGroundingActive) {
    bystanderStatus = "active";
    bystanderStatusText = "Searching";
  } else if (bystanderAvailable && bystanderCanHelp) {
    bystanderStatus = "active";
    bystanderStatusText = "Ready";
  } else if (bystanderAvailable) {
    bystanderStatus = "idle";
    bystanderStatusText = "Bystander";
  } else {
    bystanderStatus = "idle";
    bystanderStatusText = "No Bystander";
  }


  const groundingActive = Boolean(groundingRequired && groundingStatus !== "not_needed");

  let bystanderActivity = "Standing by for protocol-specific medical guidance triggers.";
  if (!latestTurn) {
    bystanderActivity = "Standing by for grounded first-aid protocol triggers.";
  } else if (groundingStatus === "pending") {
    bystanderActivity = protocolTitle
      ? `Retrieving grounded ${protocolTitle} instructions from Vertex AI Search medical handbooks.`
      : "Retrieving grounded medical instructions from Vertex AI Search.";
  } else if (protocolReady) {
    bystanderActivity = protocolTitle
      ? `Grounded ${protocolTitle} instructions successfully retrieved and ready for use.`
      : "Grounded medical instructions successfully retrieved and ready for use.";
  } else if (groundingRequired) {
    bystanderActivity = `Medical protocol identified (${protocolKey}). Preparing retrieval intents...`;
  } else if (bystanderAvailable) {
    bystanderActivity = "A bystander is present. Awaiting clinical reasoning to trigger protocol grounding.";
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
  let isExecutionPulsing = false;
  let executionActivity = latestTurn
    ? "Awaiting actionable triggers from the reasoning engine."
    : "Standing by for emergency action triggers.";

  if (canonicalExecution?.dispatch_status === "pending_confirmation") {
    executionStatus = "pending";
    executionStatusText = "Countdown";
    isExecutionPulsing = true;
    executionActivity = "Dispatch confirmation window is active before emergency services are contacted automatically.";
  } else if (
    canonicalExecution?.dispatch_status === "confirmed" ||
    canonicalExecution?.dispatch_status === "auto_dispatched"
  ) {
    executionStatus = "success";
    executionStatusText = "Dispatched";
    executionActivity = "Emergency dispatch has been triggered and the execution lane is now active.";
  } else if (executionUpdates.length > 0 || actionStates.length > 0) {
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

  if (canonicalExecution?.phase === "guidance" && guidanceSteps.length > 0) {
    executionStatus = "active";
    executionStatusText = "Guiding";
    executionActivity = currentGuidanceStep
      ? `Running grounded execution guidance. Current step: "${currentGuidanceStep}"`
      : "Running grounded execution guidance for the decided scenario.";
  }

  // Sentinel Agent Logic
  const sentinelStatus = isSentinelAnalyzing
    ? "pending"
    : sentinelDetection
      ? (sentinelDetection.fall_detected === false ? "success" : (sentinelDetection.fall_detected || detection ? "success" : "idle"))
      : "idle";

  const sentinelStatusText = isSentinelAnalyzing
    ? "Analyzing"
    : latestVideoAnalysis
      ? (latestVideoAnalysis.fall_detected ? "Fall Detected" : "No Fall Detected")
      : sentinelDetection?.video_id
        ? "Video Analyzed"
        : sentinelDetection
          ? "Detected"
          : "Standby";

  return (
    <div className="card" style={{ padding: "14px 16px" }}>
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

      {/* Sentinel Agent */}
      <div className={`agent-card ${sentinelStatus === 'success' ? 'dashboard-tone-success' : ''}`}>
        <div className="agent-header" style={{ alignItems: "flex-start" }}>
          <div className="agent-title-group">
            <div className={`agent-icon-box ${sentinelStatus} ${isSentinelAnalyzing ? 'pulsing' : ''}`} style={{ marginTop: 2 }}>
              <div style={{ width: 18, height: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Shield size={18} strokeWidth={2.2} />
              </div>
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700 }}>Sentinel Agent</div>
                <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.5, textTransform: "uppercase", background: "var(--surface2)", padding: "1px 6px", borderRadius: 4, letterSpacing: "0.2px", border: "1px solid var(--border)" }}>
                  Gemini 2.5 Flash
                </span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text-sub)", fontWeight: 400, marginTop: 2 }}>
                Used to detect whether a fall has occurred.
              </div>
            </div>
          </div>

          <div className={`agent-status-tag ${sentinelStatus}`}>
            {sentinelStatusText}
          </div>
        </div>

        <div style={{ padding: "0 2px" }}>
          {isSentinelAnalyzing && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, color: "var(--amber)", fontSize: 13 }}>
              <div className="typing-dots"><span></span><span></span><span></span></div>
              Analyzing video frames for visible fall events...
            </div>
          )}

          {(sentinelDetection?.video_summary || latestVideoAnalysis?.summary) && (
            <div
              style={{
                marginTop: 14,
                padding: "12px 14px",
                borderRadius: 12,
                background: "var(--surface2)",
                border: "1px solid var(--border)",
                fontSize: 10,
                color: "var(--text-sub)",
                lineHeight: 1.6,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>
                  Vision Summary
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {sentinelDetection?.fall_detection_confidence_score != null && (
                    <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.6, textTransform: "uppercase", background: "var(--surface3)", padding: "2px 6px", borderRadius: 4 }}>
                      Conf: {formatScore(sentinelDetection.fall_detection_confidence_score)}
                    </span>
                  )}
                </div>

              </div>
              <div style={{ color: "var(--text)", fontWeight: 500 }}>
                {latestVideoAnalysis?.summary || sentinelDetection?.video_summary}
              </div>
            </div>
          )}

        </div>
      </div>


      {/* Communication Agent */}
      <div className={`agent-card ${isCommRunning ? 'reasoning-pulse-border' : ''}`}>
        <div className="agent-header" style={{ alignItems: "flex-start" }}>
          <div className="agent-title-group">
            <div className={`agent-icon-box ${commStatus} ${isCommRunning ? 'pulsing' : ''}`} style={{ marginTop: 2 }}>
              <div style={{ width: 18, height: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <MessageSquare size={18} strokeWidth={2.2} />
              </div>
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700 }}>Communication Agent</div>
                <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.5, textTransform: "uppercase", background: "var(--surface2)", padding: "1px 6px", borderRadius: 4, letterSpacing: "0.2px", border: "1px solid var(--border)" }}>
                  Gemini 2.5 Flash
                </span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text-sub)", fontWeight: 400, marginTop: 2 }}>
                Used to facilitate dialogue, interpret intent, and guide the emergency conversation flow.
              </div>
            </div>
          </div>

          <div className={`agent-status-tag ${commStatus}`}>
            {commStatusText}
          </div>
        </div>

        <div style={{ padding: "0 2px" }}>
          {isCommRunning && (
            <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 10, padding: "2px 4px" }}>
              <div className="typing-dots amber"><span></span><span></span><span></span></div>
              <div style={{ fontSize: 10, color: "var(--text-sub)", fontWeight: 500, letterSpacing: "0.01em" }}>
                Interpreting dialogue & drafting response...
              </div>
            </div>
          )}


          {latestTurn?.canonical_communication_state?.latest_prompt && (
            <div
              style={{
                marginTop: 14,
                padding: "12px 14px",
                borderRadius: 12,
                background: "var(--surface2)",
                border: "1px solid var(--border)",
                fontSize: 10,
                color: "var(--text-sub)",
                lineHeight: 1.6,
              }}
            >
              <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6, color: "var(--text-muted)" }}>
                Active Dialogue Context
              </div>
              <div style={{ color: "var(--text)", fontWeight: 500 }}>
                {latestTurn.canonical_communication_state.latest_prompt}
              </div>
            </div>
          )}

          {latestTurn?.communication_analysis?.ai_server_error && (
            <div style={{ marginTop: 12, padding: "8px 12px", background: "var(--red-subtle)", color: "var(--red)", border: "1px solid var(--red-glow)", borderRadius: 6, fontSize: 10, lineHeight: 1.5 }}>
              <strong style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.5px" }}>AI Server Fallback</strong>
              <div style={{ marginTop: 2, opacity: 0.9 }}>{latestTurn.communication_analysis.ai_server_error}</div>
            </div>
          )}
        </div>
      </div>


      {/* Reasoning Agent */}
      <div className={`agent-card ${reasoningPulsing ? 'reasoning-pulse-border' : ''}`}>
        <div className="agent-header" style={{ alignItems: "flex-start" }}>
          <div className="agent-title-group">
            <div className={`agent-icon-box ${reasoningStatus} ${reasoningPulsing ? 'pulsing' : ''}`} style={{ marginTop: 2 }}>
              <div style={{ width: 18, height: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <BrainCircuit size={18} strokeWidth={2.2} />
              </div>
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700 }}>Reasoning Agent</div>
                <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.5, textTransform: "uppercase", background: "var(--surface2)", padding: "1px 6px", borderRadius: 4, letterSpacing: "0.2px", border: "1px solid var(--border)" }}>
                  Gemini 2.5 Pro
                </span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text-sub)", fontWeight: 400, marginTop: 2 }}>
                Evaluates clinical severity, vitals, and situational context to determine interventions.
              </div>
            </div>
          </div>

          <div className={`agent-status-tag ${reasoningStatus}`}>
            {reasoningStatusText}
          </div>
        </div>

        <div style={{ padding: "0 2px" }}>
          {reasoningStatus === "pending" && (
            <div style={{ marginTop: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "2px 4px", marginBottom: 8 }}>
                <div className="typing-dots amber"><span></span><span></span><span></span></div>
                <div style={{ fontSize: 10, color: "var(--text-sub)", fontWeight: 500, letterSpacing: "0.01em" }}>
                  Synthesizing clinical assessment...
                </div>
              </div>
              {latestAssessment?.clinical_assessment?.red_flags?.length > 0 && (
                <div style={{ fontSize: 9, color: "var(--text-muted)", fontStyle: "italic", borderLeft: "2px solid var(--border)", paddingLeft: 10, marginLeft: 4 }}>
                  Detected: {latestAssessment.clinical_assessment.red_flags.slice(0, 3).join(", ")}
                  {latestAssessment.clinical_assessment.red_flags.length > 3 ? "..." : ""}
                </div>
              )}
            </div>
          )}


          {reasoningDecision && (
            <div
              style={{
                marginTop: 14,
                padding: "12px 14px",
                borderRadius: 12,
                background: "var(--surface2)",
                border: "1px solid var(--border)",
                fontSize: 10,
                color: "var(--text-sub)",
                lineHeight: 1.6,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>
                  Final Decision
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                  <span style={{
                    fontSize: 9,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    padding: "2px 6px",
                    borderRadius: 4,
                    background: latestAssessment?.clinical_assessment?.severity === "critical" ? "var(--red-subtle)" : "var(--surface3)",
                    color: latestAssessment?.clinical_assessment?.severity === "critical" ? "var(--red)" : "var(--text-muted)",
                    border: latestAssessment?.clinical_assessment?.severity === "critical" ? "1px solid rgba(239, 68, 68, 0.2)" : "1px solid transparent"
                  }}>
                    {formatSeverity(latestAssessment?.clinical_assessment?.severity)}
                  </span>
                  <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.8, textTransform: "uppercase", background: "var(--surface3)", padding: "2px 6px", borderRadius: 4 }}>
                    Conf: {formatScore(latestAssessment?.clinical_assessment?.clinical_confidence_score)}
                  </span>
                </div>

              </div>

              <div style={{ color: "var(--text)", fontWeight: 500 }}>
                {(() => {
                  const plan = latestAssessment?.clinical_assessment?.response_plan;
                  const primary = reasoningDecision?.action ? toTitleCase(reasoningDecision.action).replace('Emergency Dispatch', 'Call Ambulance') : null;
                  const notifications = plan?.notification_actions?.some(a => a?.type === 'inform_family') ? "Inform Family" : null;
                  const mainDecision = [primary, notifications].filter(Boolean).join(" • ");
                  const instruction = reasoningDecision?.instructions || reasoningDecision?.reason;

                  return (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {mainDecision && (
                        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.2px", color: "var(--text)" }}>
                          {mainDecision}
                        </div>
                      )}
                      {instruction && (
                        <div style={{ fontSize: 10, color: "var(--text)", lineHeight: 1.5 }}>
                          {instruction}
                        </div>
                      )}

                    </div>
                  );
                })()}
              </div>




            </div>
          )}

          {(latestTurn?.reasoning_error || latestAssessment?.clinical_assessment?.ai_server_error) && (
            <div style={{ marginTop: 12, padding: "8px 12px", background: "var(--red-subtle)", color: "var(--red)", border: "1px solid var(--red-glow)", borderRadius: 6, fontSize: 10, lineHeight: 1.5 }}>
              <strong style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.5px" }}>AI Server Fallback</strong>
              <div style={{ marginTop: 2, opacity: 0.9 }}>
                {latestTurn?.reasoning_error || latestAssessment?.clinical_assessment?.ai_server_error}
              </div>
            </div>
          )}
        </div>
      </div>


      {/* Execution Agent */}
      <div className="agent-card">
        <div className="agent-header" style={{ alignItems: "flex-start" }}>
          <div className="agent-title-group">
            <div className={`agent-icon-box ${executionStatus}`} style={{ marginTop: 2 }}>
              <div style={{ width: 18, height: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Zap size={18} strokeWidth={2.2} />
              </div>
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700 }}>Execution Agent</div>
                <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.5, textTransform: "uppercase", background: "var(--surface2)", padding: "1px 6px", borderRadius: 4, letterSpacing: "0.2px", border: "1px solid var(--border)" }}>
                  Gemini 2.5 Flash
                </span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text-sub)", fontWeight: 400, marginTop: 2 }}>
                Generates clinical instructions and manages automated response triggers.
              </div>
            </div>
          </div>
          <div className={`agent-status-tag ${executionStatus}`}>
            {executionStatusText}
          </div>
        </div>

        <div className="agent-content">
          {(canonicalExecution || executionPlan) && (
            <div
              style={{
                marginTop: 14,
                padding: "12px 14px",
                borderRadius: 12,
                background: "var(--surface2)",
                border: "1px solid var(--border)",
                fontSize: 10,
                color: "var(--text-sub)",
                lineHeight: 1.6,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>
                  Execution Plan
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                  <span style={{ fontSize: 9, fontWeight: 700, opacity: 0.6, textTransform: "uppercase", background: "var(--surface3)", padding: "2px 6px", borderRadius: 4 }}>
                    {canonicalExecution?.phase || executionPlan?.scenario || "Stable"}
                  </span>
                  {canonicalExecution?.dispatch_status && (
                    <span className="tag" style={{ border: "none", background: "var(--surface3)", opacity: 0.8, padding: "2px 6px", fontSize: 9 }}>
                      {toTitleCase(canonicalExecution.dispatch_status)}
                    </span>
                  )}
                </div>
              </div>

              <div style={{ color: "var(--text)", fontWeight: 500, marginBottom: 10, fontSize: 10 }}>
                {executionPlan?.primary_message || executionActivity}
              </div>

              {guidanceSteps.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
                  {guidanceSteps.map((step, idx) => (
                    <div key={idx} style={{
                      fontSize: 10,
                      display: "flex",
                      gap: 8,
                      color: idx === currentGuidanceStepIndex ? "var(--text)" : "var(--text-muted)",
                      fontWeight: idx === currentGuidanceStepIndex ? 600 : 400
                    }}>
                      <span style={{ opacity: 0.5, width: 14 }}>{idx + 1}.</span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>


      {/* Bystander Agent (Retrieval Engine) */}
      <div className="agent-card">
        <div className="agent-header" style={{ alignItems: "flex-start" }}>
          <div className="agent-title-group">
            <div className={`agent-icon-box ${bystanderStatus} ${groundingStatus === "pending" ? "pulsing" : ""}`} style={{ marginTop: 2 }}>
              <div style={{ width: 18, height: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Users size={18} strokeWidth={2.2} />
              </div>
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700 }}>Bystander Agent</div>
                <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.5, textTransform: "uppercase", background: "var(--surface2)", padding: "1px 6px", borderRadius: 4, letterSpacing: "0.2px", border: "1px solid var(--border)" }}>
                  Vertex AI Search
                </span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text-sub)", fontWeight: 400, marginTop: 2 }}>
                Retrieves grounded clinical protocols from validated medical handbooks.
              </div>
            </div>
          </div>
          <div className={`agent-status-tag ${bystanderStatus}`}>
            {bystanderStatusText}
          </div>
        </div>

        <div className="agent-content">
          {(latestTurn || grounding) && (
            <div
              style={{
                marginTop: 14,
                padding: "12px 14px",
                borderRadius: 12,
                background: "var(--surface2)",
                border: "1px solid var(--border)",
                fontSize: 10,
                color: "var(--text-sub)",
                lineHeight: 1.6,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>
                  Grounded Intelligence
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                  {protocolReady && (
                    <span style={{ fontSize: 9, fontWeight: 700, color: "var(--green)", textTransform: "uppercase", background: "var(--green-subtle)", padding: "2px 6px", borderRadius: 4 }}>
                      Verified Source
                    </span>
                  )}
                  {groundingRequired && (
                    <span style={{
                      fontSize: 9,
                      fontWeight: 700,
                      textTransform: "uppercase",
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: protocolReady ? "var(--green-subtle)" : "var(--surface3)",
                      color: protocolReady ? "var(--green)" : "var(--text-muted)"
                    }}>
                      {toTitleCase(groundingStatus.replace('_', ' '))}
                    </span>
                  )}
                </div>
              </div>

              <div style={{ color: "var(--text)", fontWeight: 500, marginBottom: 10 }}>
                {bystanderActivity}
              </div>


              {grounding?.queries?.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
                  <div style={{ fontSize: 9, color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Active Search Queries:
                  </div>
                  {grounding.queries.slice(0, 2).map((q, i) => (
                    <div key={i} style={{ fontSize: 11, color: "var(--text-sub)", fontStyle: "italic", borderLeft: "2px solid var(--border)", paddingLeft: 8 }}>
                      "{q}"
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>


    </div>
  );
}
