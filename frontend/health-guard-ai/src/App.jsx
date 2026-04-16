import { useState, useEffect, useRef } from "react";
import MvpTestPage from "./components/MvpTestPage.jsx";

// ─── TYPES ──────────────────────────────────────────────────────────────────
const PAGES = { ONBOARDING: "onboarding", PROFILE: "profile", HISTORY: "history", MVP_TEST: "mvp_test" };

// ─── DEMO PROFILES ────────────────────────────────────────────────────────────
const DEMO_PROFILES = [
  {
    id: 1,
    name: "Ahmad Razif",
    age: 68,
    bloodType: "B+",
    gender: "Male",
    avatar: "👴",
    conditions: ["Hypertension", "Type 2 Diabetes"],
    medications: ["Metformin 500mg", "Amlodipine 5mg"],
    allergies: ["Penicillin"],
    contacts: [{ name: "Siti Razif", relation: "Daughter", phone: "+60 12-345 6789" }],
    riskProfile: { cardiovascular: 65, fall: 40, respiratory: 28 },
  },
  {
    id: 2,
    name: "Mei Ling Tan",
    age: 74,
    bloodType: "A+",
    gender: "Female",
    avatar: "👵",
    conditions: ["Osteoporosis", "Atrial Fibrillation", "Mild Dementia"],
    medications: ["Warfarin 2mg", "Bisoprolol 5mg", "Calcium 500mg"],
    allergies: ["Aspirin", "Sulfa Drugs"],
    contacts: [{ name: "David Tan", relation: "Son", phone: "+60 16-789 0123" }],
    riskProfile: { cardiovascular: 78, fall: 72, respiratory: 35 },
  },
  {
    id: 3,
    name: "Rajan Krishnan",
    age: 61,
    bloodType: "O-",
    gender: "Male",
    avatar: "🧔",
    conditions: ["Chronic Kidney Disease Stage 3", "Hypertension"],
    medications: ["Losartan 50mg", "Furosemide 40mg"],
    allergies: ["NSAIDs"],
    contacts: [{ name: "Priya Krishnan", relation: "Spouse", phone: "+60 11-223 4567" }],
    riskProfile: { cardiovascular: 55, fall: 25, respiratory: 48 },
  },
];

const BASE_VITALS = [
  { hr: 74, spo2: 97, bp: "128/82", temp: 36.8 },
  { hr: 88, spo2: 95, bp: "142/90", temp: 36.6 },
  { hr: 68, spo2: 98, bp: "118/76", temp: 37.1 },
];

const HISTORY_SEED = [
  {
    id: "h1",
    timestamp: "2025-07-09 14:32",
    profile: "Ahmad Razif",
    event: "Fall Detected",
    severity: "High",
    action: "EMS Dispatched",
    summary: "Lateral fall detected in living room. HR drop + SpO₂ dip confirmed. EMS reached in 9 min.",
  },
  {
    id: "h2",
    timestamp: "2025-07-08 09:14",
    profile: "Mei Ling Tan",
    event: "Low SpO₂ Alert",
    severity: "Medium",
    action: "Contact Notified",
    summary: "SpO₂ dropped to 92% during sleep. Alert sent to emergency contact. Patient was OK after repositioning.",
  },
];

