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

export default function DashboardActionCard({ latestAssessment, latestTurn, onActionDecision }) {
  const recommendedAction = latestAssessment?.action?.recommended;
  const escalation = latestAssessment?.response_plan?.escalation_action;
  const executionUpdates = latestTurn?.execution_updates || [];
  const monitorState = findActionState(latestTurn, "monitor");
  const familyState = findActionState(latestTurn, "contact_family");
  const dispatchState = findActionState(latestTurn, "emergency_dispatch");

  // 1. Monitor
  const isMonitor = monitorState?.status === "active" || recommendedAction === "monitor";

  // 2. Contact Family
  const familyUpdate =
    executionUpdates.find((u) => u.type === "inform_family") ||
    executionUpdates.find((u) => u.type === "family_fall_reminder");
  const familyMessage =
    familyUpdate?.message_text ||
    familyState?.message_text ||
    familyUpdate?.script_lines?.join(" ") ||
    familyState?.script_lines?.join(" ") ||
    "";
  const familyIsCompleted = familyState?.status === "completed" || familyUpdate?.status === "completed";
  const familyIsPlanned = familyState?.desired || recommendedAction === "contact_family";

  let contactFamilyStatus = "idle";
  if (familyIsCompleted) contactFamilyStatus = "completed";
  else if (familyIsPlanned) contactFamilyStatus = "active";

  // 3. Emergency Dispatch
  const dispatchUpdate = executionUpdates.find((u) => u.type === "emergency_dispatch");
  const isDispatchCompleted =
    dispatchState?.status === "completed" ||
    dispatchUpdate?.status === "completed" ||
    recommendedAction === "emergency_dispatch" ||
    escalation?.type === "emergency_dispatch";
  const isDispatchPending =
    dispatchState?.status === "pending_confirmation" ||
    recommendedAction === "dispatch_pending_confirmation" ||
    escalation?.type === "dispatch_pending_confirmation" ||
    recommendedAction === "emergency_dispatch";

  let dispatchStatus = "idle";
  if (isDispatchCompleted) dispatchStatus = "critical";
  else if (isDispatchPending) dispatchStatus = "pending";

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

      {!latestAssessment && (
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
            Continuously observing the patient's state for any signs of worsening.
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
            {familyState?.detail || familyUpdate?.detail || "Family notifications will appear here when support or reminders are sent."}
          </div>
          {familyMessage && (
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
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6, color: "var(--text-muted)" }}>
                Family Message Sent
              </div>
              <div>{familyMessage}</div>
              {familyUpdate?.occurrence_count > 1 && (
                <div style={{ marginTop: 6, color: "var(--text-muted)" }}>
                  Latest family notification: #{familyUpdate.occurrence_count}
                </div>
              )}
            </div>
          )}
        </div>

        <div className={`dashboard-action-card ${getCardClass(dispatchStatus)}`}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
              <Ambulance size={18} className="action-icon" />
              Emergency Dispatch
            </div>
            {dispatchStatus !== "idle" && (
              <span className="tag">
                {dispatchStatus === "critical" ? "Dispatched" : "Pending Confirmation"}
              </span>
            )}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-sub)", lineHeight: 1.6 }}>
            {dispatchState?.detail ||
              dispatchUpdate?.detail ||
              escalation?.reason ||
              "Dispatching medical emergency services to the current location."}
          </div>
          {dispatchState?.status === "pending_confirmation" && (
            <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              <button className="btn btn-red btn-sm" onClick={() => onActionDecision?.("emergency_dispatch", "confirm")}>
                Confirm Dispatch
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => onActionDecision?.("emergency_dispatch", "cancel")}>
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
