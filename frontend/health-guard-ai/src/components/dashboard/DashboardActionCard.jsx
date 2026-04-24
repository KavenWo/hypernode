import { useEffect, useRef, useState } from "react";
import { Activity, Phone, Ambulance, X, AlertCircle, MessageSquare } from "lucide-react";
import dispatchNotificationSound from "../../audio/dispatch-notification-sound.mp3";


const DISPATCH_CONFIRMATION_WINDOW_SECONDS = 15;

function toTitleCase(value) {
  return (value || "unknown")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function findActionState(latestTurn, actionType) {
  return latestTurn?.action_states?.find((item) => item.action_type === actionType) || null;
}

function findExecutionUpdate(latestTurn, updateType) {
  return latestTurn?.execution_updates?.find((item) => item.type === updateType) || null;
}

function findExecutionUpdates(latestTurn, updateType) {
  return (latestTurn?.execution_updates || []).filter((item) => item.type === updateType);
}

function buildMessageText(item) {
  return item?.message_text || item?.script_lines?.join(" ") || "";
}

function renderStatusTagLabel(status) {
  if (status === "critical") return "Dispatched";
  if (status === "pending") return "Pending Confirmation";
  if (status === "completed") return "Completed";
  if (status === "active") return "Active";
  return "Idle";
}

function renderDispatchMessageStatus({ isDispatchCompleted, isDispatchPending, dispatchState, dispatchUpdate }) {
  if (isDispatchCompleted) return "Sent";
  if (isDispatchPending) return "Pending";
  if (dispatchUpdate?.status === "cancelled" || dispatchState?.status === "cancelled") return "Cancelled";
  return "Ready";
}

function NotificationBlock({ title, status, detail, message, occurrenceCount, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        marginTop: 12,
        padding: "10px 12px",
        borderRadius: 10,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        fontSize: 11,
        color: "var(--text-sub)",
        lineHeight: 1.6,
        cursor: onClick ? "pointer" : "default",
        transition: "border-color 0.2s ease, background 0.2s ease",
      }}
      onMouseEnter={(e) => {
        if (onClick) {
          e.currentTarget.style.borderColor = "var(--green)";
          e.currentTarget.style.background = "var(--green-subtle)";
        }
      }}
      onMouseLeave={(e) => {
        if (onClick) {
          e.currentTarget.style.borderColor = "var(--border)";
          e.currentTarget.style.background = "var(--surface)";
        }
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 8,
          alignItems: "center",
          marginBottom: 6,
          flexWrap: "wrap",
        }}
      >
        <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>
          {title}
        </div>
        <span className="tag">{status}</span>
      </div>
      {detail && <div style={{ marginBottom: message ? 6 : 0 }}>{detail}</div>}
      {message && onClick && (
        <div style={{ marginTop: 8, color: "var(--brand)", fontSize: 10, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
           <MessageSquare size={12} /> Click to view message payload
        </div>
      )}
      {message && !onClick && <div>{message}</div>}
      {occurrenceCount > 1 && (
        <div style={{ marginTop: 6, color: "var(--text-muted)" }}>
          Sent #{occurrenceCount}
        </div>
      )}
    </div>
  );
}

function MessagePreviewModal({ payload, onClose }) {
  if (!payload) return null;

  const isSMS = payload.type === 'sms';

  return (
    <div className="modal-overlay">
      <div 
        className="modal" 
        style={{ 
          maxWidth: 420, 
          padding: 0, 
          overflow: "hidden", 
          background: isSMS ? "#fff" : "var(--surface)", 
          boxShadow: "0 24px 48px rgba(0,0,0,0.15)",
          borderRadius: 24,
          border: "none"
        }}
      >
        <div style={{ 
          padding: "16px 20px", 
          background: isSMS ? "#f9f9f9" : "var(--surface2)",
          borderBottom: "1px solid var(--border)", 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "space-between" 
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {isSMS ? <Phone size={16} color="var(--green)" /> : <Ambulance size={16} color="var(--red)" />}
            <div>
              <h2 style={{ margin: 0, fontSize: 14, fontWeight: 700, fontFamily: "Outfit, sans-serif", color: "var(--text)" }}>{payload.title}</h2>
              <div style={{ fontSize: 10, color: "var(--text-sub)", marginTop: 2, fontWeight: 500 }}>
                {isSMS ? 'iMessage • Now' : 'Secure Dispatch Channel • Automated Voice'}
              </div>
            </div>
          </div>
          <button style={{ 
              background: "rgba(0,0,0,0.05)", border: "none", color: "var(--text-sub)", 
              width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", 
              justifyContent: "center", cursor: "pointer", transition: "all 0.2s" 
            }}
            onClick={onClose}
          >
            <X size={14} />
          </button>
        </div>
        
        {isSMS ? (
          <div style={{ padding: "24px 20px 32px", background: "#fff", display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 10, color: "var(--text-muted)", textAlign: "center", marginBottom: 8 }}>Today, {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
            <div style={{ 
                background: "#007AFF", 
                color: "#fff", 
                padding: "12px 16px", 
                borderRadius: "18px 18px 4px 18px", 
                fontSize: 13, 
                lineHeight: 1.5,
                alignSelf: "flex-end",
                maxWidth: "85%",
                boxShadow: "0 2px 4px rgba(0,122,255,0.2)"
              }}>
              {payload.message}
            </div>
          </div>
        ) : (
          <div style={{ padding: "24px", background: "#0f172a", color: "#f8fafc" }}>
            <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 12, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "1px", display: "flex", alignItems: "center", gap: 6 }}>
              <div className="live-dot" style={{ background: "var(--red)" }}></div> Recording Transcript
            </div>
            <div style={{
              background: "#1e293b",
              border: "1px solid #334155",
              borderRadius: 12,
              padding: 16,
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              color: "#e2e8f0",
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              borderLeft: "3px solid var(--red)"
            }}>
              {payload.message}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DashboardActionCard({ latestAssessment, latestTurn, onActionDecision }) {
  const canonicalState = latestTurn?.state;
  const canonicalExecution = latestTurn?.execution_state;
  const reasoningDecision = latestTurn?.reasoning_decision;
  const monitorState = findActionState(latestTurn, "monitor");
  const familyState = findActionState(latestTurn, "contact_family");
  const dispatchState = findActionState(latestTurn, "emergency_dispatch");
  const latestFamilyAlert = findExecutionUpdate(latestTurn, "inform_family");
  const familyReminderUpdates = findExecutionUpdates(latestTurn, "family_fall_reminder");
  const latestFamilyReminder = familyReminderUpdates.at(-1) || null;
  const dispatchUpdate = findExecutionUpdate(latestTurn, "emergency_dispatch");
  const dispatchMessage =
    buildMessageText(dispatchUpdate) ||
    dispatchState?.message_text ||
    dispatchState?.script_lines?.join(" ") ||
    "";
  const dispatchStatusValue = canonicalExecution?.dispatch_status;
  const guidanceActive = canonicalExecution?.phase === "guidance";
  const hasAssessment = Boolean(latestAssessment || reasoningDecision);

  // 1. Monitor
  const isMonitor =
    monitorState?.status === "active" ||
    canonicalExecution?.phase === "idle" ||
    canonicalExecution?.phase === "monitoring" ||
    reasoningDecision?.action === "monitor";

  // 2. Contact Family
  const familyMessage =
    buildMessageText(latestFamilyReminder) ||
    buildMessageText(latestFamilyAlert) ||
    familyState?.message_text ||
    familyState?.script_lines?.join(" ") ||
    "";
  const familyInitialSent = canonicalExecution?.family_notified_initial || latestFamilyAlert?.status === "completed";
  const familyUpdateSent = canonicalExecution?.family_notified_update || latestFamilyReminder?.status === "completed";
  const familyIsCompleted = familyInitialSent || familyUpdateSent || familyState?.status === "completed";
  const familyIsPlanned = familyState?.desired || reasoningDecision?.action === "contact_family";

  let contactFamilyStatus = "idle";
  if (familyIsCompleted) contactFamilyStatus = "completed";
  else if (familyIsPlanned) contactFamilyStatus = "active";

  // 3. Emergency Dispatch
  const isDispatchCompleted =
    dispatchStatusValue === "confirmed" ||
    dispatchStatusValue === "auto_dispatched" ||
    dispatchState?.status === "completed" ||
    dispatchUpdate?.status === "completed";
  const isDispatchPending =
    canonicalState === "awaiting_dispatch_confirmation" ||
    dispatchStatusValue === "pending_confirmation" ||
    dispatchState?.status === "pending_confirmation";
  const dispatchRecommended =
    reasoningDecision?.action === "call_ambulance" ||
    dispatchState?.desired ||
    dispatchStatusValue === "requested";

  let dispatchStatus = "idle";
  if (isDispatchCompleted) dispatchStatus = "critical";
  else if (isDispatchPending) dispatchStatus = "pending";
  else if (dispatchRecommended || guidanceActive) dispatchStatus = "active";

  const [localCountdown, setLocalCountdown] = useState(null);
  const [pendingDecision, setPendingDecision] = useState("");
  const [, setDecisionFeedback] = useState("");
  const [selectedMessagePayload, setSelectedMessagePayload] = useState(null);
  const autoTriggeredRef = useRef(false);
  const pendingWindowKeyRef = useRef("");
  const audioRef = useRef(null);

  const onActionDecisionRef = useRef(onActionDecision);
  useEffect(() => {
    onActionDecisionRef.current = onActionDecision;
  }, [onActionDecision]);

  const pendingDecisionRef = useRef(pendingDecision);
  useEffect(() => {
    pendingDecisionRef.current = pendingDecision;
  }, [pendingDecision]);

  useEffect(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio(dispatchNotificationSound);
    }
  }, []);


  useEffect(() => {
    if (!isDispatchPending) {
      setLocalCountdown(null);
      setPendingDecision("");
      setDecisionFeedback("");
      autoTriggeredRef.current = false;
      pendingWindowKeyRef.current = "";
      return undefined;
    }

    const pendingWindowKey = [
      dispatchState?.action_type,
      dispatchState?.status,
      dispatchState?.last_updated_at || "",
      latestTurn?.state || "",
    ].join(":");

    if (pendingWindowKeyRef.current !== pendingWindowKey) {
      pendingWindowKeyRef.current = pendingWindowKey;
      setLocalCountdown(DISPATCH_CONFIRMATION_WINDOW_SECONDS);
      setPendingDecision("");
      setDecisionFeedback("");
      autoTriggeredRef.current = false;
      audioRef.current?.play().catch((err) => console.warn("Audio playback failed:", err));
    }
  }, [dispatchState?.action_type, dispatchState?.last_updated_at, dispatchState?.status, isDispatchPending, latestTurn?.state]);

  useEffect(() => {
    if (!isDispatchPending) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setLocalCountdown((currentValue) => {
        const nextValue = currentValue == null ? DISPATCH_CONFIRMATION_WINDOW_SECONDS : currentValue - 1;
        if (nextValue <= 0) {
          window.clearInterval(timer);
          if (!autoTriggeredRef.current && !pendingDecisionRef.current) {
            autoTriggeredRef.current = true;
            setPendingDecision("auto_confirm");
            setDecisionFeedback("No response detected. Dispatching automatically...");
            void Promise.resolve(onActionDecisionRef.current?.("emergency_dispatch", "auto_confirm"))
              .catch(() => {
                autoTriggeredRef.current = false;
                setPendingDecision("");
                setDecisionFeedback("Automatic dispatch failed. Please try again.");
              });
          }
          return 0;
        }
        return nextValue;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, [isDispatchPending]);

  useEffect(() => {
    if (isDispatchCompleted) {
      setPendingDecision("");
      setDecisionFeedback(
        dispatchStatusValue === "auto_dispatched"
          ? "Dispatch executed automatically."
          : "Dispatch confirmed."
      );
      autoTriggeredRef.current = false;
      return;
    }
    if (!isDispatchPending && dispatchState?.status === "cancelled") {
      setPendingDecision("");
      setDecisionFeedback("Dispatch cancelled.");
      autoTriggeredRef.current = false;
    }
  }, [dispatchState?.status, isDispatchCompleted, isDispatchPending]);

  function getCardClass(status) {
    if (status === "critical") return "dashboard-action-critical";
    if (status === "completed") return "dashboard-action-complete";
    if (status === "active") return "dashboard-action-live";
    if (status === "pending") return "dashboard-action-pending";
    return "dashboard-action-idle";
  }

  async function handleDecision(decision) {
    if (!onActionDecision || pendingDecision) {
      return;
    }

    setPendingDecision(decision);
    setDecisionFeedback(decision === "confirm" ? "Confirming dispatch..." : "Cancelling dispatch...");

    try {
      await onActionDecision("emergency_dispatch", decision);


    } catch {
      setDecisionFeedback(decision === "confirm" ? "Failed to confirm dispatch." : "Failed to cancel dispatch.");
      setPendingDecision("");
      if (decision === "confirm") {
        autoTriggeredRef.current = false;
      }
    }
  }

  return (
    <div className="card">
      <div className="card-title">Live Actions</div>

      {!hasAssessment && (
        <p style={{ fontSize: 11, color: "var(--text-sub)", lineHeight: 1.6, marginBottom: 16 }}>
          Response actions will update visually.
        </p>
      )}

      <div className="dashboard-actions-grid" style={{ gridTemplateColumns: "1fr" }}>
        <div className={`dashboard-action-card ${getCardClass(isMonitor ? "active" : "idle")}`}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 11 }}>
              <Activity size={15} className="action-icon" />
              Monitor
            </div>
            {isMonitor && <span className="tag">Active</span>}
          </div>
          <div style={{ fontSize: 10, color: "var(--text-sub)", lineHeight: 1.6 }}>
            {guidanceActive
              ? "Monitoring remains active while the execution agent walks the responder through the current grounded guidance."
              : "Continuously observing the patient's state for any signs of worsening."}
          </div>
        </div>

        <div className={`dashboard-action-card ${getCardClass(contactFamilyStatus)}`}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 10 }}>
              <Phone size={15} className="action-icon" />
              Contact Family
            </div>
            {contactFamilyStatus !== "idle" && (
              <span className="tag">{toTitleCase(contactFamilyStatus)}</span>
            )}
          </div>
          <div style={{ fontSize: 10, color: "var(--text-sub)", lineHeight: 1.6 }}>
            {familyState?.detail ||
              latestFamilyReminder?.detail ||
              latestFamilyAlert?.detail ||
              "Family notifications will appear here when support or reminders are sent."}
          </div>
          {(familyInitialSent || latestFamilyAlert || familyState?.desired) && (
            <NotificationBlock
              title="Initial Family Alert"
              status={familyInitialSent ? "Sent" : familyState?.desired ? "Planned" : "Waiting"}
              detail={latestFamilyAlert?.detail || familyState?.detail || "Primary family notification for support escalation."}
              message={buildMessageText(latestFamilyAlert) || (!familyInitialSent && familyIsPlanned ? familyMessage : "")}
              occurrenceCount={latestFamilyAlert?.occurrence_count || familyState?.occurrence_count || 1}
              onClick={
                (buildMessageText(latestFamilyAlert) || (!familyInitialSent && familyIsPlanned ? familyMessage : ""))
                  ? () => setSelectedMessagePayload({
                      title: "Initial Family Alert",
                      message: buildMessageText(latestFamilyAlert) || familyMessage,
                      type: 'sms'
                    })
                  : undefined
              }
            />
          )}
          {(familyUpdateSent || latestFamilyReminder) && (
            <NotificationBlock
              title="Follow-up Family Update"
              status={familyUpdateSent ? "Sent" : "Waiting"}
              detail={latestFamilyReminder?.detail || "Latest follow-up family update generated by the execution lane."}
              message={buildMessageText(latestFamilyReminder)}
              occurrenceCount={latestFamilyReminder?.occurrence_count || familyReminderUpdates.length || 1}
              onClick={
                buildMessageText(latestFamilyReminder)
                  ? () => setSelectedMessagePayload({
                      title: "Follow-up Family Update",
                      message: buildMessageText(latestFamilyReminder),
                      type: 'sms'
                    })
                  : undefined
              }
            />
          )}
        </div>

        <div className={`dashboard-action-card ${getCardClass(dispatchStatus)}`} style={{ transition: "all 0.3s ease" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 11 }}>
              <Ambulance size={15} className="action-icon" />
              Emergency Dispatch
            </div>
            {dispatchStatus !== "idle" && (
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div className={`vital-status-dot ${dispatchStatus === "critical" ? "dot-crit" : dispatchStatus === "pending" ? "dot-warn" : "dot-ok"}`} />
                <span style={{ fontSize: 9, fontWeight: 600, color: "var(--text-sub)" }}>
                  {renderStatusTagLabel(dispatchStatus)}
                </span>
              </div>
            )}
          </div>

          {dispatchStatus === "idle" && (
            <div style={{ fontSize: 10, color: "var(--text-sub)", lineHeight: 1.6 }}>
              Emergency dispatch and coordination services will be activated if life-threatening conditions or critical vitals are detected.
            </div>
          )}

          {/* Suspected Emergency Explanation Box */}
          {(isDispatchPending || dispatchRecommended || guidanceActive) && !isDispatchCompleted && (
            <div style={{
              background: "var(--red-subtle)",
              border: "1px solid rgba(239, 68, 68, 0.15)",
              borderRadius: 12,
              padding: "12px 14px",
              marginBottom: 14,
              display: "flex",
              gap: 12,
              alignItems: "flex-start"
            }}>
              <div style={{ color: "var(--red)", marginTop: 2 }}>
                <AlertCircle size={16} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 10, color: "var(--red-dim)", fontWeight: 600, marginBottom: 4 }}>
                  High Emergency Suspected
                </div>
                <div style={{ fontSize: 9, color: "var(--text-sub)", lineHeight: 1.5 }}>
                  {dispatchState?.detail || dispatchUpdate?.detail || "The clinical reasoning engine has detected critical vitals. An immediate 999 dispatch is required to ensure patient safety."}
                </div>
              </div>
            </div>
          )}

          {/* Action Row for Pending Dispatch */}
          {isDispatchPending && (
            <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center" }}>
              <button
                className="btn btn-red"
                style={{ flex: 1, justifyContent: "center", height: 40, borderRadius: 10, fontSize: 10 }}
                onClick={() => void handleDecision("confirm")}
                disabled={Boolean(pendingDecision)}
              >
                {pendingDecision === "confirm" ? "Confirming..." : (
                  <>
                    Confirm Dispatch ({localCountdown ?? 15}s)
                  </>
                )}
              </button>
              <button
                className="btn btn-ghost"
                style={{ width: 40, height: 40, padding: 0, justifyContent: "center", borderRadius: 10 }}
                onClick={() => void handleDecision("cancel")}
                disabled={Boolean(pendingDecision)}
              >
                <X size={16} />
              </button>
            </div>
          )}

          {isDispatchCompleted && (
            <div style={{ fontSize: 10, color: "var(--text-sub)", lineHeight: 1.6, marginBottom: dispatchMessage ? 12 : 0 }}>
              {dispatchUpdate?.detail || dispatchState?.detail || "Emergency dispatch has been successfully executed and services are on route."}
            </div>
          )}

          {dispatchMessage && (
            <NotificationBlock
              title="Emergency Alert Message"
              status={renderDispatchMessageStatus({ isDispatchCompleted, isDispatchPending, dispatchState, dispatchUpdate })}
              detail={dispatchUpdate?.detail || dispatchState?.detail || "Dispatch payload prepared for emergency responders."}
              message={dispatchMessage}
              occurrenceCount={dispatchUpdate?.occurrence_count || dispatchState?.occurrence_count || 1}
              onClick={() => setSelectedMessagePayload({ title: "Emergency Alert Message", message: dispatchMessage, type: "voice" })}
            />
          )}
        </div>
      </div>
      
      {selectedMessagePayload && (
        <MessagePreviewModal payload={selectedMessagePayload} onClose={() => setSelectedMessagePayload(null)} />
      )}
    </div>
  );
}