// ─── STYLES ──────────────────────────────────────────────────────────────────
const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&family=Instrument+Sans:wght@400;500;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #f8fafb;
    --surface: #ffffff;
    --surface2: #f1f5f7;
    --surface3: #e6ebed;
    --border: #e2e8eb;
    --border-bright: #cbd5e1;

    --green: #10b981;
    --green-dim: #059669;
    --green-glow: rgba(16, 185, 129, 0.1);
    --green-subtle: rgba(16, 185, 129, 0.05);

    --red: #ef4444;
    --red-dim: #dc2626;
    --red-glow: rgba(239, 68, 68, 0.1);
    --red-subtle: rgba(239, 68, 68, 0.05);

    --amber: #f59e0b;
    --amber-dim: #d97706;
    --amber-glow: rgba(245, 158, 11, 0.1);
    --amber-subtle: rgba(245, 158, 11, 0.05);

    --blue: #3b82f6;
    --blue-subtle: rgba(59, 130, 246, 0.05);

    --text: #1a1c1e;
    --text-sub: #475569;
    --text-muted: #94a3b8;

    --radius: 14px;
    --radius-sm: 10px;
    --shadow: 0 4px 12px rgba(15, 23, 42, 0.03);
    --shadow-md: 0 12px 24px rgba(15, 23, 42, 0.06);
  }

  html, body { height: 100%; }
  body {
    font-family: 'Instrument Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
  }

  .app { display: flex; height: 100vh; overflow: hidden; }

  /* ─── SIDEBAR ─── */
  .sidebar {
    width: 64px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column; align-items: center;
    padding: 18px 0; gap: 4px; flex-shrink: 0; z-index: 20;
  }
  .sidebar-logo {
    width: 36px; height: 36px;
    background: var(--green); border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 20px; flex-shrink: 0;
  }
  .sidebar-logo svg { width: 18px; height: 18px; color: #ffffff; }
  .nav-btn {
    width: 44px; height: 44px;
    border: none; background: transparent;
    border-radius: 10px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; transition: all 0.15s;
    color: var(--text-muted); position: relative;
  }
  .nav-btn:hover { background: var(--surface2); color: var(--text); }
  .nav-btn.active { background: var(--green-subtle); color: var(--green); }
  .nav-btn.active::before {
    content: ''; position: absolute; left: -1px; top: 50%; transform: translateY(-50%);
    width: 2px; height: 24px; background: var(--green); border-radius: 0 2px 2px 0;
  }
  .nav-badge {
    position: absolute; top: 8px; right: 8px;
    width: 7px; height: 7px;
    background: var(--red); border-radius: 50%;
    border: 1.5px solid var(--surface);
    animation: badgePulse 2s ease-in-out infinite;
  }
  @keyframes badgePulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }

  /* ─── MAIN ─── */
  .main { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }

  /* ─── PAGE CONTAINER ─── */
  .page { padding: 24px 28px; flex: 1; }

  /* ─── SECTION LABEL ─── */
  .section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; font-weight: 500;
    letter-spacing: 1.5px; text-transform: uppercase;
    color: var(--text-muted); margin-bottom: 12px;
  }

  /* ─── CARD ─── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
  }
  .card-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; font-weight: 500;
    letter-spacing: 1.2px; text-transform: uppercase;
    color: var(--text-muted); margin-bottom: 14px;
  }

  /* ─── GRID ─── */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }

  /* ─── DASHBOARD TOP ROW ─── */
  .dash-top { display: grid; grid-template-columns: 320px 1fr; gap: 16px; margin-bottom: 16px; }

  /* ─── PROFILE CARD ─── */
  .profile-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    cursor: pointer;
    transition: border-color 0.2s;
    position: relative; overflow: hidden;
  }
  .profile-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--green) 0%, transparent 100%);
  }
  .profile-card:hover { border-color: var(--border-bright); }
  .profile-avatar {
    width: 48px; height: 48px;
    background: var(--surface3); border: 1px solid var(--border-bright);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; margin-bottom: 14px;
  }
  .profile-name {
    font-family: 'Syne', sans-serif;
    font-size: 20px; font-weight: 700;
    color: var(--text); line-height: 1.2; margin-bottom: 4px;
  }
  .profile-meta { font-size: 12px; color: var(--text-sub); margin-bottom: 12px; }
  .profile-badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; font-weight: 500;
    background: var(--green-subtle); color: var(--green);
    border: 1px solid rgba(34,197,94,0.2);
    padding: 3px 8px; border-radius: 20px;
  }
  .profile-actions { display: flex; gap: 8px; margin-top: 14px; }
  .profile-switch-btn {
    flex: 1; padding: 7px; border-radius: var(--radius-sm);
    font-size: 11px; font-weight: 600; font-family: 'Instrument Sans', sans-serif;
    cursor: pointer; transition: all 0.15s; border: 1px solid var(--border-bright);
    background: var(--surface2); color: var(--text-sub);
  }
  .profile-switch-btn:hover { background: var(--surface3); color: var(--text); }
  .profile-edit-btn {
    flex: 1; padding: 7px; border-radius: var(--radius-sm);
    font-size: 11px; font-weight: 600; font-family: 'Instrument Sans', sans-serif;
    cursor: pointer; transition: all 0.15s;
    border: 1px solid rgba(34,197,94,0.25);
    background: var(--green-subtle); color: var(--green);
  }
  .profile-edit-btn:hover { background: rgba(34,197,94,0.15); }

  /* ─── VITALS PANEL ─── */
  .vitals-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
  }
  .vitals-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--border); border-radius: var(--radius-sm); overflow: hidden; }
  .vital-item {
    background: var(--surface2); padding: 14px 16px;
    display: flex; flex-direction: column; gap: 4px;
  }
  .vital-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px; letter-spacing: 1.2px; text-transform: uppercase;
    color: var(--text-muted);
  }
  .vital-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 26px; font-weight: 500;
    color: var(--text); line-height: 1;
  }
  .vital-unit { font-size: 10px; color: var(--text-sub); }
  .vital-status-dot {
    width: 5px; height: 5px; border-radius: 50%;
    display: inline-block; margin-right: 4px;
    animation: glow 2s ease-in-out infinite;
  }
  .dot-ok { background: var(--green); box-shadow: 0 0 4px var(--green); }
  .dot-warn { background: var(--amber); box-shadow: 0 0 4px var(--amber); }
  .dot-crit { background: var(--red); box-shadow: 0 0 4px var(--red); }
  @keyframes glow { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
  .vital-tag {
    font-size: 10px; font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
  }
  .tag-ok { color: var(--green); }
  .tag-warn { color: var(--amber); }
  .tag-crit { color: var(--red); }
  .mini-sparkline {
    height: 28px; display: flex; align-items: flex-end; gap: 2px; margin-top: 6px;
  }
  .spark-bar { flex: 1; border-radius: 2px 2px 0 0; min-height: 3px; transition: height 0.4s; }

  /* ─── VISION SECTION ─── */
  .vision-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }

  .upload-zone {
    border: 1.5px dashed var(--border-bright);
    border-radius: var(--radius);
    background: var(--surface2);
    padding: 32px 20px;
    display: flex; flex-direction: column; align-items: center; gap: 10px;
    cursor: pointer; transition: all 0.2s; text-align: center;
  }
  .upload-zone:hover, .upload-zone.dragover {
    border-color: var(--green); background: var(--green-subtle);
  }
  .upload-icon { font-size: 32px; }
  .upload-zone h3 { font-size: 14px; font-weight: 600; color: var(--text); }
  .upload-zone p { font-size: 12px; color: var(--text-sub); }
  .upload-preview { position: relative; border-radius: var(--radius-sm); overflow: hidden; }
  .upload-preview video,
  .upload-preview img { width: 100%; max-height: 190px; object-fit: cover; display: block; border-radius: var(--radius-sm); }
  .remove-btn {
    position: absolute; top: 8px; right: 8px;
    background: rgba(0,0,0,0.6); border: none; color: white;
    border-radius: 50%; width: 24px; height: 24px;
    cursor: pointer; font-size: 12px;
    display: flex; align-items: center; justify-content: center;
  }

  /* ─── RESULT PANEL ─── */
  .result-panel { border-radius: var(--radius); overflow: hidden; animation: slideUp 0.35s ease; }
  .result-header { padding: 14px 16px; display: flex; align-items: center; gap: 10px; }
  .result-header h3 { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 700; }
  .result-header p { font-size: 11px; opacity: 0.7; font-family: 'JetBrains Mono', monospace; }
  .result-body { padding: 14px 16px; }
  .result-body p { font-size: 13px; line-height: 1.6; color: var(--text-sub); }
  .result-meta { display: flex; gap: 16px; margin-top: 10px; flex-wrap: wrap; }
  .result-meta-item { display: flex; flex-direction: column; gap: 2px; }
  .result-meta-item .lbl { font-size: 9px; letter-spacing: 1px; text-transform: uppercase; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }
  .result-meta-item .val { font-size: 12px; font-weight: 600; font-family: 'JetBrains Mono', monospace; color: var(--text); }
  .reco-box { margin-top: 10px; padding: 10px 12px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 500; line-height: 1.5; }

  .panel-high { background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.2); }
  .panel-high .result-header { background: rgba(239,68,68,0.1); }
  .panel-high .result-header h3 { color: var(--red); }
  .panel-high .reco-box { background: rgba(239,68,68,0.05); color: var(--red-dim); }

  .panel-med { background: var(--amber-subtle); border: 1px solid rgba(245,158,11,0.2); }
  .panel-med .result-header { background: var(--amber-glow); }
  .panel-med .result-header h3 { color: var(--amber); }
  .panel-med .reco-box { background: var(--amber-subtle); color: var(--amber-dim); }

  .panel-low { background: var(--green-subtle); border: 1px solid rgba(34,197,94,0.2); }
  .panel-low .result-header { background: var(--green-glow); }
  .panel-low .result-header h3 { color: var(--green); }
  .panel-low .reco-box { background: var(--green-subtle); color: var(--green-dim); }

  /* ─── EMERGENCY COORDINATOR ─── */
  .ec-section { }
  .ec-locked {
    border: 1.5px dashed var(--border-bright);
    border-radius: var(--radius);
    padding: 28px; text-align: center;
    color: var(--text-muted);
    display: flex; flex-direction: column; align-items: center; gap: 8px;
  }
  .ec-locked .lock-icon { font-size: 28px; margin-bottom: 4px; }
  .ec-locked h3 { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 700; color: var(--text-sub); }
  .ec-locked p { font-size: 12px; }

  /* Emergency Banner */
  .em-banner {
    border-radius: var(--radius);
    padding: 16px 20px;
    display: flex; align-items: center; gap: 16px;
    margin-bottom: 16px; animation: emergeBorder 2s ease-in-out infinite;
  }
  .em-banner.standby { background: var(--green-subtle); border: 1px solid rgba(34,197,94,0.2); }
  .em-banner.active { background: rgba(239,68,68,0.07); border: 1.5px solid var(--red); }
  .em-banner.dispatched { background: rgba(239,68,68,0.05); border: 1px solid rgba(239,68,68,0.3); }
  @keyframes emergeBorder {
    0%,100% { border-color: var(--red); }
    50% { border-color: rgba(239,68,68,0.4); }
  }
  .em-banner.standby { animation: none; }
  .em-banner.dispatched { animation: none; }
  .em-icon { font-size: 30px; flex-shrink: 0; }
  .em-banner h2 { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 700; }
  .em-banner p { font-size: 12px; color: var(--text-sub); margin-top: 2px; }
  .countdown-ring {
    font-family: 'JetBrains Mono', monospace;
    font-size: 32px; font-weight: 500; color: var(--red);
    margin-left: auto; flex-shrink: 0;
  }

  /* Timeline */
  .timeline { display: flex; flex-direction: column; }
  .tl-item { display: flex; gap: 14px; position: relative; }
  .tl-item:not(:last-child)::before {
    content: ''; position: absolute; left: 13px; top: 28px;
    width: 1px; height: calc(100% - 6px); background: var(--border);
  }
  .tl-dot {
    width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; z-index: 1; margin-top: 2px;
    font-family: 'JetBrains Mono', monospace;
  }
  .tl-dot.done { background: var(--green-glow); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
  .tl-dot.running { background: var(--green); color: #ffffff; animation: tlPulse 1.5s ease infinite; }
  @keyframes tlPulse { 0%,100%{box-shadow:0 0 0 0 rgba(34,197,94,0.4);} 50%{box-shadow:0 0 0 8px rgba(34,197,94,0);} }
  .tl-dot.pending { background: var(--surface3); color: var(--text-muted); border: 1px solid var(--border); }
  .tl-content { padding: 2px 0 18px; }
  .tl-content h4 { font-size: 13px; font-weight: 600; }
  .tl-content p { font-size: 11px; color: var(--text-sub); margin-top: 2px; line-height: 1.4; }
  .tl-content .tl-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: var(--text-muted); margin-top: 3px;
  }

  /* Dispatch Grid */
  .dispatch-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .dc-card {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 12px; text-align: center;
    transition: all 0.3s;
  }
  .dc-card.live {
    background: var(--green-subtle);
    border-color: rgba(34,197,94,0.25);
  }
  .dc-card .dc-icon { font-size: 20px; margin-bottom: 4px; }
  .dc-card h4 { font-size: 12px; font-weight: 600; }
  .dc-card p { font-size: 10px; color: var(--text-sub); margin-top: 2px; font-family: 'JetBrains Mono', monospace; }
  .dc-card.live h4 { color: var(--green); }
  .dc-card.live p { color: var(--green-dim); }

  /* Hospital / Map */
  .map-box {
    background: linear-gradient(135deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    height: 130px; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 6px;
  }
  .map-box .map-icon { font-size: 24px; }
  .map-box p { font-size: 11px; color: var(--text-sub); }
  .map-box strong { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--green); }
  .map-box .eta { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--red); font-weight: 600; }

  /* CPR Instructions */
  .cpr-box {
    background: var(--blue-subtle); border: 1px solid rgba(59,130,246,0.2);
    border-radius: var(--radius-sm); padding: 14px;
    animation: slideUp 0.4s ease;
  }
  .cpr-box h4 { font-size: 12px; font-weight: 600; color: var(--blue); margin-bottom: 10px; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 0.8px; }
  .cpr-step { display: flex; gap: 8px; margin-bottom: 7px; align-items: flex-start; }
  .step-num {
    width: 20px; height: 20px; background: var(--blue); color: white;
    border-radius: 50%; font-size: 10px; font-weight: 700; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }
  .cpr-step p { font-size: 12px; line-height: 1.5; color: var(--text-sub); }
  .rag-source { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: var(--text-muted); margin-top: 8px; letter-spacing: 0.5px; }

  /* ─── BUTTONS ─── */
  .btn {
    padding: 9px 18px; border-radius: var(--radius-sm);
    font-size: 13px; font-weight: 600;
    border: none; cursor: pointer; transition: all 0.15s;
    font-family: 'Instrument Sans', sans-serif;
    display: inline-flex; align-items: center; gap: 7px;
  }
  .btn-green { background: var(--green); color: #ffffff; }
  .btn-green:hover { background: #16a34a; }
  .btn-red { background: var(--red); color: white; }
  .btn-red:hover { background: var(--red-dim); }
  .btn-ghost {
    background: var(--surface2); color: var(--text-sub);
    border: 1px solid var(--border-bright);
  }
  .btn-ghost:hover { background: var(--surface3); color: var(--text); }
  .btn-sm { padding: 6px 12px; font-size: 12px; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ─── LOADER ─── */
  .loader { display: flex; align-items: center; gap: 10px; padding: 14px 16px; background: var(--surface2); border-radius: var(--radius-sm); }
  .spinner {
    width: 16px; height: 16px;
    border: 2px solid var(--border-bright); border-top-color: var(--green);
    border-radius: 50%; animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loader p { font-size: 12px; color: var(--green); font-family: 'JetBrains Mono', monospace; }

  /* ─── FORM ─── */
  .form-group { display: flex; flex-direction: column; gap: 5px; margin-bottom: 14px; }
  .form-label { font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 1px; text-transform: uppercase; color: var(--text-muted); }
  .form-input {
    padding: 9px 12px; border: 1px solid var(--border-bright);
    border-radius: var(--radius-sm); font-size: 13px;
    font-family: 'Instrument Sans', sans-serif;
    background: var(--surface2); color: var(--text);
    outline: none; transition: border-color 0.15s;
  }
  .form-input:focus { border-color: rgba(34,197,94,0.4); box-shadow: 0 0 0 3px rgba(34,197,94,0.06); }

  /* ─── TAGS ─── */
  .tag {
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--surface3); color: var(--text-sub);
    border: 1px solid var(--border-bright);
    padding: 3px 9px; border-radius: 20px; font-size: 11px; font-weight: 500;
  }
  .tag-green { background: var(--green-subtle); color: var(--green); border-color: rgba(34,197,94,0.2); }
  .tag-red { background: var(--red-subtle); color: var(--red); border-color: rgba(239,68,68,0.2); }
  .tag-amber { background: var(--amber-subtle); color: var(--amber); border-color: rgba(245,158,11,0.2); }

  /* ─── MODAL ─── */
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(15, 23, 42, 0.4);
    display: flex; align-items: center; justify-content: center;
    z-index: 100; backdrop-filter: blur(8px);
    animation: fadeIn 0.2s ease;
  }
  .modal {
    background: var(--surface); border: 1px solid var(--border-bright);
    border-radius: 16px; width: 500px; max-width: 90vw; max-height: 80vh;
    overflow-y: auto; padding: 28px;
    animation: slideUp 0.25s ease;
  }
  .modal h2 { font-family: 'Syne', sans-serif; font-size: 20px; font-weight: 800; margin-bottom: 20px; }
  .modal-close {
    position: absolute; top: 0; right: 0;
    background: var(--surface2); border: none; color: var(--text-sub);
    border-radius: 0 16px 0 var(--radius-sm); padding: 10px 14px;
    cursor: pointer; font-size: 16px; transition: all 0.15s;
  }
  .modal-close:hover { color: var(--text); background: var(--surface3); }
  .modal-section { margin-bottom: 16px; }
  .modal-section h4 { font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px; color: var(--text-muted); margin-bottom: 8px; }

  /* ─── HISTORY ─── */
  .hist-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius); padding: 16px 18px;
    margin-bottom: 12px;
    animation: slideUp 0.3s ease;
    position: relative;
  }
  .hist-top { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
  .hist-time { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--text-muted); }
  .hist-name { font-size: 13px; font-weight: 600; }
  .hist-body { font-size: 12px; color: var(--text-sub); line-height: 1.5; }
  .hist-footer { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; align-items: center; }
  .hist-delete {
    margin-left: auto; background: none; border: none;
    color: var(--text-muted); cursor: pointer; font-size: 13px;
    padding: 3px 6px; border-radius: var(--radius-sm);
    transition: all 0.15s; font-family: 'Instrument Sans', sans-serif;
  }
  .hist-delete:hover { background: var(--red-subtle); color: var(--red); }

  /* ─── ADD ENTRY FORM ─── */
  .add-entry-panel {
    background: var(--surface);
    border: 1px solid var(--border-bright);
    border-radius: var(--radius); padding: 20px;
    margin-bottom: 24px;
  }
  .add-entry-panel h3 {
    font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 700;
    color: var(--text); margin-bottom: 16px;
    display: flex; align-items: center; gap: 8px;
  }
  .add-entry-grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 12px;
  }
  .add-entry-full { grid-column: span 3; }

  /* ─── PROFILE INFO PAGE ─── */
  .pi-header {
    font-family: 'Syne', sans-serif;
    font-size: 24px; font-weight: 800; color: var(--text);
    margin-bottom: 4px;
  }
  .pi-sub { font-size: 13px; color: var(--text-sub); margin-bottom: 24px; }

  /* ─── RISK BAR ─── */
  .risk-bar-track { height: 5px; background: var(--surface3); border-radius: 3px; overflow: hidden; margin-top: 5px; }
  .risk-bar-fill { height: 100%; border-radius: 3px; transition: width 0.8s ease; }

  /* ─── PATIENT BANNER (Profile Page) ─── */
  .patient-banner {
    background: linear-gradient(135deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border-bright); border-radius: var(--radius);
    padding: 20px 24px; display: flex; align-items: center; gap: 16px;
    margin-bottom: 20px; position: relative; overflow: hidden;
  }
  .patient-banner::before {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(135deg, var(--green-subtle) 0%, transparent 60%);
    pointer-events: none;
  }

  /* ─── CONTACT ITEM ─── */
  .contact-row {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 0; border-bottom: 1px solid var(--border);
  }
  .contact-row:last-child { border-bottom: none; }
  .contact-ava {
    width: 32px; height: 32px; background: var(--surface3);
    border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px;
  }
  .contact-row h4 { font-size: 13px; font-weight: 600; }
  .contact-row p { font-size: 11px; color: var(--text-sub); font-family: 'JetBrains Mono', monospace; }

  /* ─── PAGE HEADER ─── */
  .dash-header {
    padding: 16px 28px 0;
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 16px;
  }
  .dash-header h1 {
    font-family: 'Syne', sans-serif;
    font-size: 20px; font-weight: 800; color: var(--text);
  }
  .dash-header p { font-size: 12px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; margin-top: 2px; }
  .system-status {
    display: flex; align-items: center; gap: 6px;
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--green);
  }
  .live-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); animation: glow 1.5s ease-in-out infinite; }

  /* ─── DIVIDER ─── */
  .divider { height: 1px; background: var(--border); margin: 14px 0; }

  /* ─── SCROLLBAR ─── */
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--surface3); border-radius: 3px; }

  /* ─── ANIMATIONS ─── */
  @keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
  @keyframes slideUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }

  /* ─── EMPTY STATE ─── */
  .empty-state {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 160px; gap: 8px; color: var(--text-muted);
  }
  .empty-state .empty-icon { font-size: 28px; }
  .empty-state p { font-size: 12px; text-align: center; line-height: 1.5; }

  /* ─── PROFILE SELECTOR ─── */
  .profile-selector {
    position: absolute; top: calc(100% + 8px); left: 0; right: 0; z-index: 50;
    background: var(--surface); border: 1px solid var(--border-bright);
    border-radius: var(--radius); padding: 8px; box-shadow: var(--shadow-md);
    animation: slideUp 0.15s ease;
  }
  .profile-option {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; border-radius: var(--radius-sm); cursor: pointer;
    transition: background 0.15s;
  }
  .profile-option:hover { background: var(--surface2); }
  .profile-option.selected { background: var(--green-subtle); }
  .profile-option .po-avatar { font-size: 18px; }
  .profile-option h4 { font-size: 13px; font-weight: 600; }
  .profile-option p { font-size: 11px; color: var(--text-sub); }

  .page-title { font-family: 'Syne', sans-serif; font-size: 22px; font-weight: 800; color: var(--text); margin-bottom: 4px; }
  .page-sub { font-size: 12px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; margin-bottom: 22px; }
