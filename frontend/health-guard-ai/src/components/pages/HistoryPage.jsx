import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { fetchIncidentRecord, fetchSessionIncidents } from "../../lib/patientApi";

function sevColor(severity) {
  if (severity === "Critical" || severity === "High" || severity === "Red") return "tag-red";
  if (severity === "Medium" || severity === "Amber" || severity === "Yellow") return "tag-amber";
  return "tag-green";
}

function toTitleCase(value) {
  return String(value || "")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildMessageText(item) {
  return item?.message_text || item?.script_lines?.join(" ") || item?.message || "";
}

function getInstructionItems(record) {
  const items = [];
  const latestPrompt = record?.canonical_communication_state?.latest_prompt;
  const reasoningInstructions = record?.reasoning_decision?.instructions;
  const reasoningReason = record?.reasoning_decision?.reason;

  if (latestPrompt) {
    items.push({ label: "Latest agent prompt", value: latestPrompt });
  }
  if (reasoningInstructions) {
    items.push({ label: "Reasoning instructions", value: reasoningInstructions });
  }
  if (reasoningReason && reasoningReason !== reasoningInstructions) {
    items.push({ label: "Why this guidance", value: reasoningReason });
  }

  return items;
}

function getActionTimeline(record) {
  const executionUpdates = record?.execution_updates || [];
  const actionTaken = record?.action_taken;
  const timeline = executionUpdates.map((item, index) => ({
    id: `${item.type || "update"}-${index}`,
    title: toTitleCase(item.type || "action_update"),
    status: item.status || "logged",
    detail: item.detail || "",
    message: buildMessageText(item),
  }));

  if (actionTaken) {
    timeline.push({
      id: "final-action",
      title: toTitleCase(actionTaken.action || record?.final_action || "action_taken"),
      status: actionTaken.executed ? "completed" : "recorded",
      detail: "Final incident action stored in the incident record.",
      message: actionTaken.message || "",
    });
  }

  return timeline;
}

function getGuidanceTimeline(record) {
  const protocol = record?.protocol_guidance;
  const steps = record?.guidance_steps || protocol?.steps || [];
  if (!steps.length) {
    return [];
  }

  return steps.map((step, index) => ({
    id: `guidance-${index}`,
    title: protocol?.protocol_key ? `${toTitleCase(protocol.protocol_key)} Step ${index + 1}` : `Guidance Step ${index + 1}`,
    detail: protocol?.title || protocol?.rationale || "Grounded execution guidance generated for this incident.",
    message: step,
  }));
}

function getTranscript(record) {
  return (record?.conversation_history || []).filter(
    (message) => message?.text || message?.content || message?.message,
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div style={{ fontWeight: 600, color: "var(--text-primary)", marginBottom: 8, letterSpacing: "0.5px", fontSize: "0.8rem", textTransform: "uppercase" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

export default function HistoryPage({ incidentLog, setIncidentLog, patientProfiles, authSession }) {
  const [expandedId, setExpandedId] = useState(null);
  const [details, setDetails] = useState({});
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const patientCount = patientProfiles.length;

  const handleRefresh = async () => {
    const sessionUid = authSession?.backendSession?.session_uid;
    if (!sessionUid) return;

    setRefreshing(true);
    try {
      const history = await fetchSessionIncidents(sessionUid);
      setIncidentLog(history);
    } catch (err) {
      console.error("Failed to refresh history:", err);
    } finally {
      setRefreshing(false);
    }
  };

  const handleExpand = async (incidentId, sessionUid) => {
    if (!incidentId) return;
    if (expandedId === incidentId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(incidentId);
    if (!details[incidentId]) {
      setLoading(true);
      try {
        const data = await fetchIncidentRecord(incidentId, sessionUid);
        setDetails(prev => ({ ...prev, [incidentId]: data }));
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 4 }}>
        <div>
          <p className="page-title">Incident History</p>
          <p className="page-sub">
            SESSION-BACKED EMERGENCY LOG · {incidentLog.length} RECORD{incidentLog.length !== 1 ? "S" : ""} · {patientCount} PATIENT{patientCount !== 1 ? "S" : ""}
          </p>
        </div>
        <button
          className="btn btn-ghost btn-sm"
          onClick={handleRefresh}
          disabled={refreshing}
          style={{ gap: 8 }}
        >
          <RefreshCw size={14} className={refreshing ? "spin-animation" : ""} />
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {incidentLog.length === 0 ? (
        <div className="empty-state" style={{ height: 240 }}>
          <span className="empty-icon">Records</span>
          <p>
            No completed incidents have been logged yet.
            <br />
            Start a dashboard simulation and complete an action to see it appear here.
          </p>
        </div>
      ) : null}

      {incidentLog.map((entry) => (
        <div key={entry.id} className="hist-item" onClick={() => handleExpand(entry.incidentId, entry.sessionUid)} style={{ cursor: "pointer", transition: "all 0.2s ease" }}>
          <div className="hist-top">
            <div style={{ flex: 1 }}>
              <div className="hist-name" style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                {entry.event}
                <span style={{ float: 'right', fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
                  {expandedId === entry.incidentId ? '▼' : '►'}
                </span>
              </div>
              <div className="hist-time" style={{ opacity: 0.8 }}>
                {entry.timestamp} · {entry.profile}
              </div>
            </div>
          </div>

          {expandedId === entry.incidentId && (
            <div className="hist-expanded" style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.08)", fontSize: 11, color: "var(--text-secondary)", cursor: "default" }} onClick={(e) => e.stopPropagation()}>
              <div style={{ marginBottom: 16, paddingBottom: 16, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                <p className="hist-body" style={{ margin: "0 0 12px 0", fontSize: 11 }}>{entry.summary}</p>
                <div className="hist-footer" style={{ marginTop: 0 }}>
                  <span className={`tag ${sevColor(entry.severity)}`}>Severity: {entry.severity}</span>
                  <span className="tag">{entry.action}</span>
                </div>
              </div>


              {loading && !details[entry.incidentId] ? (
                <div style={{ textAlign: "center", padding: "12px 0", color: "var(--text-secondary)" }}>Loading incident details...</div>
              ) : details[entry.incidentId] ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <Section title="Reasoning">
                    <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: "8px 12px", color: "var(--text-primary)", lineHeight: 1.6, display: "flex", flexDirection: "column", gap: 10 }}>
                      <div style={{ fontSize: 11 }}>{details[entry.incidentId].ai_result?.reasoning || details[entry.incidentId].reasoning_decision?.reason || "No reasoning summary logged."}</div>
                      {details[entry.incidentId].reasoning_decision?.action && (
                        <div style={{ color: "var(--text-secondary)", fontSize: 9 }}>
                          Decision: {toTitleCase(details[entry.incidentId].reasoning_decision.action)}
                        </div>
                      )}
                    </div>
                  </Section>

                  {getInstructionItems(details[entry.incidentId]).length > 0 && (
                    <Section title="Instructions Given">
                      <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: "8px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
                        {getInstructionItems(details[entry.incidentId]).map((item) => (
                          <div key={`${item.label}-${item.value}`} style={{ color: "var(--text-primary)" }}>
                            <div style={{ fontSize: 8, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-secondary)", marginBottom: 4 }}>
                              {item.label}
                            </div>
                            <div style={{ lineHeight: 1.6, fontSize: 11 }}>{item.value}</div>
                          </div>
                        ))}
                      </div>
                    </Section>
                  )}

                  {getActionTimeline(details[entry.incidentId]).length > 0 && (
                    <Section title="Actions">
                      <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: "8px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
                        {getActionTimeline(details[entry.incidentId]).map((item) => (
                          <div key={item.id} style={{ paddingBottom: 10, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 4 }}>
                              <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: 11 }}>{item.title}</div>
                              <div style={{ fontSize: 8, textTransform: "uppercase", color: "var(--text-secondary)" }}>{toTitleCase(item.status)}</div>
                            </div>
                            {item.detail ? <div style={{ color: "var(--text-secondary)", marginBottom: item.message ? 4 : 0, fontSize: 10 }}>{item.detail}</div> : null}
                            {item.message ? <div style={{ color: "var(--text-primary)", lineHeight: 1.6, fontSize: 11 }}>{item.message}</div> : null}
                          </div>
                        ))}
                      </div>
                    </Section>
                  )}

                  {getGuidanceTimeline(details[entry.incidentId]).length > 0 && (
                    <Section title="Clinical Guidance Given">
                      <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: "12px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
                        {getGuidanceTimeline(details[entry.incidentId]).map((item) => (
                          <div key={item.id} style={{ paddingBottom: 10, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                            <div style={{ fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>{item.title}</div>
                            {item.detail ? <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>{item.detail}</div> : null}
                            <div style={{ color: "var(--text-primary)", lineHeight: 1.6 }}>{item.message}</div>
                          </div>
                        ))}
                      </div>
                    </Section>
                  )}

                  {details[entry.incidentId].triage_answers?.length > 0 && (
                    <Section title="Triage Signals">
                      <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: "12px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
                        {details[entry.incidentId].triage_answers.map((qa, i) => (
                          <div key={i}>
                            <div style={{ fontWeight: 500, color: "var(--accent-blue)", marginBottom: 2 }}>{qa.question}</div>
                            <div style={{ color: "var(--text-primary)" }}>{String(qa.answer ?? "")}</div>
                          </div>
                        ))}
                      </div>
                    </Section>
                  )}

                  {getTranscript(details[entry.incidentId]).length > 0 && (
                    <Section title="Conversation Transcript">
                      <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: "8px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
                        {getTranscript(details[entry.incidentId]).map((message, index) => (
                          <div key={`${message.role || "message"}-${index}`} style={{ paddingBottom: 10, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                            <div style={{ fontSize: 8, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-secondary)", marginBottom: 4 }}>
                              {toTitleCase(message.role || "message")}
                            </div>
                            <div style={{ color: "var(--text-primary)", lineHeight: 1.6, fontSize: 11 }}>
                              {message.text || message.content || message.message}
                            </div>
                          </div>
                        ))}
                      </div>
                    </Section>
                  )}
                </div>
              ) : (
                <div style={{ color: "var(--accent-red)", textAlign: "center", padding: "12px 0" }}>Failed to load details.</div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
