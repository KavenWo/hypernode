import { useState } from "react";
import { DEMO_PROFILES } from "../../data/mockData";

const BLANK_ENTRY = {
  timestamp: "",
  profile: DEMO_PROFILES[0].name,
  event: "",
  severity: "Medium",
  action: "",
  summary: "",
};

export default function HistoryPage({ historyLog, setHistoryLog }) {
  const [showForm, setShowForm]         = useState(false);
  const [advanced, setAdvanced]         = useState(false);
  const [quickNote, setQuickNote]       = useState("");
  const [form, setForm]                 = useState({ ...BLANK_ENTRY });
  const [formErr, setFormErr]           = useState("");

  const sevColor = (sev) => {
    if (sev === "High" || sev === "Critical") return "tag-red";
    if (sev === "Medium") return "tag-amber";
    return "tag-green";
  };
  const sevIcon = (sev) => {
    if (sev === "High" || sev === "Critical") return "🔴";
    if (sev === "Medium") return "🟠";
    return "🟡";
  };

  const nowString = () => {
    const d = new Date();
    return d.toLocaleString("en-MY", { hour12: false, year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" });
  };

  const resetForm = () => {
    setShowForm(false); setAdvanced(false);
    setQuickNote(""); setForm({ ...BLANK_ENTRY }); setFormErr("");
  };

  const handleQuickSave = () => {
    if (!quickNote.trim()) { setFormErr("Please write a note before saving."); return; }
    const entry = {
      id: `h${Date.now()}`,
      timestamp: nowString(),
      profile: "—",
      event: "Manual Note",
      severity: "Low",
      action: "Noted",
      summary: quickNote.trim(),
    };
    setHistoryLog(prev => [entry, ...prev]);
    resetForm();
  };

  const handleStructuredSave = () => {
    if (!form.event.trim() || !form.action.trim() || !form.summary.trim()) {
      setFormErr("Event, Action, and Summary are required.");
      return;
    }
    const entry = {
      ...form,
      id: `h${Date.now()}`,
      timestamp: form.timestamp
        ? form.timestamp.replace("T", " ")
        : nowString(),
    };
    setHistoryLog(prev => [entry, ...prev]);
    resetForm();
  };

  const handleDelete = (id) => setHistoryLog(prev => prev.filter(e => e.id !== id));

  const selectField = (key, label, options) => (
    <div className="form-group" style={{ margin: 0 }}>
      <label className="form-label">{label}</label>
      <select className="form-input" value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}>
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
    </div>
  );

  const textField = (key, label, type = "text") => (
    <div className="form-group" style={{ margin: 0 }}>
      <label className="form-label">{label}</label>
      <input
        className="form-input" type={type}
        placeholder={type === "datetime-local" ? "" : `Enter ${label.toLowerCase()}…`}
        value={form[key]}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
      />
    </div>
  );

  return (
    <div className="page">
      {/* ── PAGE HEADER ── */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 4 }}>
        <p className="page-title">Incident History</p>
        <button
          className="btn btn-green btn-sm"
          style={{ marginTop: 4 }}
          onClick={() => { setShowForm(s => !s); setFormErr(""); if (showForm) resetForm(); }}
        >
          {showForm ? "✕ Cancel" : "+ Add Entry"}
        </button>
      </div>
      <p className="page-sub">PAST EMERGENCY TRIALS · SYSTEM LOG · {historyLog.length} RECORD{historyLog.length !== 1 ? "S" : ""}</p>

      {/* ── ADD ENTRY PANEL ── */}
      {showForm && (
        <div className="add-entry-panel" style={{ animation: "slideUp 0.2s ease" }}>
          <h3>📝 Log New Incident</h3>

          {/* Mode toggle */}
          <div style={{ display: "flex", gap: 0, marginBottom: 18, background: "var(--surface2)", borderRadius: "var(--radius-sm)", padding: 3, width: "fit-content", border: "1px solid var(--border)" }}>
            {[["Quick Note", false], ["Structured Entry", true]].map(([label, val]) => (
              <button
                key={label}
                onClick={() => { setAdvanced(val); setFormErr(""); }}
                style={{
                  padding: "6px 14px", borderRadius: 6, border: "none", cursor: "pointer",
                  fontFamily: "'Instrument Sans', sans-serif", fontSize: 12, fontWeight: 600,
                  transition: "all 0.15s",
                  background: advanced === val ? "var(--green)" : "transparent",
                  color: advanced === val ? "#0d0f0e" : "var(--text-muted)",
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* ── QUICK NOTE MODE ── */}
          {!advanced && (
            <div style={{ animation: "fadeIn 0.15s ease" }}>
              <div className="form-group" style={{ margin: "0 0 12px" }}>
                <label className="form-label">Quick Note</label>
                <textarea
                  className="form-input"
                  rows={3}
                  autoFocus
                  placeholder="Describe what happened in plain language — e.g. 'Patient reported dizziness during morning walk, no fall, vitals normal.' Timestamp will be set automatically."
                  value={quickNote}
                  onChange={e => { setQuickNote(e.target.value); setFormErr(""); }}
                  style={{ resize: "vertical", lineHeight: 1.6 }}
                />
              </div>
              <p style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace", marginBottom: 12 }}>
                ⏱ Timestamp, severity, and action will default to now / Low / Noted. Use Structured Entry for full control.
              </p>
              {formErr && <p style={{ fontSize: 12, color: "var(--red)", marginBottom: 10, fontFamily: "'JetBrains Mono', monospace" }}>⚠ {formErr}</p>}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button className="btn btn-ghost btn-sm" onClick={resetForm}>Cancel</button>
                <button className="btn btn-green btn-sm" onClick={handleQuickSave}>✓ Save Note</button>
              </div>
            </div>
          )}

          {/* ── STRUCTURED ENTRY MODE ── */}
          {advanced && (
            <div style={{ animation: "fadeIn 0.15s ease" }}>
              <div className="add-entry-grid" style={{ marginBottom: 12 }}>
                {textField("timestamp", "Date & Time (optional)", "datetime-local")}
                {selectField("profile", "Patient Profile", DEMO_PROFILES.map(p => p.name))}
                {selectField("severity", "Severity", ["Low", "Medium", "High", "Critical"])}
                {textField("event", "Event / Detected Anomaly")}
                {textField("action", "Action Taken")}
              </div>
              <div className="form-group" style={{ margin: "0 0 12px" }}>
                <label className="form-label">Summary <span style={{ color: "var(--red)", marginLeft: 2 }}>*</span></label>
                <textarea
                  className="form-input"
                  rows={3}
                  placeholder="Describe what happened, what the system detected, and the outcome…"
                  value={form.summary}
                  onChange={e => { setForm(f => ({ ...f, summary: e.target.value })); setFormErr(""); }}
                  style={{ resize: "vertical", lineHeight: 1.5 }}
                />
              </div>
              <p style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace", marginBottom: 12 }}>
                * Required fields: Event, Action, Summary. Date defaults to now if left blank.
              </p>
              {formErr && <p style={{ fontSize: 12, color: "var(--red)", marginBottom: 10, fontFamily: "'JetBrains Mono', monospace" }}>⚠ {formErr}</p>}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button className="btn btn-ghost btn-sm" onClick={resetForm}>Cancel</button>
                <button className="btn btn-green btn-sm" onClick={handleStructuredSave}>✓ Save Entry</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── ENTRY LIST ── */}
      {historyLog.length === 0 && (
        <div className="empty-state" style={{ height: 240 }}>
          <span className="empty-icon">📋</span>
          <p>No incidents logged yet.<br />Run a simulation from the Dashboard or add an entry manually.</p>
        </div>
      )}

      {historyLog.map((entry) => (
        <div key={entry.id} className="hist-item">
          <div className="hist-top">
            <span style={{ fontSize: 20 }}>{sevIcon(entry.severity)}</span>
            <div style={{ flex: 1 }}>
              <div className="hist-name">{entry.event}</div>
              <div className="hist-time">{entry.timestamp} · {entry.profile}</div>
            </div>
          </div>
          <p className="hist-body">{entry.summary}</p>
          <div className="hist-footer">
            <span className={`tag ${sevColor(entry.severity)}`}>Severity: {entry.severity}</span>
            <span className="tag">{entry.action}</span>
            <button className="hist-delete" onClick={() => handleDelete(entry.id)} title="Delete entry">
              🗑 Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
