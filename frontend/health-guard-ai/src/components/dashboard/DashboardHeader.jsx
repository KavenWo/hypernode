export default function DashboardHeader({ authSession }) {
  const sessionUid = authSession?.backendSession?.session_uid || authSession?.firebaseUser?.uid || "";
  const shortUid = sessionUid ? `${sessionUid.slice(0, 8)}...` : "None";

  return (
    <div className="dash-header">
      <div>
        <h1>Dashboard & Workflow Monitor</h1>
        <p>Real-time orchestrator observing the clinical reasoning and response chain</p>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", justifyContent: "flex-end" }}>
        <div className="system-status" style={{ fontSize: 10, color: "var(--text-sub)", fontWeight: 500 }}>
          Anonymous Session: <span style={{ color: "var(--text)", fontFamily: "'JetBrains Mono', monospace" }}>{shortUid}</span>
        </div>
      </div>
    </div>
  );
}
