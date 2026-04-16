function RuntimePill({ active, label, danger = false }) {
  return (
    <span className={`tag ${danger ? "tag-red" : ""}`} style={{ opacity: active ? 1 : 0.65 }}>
      {active ? "Live" : "Off"} - {label}
    </span>
  );
}

export default function DashboardHeader({ runtimeStatus }) {
  const now = new Date().toLocaleTimeString("en-MY", { hour12: false });

  return (
    <div className="dash-header">
      <div>
        <h1>Live Dashboard</h1>
        <p>Phase 4 session orchestration with dashboard-driven patient context</p>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", justifyContent: "flex-end" }}>
        <RuntimePill active={Boolean(runtimeStatus?.backend_ok)} label="Backend API" danger={!runtimeStatus?.backend_ok} />
        <RuntimePill active={Boolean(runtimeStatus?.gemini_configured)} label="AI Model" />
        <RuntimePill active={Boolean(runtimeStatus?.vertex_search_configured)} label="Vertex Search" />
        <div className="system-status">
          <div className="live-dot" />
          AGENTS ONLINE - {now}
        </div>
      </div>
    </div>
  );
}
