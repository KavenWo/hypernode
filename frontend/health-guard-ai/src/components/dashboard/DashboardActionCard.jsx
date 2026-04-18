import { Activity, Phone, Ambulance } from "lucide-react";

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
        fontSize: 12,
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
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>
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

  function getCardClass(status) {
    if (status === "critical") return "dashboard-action-critical";
    if (status === "completed") return "dashboard-action-complete";
    if (status === "active") return "dashboard-action-live";
    if (status === "pending") return "dashboard-action-pending";
    return "dashboard-action-idle";
  }

  return (
    <div className="card">
      <div className="card-title">Live Actions</div>

      {!hasAssessment && (
        <p style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6, marginBottom: 16 }}>
          Response actions will update visually once the reasoning policy engages.
        </p>
      )}

      <div className="dashboard-actions-grid" style={{ gridTemplateColumns: "1fr" }}>
        <div className={`dashboard-action-card ${getCardClass(isMonitor ? "active" : "idle")}`}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
              <Activity size={18} className="action-icon" />
              Monitor
            </div>
            {isMonitor && <span className="tag">Active</span>}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
            {guidanceActive
              ? "Monitoring remains active while the execution agent walks the responder through the current grounded guidance."
              : "Continuously observing the patient's state for any signs of worsening."}
          </div>
        </div>

        <div className={`dashboard-action-card ${getCardClass(contactFamilyStatus)}`}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
              <Phone size={18} className="action-icon" />
              Contact Family
            </div>
            {contactFamilyStatus !== "idle" && (
              <span className="tag">{toTitleCase(contactFamilyStatus)}</span>
            )}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
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

        <div className={`dashboard-action-card ${getCardClass(dispatchStatus)}`}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
              <Ambulance size={18} className="action-icon" />
              Emergency Dispatch
            </div>
            {dispatchStatus !== "idle" && (
              <span className="tag">{renderStatusTagLabel(dispatchStatus)}</span>
            )}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
            {dispatchState?.detail ||
              dispatchUpdate?.detail ||
              (canonicalExecution?.dispatch_status === "pending_confirmation"
                ? "Emergency dispatch is waiting for the 15-second confirmation decision."
                : null) ||
              (canonicalExecution?.dispatch_status === "confirmed" || canonicalExecution?.dispatch_status === "auto_dispatched"
                ? "Emergency dispatch has been executed."
                : null) ||
              reasoningDecision?.reason ||
              "Dispatching medical emergency services to the current location."}
          </div>
          {(dispatchRecommended || dispatchStatusValue) && (
            <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              {dispatchStatusValue && <span className="tag">Dispatch State - {toTitleCase(dispatchStatusValue)}</span>}
              {canonicalExecution?.phase && <span className="tag">Execution Phase - {toTitleCase(canonicalExecution.phase)}</span>}
            </div>
          )}
          {isDispatchPending && (
            <>
              <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
                <span className="tag tag-red">Countdown {canonicalExecution?.countdown_seconds ?? dispatchState?.countdown_seconds ?? 15}s</span>
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              <button className="btn btn-red btn-sm" onClick={() => onActionDecision?.("emergency_dispatch", "confirm")}>
                Confirm Dispatch
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => onActionDecision?.("emergency_dispatch", "cancel")}>
                Cancel
              </button>
              </div>
            </>
          )}
          {dispatchUpdate?.message_text && !isDispatchPending && (
            <NotificationBlock
              title="Dispatch Message"
              status={isDispatchCompleted ? "Sent" : "Prepared"}
              detail={dispatchUpdate?.detail || "Structured emergency dispatch message generated by the execution lane."}
              message={dispatchUpdate.message_text}
              occurrenceCount={dispatchUpdate?.occurrence_count || 1}
            />
          )}
        </div>
      </div>
    </div>
  );
}
