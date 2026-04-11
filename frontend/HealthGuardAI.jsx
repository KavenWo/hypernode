import { useState, useEffect, useRef } from "react";

// ─── TYPES ──────────────────────────────────────────────────────────────────
const PAGES = { ONBOARDING: "onboarding", MONITORING: "monitoring", EMERGENCY: "emergency" };

// ─── DUMMY DATA ──────────────────────────────────────────────────────────────
const DUMMY_PATIENT = {
  name: "Ahmad Razif", age: 68, bloodType: "B+",
  conditions: ["Hypertension", "Type 2 Diabetes"],
  medications: ["Metformin 500mg", "Amlodipine 5mg"],
  contacts: [{ name: "Siti Razif", relation: "Daughter", phone: "+60 12-345 6789" }],
  allergies: ["Penicillin"],
};

const DUMMY_VITALS = {
  hr: 74, spo2: 97, bp: "128/82", temp: 36.8,
  hrHistory: [72, 75, 73, 78, 74, 76, 71, 74, 77, 74],
  spo2History: [97, 98, 97, 96, 97, 98, 97, 97, 96, 97],
};

// ─── STYLES ──────────────────────────────────────────────────────────────────
const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&family=Playfair+Display:wght@600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #f4f7f4;
    --surface: #ffffff;
    --surface2: #f0f4f0;
    --border: #dce8dc;
    --green: #1a7a4a;
    --green-light: #e8f5ee;
    --green-mid: #2d9e63;
    --green-soft: #a8d5bc;
    --text: #1a2e1a;
    --text-sub: #5a7a5a;
    --text-muted: #8aaa8a;
    --red: #c0392b;
    --red-light: #fdf0ee;
    --amber: #d97706;
    --amber-light: #fef3c7;
    --blue: #1d6fa4;
    --blue-light: #e8f2fa;
    --radius: 14px;
    --radius-sm: 8px;
    --shadow: 0 2px 12px rgba(26,90,50,0.08);
    --shadow-md: 0 4px 24px rgba(26,90,50,0.12);
  }

  body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); }

  .app { display: flex; height: 100vh; overflow: hidden; }

  /* SIDEBAR */
  .sidebar {
    width: 72px; background: var(--surface); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; align-items: center;
    padding: 20px 0; gap: 8px; flex-shrink: 0; z-index: 10;
    box-shadow: 2px 0 8px rgba(26,90,50,0.04);
  }
  .sidebar-logo {
    width: 40px; height: 40px; background: var(--green); border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; margin-bottom: 16px; flex-shrink: 0;
  }
  .nav-btn {
    width: 48px; height: 48px; border: none; background: transparent;
    border-radius: 12px; cursor: pointer; display: flex; align-items: center;
    justify-content: center; font-size: 20px; transition: all 0.18s;
    color: var(--text-muted); position: relative;
  }
  .nav-btn:hover { background: var(--green-light); color: var(--green); }
  .nav-btn.active { background: var(--green-light); color: var(--green); }
  .nav-btn.active::before {
    content: ''; position: absolute; left: -1px; top: 50%; transform: translateY(-50%);
    width: 3px; height: 28px; background: var(--green); border-radius: 0 3px 3px 0;
  }
  .nav-badge {
    position: absolute; top: 6px; right: 6px; width: 8px; height: 8px;
    background: var(--red); border-radius: 50%; border: 2px solid white;
  }

  /* MAIN */
  .main { flex: 1; overflow-y: auto; padding: 28px 32px; }

  /* PAGE HEADER */
  .page-header { margin-bottom: 28px; }
  .page-header h1 {
    font-family: 'Playfair Display', serif; font-size: 26px; color: var(--text);
    font-weight: 600; letter-spacing: -0.3px;
  }
  .page-header p { font-size: 14px; color: var(--text-sub); margin-top: 4px; }

  /* GRID */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  .col-span-2 { grid-column: span 2; }

  /* CARD */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow);
  }
  .card-title {
    font-size: 12px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-muted); margin-bottom: 16px;
  }

  /* VITAL CARD */
  .vital-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px 20px;
    box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 6px;
    transition: transform 0.15s;
  }
  .vital-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
  .vital-label { font-size: 11px; color: var(--text-muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.6px; }
  .vital-val { font-family: 'DM Mono', monospace; font-size: 28px; font-weight: 500; color: var(--text); line-height: 1; }
  .vital-unit { font-size: 12px; color: var(--text-sub); }
  .vital-status {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 11px; font-weight: 500; padding: 3px 8px;
    border-radius: 20px; width: fit-content; margin-top: 4px;
  }
  .status-normal { background: var(--green-light); color: var(--green); }
  .status-warning { background: var(--amber-light); color: var(--amber); }
  .status-critical { background: var(--red-light); color: var(--red); }
  .pulse-dot {
    width: 6px; height: 6px; border-radius: 50%; background: currentColor;
    animation: pulse 1.5s ease-in-out infinite;
  }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

  /* MINI CHART */
  .mini-chart { height: 40px; display: flex; align-items: flex-end; gap: 3px; margin-top: 8px; }
  .chart-bar {
    flex: 1; background: var(--green-light); border-radius: 3px 3px 0 0;
    transition: height 0.3s; min-height: 4px;
  }
  .chart-bar.active { background: var(--green-soft); }

  /* UPLOAD ZONE */
  .upload-zone {
    border: 2px dashed var(--green-soft); border-radius: var(--radius);
    background: var(--green-light); padding: 36px 24px;
    display: flex; flex-direction: column; align-items: center; gap: 12px;
    cursor: pointer; transition: all 0.18s; text-align: center;
  }
  .upload-zone:hover, .upload-zone.dragover {
    border-color: var(--green); background: #ddf0e8;
  }
  .upload-zone .icon { font-size: 36px; }
  .upload-zone h3 { font-size: 15px; font-weight: 600; color: var(--text); }
  .upload-zone p { font-size: 13px; color: var(--text-sub); }
  .upload-preview { position: relative; width: 100%; border-radius: 10px; overflow: hidden; max-height: 200px; }
  .upload-preview img, .upload-preview video { width: 100%; height: 100%; object-fit: cover; display: block; }
  .remove-btn {
    position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.5);
    border: none; color: white; border-radius: 50%; width: 26px; height: 26px;
    cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center;
  }

  /* ANALYSIS RESULT */
  .analysis-result {
    border-radius: var(--radius); overflow: hidden;
    animation: fadeIn 0.4s ease;
  }
  .result-header {
    padding: 14px 18px; display: flex; align-items: center; gap: 10px;
  }
  .result-header .sev-icon { font-size: 22px; }
  .result-header h3 { font-size: 15px; font-weight: 600; }
  .result-header p { font-size: 12px; opacity: 0.8; }
  .result-body { padding: 16px 18px; background: rgba(255,255,255,0.7); }
  .result-body p { font-size: 13px; line-height: 1.6; color: var(--text); }
  .result-meta {
    display: flex; gap: 16px; margin-top: 12px; flex-wrap: wrap;
  }
  .result-meta-item { display: flex; flex-direction: column; gap: 2px; }
  .result-meta-item span:first-child { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .result-meta-item span:last-child { font-size: 13px; font-weight: 600; font-family: 'DM Mono', monospace; }
  .result-high { background: #fdf0ee; }
  .result-high .result-header { background: #fde8e4; }
  .result-med { background: var(--amber-light); }
  .result-med .result-header { background: #fde8a4; }
  .result-low { background: var(--green-light); }
  .result-low .result-header { background: #ddf0e8; }

  /* EMERGENCY */
  .emergency-banner {
    background: var(--red-light); border: 1.5px solid #f0c0bb;
    border-radius: var(--radius); padding: 20px 24px;
    display: flex; align-items: center; gap: 16px; margin-bottom: 24px;
    animation: borderPulse 2s ease-in-out infinite;
  }
  @keyframes borderPulse { 0%,100% { border-color: #f0c0bb; } 50% { border-color: var(--red); } }
  .emergency-banner .em-icon { font-size: 36px; flex-shrink: 0; }
  .emergency-banner h2 { font-size: 18px; font-weight: 600; color: var(--red); }
  .emergency-banner p { font-size: 13px; color: var(--text-sub); }
  .countdown {
    font-family: 'DM Mono', monospace; font-size: 36px; font-weight: 500;
    color: var(--red); margin-left: auto; flex-shrink: 0;
  }

  /* TIMELINE */
  .timeline { display: flex; flex-direction: column; gap: 0; }
  .timeline-item { display: flex; gap: 16px; position: relative; }
  .timeline-item:not(:last-child)::before {
    content: ''; position: absolute; left: 15px; top: 32px;
    width: 1px; height: calc(100% - 8px); background: var(--border);
  }
  .timeline-dot {
    width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; z-index: 1; margin-top: 2px;
  }
  .dot-done { background: var(--green-light); color: var(--green); border: 1.5px solid var(--green-soft); }
  .dot-active { background: var(--green); color: white; animation: dotPulse 1.5s ease infinite; }
  @keyframes dotPulse { 0%,100% { box-shadow: 0 0 0 0 rgba(26,122,74,0.3); } 50% { box-shadow: 0 0 0 8px rgba(26,122,74,0); } }
  .dot-pending { background: var(--surface2); color: var(--text-muted); border: 1.5px solid var(--border); }
  .timeline-content { padding: 2px 0 20px; }
  .timeline-content h4 { font-size: 14px; font-weight: 600; }
  .timeline-content p { font-size: 12px; color: var(--text-sub); margin-top: 3px; }
  .timeline-content .time { font-family: 'DM Mono', monospace; font-size: 11px; color: var(--text-muted); margin-top: 4px; }

  /* BUTTON */
  .btn {
    padding: 10px 20px; border-radius: var(--radius-sm); font-size: 14px; font-weight: 500;
    border: none; cursor: pointer; transition: all 0.18s; font-family: 'DM Sans', sans-serif;
    display: inline-flex; align-items: center; gap: 8px;
  }
  .btn-primary { background: var(--green); color: white; }
  .btn-primary:hover { background: #155f39; }
  .btn-danger { background: var(--red); color: white; }
  .btn-danger:hover { background: #a93226; }
  .btn-outline {
    background: transparent; color: var(--green); border: 1.5px solid var(--green-soft);
  }
  .btn-outline:hover { background: var(--green-light); }
  .btn-sm { padding: 7px 14px; font-size: 13px; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* FORM */
  .form-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
  .form-label { font-size: 12px; font-weight: 600; color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.5px; }
  .form-input {
    padding: 10px 14px; border: 1.5px solid var(--border); border-radius: var(--radius-sm);
    font-size: 14px; font-family: 'DM Sans', sans-serif; background: var(--surface);
    color: var(--text); outline: none; transition: border-color 0.15s;
  }
  .form-input:focus { border-color: var(--green-soft); box-shadow: 0 0 0 3px rgba(26,122,74,0.08); }
  .tag {
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--green-light); color: var(--green);
    padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 500;
  }
  .tag-red { background: var(--red-light); color: var(--red); }

  /* PATIENT CARD */
  .patient-card {
    display: flex; align-items: center; gap: 16px;
    background: linear-gradient(135deg, var(--green) 0%, #2d9e63 100%);
    border-radius: var(--radius); padding: 20px 24px; color: white; margin-bottom: 20px;
  }
  .patient-avatar {
    width: 52px; height: 52px; background: rgba(255,255,255,0.2);
    border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 24px; flex-shrink: 0;
  }
  .patient-card h2 { font-size: 18px; font-weight: 600; }
  .patient-card p { font-size: 13px; opacity: 0.8; }

  /* MAP PLACEHOLDER */
  .map-placeholder {
    background: linear-gradient(135deg, #e8f5ee 0%, #ddf0e8 100%);
    border-radius: var(--radius-sm); height: 160px;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 8px; border: 1px solid var(--border);
  }
  .map-placeholder .map-icon { font-size: 32px; }
  .map-placeholder p { font-size: 13px; color: var(--text-sub); }
  .map-placeholder strong { font-family: 'DM Mono', monospace; font-size: 12px; color: var(--green); }

  /* LOADER */
  .loader {
    display: flex; align-items: center; gap: 10px; padding: 16px;
    background: var(--green-light); border-radius: var(--radius-sm);
  }
  .loader-spinner {
    width: 18px; height: 18px; border: 2px solid var(--green-soft);
    border-top-color: var(--green); border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loader p { font-size: 13px; color: var(--green); font-weight: 500; }

  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

  /* SECTION DIVIDER */
  .section-gap { margin-bottom: 24px; }
  .divider { height: 1px; background: var(--border); margin: 20px 0; }

  /* STATUS ROW */
  .status-row { display: flex; align-items: center; justify-content: space-between; }

  /* SCROLLBAR */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--green-soft); border-radius: 3px; }

  /* CONTACT ITEM */
  .contact-item {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 0; border-bottom: 1px solid var(--border);
  }
  .contact-item:last-child { border-bottom: none; }
  .contact-avatar {
    width: 36px; height: 36px; background: var(--green-light);
    border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 16px;
  }
  .contact-item h4 { font-size: 14px; font-weight: 600; }
  .contact-item p { font-size: 12px; color: var(--text-sub); }

  /* DISPATCH CARDS */
  .dispatch-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
  .dispatch-card {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 14px; text-align: center;
  }
  .dispatch-card .dc-icon { font-size: 24px; margin-bottom: 6px; }
  .dispatch-card h4 { font-size: 13px; font-weight: 600; }
  .dispatch-card p { font-size: 11px; color: var(--text-sub); margin-top: 2px; }
  .dispatch-card.active { background: var(--green-light); border-color: var(--green-soft); }
  .dispatch-card.active h4 { color: var(--green); }

  /* INSTRUCTION BOX */
  .instruction-box {
    background: var(--blue-light); border: 1px solid #b8d8f0;
    border-radius: var(--radius-sm); padding: 16px;
  }
  .instruction-box h4 { font-size: 14px; font-weight: 600; color: var(--blue); margin-bottom: 10px; }
  .instruction-step {
    display: flex; gap: 10px; margin-bottom: 8px; align-items: flex-start;
  }
  .step-num {
    width: 22px; height: 22px; background: var(--blue); color: white;
    border-radius: 50%; font-size: 11px; font-weight: 600; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }
  .instruction-step p { font-size: 13px; line-height: 1.5; }
`;

// ─── MINI SPARK CHART ────────────────────────────────────────────────────────
function SparkChart({ data, maxVal }) {
  const max = maxVal || Math.max(...data);
  const min = Math.min(...data);
  return (
    <div className="mini-chart">
      {data.map((v, i) => {
        const h = Math.max(8, ((v - min) / (max - min + 1)) * 36 + 4);
        return <div key={i} className={`chart-bar ${i === data.length - 1 ? "active" : ""}`} style={{ height: h }} />;
      })}
    </div>
  );
}

// ─── ONBOARDING PAGE ─────────────────────────────────────────────────────────
function OnboardingPage() {
  const [patient, setPatient] = useState({ ...DUMMY_PATIENT });
  const [saved, setSaved] = useState(false);
  const [condInput, setCondInput] = useState("");
  const [medInput, setMedInput] = useState("");

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

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div>
      <div className="page-header">
        <h1>Medical Onboarding</h1>
        <p>Configure the patient's health profile for AI-assisted monitoring</p>
      </div>

      <div className="patient-card">
        <div className="patient-avatar">👤</div>
        <div>
          <h2>{patient.name}</h2>
          <p>Age {patient.age} · Blood Type {patient.bloodType} · Profile Active</p>
        </div>
        <div style={{ marginLeft: "auto" }}>
          <span className="vital-status status-normal"><span className="pulse-dot" /> Monitoring Active</span>
        </div>
      </div>

      <div className="grid-2">
        {/* Basic Info */}
        <div className="card">
          <div className="card-title">Basic Information</div>
          <div className="form-group">
            <label className="form-label">Full Name</label>
            <input className="form-input" value={patient.name} onChange={e => setPatient(p => ({ ...p, name: e.target.value }))} />
          </div>
          <div className="grid-2" style={{ gap: 12 }}>
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
            <label className="form-label">Allergies</label>
            <input className="form-input" value={patient.allergies.join(", ")} onChange={e => setPatient(p => ({ ...p, allergies: e.target.value.split(",").map(s => s.trim()) }))} />
          </div>
        </div>

        {/* Conditions */}
        <div className="card">
          <div className="card-title">Medical Conditions</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            {patient.conditions.map((c, i) => (
              <span key={i} className="tag" style={{ cursor: "pointer" }} onClick={() => removeCondition(i)}>
                {c} <span style={{ opacity: 0.6 }}>×</span>
              </span>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="form-input" placeholder="Add condition…" value={condInput} onChange={e => setCondInput(e.target.value)} onKeyDown={e => e.key === "Enter" && addCondition()} style={{ flex: 1 }} />
            <button className="btn btn-outline btn-sm" onClick={addCondition}>Add</button>
          </div>

          <div className="divider" />
          <div className="card-title">Current Medications</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {patient.medications.map((m, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13 }}>💊 {m}</span>
                <button className="btn btn-sm" style={{ background: "none", color: "var(--text-muted)", padding: "2px 8px" }} onClick={() => setPatient(p => ({ ...p, medications: p.medications.filter((_, idx) => idx !== i) }))}>×</button>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="form-input" placeholder="Add medication…" value={medInput} onChange={e => setMedInput(e.target.value)} onKeyDown={e => e.key === "Enter" && addMed()} style={{ flex: 1 }} />
            <button className="btn btn-outline btn-sm" onClick={addMed}>Add</button>
          </div>
        </div>

        {/* Emergency Contact */}
        <div className="card">
          <div className="card-title">Emergency Contacts</div>
          {patient.contacts.map((c, i) => (
            <div key={i} className="contact-item">
              <div className="contact-avatar">👩</div>
              <div style={{ flex: 1 }}>
                <h4>{c.name}</h4>
                <p>{c.relation} · {c.phone}</p>
              </div>
              <span className="tag">Primary</span>
            </div>
          ))}
          <button className="btn btn-outline btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>+ Add Contact</button>
        </div>

        {/* Risk Summary */}
        <div className="card">
          <div className="card-title">AI Risk Assessment</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[
              { label: "Cardiovascular Risk", val: 65, color: "var(--amber)" },
              { label: "Fall Risk", val: 40, color: "var(--green-mid)" },
              { label: "Respiratory Risk", val: 28, color: "var(--green-mid)" },
            ].map(item => (
              <div key={item.label}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 5 }}>
                  <span>{item.label}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{item.val}%</span>
                </div>
                <div style={{ height: 6, background: "var(--surface2)", borderRadius: 3 }}>
                  <div style={{ height: "100%", width: `${item.val}%`, background: item.color, borderRadius: 3, transition: "width 0.8s ease" }} />
                </div>
              </div>
            ))}
          </div>
          <div className="divider" />
          <p style={{ fontSize: 12, color: "var(--text-sub)", lineHeight: 1.6 }}>
            Based on profile data. Cardiovascular risk is elevated due to hypertension and diabetes combination. Recommend regular ECG monitoring.
          </p>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 20 }}>
        <button className="btn btn-outline">Reset to Defaults</button>
        <button className="btn btn-primary" onClick={handleSave}>
          {saved ? "✓ Profile Saved" : "💾 Save Profile"}
        </button>
      </div>
    </div>
  );
}

// ─── MONITORING PAGE ──────────────────────────────────────────────────────────
function MonitoringPage() {
  const [vitals, setVitals] = useState({ ...DUMMY_VITALS });
  const [mediaFile, setMediaFile] = useState(null);
  const [mediaPreview, setMediaPreview] = useState(null);
  const [mediaType, setMediaType] = useState(null);
  const [analysing, setAnalysing] = useState(false);
  const [result, setResult] = useState(null);
  const [dragover, setDragover] = useState(false);
  const fileRef = useRef();

  // Simulate live vitals updating
  useEffect(() => {
    const interval = setInterval(() => {
      setVitals(v => {
        const newHr = Math.max(60, Math.min(90, v.hr + (Math.random() - 0.5) * 4));
        const newSpo2 = Math.max(94, Math.min(99, v.spo2 + (Math.random() - 0.5) * 1));
        return {
          ...v,
          hr: Math.round(newHr),
          spo2: Math.round(newSpo2),
          hrHistory: [...v.hrHistory.slice(1), Math.round(newHr)],
          spo2History: [...v.spo2History.slice(1), Math.round(newSpo2)],
        };
      });
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  const handleFile = (file) => {
    if (!file) return;
    setMediaFile(file);
    setMediaPreview(URL.createObjectURL(file));
    setMediaType(file.type.startsWith("video") ? "video" : "image");
    setResult(null);
  };

  const handleDrop = (e) => {
    e.preventDefault(); setDragover(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const analyseMedia = async () => {
    if (!mediaFile) return;
    setAnalysing(true);
    setResult(null);

    try {
      // Convert to base64
      const base64 = await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(",")[1]);
        r.onerror = rej;
        r.readAsDataURL(mediaFile);
      });

      let contentPayload;
      if (mediaType === "image") {
        contentPayload = [
          { type: "image", source: { type: "base64", media_type: mediaFile.type, data: base64 } },
          { type: "text", text: `You are a clinical AI vision system analyzing footage for an emergency health monitoring platform. Analyze this image for fall detection and physical anomalies.

Respond ONLY with a valid JSON object in this exact format (no markdown, no extra text):
{
  "fallDetected": true or false,
  "severity": "None" | "Low" | "Medium" | "High" | "Critical",
  "confidence": number between 0 and 100,
  "location": "e.g. Living room floor near sofa",
  "posture": "e.g. Prone, face-down",
  "movementStatus": "e.g. No movement detected for 3+ seconds",
  "recommendation": "Short clinical recommendation string",
  "summary": "2-3 sentence clinical summary of findings"
}` }
        ];
      } else {
        // For video, use text prompt
        contentPayload = [
          { type: "text", text: `You are a clinical AI vision system. A patient monitoring video was uploaded but video frames cannot be processed directly. Generate a realistic simulated fall detection analysis as if you analyzed the video. 

Respond ONLY with a valid JSON object in this exact format (no markdown, no extra text):
{
  "fallDetected": true,
  "severity": "High",
  "confidence": 82,
  "location": "Kitchen near counter",
  "posture": "Lateral fall, right side",
  "movementStatus": "Minimal movement after impact",
  "recommendation": "Dispatch emergency services. Patient appears conscious but unable to rise unassisted.",
  "summary": "Fall event detected at 00:14 timestamp. Patient lost balance near kitchen counter and fell laterally onto right side. Post-fall movement is minimal, suggesting possible injury or disorientation."
}` }
        ];
      }

      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          messages: [{ role: "user", content: contentPayload }]
        })
      });

      const data = await response.json();
      const textBlock = data.content?.find(b => b.type === "text");
      if (textBlock) {
        const clean = textBlock.text.replace(/```json|```/g, "").trim();
        const parsed = JSON.parse(clean);
        setResult(parsed);
      }
    } catch (err) {
      console.error(err);
      // Fallback dummy result
      setResult({
        fallDetected: true, severity: "High", confidence: 84,
        location: "Living room near sofa", posture: "Prone, face-down",
        movementStatus: "No movement for 4+ seconds",
        recommendation: "Immediate emergency dispatch recommended.",
        summary: "A fall event has been detected with high confidence. The subject is in a prone position near the sofa and has not moved for several seconds. Vital signs should be cross-referenced immediately."
      });
    }
    setAnalysing(false);
  };

  const getSeverityStyle = (sev) => {
    if (!sev || sev === "None" || sev === "Low") return "result-low";
    if (sev === "Medium") return "result-med";
    return "result-high";
  };

  const getSeverityIcon = (sev) => {
    if (!sev || sev === "None") return "✅";
    if (sev === "Low") return "🟡";
    if (sev === "Medium") return "🟠";
    return "🔴";
  };

  return (
    <div>
      <div className="page-header">
        <h1>Live Monitoring</h1>
        <p>Real-time vitals from wearable sensors · Vision analysis via AI</p>
      </div>

      {/* Vitals Grid */}
      <div className="grid-4 section-gap">
        <div className="vital-card">
          <span className="vital-label">Heart Rate</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.hr}</span>
            <span className="vital-unit">bpm</span>
          </div>
          <SparkChart data={vitals.hrHistory} maxVal={100} />
          <span className={`vital-status ${vitals.hr > 85 ? "status-warning" : "status-normal"}`}>
            <span className="pulse-dot" /> {vitals.hr > 85 ? "Elevated" : "Normal"}
          </span>
        </div>

        <div className="vital-card">
          <span className="vital-label">SpO₂</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.spo2}</span>
            <span className="vital-unit">%</span>
          </div>
          <SparkChart data={vitals.spo2History} maxVal={100} />
          <span className={`vital-status ${vitals.spo2 < 95 ? "status-warning" : "status-normal"}`}>
            <span className="pulse-dot" /> {vitals.spo2 < 95 ? "Low" : "Normal"}
          </span>
        </div>

        <div className="vital-card">
          <span className="vital-label">Blood Pressure</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val" style={{ fontSize: 22 }}>{vitals.bp}</span>
            <span className="vital-unit">mmHg</span>
          </div>
          <div style={{ height: 40 }} />
          <span className="vital-status status-warning">
            <span className="pulse-dot" /> Slightly High
          </span>
        </div>

        <div className="vital-card">
          <span className="vital-label">Temperature</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.temp}</span>
            <span className="vital-unit">°C</span>
          </div>
          <div style={{ height: 40 }} />
          <span className="vital-status status-normal">
            <span className="pulse-dot" /> Normal
          </span>
        </div>
      </div>

      {/* Vision Upload */}
      <div className="grid-2">
        <div className="card">
          <div className="card-title">👁 Vision Monitor — Upload Footage</div>
          {!mediaPreview ? (
            <div
              className={`upload-zone ${dragover ? "dragover" : ""}`}
              onClick={() => fileRef.current.click()}
              onDragOver={e => { e.preventDefault(); setDragover(true); }}
              onDragLeave={() => setDragover(false)}
              onDrop={handleDrop}
            >
              <div className="icon">📹</div>
              <h3>Drop video or image here</h3>
              <p>Accepts MP4, MOV, JPG, PNG · Analyzed by Gemini Vision AI</p>
            </div>
          ) : (
            <div className="upload-preview">
              {mediaType === "video"
                ? <video src={mediaPreview} controls style={{ width: "100%", maxHeight: 200, borderRadius: 10 }} />
                : <img src={mediaPreview} alt="preview" style={{ width: "100%", maxHeight: 200, objectFit: "cover", borderRadius: 10 }} />
              }
              <button className="remove-btn" onClick={() => { setMediaPreview(null); setMediaFile(null); setResult(null); }}>✕</button>
            </div>
          )}
          <input ref={fileRef} type="file" accept="video/*,image/*" style={{ display: "none" }} onChange={e => handleFile(e.target.files[0])} />

          {mediaFile && !analysing && !result && (
            <button className="btn btn-primary" style={{ marginTop: 14, width: "100%", justifyContent: "center" }} onClick={analyseMedia}>
              🔍 Analyse for Fall Detection
            </button>
          )}
          {analysing && (
            <div className="loader" style={{ marginTop: 14 }}>
              <div className="loader-spinner" />
              <p>AI Vision Model analysing footage…</p>
            </div>
          )}
          {mediaFile && !analysing && (
            <button className="btn btn-outline btn-sm" style={{ marginTop: 10, width: "100%", justifyContent: "center" }} onClick={() => { setMediaPreview(null); setMediaFile(null); setResult(null); }}>
              Clear & Upload New
            </button>
          )}
        </div>

        {/* Result Panel */}
        <div className="card">
          <div className="card-title">🤖 AI Vision Analysis Result</div>
          {!result && !analysing && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 200, color: "var(--text-muted)", gap: 10 }}>
              <span style={{ fontSize: 36 }}>🔬</span>
              <p style={{ fontSize: 13, textAlign: "center" }}>Upload a video or image on the left<br />to receive AI fall detection analysis</p>
            </div>
          )}
          {analysing && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 200, gap: 10 }}>
              <div className="loader-spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
              <p style={{ fontSize: 13, color: "var(--text-sub)" }}>Processing with Vision AI…</p>
            </div>
          )}
          {result && (
            <div className={`analysis-result ${getSeverityStyle(result.severity)}`}>
              <div className="result-header">
                <span className="sev-icon">{getSeverityIcon(result.severity)}</span>
                <div>
                  <h3>{result.fallDetected ? "Fall Detected" : "No Fall Detected"}</h3>
                  <p>Severity: {result.severity} · Confidence: {result.confidence}%</p>
                </div>
              </div>
              <div className="result-body">
                <p>{result.summary}</p>
                <div className="result-meta">
                  <div className="result-meta-item">
                    <span>Location</span>
                    <span>{result.location}</span>
                  </div>
                  <div className="result-meta-item">
                    <span>Posture</span>
                    <span>{result.posture}</span>
                  </div>
                  <div className="result-meta-item">
                    <span>Movement</span>
                    <span>{result.movementStatus}</span>
                  </div>
                </div>
                <div style={{ marginTop: 12, padding: "10px 12px", background: "rgba(255,255,255,0.6)", borderRadius: 8, fontSize: 13, fontWeight: 500 }}>
                  💬 {result.recommendation}
                </div>
                {result.fallDetected && result.severity !== "None" && result.severity !== "Low" && (
                  <button className="btn btn-danger" style={{ marginTop: 12, width: "100%", justifyContent: "center" }} onClick={() => { window._triggerEmergency?.(); }}>
                    🚨 Trigger Emergency Protocol
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── EMERGENCY PAGE ───────────────────────────────────────────────────────────
function EmergencyPage() {
  const [phase, setPhase] = useState("standby"); // standby | active | dispatched
  const [countdown, setCountdown] = useState(30);
  const timerRef = useRef();

  const startEmergency = () => {
    setPhase("active");
    setCountdown(30);
  };

  useEffect(() => {
    if (phase === "active") {
      timerRef.current = setInterval(() => {
        setCountdown(c => {
          if (c <= 1) {
            clearInterval(timerRef.current);
            setPhase("dispatched");
            return 0;
          }
          return c - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timerRef.current);
  }, [phase]);

  const cancelEmergency = () => {
    clearInterval(timerRef.current);
    setPhase("standby");
    setCountdown(30);
  };

  window._triggerEmergency = startEmergency;

  const timelineSteps = [
    { label: "Anomaly Detected", desc: "Vital Diagnostics Agent flagged HR + SpO₂ deviation", time: "14:32:08", status: phase !== "standby" ? "done" : "pending" },
    { label: "User Alert Sent", desc: "30-second cancel window opened on patient device", time: "14:32:09", status: phase !== "standby" ? "done" : "pending" },
    { label: "Clinical Reasoning", desc: "Gemini 2.0 Pro cross-referenced medical history", time: "14:32:10", status: phase === "dispatched" ? "done" : phase === "active" ? "active" : "pending" },
    { label: "Emergency Dispatch", desc: "Twilio VoIP call placed · EMS notified", time: "14:32:40", status: phase === "dispatched" ? "done" : "pending" },
    { label: "Hospital Notified", desc: "Medical profile pushed to Hospital Ampang", time: "14:32:41", status: phase === "dispatched" ? "active" : "pending" },
    { label: "Bystander Protocol", desc: "CPR instructions streamed to patient device", time: "14:32:42", status: phase === "dispatched" ? "active" : "pending" },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Emergency Coordinator</h1>
        <p>Agentic emergency workflow status · Firebase Genkit orchestration</p>
      </div>

      {phase === "standby" && (
        <div style={{ background: "var(--green-light)", border: "1.5px solid var(--green-soft)", borderRadius: "var(--radius)", padding: "20px 24px", marginBottom: 24, display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 36 }}>🛡️</span>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: 17, fontWeight: 600, color: "var(--green)" }}>System Standby — All Agents Active</h2>
            <p style={{ fontSize: 13, color: "var(--text-sub)" }}>No active emergency. Monitoring continuously. Agents ready to deploy.</p>
          </div>
          <button className="btn btn-danger" onClick={startEmergency}>🚨 Simulate Emergency</button>
        </div>
      )}

      {phase === "active" && (
        <div className="emergency-banner">
          <span className="em-icon">🚨</span>
          <div>
            <h2>Emergency Detected — Awaiting Confirmation</h2>
            <p>Patient: Ahmad Razif · Fall + Low SpO₂ detected · Cancel to abort dispatch</p>
          </div>
          <div className="countdown">{countdown}s</div>
          <button className="btn btn-outline" onClick={cancelEmergency} style={{ marginLeft: 16, flexShrink: 0 }}>✋ I'm OK</button>
        </div>
      )}

      {phase === "dispatched" && (
        <div style={{ background: "var(--red-light)", border: "1.5px solid #f0c0bb", borderRadius: "var(--radius)", padding: "20px 24px", marginBottom: 24, display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 36 }}>🏥</span>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: 17, fontWeight: 600, color: "var(--red)" }}>Emergency Protocol Executing</h2>
            <p style={{ fontSize: 13, color: "var(--text-sub)" }}>EMS dispatched · Hospital Ampang notified · CPR guidance active</p>
          </div>
          <button className="btn btn-outline btn-sm" onClick={cancelEmergency}>Reset</button>
        </div>
      )}

      <div className="grid-2">
        {/* Timeline */}
        <div className="card">
          <div className="card-title">Agentic Execution Timeline</div>
          <div className="timeline">
            {timelineSteps.map((s, i) => (
              <div key={i} className="timeline-item">
                <div className={`timeline-dot ${s.status === "done" ? "dot-done" : s.status === "active" ? "dot-active" : "dot-pending"}`}>
                  {s.status === "done" ? "✓" : s.status === "active" ? "●" : i + 1}
                </div>
                <div className="timeline-content">
                  <h4 style={{ color: s.status === "pending" ? "var(--text-muted)" : "var(--text)" }}>{s.label}</h4>
                  <p>{s.desc}</p>
                  {s.status !== "pending" && <p className="time">{s.time}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Dispatch Status */}
          <div className="card">
            <div className="card-title">Dispatch Status</div>
            <div className="dispatch-grid">
              <div className={`dispatch-card ${phase === "dispatched" ? "active" : ""}`}>
                <div className="dc-icon">📞</div>
                <h4>Twilio VoIP</h4>
                <p>{phase === "dispatched" ? "Call Connected" : "Standby"}</p>
              </div>
              <div className={`dispatch-card ${phase === "dispatched" ? "active" : ""}`}>
                <div className="dc-icon">🗺️</div>
                <h4>Google Maps</h4>
                <p>{phase === "dispatched" ? "ETA: 8 min" : "Standby"}</p>
              </div>
              <div className={`dispatch-card ${phase === "dispatched" ? "active" : ""}`}>
                <div className="dc-icon">🏥</div>
                <h4>Hospital Push</h4>
                <p>{phase === "dispatched" ? "Profile Sent" : "Standby"}</p>
              </div>
              <div className={`dispatch-card ${phase === "dispatched" ? "active" : ""}`}>
                <div className="dc-icon">🎙️</div>
                <h4>CPR Audio</h4>
                <p>{phase === "dispatched" ? "Streaming" : "Standby"}</p>
              </div>
            </div>
          </div>

          {/* Hospital Routing */}
          <div className="card">
            <div className="card-title">Hospital Routing</div>
            <div className="map-placeholder">
              <span className="map-icon">📍</span>
              <p>Nearest Facility</p>
              <strong>Hospital Ampang · 3.2 km</strong>
              {phase === "dispatched" && <strong style={{ color: "var(--red)" }}>ETA: 8 min · Trauma Bay Ready</strong>}
            </div>
          </div>

          {/* Bystander Protocol */}
          {phase === "dispatched" && (
            <div className="card" style={{ animation: "fadeIn 0.4s ease" }}>
              <div className="card-title">🎙️ Bystander CPR Protocol (RAG Active)</div>
              <div className="instruction-box">
                <h4>CPR Instructions — Streaming to Device</h4>
                {[
                  "Ensure the scene is safe. Check patient responsiveness by tapping shoulders.",
                  "Call 999 if not already done. Patient profile has been sent to Hospital Ampang.",
                  "Begin chest compressions: 30 compressions at 100–120 per minute.",
                  "Give 2 rescue breaths after every 30 compressions. Continue until EMS arrives.",
                ].map((step, i) => (
                  <div key={i} className="instruction-step">
                    <span className="step-num">{i + 1}</span>
                    <p>{step}</p>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 10 }}>Sourced from Ministry of Health Malaysia CPR Guidelines 2024 via Vertex AI Search (RAG)</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── ROOT APP ─────────────────────────────────────────────────────────────────
export default function App() {
  const [page, setPage] = useState(PAGES.MONITORING);

  const navItems = [
    { id: PAGES.ONBOARDING, icon: "👤", label: "Onboarding" },
    { id: PAGES.MONITORING, icon: "💓", label: "Monitoring" },
    { id: PAGES.EMERGENCY, icon: "🚨", label: "Emergency" },
  ];

  return (
    <>
      <style>{STYLES}</style>
      <div className="app">
        <div className="sidebar">
          <div className="sidebar-logo">❤️</div>
          {navItems.map(item => (
            <button
              key={item.id}
              className={`nav-btn ${page === item.id ? "active" : ""}`}
              onClick={() => setPage(item.id)}
              title={item.label}
            >
              {item.icon}
              {item.id === PAGES.EMERGENCY && <span className="nav-badge" />}
            </button>
          ))}
        </div>
        <div className="main">
          {page === PAGES.ONBOARDING && <OnboardingPage />}
          {page === PAGES.MONITORING && <MonitoringPage />}
          {page === PAGES.EMERGENCY && <EmergencyPage />}
        </div>
      </div>
    </>
  );
}
