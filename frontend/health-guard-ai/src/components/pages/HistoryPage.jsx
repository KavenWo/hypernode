function sevColor(severity) {
  if (severity === "Critical" || severity === "High" || severity === "Red") return "tag-red";
  if (severity === "Medium" || severity === "Amber" || severity === "Yellow") return "tag-amber";
  return "tag-green";
}

export default function HistoryPage({ historyLog, patientProfiles }) {
  const patientCount = patientProfiles.length;

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 4 }}>
        <div>
          <p className="page-title">Incident History</p>
          <p className="page-sub">
            SESSION-BACKED EMERGENCY LOG · {historyLog.length} RECORD{historyLog.length !== 1 ? "S" : ""} · {patientCount} PATIENT{patientCount !== 1 ? "S" : ""}
          </p>
        </div>
      </div>

      {historyLog.length === 0 ? (
        <div className="empty-state" style={{ height: 240 }}>
          <span className="empty-icon">Records</span>
          <p>
            No completed incidents have been logged yet.
            <br />
            Start a dashboard simulation and complete an action to see it appear here.
          </p>
        </div>
      ) : null}

      {historyLog.map((entry) => (
        <div key={entry.id} className="hist-item">
          <div className="hist-top">
            <div style={{ flex: 1 }}>
              <div className="hist-name">{entry.event}</div>
              <div className="hist-time">
                {entry.timestamp} · {entry.profile}
              </div>
            </div>
          </div>
          <p className="hist-body">{entry.summary}</p>
          <div className="hist-footer">
            <span className={`tag ${sevColor(entry.severity)}`}>Severity: {entry.severity}</span>
            <span className="tag">{entry.action}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
