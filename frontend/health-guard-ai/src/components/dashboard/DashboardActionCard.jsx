import { Activity, Phone, Ambulance } from "lucide-react";

function toTitleCase(value) {
  return (value || "unknown")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function DashboardActionCard({ latestAssessment, latestTurn }) {
  const recommendedAction = latestAssessment?.action?.recommended;
  const escalation = latestAssessment?.response_plan?.escalation_action;
  const executionUpdates = latestTurn?.execution_updates || [];

  // 1. Monitor
  const isMonitor = recommendedAction === "monitor";

  // 2. Contact Family
  const familyUpdate = executionUpdates.find((u) => u.type === "inform_family");
  const familyIsCompleted = familyUpdate?.status === "completed";
  const familyIsPlanned =
    recommendedAction === "contact_family" ||
    latestAssessment?.response_plan?.notification_actions?.some((a) => a.type === "inform_family");

  let contactFamilyStatus = "idle";
  if (familyIsCompleted) contactFamilyStatus = "completed";
  else if (familyIsPlanned) contactFamilyStatus = "active";

  // 3. Emergency Dispatch
  const dispatchUpdate = executionUpdates.find((u) => u.type === "emergency_dispatch");
  const isDispatchCompleted =
    dispatchUpdate?.status === "completed" ||
    recommendedAction === "emergency_dispatch" ||
    escalation?.type === "emergency_dispatch";
  const isDispatchPending =
    recommendedAction === "dispatch_pending_confirmation" ||
    escalation?.type === "dispatch_pending_confirmation";

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
            {familyUpdate?.detail || "Notifying emergency contacts about the incident."}
          </div>
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
            {dispatchUpdate?.detail ||
              escalation?.reason ||
              "Dispatching medical emergency services to the current location."}
          </div>
        </div>
      </div>
    </div>
  );
}
