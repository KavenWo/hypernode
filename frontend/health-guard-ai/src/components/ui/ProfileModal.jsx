export default function ProfileModal({ profile, onClose }) {
  const conditions = profile.conditions?.length ? profile.conditions : ["None recorded"];
  const medications = profile.medications?.length ? profile.medications : ["None recorded"];
  const allergies = profile.allergies?.length ? profile.allergies : ["None recorded"];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ position: "relative" }} onClick={(event) => event.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>x</button>
        <h2>{profile.avatar} {profile.name}</h2>
        <div className="modal-section">
          <h4>Basic Info</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {[
              ["Age", `${profile.age} years`],
              ["Blood Type", profile.bloodType],
              ["Gender", profile.gender],
            ].map(([key, value]) => (
              <div key={key} style={{ background: "var(--surface2)", borderRadius: "var(--radius-sm)", padding: "10px 12px" }}>
                <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>
                  {key.toUpperCase()}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{value}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="modal-section">
          <h4>Conditions</h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {conditions.map((condition, index) => <span key={index} className="tag tag-amber">{condition}</span>)}
          </div>
        </div>
        <div className="modal-section">
          <h4>Medications</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {medications.map((medication, index) => (
              <div key={index} style={{ fontSize: 13, color: "var(--text-sub)" }}>Medication: {medication}</div>
            ))}
          </div>
        </div>
        <div className="modal-section">
          <h4>Allergies</h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {allergies.map((allergy, index) => <span key={index} className="tag tag-red">{allergy}</span>)}
          </div>
        </div>
        <div className="modal-section">
          <h4>Emergency Contacts</h4>
          {profile.contacts.map((contact, index) => (
            <div key={index} className="contact-row">
              <div className="contact-ava">Contact</div>
              <div>
                <h4>{contact.name}</h4>
                <p>{contact.relation} · {contact.phone}</p>
              </div>
              <span className="tag tag-green" style={{ marginLeft: "auto" }}>Primary</span>
            </div>
          ))}
        </div>
        <div className="modal-section">
          <h4>AI Risk Profile</h4>
          {Object.entries(profile.riskProfile).map(([key, value]) => {
            const color = value > 60 ? "var(--red)" : value > 40 ? "var(--amber)" : "var(--green)";
            return (
              <div key={key} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
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
    </div>
  );
}
