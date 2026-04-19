import { useEffect, useState } from "react";

const EMPTY_PROFILE = {
  patientId: "",
  name: "",
  age: "",
  bloodType: "Unknown",
  gender: "Unspecified",
  primaryLanguage: "en",
  address: "",
  profileNote: "",
  bloodThinners: false,
  mobilitySupport: false,
  conditions: [],
  medications: [],
  allergies: [],
  contacts: [],
};

export default function ProfilePage({
  patientProfiles,
  currentPatientId,
  onSaveProfile,
}) {
  const selectedProfile = patientProfiles.find((item) => item.patientId === currentPatientId) || EMPTY_PROFILE;
  const [patient, setPatient] = useState(selectedProfile);
  const [condInput, setCondInput] = useState("");
  const [medInput, setMedInput] = useState("");
  const [contactForm, setContactForm] = useState({ name: "", relation: "", phone: "" });
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

  const addContact = () => {
    if (!contactForm.name || !contactForm.phone) return;
    setPatient((current) => ({
      ...current,
      contacts: [...(current.contacts || []), { ...contactForm }],
    }));
    setContactForm({ name: "", relation: "", phone: "" });
  };

  const removeContact = (index) => {
    setPatient((current) => ({
      ...current,
      contacts: current.contacts.filter((_, i) => i !== index),
    }));
  };

  return (
    <div className="page">
      <p className="page-title">Profile Information</p>
      <p className="page-sub">VIEW · EDIT · SAVE PATIENT HEALTH PROFILE</p>

      <div className="patient-banner" style={{ padding: "12px 20px", marginBottom: 16 }}>
        <div style={{ fontSize: 24, opacity: 0.8 }}>👤</div>
        <div>
          <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 16, fontWeight: 800 }}>{patient.name || "New Profile"}</div>
          <div style={{ fontSize: 11, color: "var(--text-sub)", marginTop: 2 }}>
            {patient.age ? `Age ${patient.age}` : "No Age Set"} · {patient.bloodType} · {patient.gender}
          </div>
        </div>
        
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          {saveError && <span style={{ color: "var(--red-dim)", fontSize: 12 }}>{saveError}</span>}
          <button className="btn btn-ghost btn-sm" onClick={() => setPatient(selectedProfile)} style={{ height: 32 }}>Reset</button>
          <button
            className="btn btn-green btn-sm"
            style={{ height: 32, minWidth: 100 }}
            onClick={async () => {
              setSaveError("");
              try {
                await onSaveProfile(patient);
                setSaved(true);
                setTimeout(() => setSaved(false), 2500);
              } catch (error) {
                setSaveError(error.message || "Error");
              }
            }}
          >
            {saved ? "✓ Saved" : "Save Profile"}
          </button>
        </div>
      </div>

      <div className="grid-2" style={{ gap: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ padding: 16 }}>
            <div className="card-title">Basic Information</div>
            <div className="form-group" style={{ marginBottom: 10 }}>
              <label className="form-label">Full Name</label>
              <input className="form-input" value={patient.name} onChange={(event) => setPatient((current) => ({ ...current, name: event.target.value }))} />
            </div>
            <div className="grid-2" style={{ gap: 10, marginBottom: 10 }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Age</label>
                <input className="form-input" type="number" value={patient.age} onChange={(event) => setPatient((current) => ({ ...current, age: event.target.value }))} />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Primary Language</label>
                <input className="form-input" value={patient.primaryLanguage} onChange={(event) => setPatient((current) => ({ ...current, primaryLanguage: event.target.value }))} />
              </div>
            </div>
            <div className="grid-2" style={{ gap: 10, marginBottom: 10 }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Blood Type</label>
                <select className="form-input" value={patient.bloodType} onChange={(event) => setPatient((current) => ({ ...current, bloodType: event.target.value }))}>
                  {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"].map((type) => (
                    <option key={type}>{type}</option>
                  ))}
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Gender</label>
                <select className="form-input" value={patient.gender} onChange={(event) => setPatient((current) => ({ ...current, gender: event.target.value }))}>
                  {["Female", "Male", "Non-binary", "Prefer not to say", "Unspecified"].map((option) => (
                    <option key={option}>{option}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-group" style={{ marginBottom: 10 }}>
              <label className="form-label">Residential Address</label>
              <textarea
                className="form-input"
                style={{ minHeight: 40, padding: "6px 10px", lineHeight: 1.4, fontSize: 11 }}
                value={patient.address}
                onChange={(event) => setPatient((current) => ({ ...current, address: event.target.value }))}
                placeholder="Full address..."
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Allergies</label>
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
            <div className="divider" style={{ margin: "12px 0" }} />
            <div className="card-title">Clinical Indicators</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <label className="custom-checkbox-container">
                <input
                  type="checkbox"
                  style={{ display: "none" }}
                  checked={patient.bloodThinners}
                  onChange={(e) => setPatient(prev => ({ ...prev, bloodThinners: e.target.checked }))}
                />
                <div className="custom-checkbox-box"></div>
                <div className="custom-checkbox-label">
                  <div style={{ fontSize: 11, fontWeight: 700 }}>Blood Thinners</div>
                  <div style={{ fontSize: 10, color: "var(--text-sub)" }}>Anticoagulant usage (e.g. Warfarin)</div>
                </div>
              </label>
              
              <label className="custom-checkbox-container">
                <input
                  type="checkbox"
                  style={{ display: "none" }}
                  checked={patient.mobilitySupport}
                  onChange={(e) => setPatient(prev => ({ ...prev, mobilitySupport: e.target.checked }))}
                />
                <div className="custom-checkbox-box"></div>
                <div className="custom-checkbox-label">
                  <div style={{ fontSize: 11, fontWeight: 700 }}>Mobility Support</div>
                  <div style={{ fontSize: 10, color: "var(--text-sub)" }}>Physical aids required (e.g. walker)</div>
                </div>
              </label>
            </div>
          </div>

          <div className="card" style={{ padding: 16, position: "relative" }}>
            <div className="card-title" style={{ marginBottom: 12 }}>Autonomous AI Risk Assessment</div>
            <div className="blur-teaser-container">
              <div className="blur-teaser-content">      
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontWeight: 600 }}>
                      <span>Physical Stability</span>
                      <span>82%</span>
                    </div>
                    <div className="risk-mini-bar">
                      <div className="risk-mini-fill" style={{ width: '82%', background: 'var(--green)' }}></div>
                    </div>
                  </div>
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontWeight: 600 }}>
                      <span>Medication Safety</span>
                      <span>64%</span>
                    </div>
                    <div className="risk-mini-bar">
                      <div className="risk-mini-fill" style={{ width: '64%', background: 'var(--amber)' }}></div>
                    </div>
                  </div>
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontWeight: 600 }}>
                      <span>Environmental Risk</span>
                      <span>50%</span>
                    </div>
                    <div className="risk-mini-bar">
                      <div className="risk-mini-fill" style={{ width: '50%', background: 'var(--red)' }}></div>
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 12, padding: 8, background: "var(--surface2)", borderRadius: 8, fontSize: 11, color: "var(--text-sub)", lineHeight: 1.4 }}>
                  AI Observation: Patient demonstrates slight postural sway during transitions.
                </div>
              </div>
              <div className="blur-teaser-overlay">
                <div style={{ fontSize: 11, fontWeight: 800, color: "var(--text)", marginBottom: 4 }}>Coming Soon</div>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ padding: 16 }}>
            <div className="card-title">Medical History</div>
            <div className="form-label" style={{ marginBottom: 8 }}>Pre-existing Conditions</div>
            <div style={{ marginBottom: 10 }}>
              {patient.conditions.map((condition, index) => (
                <div key={`${condition}-${index}`} className="profile-record-row">
                  <div className="profile-record-dot amber"></div>
                  <div className="profile-record-content">{condition}</div>
                  <button
                    className="profile-record-remove"
                    onClick={() =>
                      setPatient((current) => ({
                        ...current,
                        conditions: current.conditions.filter((_, currentIndex) => currentIndex !== index),
                      }))
                    }
                  >
                    ×
                  </button>
                </div>
              ))}
              {patient.conditions.length === 0 && (
                <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic", marginBottom: 8 }}>No conditions listed</div>
              )}
            </div>
            <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
              <input className="form-input" placeholder="Add condition..." value={condInput} onChange={(event) => setCondInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && addCondition()} style={{ flex: 1, height: 32, fontSize: 12 }} />
              <button className="btn btn-ghost btn-sm" style={{ height: 32 }} onClick={addCondition}>Add</button>
            </div>

            <div className="form-label" style={{ marginBottom: 8 }}>Active Medications</div>
            <div style={{ marginBottom: 10 }}>
              {patient.medications.map((medication, index) => (
                <div key={`${medication}-${index}`} className="profile-record-row">
                  <div className="profile-record-dot blue"></div>
                  <div className="profile-record-content">{medication}</div>
                  <button
                    className="profile-record-remove"
                    onClick={() =>
                      setPatient((current) => ({
                        ...current,
                        medications: current.medications.filter((_, currentIndex) => currentIndex !== index),
                      }))
                    }
                  >
                    ×
                  </button>
                </div>
              ))}
              {patient.medications.length === 0 && (
                <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic", marginBottom: 8 }}>No medications listed</div>
              )}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <input className="form-input" placeholder="Add medication..." value={medInput} onChange={(event) => setMedInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && addMed()} style={{ flex: 1, height: 32, fontSize: 12 }} />
              <button className="btn btn-ghost btn-sm" style={{ height: 32 }} onClick={addMed}>Add</button>
            </div>
          </div>

          <div className="card" style={{ padding: 16 }}>
            <div className="card-title">Emergency Contacts</div>
            <div style={{ marginBottom: 12 }}>
              {(patient.contacts || []).map((contact, index) => (
                <div key={`${contact.phone}-${index}`} className="profile-record-row">
                  <div className="profile-record-dot green"></div>
                  <div className="profile-record-content">
                    <div style={{ fontSize: 11, fontWeight: 700 }}>{contact.name}</div>
                    <div style={{ fontSize: 10, color: "var(--text-sub)", marginTop: 1 }}>{contact.relation} · {contact.phone}</div>
                  </div>
                  <button
                    className="profile-record-remove"
                    onClick={() => removeContact(index)}
                  >
                    ×
                  </button>
                </div>
              ))}
              {(patient.contacts || []).length === 0 && (
                <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic", marginBottom: 8 }}>No contacts added</div>
              )}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 6 }}>
              <input className="form-input" style={{ height: 32, fontSize: 12 }} placeholder="Name" value={contactForm.name} onChange={(e) => setContactForm(prev => ({ ...prev, name: e.target.value }))} />
              <input className="form-input" style={{ height: 32, fontSize: 12 }} placeholder="Relation" value={contactForm.relation} onChange={(e) => setContactForm(prev => ({ ...prev, relation: e.target.value }))} />
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <input className="form-input" style={{ flex: 1, height: 32, fontSize: 12 }} placeholder="Phone" value={contactForm.phone} onChange={(e) => setContactForm(prev => ({ ...prev, phone: e.target.value }))} onKeyDown={(e) => e.key === "Enter" && addContact()} />
              <button className="btn btn-green btn-sm" style={{ height: 32 }} onClick={addContact}>Add Contact</button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