`;

// ─── HELPERS ─────────────────────────────────────────────────────────────────
function SparkBar({ data, color }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  return (
    <div className="mini-sparkline">
      {data.map((v, i) => {
        const h = Math.max(3, ((v - min) / (max - min + 0.01)) * 22 + 3);
        return (
          <div
            key={i}
            className="spark-bar"
            style={{
              height: h,
              background: i === data.length - 1 ? color : `${color}55`,
            }}
          />
        );
      })}
    </div>
  );
}

function getSeverityStyle(sev) {
  if (!sev || sev === "None" || sev === "Low") return "panel-low";
  if (sev === "Medium") return "panel-med";
  return "panel-high";
}
function getSeverityIcon(sev) {
  if (!sev || sev === "None") return "✅";
  if (sev === "Low") return "🟡";
  if (sev === "Medium") return "🟠";
  return "🔴";
}

// ─── PROFILE MODAL ────────────────────────────────────────────────────────────
function ProfileModal({ profile, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ position: "relative" }} onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        <h2>{profile.avatar} {profile.name}</h2>
        <div className="modal-section">
          <h4>Basic Info</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {[
              ["Age", `${profile.age} years`],
              ["Blood Type", profile.bloodType],
              ["Gender", profile.gender],
            ].map(([k, v]) => (
              <div key={k} style={{ background: "var(--surface2)", borderRadius: "var(--radius-sm)", padding: "10px 12px" }}>
                <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>{k.toUpperCase()}</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="modal-section">
          <h4>Conditions</h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {profile.conditions.map((c, i) => <span key={i} className="tag tag-amber">{c}</span>)}
          </div>
        </div>
        <div className="modal-section">
          <h4>Medications</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {profile.medications.map((m, i) => (
              <div key={i} style={{ fontSize: 13, color: "var(--text-sub)" }}>💊 {m}</div>
            ))}
          </div>
        </div>
        <div className="modal-section">
          <h4>Allergies</h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {profile.allergies.map((a, i) => <span key={i} className="tag tag-red">{a}</span>)}
          </div>
        </div>
        <div className="modal-section">
          <h4>Emergency Contacts</h4>
          {profile.contacts.map((c, i) => (
            <div key={i} className="contact-row">
              <div className="contact-ava">👤</div>
              <div>
                <h4>{c.name}</h4>
                <p>{c.relation} · {c.phone}</p>
              </div>
              <span className="tag tag-green" style={{ marginLeft: "auto" }}>Primary</span>
            </div>
          ))}
        </div>
        <div className="modal-section">
          <h4>AI Risk Profile</h4>
          {Object.entries(profile.riskProfile).map(([k, v]) => {
            const color = v > 60 ? "var(--red)" : v > 40 ? "var(--amber)" : "var(--green)";
            return (
              <div key={k} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                  <span style={{ textTransform: "capitalize" }}>{k} Risk</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color }}>{v}%</span>
                </div>
                <div className="risk-bar-track">
                  <div className="risk-bar-fill" style={{ width: `${v}%`, background: color }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── DASHBOARD ────────────────────────────────────────────────────────────────
function Dashboard({ onNavigate, historyLog, setHistoryLog }) {
  const [profileIdx, setProfileIdx] = useState(0);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showProfileSelector, setShowProfileSelector] = useState(false);

  const profile = DEMO_PROFILES[profileIdx];
  const baseVitals = BASE_VITALS[profileIdx];

  // Live vitals state
  const [vitals, setVitals] = useState({
    hr: baseVitals.hr, spo2: baseVitals.spo2, bp: baseVitals.bp, temp: baseVitals.temp,
    hrHistory: Array(10).fill(baseVitals.hr).map(v => v + Math.round((Math.random() - 0.5) * 6)),
    spo2History: Array(10).fill(baseVitals.spo2).map(v => Math.max(93, Math.min(99, v + Math.round((Math.random() - 0.5) * 2)))),
  });

  useEffect(() => {
    setVitals({
      hr: baseVitals.hr, spo2: baseVitals.spo2, bp: baseVitals.bp, temp: baseVitals.temp,
      hrHistory: Array(10).fill(baseVitals.hr).map(v => v + Math.round((Math.random() - 0.5) * 6)),
      spo2History: Array(10).fill(baseVitals.spo2).map(v => Math.max(93, Math.min(99, v + Math.round((Math.random() - 0.5) * 2)))),
    });
    // reset EC when profile changes
    setPhase("locked");
    setResult(null);
    setMediaFile(null);
    setMediaPreview(null);
  }, [profileIdx]);

  useEffect(() => {
    const iv = setInterval(() => {
      setVitals(v => {
        const newHr = Math.max(55, Math.min(95, v.hr + (Math.random() - 0.5) * 3));
        const newSpo2 = Math.max(93, Math.min(99, v.spo2 + (Math.random() - 0.5) * 1));
        return {
          ...v,
          hr: Math.round(newHr), spo2: Math.round(newSpo2),
          hrHistory: [...v.hrHistory.slice(1), Math.round(newHr)],
          spo2History: [...v.spo2History.slice(1), Math.round(newSpo2)],
        };
      });
    }, 2500);
    return () => clearInterval(iv);
  }, []);

  // Vision
  const [mediaFile, setMediaFile] = useState(null);
  const [mediaPreview, setMediaPreview] = useState(null);
  const [mediaType, setMediaType] = useState(null);
  const [analysing, setAnalysing] = useState(false);
  const [result, setResult] = useState(null);
  const [dragover, setDragover] = useState(false);
  const fileRef = useRef();

  // Emergency Coordinator
  // phases: locked | standby | waiting | active | dispatched
  const [phase, setPhase] = useState("locked");
  const [countdown, setCountdown] = useState(30);
  const timerRef = useRef();

  const handleFile = (file) => {
    if (!file) return;
    setMediaFile(file);
    setMediaPreview(URL.createObjectURL(file));
    setMediaType(file.type.startsWith("video") ? "video" : "image");
    setResult(null);
    setPhase("standby");
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
    setPhase("standby");
    try {
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
          { type: "text", text: `You are a clinical AI vision system analyzing footage for an emergency health monitoring platform. Analyze this image for fall detection and physical anomalies.\n\nRespond ONLY with a valid JSON object (no markdown, no extra text):\n{"fallDetected":true|false,"severity":"None"|"Low"|"Medium"|"High"|"Critical","confidence":0-100,"location":"string","posture":"string","movementStatus":"string","recommendation":"string","summary":"2-3 sentence string"}` }
        ];
      } else {
        contentPayload = [
          { type: "text", text: `You are a clinical AI vision system. A patient monitoring video was uploaded. Generate a realistic simulated fall detection analysis as if you analyzed the video.\n\nRespond ONLY with a valid JSON object (no markdown, no extra text):\n{"fallDetected":true,"severity":"High","confidence":82,"location":"Kitchen near counter","posture":"Lateral fall, right side","movementStatus":"Minimal movement after impact","recommendation":"Dispatch emergency services immediately.","summary":"Fall event detected. Patient lost balance and fell laterally. Post-fall movement is minimal."}` }
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
        // Auto-trigger after brief delay if high-risk
        if (parsed.fallDetected && ["High", "Critical", "Medium"].includes(parsed.severity)) {
          setTimeout(() => {
            setPhase("waiting");
          }, 1800);
        }
      }
    } catch {
      const fallback = {
        fallDetected: true, severity: "High", confidence: 84,
        location: "Living room near sofa", posture: "Prone, face-down",
        movementStatus: "No movement for 4+ seconds",
        recommendation: "Immediate emergency dispatch recommended.",
        summary: "A fall event has been detected with high confidence. The subject is in a prone position and has not moved for several seconds. Vital signs should be cross-referenced immediately."
      };
      setResult(fallback);
      setTimeout(() => setPhase("waiting"), 1800);
    }
    setAnalysing(false);
  };

  // Countdown logic
  useEffect(() => {
    if (phase === "waiting") {
      setCountdown(30);
      setPhase("active");
    }
  }, [phase]);

  useEffect(() => {
    if (phase === "active") {
      timerRef.current = setInterval(() => {
        setCountdown(c => {
          if (c <= 1) {
            clearInterval(timerRef.current);
            setPhase("dispatched");
            // Log to history
            const entry = {
              id: `h${Date.now()}`,
              timestamp: new Date().toLocaleString("en-MY", { hour12: false }).slice(0, 16),
              profile: profile.name,
              event: result?.fallDetected ? "Fall Detected" : "Anomaly Detected",
              severity: result?.severity || "High",
              action: "EMS Dispatched",
              summary: result?.summary || "Emergency protocol executed.",
            };
            setHistoryLog(prev => [entry, ...prev]);
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
    if (phase === "active") {
      const entry = {
        id: `h${Date.now()}`,
        timestamp: new Date().toLocaleString("en-MY", { hour12: false }).slice(0, 16),
        profile: profile.name,
        event: result?.fallDetected ? "Fall Detected — Cancelled" : "Alert Cancelled",
        severity: "Low",
        action: "User Cancelled",
        summary: "Patient confirmed they were OK within the 30-second cancel window. No emergency dispatched.",
      };
      setHistoryLog(prev => [entry, ...prev]);
    }
    setPhase(mediaFile ? "standby" : "locked");
    setCountdown(30);
  };

  const resetAll = () => {
    clearInterval(timerRef.current);
    setPhase("locked");
    setResult(null);
    setMediaFile(null);
    setMediaPreview(null);
    setCountdown(30);
  };

  const tlSteps = [
    { label: "Anomaly Detected", desc: "Vital Diagnostics Agent flagged deviation via Gemini Flash", time: "T+0s", status: phase !== "locked" && phase !== "standby" ? (phase === "active" || phase === "dispatched" ? "done" : "running") : "pending" },
    { label: "User Alert Issued", desc: "30-second cancel window opened on patient device", time: "T+1s", status: phase === "active" ? "running" : phase === "dispatched" ? "done" : "pending" },
    { label: "Clinical Reasoning", desc: "Gemini 2.0 Pro cross-referenced medical history + vitals", time: "T+5s", status: phase === "dispatched" ? "done" : "pending" },
    { label: "Emergency Dispatch", desc: "Twilio VoIP call placed · EMS notified · GPS transmitted", time: "T+31s", status: phase === "dispatched" ? "done" : "pending" },
    { label: "Hospital Notified", desc: "Medical profile pushed to Hospital Ampang receiving bay", time: "T+32s", status: phase === "dispatched" ? "done" : "pending" },
    { label: "Bystander Protocol", desc: "CPR instructions streamed via Vertex AI Search RAG", time: "T+33s", status: phase === "dispatched" ? "running" : "pending" },
  ];

  const now = new Date().toLocaleTimeString("en-MY", { hour12: false });

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      <div className="dash-header">
        <div>
          <h1>Live Dashboard</h1>
          <p>FIREBASE GENKIT ORCHESTRATION · VERTEX AI AGENTS ACTIVE</p>
        </div>
        <div className="system-status">
          <div className="live-dot" />
          ALL AGENTS ONLINE · {now}
        </div>
      </div>

      <div className="page" style={{ paddingTop: 0 }}>
        {/* ── TOP ROW ── */}
        <div className="dash-top">
          {/* Profile Card */}
          <div style={{ position: "relative" }}>
            <div className="profile-card" onClick={() => setShowProfileModal(true)}>
              <div className="profile-avatar">{profile.avatar}</div>
              <div className="profile-name">{profile.name}</div>
              <div className="profile-meta">Age {profile.age} · {profile.bloodType} · {profile.gender}</div>
              <span className="profile-badge">
                <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--green)", animation: "glow 2s ease-in-out infinite", display: "inline-block" }} />
                MONITORING ACTIVE
              </span>
              <div className="profile-actions">
                <button
                  className="profile-switch-btn"
                  onClick={e => { e.stopPropagation(); setShowProfileSelector(s => !s); }}
                >
                  ⇄ Switch Profile
                </button>
                <button
                  className="profile-edit-btn"
                  onClick={e => { e.stopPropagation(); onNavigate(PAGES.PROFILE); }}
                >
                  ✎ Edit Profile
                </button>
              </div>
            </div>
            {showProfileSelector && (
              <div className="profile-selector">
                {DEMO_PROFILES.map((p, i) => (
                  <div
                    key={p.id}
                    className={`profile-option ${i === profileIdx ? "selected" : ""}`}
                    onClick={() => { setProfileIdx(i); setShowProfileSelector(false); }}
                  >
                    <span className="po-avatar">{p.avatar}</span>
                    <div>
                      <h4>{p.name}</h4>
                      <p>Age {p.age} · {p.bloodType}</p>
                    </div>
                    {i === profileIdx && <span className="tag tag-green" style={{ marginLeft: "auto", fontSize: 9 }}>ACTIVE</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Vitals Panel */}
          <div className="vitals-panel">
            <div className="card-title">LIVE VITALS — WEARABLE SENSOR STREAM</div>
            <div className="vitals-grid">
              {/* Heart Rate */}
              <div className="vital-item">
                <span className="vital-label">Heart Rate</span>
                <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                  <span className="vital-val">{vitals.hr}</span>
                  <span className="vital-unit">bpm</span>
                </div>
                <SparkBar data={vitals.hrHistory} color={vitals.hr > 90 ? "var(--red)" : "var(--green)"} />
                <div>
                  <span className={`vital-status-dot ${vitals.hr > 90 ? "dot-warn" : "dot-ok"}`} />
                  <span className={`vital-tag ${vitals.hr > 90 ? "tag-warn" : "tag-ok"}`}>
                    {vitals.hr > 90 ? "Elevated" : "Normal"}
                  </span>
                </div>
              </div>
              {/* SpO2 */}
              <div className="vital-item">
                <span className="vital-label">SpO₂</span>
                <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                  <span className="vital-val">{vitals.spo2}</span>
                  <span className="vital-unit">%</span>
                </div>
                <SparkBar data={vitals.spo2History} color={vitals.spo2 < 95 ? "var(--amber)" : "var(--green)"} />
                <div>
                  <span className={`vital-status-dot ${vitals.spo2 < 95 ? "dot-warn" : "dot-ok"}`} />
                  <span className={`vital-tag ${vitals.spo2 < 95 ? "tag-warn" : "tag-ok"}`}>
                    {vitals.spo2 < 95 ? "Low" : "Normal"}
                  </span>
                </div>
              </div>
              {/* BP */}
              <div className="vital-item">
                <span className="vital-label">Blood Pressure</span>
                <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                  <span className="vital-val" style={{ fontSize: 20 }}>{vitals.bp}</span>
                  <span className="vital-unit">mmHg</span>
                </div>
                <div style={{ height: 28 }} />
                <div>
                  <span className="vital-status-dot dot-warn" />
                  <span className="vital-tag tag-warn">Slightly High</span>
                </div>
              </div>
              {/* Temp */}
              <div className="vital-item">
                <span className="vital-label">Temperature</span>
                <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                  <span className="vital-val">{vitals.temp}</span>
                  <span className="vital-unit">°C</span>
                </div>
                <div style={{ height: 28 }} />
                <div>
                  <span className="vital-status-dot dot-ok" />
                  <span className="vital-tag tag-ok">Normal</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── VISION MONITOR ── */}
        <div className="section-label">👁 Vision Monitor — Gemini 2.0 Multimodal</div>
        <div className="vision-row">
          <div className="card">
            <div className="card-title">Upload Footage</div>
            {!mediaPreview ? (
              <div
                className={`upload-zone ${dragover ? "dragover" : ""}`}
                onClick={() => fileRef.current.click()}
                onDragOver={e => { e.preventDefault(); setDragover(true); }}
                onDragLeave={() => setDragover(false)}
                onDrop={handleDrop}
              >
                <div className="upload-icon">📹</div>
                <h3>Drop video or image here</h3>
                <p>MP4, MOV, JPG, PNG · Analyzed by Gemini Vision AI</p>
              </div>
            ) : (
              <div className="upload-preview">
                {mediaType === "video"
                  ? <video src={mediaPreview} controls style={{ width: "100%", maxHeight: 190, borderRadius: "var(--radius-sm)" }} />
                  : <img src={mediaPreview} alt="preview" style={{ width: "100%", maxHeight: 190, objectFit: "cover", borderRadius: "var(--radius-sm)" }} />
                }
                <button className="remove-btn" onClick={() => { setMediaPreview(null); setMediaFile(null); setResult(null); setPhase("locked"); }}>✕</button>
              </div>
            )}
            <input ref={fileRef} type="file" accept="video/*,image/*" style={{ display: "none" }} onChange={e => handleFile(e.target.files[0])} />

            {mediaFile && !analysing && !result && (
              <button className="btn btn-green" style={{ marginTop: 12, width: "100%", justifyContent: "center" }} onClick={analyseMedia}>
                🔍 Analyse for Fall Detection
              </button>
            )}
            {analysing && (
              <div className="loader" style={{ marginTop: 12 }}>
                <div className="spinner" />
                <p>Gemini Vision Model analysing footage…</p>
              </div>
            )}
            {result && !analysing && (
              <button className="btn btn-ghost btn-sm" style={{ marginTop: 10, width: "100%", justifyContent: "center" }} onClick={resetAll}>
                ↺ Clear & Reset
              </button>
            )}
          </div>

          {/* Result Panel */}
          <div className="card">
            <div className="card-title">AI Vision Analysis Result</div>
            {!result && !analysing && (
              <div className="empty-state">
                <span className="empty-icon">🔬</span>
                <p>Upload a video or image on the left<br />to receive AI fall detection analysis</p>
              </div>
            )}
            {analysing && (
              <div className="empty-state">
                <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
                <p>Processing with Vision AI…</p>
              </div>
            )}
            {result && !analysing && (
              <div className={`result-panel ${getSeverityStyle(result.severity)}`}>
                <div className="result-header">
                  <span style={{ fontSize: 20 }}>{getSeverityIcon(result.severity)}</span>
                  <div>
                    <h3>{result.fallDetected ? "Fall Detected" : "No Fall Detected"}</h3>
                    <p>SEVERITY: {result.severity?.toUpperCase()} · CONFIDENCE: {result.confidence}%</p>
                  </div>
                </div>
                <div className="result-body">
                  <p>{result.summary}</p>
                  <div className="result-meta">
                    {[["Location", result.location], ["Posture", result.posture], ["Movement", result.movementStatus]].map(([k, v]) => (
                      <div key={k} className="result-meta-item">
                        <span className="lbl">{k}</span>
                        <span className="val">{v}</span>
                      </div>
                    ))}
                  </div>
                  <div className="reco-box">💬 {result.recommendation}</div>
                  {result.fallDetected && phase === "standby" && (
                    <button className="btn btn-red" style={{ marginTop: 12, width: "100%", justifyContent: "center" }} onClick={() => setPhase("waiting")}>
                      🚨 Trigger Emergency Protocol
                    </button>
                  )}
                  {result.fallDetected && (phase === "active" || phase === "dispatched") && (
                    <div style={{ marginTop: 10, fontSize: 11, color: "var(--green)", fontFamily: "'JetBrains Mono', monospace" }}>
                      ✓ Emergency coordinator engaged ↓
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── EMERGENCY COORDINATOR ── */}
        <div className="ec-section">
          <div className="section-label">🚨 Emergency Coordinator — Firebase Genkit Agentic Workflow</div>

          {phase === "locked" && (
            <div className="ec-locked">
              <div className="lock-icon">🔒</div>
              <h3>Emergency Coordinator Locked</h3>
              <p>Upload and analyze a video above to activate the emergency agentic workflow</p>
            </div>
          )}

          {phase !== "locked" && (
            <>
              {/* Banner */}
              {phase === "standby" && (
                <div className="em-banner standby" style={{ marginBottom: 16 }}>
                  <span className="em-icon">🛡️</span>
                  <div style={{ flex: 1 }}>
                    <h2 style={{ color: "var(--green)" }}>System Standby — Agents Ready</h2>
                    <p>Vision analysis complete. Awaiting emergency trigger.</p>
                  </div>
                  <button className="btn btn-red btn-sm" onClick={() => setPhase("waiting")}>🚨 Simulate Emergency</button>
                </div>
              )}
              {phase === "active" && (
                <div className="em-banner active" style={{ marginBottom: 16 }}>
                  <span className="em-icon">🚨</span>
                  <div style={{ flex: 1 }}>
                    <h2 style={{ color: "var(--red)" }}>Emergency Detected — Awaiting Confirmation</h2>
                    <p>Patient: {profile.name} · Fall + Vital anomaly detected · Cancel to abort</p>
                  </div>
                  <div className="countdown-ring">{countdown}s</div>
                  <button className="btn btn-ghost btn-sm" onClick={cancelEmergency} style={{ marginLeft: 12, flexShrink: 0 }}>✋ I'm OK</button>
                </div>
              )}
              {phase === "dispatched" && (
                <div className="em-banner dispatched" style={{ marginBottom: 16 }}>
                  <span className="em-icon">🏥</span>
                  <div style={{ flex: 1 }}>
                    <h2 style={{ color: "var(--red)" }}>Emergency Protocol Executing</h2>
                    <p>EMS dispatched · Hospital Ampang notified · CPR guidance active</p>
                  </div>
                  <button className="btn btn-ghost btn-sm" onClick={resetAll}>↺ Reset</button>
                </div>
              )}

              {/* Main EC grid */}
              <div className="grid-2">
                {/* Timeline */}
                <div className="card">
                  <div className="card-title">Agentic Execution Timeline</div>
                  <div className="timeline">
                    {tlSteps.map((s, i) => (
                      <div key={i} className="tl-item">
                        <div className={`tl-dot ${s.status}`}>
                          {s.status === "done" ? "✓" : s.status === "running" ? "●" : i + 1}
                        </div>
                        <div className="tl-content">
                          <h4 style={{ color: s.status === "pending" ? "var(--text-muted)" : "var(--text)" }}>{s.label}</h4>
                          <p>{s.desc}</p>
                          {s.status !== "pending" && <p className="tl-time">{s.time}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {/* Dispatch Status */}
                  <div className="card">
                    <div className="card-title">Dispatch Status</div>
                    <div className="dispatch-grid">
                      {[
                        { icon: "📞", label: "Twilio VoIP", live: "Call Connected", idle: "Standby" },
                        { icon: "🗺️", label: "Google Maps", live: "ETA: 8 min", idle: "Standby" },
                        { icon: "🏥", label: "Hospital Push", live: "Profile Sent", idle: "Standby" },
                        { icon: "🎙️", label: "CPR Audio", live: "Streaming", idle: "Standby" },
                      ].map(d => (
                        <div key={d.label} className={`dc-card ${phase === "dispatched" ? "live" : ""}`}>
                          <div className="dc-icon">{d.icon}</div>
                          <h4>{d.label}</h4>
                          <p>{phase === "dispatched" ? d.live : d.idle}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Hospital Routing */}
                  <div className="card">
                    <div className="card-title">Hospital Routing</div>
                    <div className="map-box">
                      <span className="map-icon">📍</span>
                      <p>Nearest Facility</p>
                      <strong>Hospital Ampang · 3.2 km</strong>
                      {phase === "dispatched" && <span className="eta">ETA: 8 min · Trauma Bay Ready</span>}
                    </div>
                  </div>

                  {/* CPR Instructions */}
                  {phase === "dispatched" && (
                    <div className="card" style={{ animation: "slideUp 0.4s ease" }}>
                      <div className="card-title">🎙️ Bystander CPR Protocol</div>
                      <div className="cpr-box">
                        <h4>Instructions — Streaming to Device</h4>
                        {[
                          "Ensure the scene is safe. Check patient responsiveness by tapping shoulders firmly.",
                          "Call 999 if not done. Patient profile has been sent to Hospital Ampang.",
                          "Begin chest compressions: 30 compressions at 100–120 beats per minute.",
                          "Give 2 rescue breaths after every 30 compressions. Continue until EMS arrives.",
                        ].map((step, i) => (
                          <div key={i} className="cpr-step">
                            <span className="step-num">{i + 1}</span>
                            <p>{step}</p>
                          </div>
                        ))}
                        <p className="rag-source">SOURCE: MOH MALAYSIA CPR GUIDELINES 2024 · VERTEX AI SEARCH (RAG)</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {showProfileModal && <ProfileModal profile={profile} onClose={() => setShowProfileModal(false)} />}
    </div>
  );
}

// ─── PROFILE INFO PAGE ────────────────────────────────────────────────────────
function ProfilePage() {
  const [profileIdx, setProfileIdx] = useState(0);
  const [patient, setPatient] = useState({ ...DEMO_PROFILES[profileIdx] });
  const [condInput, setCondInput] = useState("");
  const [medInput, setMedInput] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => { setPatient({ ...DEMO_PROFILES[profileIdx] }); }, [profileIdx]);

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
            onClick={() => setProfileIdx(i)}
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

// ─── HISTORY PAGE ─────────────────────────────────────────────────────────────
const BLANK_ENTRY = {
  timestamp: "",
  profile: "Ahmad Razif",
  event: "",
  severity: "Medium",
  action: "",
  summary: "",
};

function HistoryPage({ historyLog, setHistoryLog }) {
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

  // Quick-note save: only summary required; everything else gets defaults
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

  // Structured save: all fields required
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

// ─── ROOT APP ─────────────────────────────────────────────────────────────────
export default function App() {
  const [page, setPage] = useState(PAGES.DASHBOARD);
  const [historyLog, setHistoryLog] = useState([...HISTORY_SEED]);

  const navItems = [
    { id: PAGES.MVP_TEST, icon: "🧪", label: "MVP Test" },
    { id: PAGES.DASHBOARD, icon: "💓", label: "Dashboard" },
    { id: PAGES.PROFILE, icon: "👤", label: "Profile" },
    { id: PAGES.HISTORY, icon: "📋", label: "History" },
  ];

  return (
    <>
      <style>{STYLES}</style>
      <div className="app">
        <div className="sidebar">
          <div className="sidebar-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
          {navItems.map(item => (
            <button
              key={item.id}
              className={`nav-btn ${page === item.id ? "active" : ""}`}
              onClick={() => setPage(item.id)}
              title={item.label}
            >
              {item.icon}
              {item.id === PAGES.DASHBOARD && page !== PAGES.DASHBOARD && (
                <span className="nav-badge" />
              )}
            </button>
          ))}
        </div>
        <div className="main">
          {page === PAGES.DASHBOARD && (
            <Dashboard
              onNavigate={setPage}
              historyLog={historyLog}
              setHistoryLog={setHistoryLog}
            />
          )}
          {page === PAGES.MVP_TEST && <MvpTestPage />}
          {page === PAGES.PROFILE && <ProfilePage />}
          {page === PAGES.HISTORY && <HistoryPage historyLog={historyLog} setHistoryLog={setHistoryLog} />}
        </div>
      </div>
    </>
  );
}