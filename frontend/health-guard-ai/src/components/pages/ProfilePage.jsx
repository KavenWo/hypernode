import { useEffect, useState } from "react";

const EMPTY_PROFILE = {
  patientId: "",
  name: "",
  age: "",
  bloodType: "Unknown",
  gender: "Unspecified",
  avatar: "🙂",
  profileNote: "",
  conditions: [],
  medications: [],
  allergies: [],
  contacts: [],
  riskProfile: { cardiovascular: 0, fall: 0, respiratory: 0 },
};

export default function ProfilePage({
  patientProfiles,
  currentPatientId,
  onSelectPatient,
  onSaveProfile,
}) {
  const selectedProfile = patientProfiles.find((item) => item.patientId === currentPatientId) || EMPTY_PROFILE;
  const [patient, setPatient] = useState(selectedProfile);
  const [condInput, setCondInput] = useState("");
  const [medInput, setMedInput] = useState("");
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    setPatient(selectedProfile);
  }, [selectedProfile]);

  const addCondition = () => {
    if (!condInput.trim()) return;
    setPatient((current) => ({ ...current, conditions: [...current.conditions, condInput.trim()] }));
    setCondInput("");
  };

  const addMed = () => {
    if (!medInput.trim()) return;
    setPatient((current) => ({ ...current, medications: [...current.medications, medInput.trim()] }));
    setMedInput("");
  };

  return (
    <div className="page">
      <p className="page-title">Profile Information</p>
      <p className="page-sub">VIEW · EDIT · SAVE PATIENT HEALTH PROFILE</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {patientProfiles.map((profile) => (
          <button
            key={profile.patientId}
            onClick={() => onSelectPatient(profile.patientId)}
            className="btn btn-sm"
            style={{
              background: profile.patientId === currentPatientId ? "var(--green-subtle)" : "var(--surface2)",
              color: profile.patientId === currentPatientId ? "var(--green)" : "var(--text-sub)",
              border:
                profile.patientId === currentPatientId
                  ? "1px solid rgba(34,197,94,0.25)"
                  : "1px solid var(--border-bright)",
            }}
          >
            {profile.avatar} {profile.name}
          </button>
        ))}
      </div>

      <div className="patient-banner">
        <div style={{ fontSize: 40 }}>{patient.avatar}</div>
        <div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 22, fontWeight: 800 }}>{patient.name}</div>
          <div style={{ fontSize: 13, color: "var(--text-sub)", marginTop: 3 }}>
            Age {patient.age} · {patient.bloodType} · {patient.gender}
          </div>
        </div>
        <span className="profile-badge" style={{ marginLeft: "auto" }}>
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "var(--green)",
              animation: "glow 2s ease-in-out infinite",
              display: "inline-block",
            }}
          />
          MONITORING ACTIVE
        </span>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-title">Basic Information</div>
          <div className="form-group">
            <label className="form-label">Full Name</label>
            <input className="form-input" value={patient.name} onChange={(event) => setPatient((current) => ({ ...current, name: event.target.value }))} />
          </div>
          <div className="grid-2" style={{ gap: 10 }}>
            <div className="form-group">
              <label className="form-label">Age</label>
              <input className="form-input" type="number" value={patient.age} onChange={(event) => setPatient((current) => ({ ...current, age: event.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Blood Type</label>
              <select className="form-input" value={patient.bloodType} onChange={(event) => setPatient((current) => ({ ...current, bloodType: event.target.value }))}>
                {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"].map((type) => (
                  <option key={type}>{type}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Allergies (comma-separated)</label>
            <input
              className="form-input"
              value={patient.allergies.join(", ")}
              onChange={(event) =>
                setPatient((current) => ({
                  ...current,
                  allergies: event.target.value.split(",").map((item) => item.trim()).filter(Boolean),
                }))
              }
            />
          </div>
        </div>

        <div className="card">
          <div className="card-title">Medical Conditions</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
            {patient.conditions.map((condition, index) => (
              <span
                key={`${condition}-${index}`}
                className="tag tag-amber"
                style={{ cursor: "pointer" }}
                onClick={() =>
                  setPatient((current) => ({
                    ...current,
                    conditions: current.conditions.filter((_, currentIndex) => currentIndex !== index),
                  }))
                }
              >
                {condition} <span style={{ opacity: 0.6 }}>x</span>
              </span>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input className="form-input" placeholder="Add condition..." value={condInput} onChange={(event) => setCondInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && addCondition()} style={{ flex: 1 }} />
            <button className="btn btn-ghost btn-sm" onClick={addCondition}>Add</button>
          </div>
          <div className="divider" />
          <div className="card-title">Current Medications</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 10 }}>
            {patient.medications.map((medication, index) => (
              <div key={`${medication}-${index}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13 }}>Medication: {medication}</span>
                <button
                  className="btn btn-sm"
                  style={{ background: "none", color: "var(--text-muted)", padding: "2px 8px" }}
                  onClick={() =>
                    setPatient((current) => ({
                      ...current,
                      medications: current.medications.filter((_, currentIndex) => currentIndex !== index),
                    }))
                  }
                >
                  x
                </button>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="form-input" placeholder="Add medication..." value={medInput} onChange={(event) => setMedInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && addMed()} style={{ flex: 1 }} />
            <button className="btn btn-ghost btn-sm" onClick={addMed}>Add</button>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Emergency Contacts</div>
          {patient.contacts.map((contact, index) => (
            <div key={`${contact.phone}-${index}`} className="contact-row">
              <div className="contact-ava">Contact</div>
              <div style={{ flex: 1 }}>
                <h4>{contact.name}</h4>
                <p>{contact.relation} · {contact.phone}</p>
              </div>
              <span className="tag tag-green">Primary</span>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-title">AI Risk Assessment</div>
          {Object.entries(patient.riskProfile).map(([key, value]) => {
            const color = value > 60 ? "var(--red)" : value > 40 ? "var(--amber)" : "var(--green)";
            return (
              <div key={key} style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                  <span style={{ textTransform: "capitalize" }}>{key} Risk</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color }}>{value}%</span>
                </div>
                <div className="risk-bar-track">
                  <div className="risk-bar-fill" style={{ width: `${value}%`, background: color }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
        {saveError ? <span style={{ marginRight: "auto", color: "var(--red-dim)", fontSize: 13 }}>{saveError}</span> : null}
        <button className="btn btn-ghost" onClick={() => setPatient(selectedProfile)}>Reset</button>
        <button
          className="btn btn-green"
          onClick={async () => {
            setSaveError("");
            try {
              await onSaveProfile(patient);
              setSaved(true);
              setTimeout(() => setSaved(false), 2500);
            } catch (error) {
              setSaveError(error.message || "Unable to save profile.");
            }
          }}
        >
          {saved ? "Saved" : "Save Profile"}
        </button>
      </div>
    </div>
  );
}
