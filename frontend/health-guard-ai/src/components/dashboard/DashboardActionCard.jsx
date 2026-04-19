import { useEffect, useRef, useState } from "react";
import { Activity, Phone, Ambulance, X, AlertCircle } from "lucide-react";

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

function NotificationBlock({ title, status, detail, message, occurrenceCount }) {
  return (
    <div
      style={{
        marginTop: 12,
        padding: "10px 12px",
        borderRadius: 10,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        fontSize: 11,
        color: "var(--text-sub)",
        lineHeight: 1.6,
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
      {message && <div>{message}</div>}
      {occurrenceCount > 1 && (
        <div style={{ marginTop: 6, color: "var(--text-muted)" }}>
          Sent #{occurrenceCount}
        </div>
      )}
    </div>
  );
}

export default function DashboardActionCard({ latestAssessment, latestTurn, onActionDecision }) {
  const canonicalState = latestTurn?.state;
  const canonicalExecution = latestTurn?.execution_state;
  const reasoningDecision = latestTurn?.reasoning_decision;
  const executionUpdates = latestTurn?.execution_updates || [];
  const monitorState = findActionState(latestTurn, "monitor");
  const familyState = findActionState(latestTurn, "contact_family");
  const dispatchState = findActionState(latestTurn, "emergency_dispatch");
  const latestFamilyAlert = findExecutionUpdate(latestTurn, "inform_family");
  const familyReminderUpdates = findExecutionUpdates(latestTurn, "family_fall_reminder");
  const latestFamilyReminder = familyReminderUpdates.at(-1) || null;
  const dispatchUpdate = findExecutionUpdate(latestTurn, "emergency_dispatch");
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
  const [decisionFeedback, setDecisionFeedback] = useState("");
  const autoTriggeredRef = useRef(false);
  const pendingWindowKeyRef = useRef("");

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
    }

    const timer = window.setInterval(() => {
      setLocalCountdown((currentValue) => {
        const nextValue = currentValue == null ? DISPATCH_CONFIRMATION_WINDOW_SECONDS : currentValue - 1;
        if (nextValue <= 0) {
          window.clearInterval(timer);
          if (!autoTriggeredRef.current && !pendingDecision) {
            autoTriggeredRef.current = true;
            setPendingDecision("confirm");
            setDecisionFeedback("No response detected. Dispatching automatically...");
            void Promise.resolve(onActionDecision?.("emergency_dispatch", "confirm"))
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
  }, [dispatchState?.action_type, dispatchState?.last_updated_at, dispatchState?.status, isDispatchPending, latestTurn?.state, onActionDecision, pendingDecision]);

  useEffect(() => {
    if (isDispatchCompleted) {
      setPendingDecision("");
      setDecisionFeedback("Dispatch confirmed.");
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
          Response actions will update visually once the reasoning policy engages.
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
            />
          )}
          {(familyUpdateSent || latestFamilyReminder) && (
            <NotificationBlock
              title="Follow-up Family Update"
              status={familyUpdateSent ? "Sent" : "Waiting"}
              detail={latestFamilyReminder?.detail || "Latest follow-up family update generated by the execution lane."}
              message={buildMessageText(latestFamilyReminder)}
              occurrenceCount={latestFamilyReminder?.occurrence_count || familyReminderUpdates.length || 1}
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

          {/* Post-Dispatch Clean Message */}
          {isDispatchCompleted && (
            <div style={{ fontSize: 10, color: "var(--text-sub)", lineHeight: 1.6, marginBottom: dispatchUpdate?.message_text ? 12 : 0 }}>
              Emergency dispatch has been successfully executed and services are on route.
            </div>
          )}

          {isDispatchCompleted && dispatchUpdate?.message_text && (
            <div style={{
              marginTop: 12,
              padding: "12px",
              borderRadius: 10,
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              fontSize: 10,
              color: "var(--text-sub)",
              lineHeight: 1.6,
            }}>
              <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 8 }}>
                Emergency Alert Message
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 8, background: "var(--surface)", padding: 10, borderRadius: 6, border: "1px solid var(--border)" }}>
                {dispatchUpdate.message_text}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
