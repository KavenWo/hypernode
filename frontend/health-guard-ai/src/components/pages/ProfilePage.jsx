import { useState } from "react";
import { DEMO_PROFILES } from "../../data/mockData";

export default function ProfilePage() {
  const [profileIdx, setProfileIdx] = useState(0);
  const [patient, setPatient] = useState({ ...DEMO_PROFILES[profileIdx] });
  const [condInput, setCondInput] = useState("");
  const [medInput, setMedInput] = useState("");
  const [saved, setSaved] = useState(false);

  const addCondition = () => {
    if (!condInput.trim()) return;
    setPatient(p => ({ ...p, conditions: [...p.conditions, condInput.trim()] }));
    setCondInput("");
  };
  const removeCondition = (i) => setPatient(p => ({ ...p, conditions: p.conditions.filter((_, idx) => idx !== i) }));
  const addMed = () => {
    if (!medInput.trim()) return;
    setPatient(p => ({ ...p, medications: [...p.medications, medInput.trim()] }));
    setMedInput("");
  };
  const removeMed = (i) => setPatient(p => ({ ...p, medications: p.medications.filter((_, idx) => idx !== i) }));

  return (
    <div className="page">
      <p className="page-title">Profile Information</p>
      <p className="page-sub">VIEW · EDIT · SAVE PATIENT HEALTH PROFILE</p>

      {/* Profile selector */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {DEMO_PROFILES.map((p, i) => (
          <button
            key={p.id}
            onClick={() => {
              setProfileIdx(i);
              setPatient({ ...DEMO_PROFILES[i] });
            }}
            className="btn btn-sm"
            style={{
              background: i === profileIdx ? "var(--green-subtle)" : "var(--surface2)",
              color: i === profileIdx ? "var(--green)" : "var(--text-sub)",
              border: i === profileIdx ? "1px solid rgba(34,197,94,0.25)" : "1px solid var(--border-bright)",
            }}
          >
            {p.avatar} {p.name}
          </button>
        ))}
      </div>

      <div className="patient-banner">
        <div style={{ fontSize: 40 }}>{patient.avatar}</div>
        <div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 22, fontWeight: 800 }}>{patient.name}</div>
          <div style={{ fontSize: 13, color: "var(--text-sub)", marginTop: 3 }}>Age {patient.age} · {patient.bloodType} · {patient.gender}</div>
        </div>
        <span className="profile-badge" style={{ marginLeft: "auto" }}>
          <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--green)", animation: "glow 2s ease-in-out infinite", display: "inline-block" }} />
          MONITORING ACTIVE
        </span>
      </div>

      <div className="grid-2">
        {/* Basic Info */}
        <div className="card">
          <div className="card-title">Basic Information</div>
          <div className="form-group">
            <label className="form-label">Full Name</label>
            <input className="form-input" value={patient.name} onChange={e => setPatient(p => ({ ...p, name: e.target.value }))} />
          </div>
          <div className="grid-2" style={{ gap: 10 }}>
            <div className="form-group">
              <label className="form-label">Age</label>
              <input className="form-input" type="number" value={patient.age} onChange={e => setPatient(p => ({ ...p, age: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Blood Type</label>
              <select className="form-input" value={patient.bloodType} onChange={e => setPatient(p => ({ ...p, bloodType: e.target.value }))}>
                {["A+","A-","B+","B-","AB+","AB-","O+","O-"].map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Allergies (comma-separated)</label>
            <input className="form-input" value={patient.allergies.join(", ")} onChange={e => setPatient(p => ({ ...p, allergies: e.target.value.split(",").map(s => s.trim()).filter(Boolean) }))} />
          </div>
        </div>

        {/* Conditions + Medications */}
        <div className="card">
          <div className="card-title">Medical Conditions</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
            {patient.conditions.map((c, i) => (
              <span key={i} className="tag tag-amber" style={{ cursor: "pointer" }} onClick={() => removeCondition(i)}>
                {c} <span style={{ opacity: 0.6 }}>×</span>
              </span>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input className="form-input" placeholder="Add condition…" value={condInput} onChange={e => setCondInput(e.target.value)} onKeyDown={e => e.key === "Enter" && addCondition()} style={{ flex: 1 }} />
            <button className="btn btn-ghost btn-sm" onClick={addCondition}>Add</button>
          </div>
          <div className="divider" />
          <div className="card-title">Current Medications</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 10 }}>
            {patient.medications.map((m, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13 }}>💊 {m}</span>
                <button className="btn btn-sm" style={{ background: "none", color: "var(--text-muted)", padding: "2px 8px" }} onClick={() => removeMed(i)}>×</button>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="form-input" placeholder="Add medication…" value={medInput} onChange={e => setMedInput(e.target.value)} onKeyDown={e => e.key === "Enter" && addMed()} style={{ flex: 1 }} />
            <button className="btn btn-ghost btn-sm" onClick={addMed}>Add</button>
          </div>
        </div>

        {/* Emergency Contact */}
        <div className="card">
          <div className="card-title">Emergency Contacts</div>
          {patient.contacts.map((c, i) => (
            <div key={i} className="contact-row">
              <div className="contact-ava">👤</div>
              <div style={{ flex: 1 }}>
                <h4>{c.name}</h4>
                <p>{c.relation} · {c.phone}</p>
              </div>
              <span className="tag tag-green">Primary</span>
            </div>
          ))}
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>+ Add Contact</button>
        </div>

        {/* AI Risk Summary */}
        <div className="card">
          <div className="card-title">AI Risk Assessment</div>
          {Object.entries(patient.riskProfile).map(([k, v]) => {
            const color = v > 60 ? "var(--red)" : v > 40 ? "var(--amber)" : "var(--green)";
            return (
              <div key={k} style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                  <span style={{ textTransform: "capitalize" }}>{k} Risk</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color }}>{v}%</span>
                </div>
                <div className="risk-bar-track">
                  <div className="risk-bar-fill" style={{ width: `${v}%`, background: color }} />
                </div>
              </div>
            );
          })}
          <div className="divider" />
          <p style={{ fontSize: 12, color: "var(--text-sub)", lineHeight: 1.6 }}>
            Risk scores computed by Gemini 2.0 Pro based on conditions, medications, and demographic profile. Recommend regular ECG monitoring.
          </p>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
        <button className="btn btn-ghost" onClick={() => setPatient({ ...DEMO_PROFILES[profileIdx] })}>Reset</button>
        <button className="btn btn-green" onClick={() => { setSaved(true); setTimeout(() => setSaved(false), 2500); }}>
          {saved ? "✓ Saved" : "💾 Save Profile"}
        </button>
      </div>
    </div>
  );
}
