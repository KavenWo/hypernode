export default function DashboardProfileCard({
  profile,
  patientProfiles,
  currentPatientId,
  showProfileSelector,
  setShowProfileModal,
  setShowProfileSelector,
  onSelectPatient,
  onNavigateToProfile,
}) {
  return (
    <div style={{ position: "relative" }}>
      <div className="profile-card" onClick={() => setShowProfileModal(true)}>
        <div className="profile-avatar">{profile.avatar}</div>
        <div className="profile-name">{profile.name}</div>
        <div className="profile-meta">
          Age {profile.age} · {profile.bloodType} · {profile.gender}
        </div>
        <div style={{ fontSize: 12, color: "var(--text-sub)", lineHeight: 1.6, marginBottom: 14 }}>
          {profile.profileNote}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
          <span className="tag">{profile.scenarioLabel}</span>
          <span className={`tag ${profile.mobilitySupport ? "tag-amber" : ""}`}>
            {profile.mobilitySupport ? "Mobility support" : "Independent walking"}
          </span>
          <span className={`tag ${profile.bloodThinners ? "tag-red" : ""}`}>
            {profile.bloodThinners ? "Blood thinners" : "No blood thinners"}
          </span>
        </div>
        <span className="profile-badge">
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
        <div className="profile-actions">
          <button
            className="profile-switch-btn"
            onClick={(event) => {
              event.stopPropagation();
              setShowProfileSelector((current) => !current);
            }}
          >
            Switch Profile
          </button>
          <button
            className="profile-edit-btn"
            onClick={(event) => {
              event.stopPropagation();
              onNavigateToProfile();
            }}
          >
            Edit Profile
          </button>
        </div>
      </div>
      {patientProfiles.length > 1 && showProfileSelector ? (
        <div className="profile-selector" style={{ marginTop: 10 }}>
          {patientProfiles.map((item) => (
            <div
              key={item.patientId}
              className={`profile-option ${item.patientId === currentPatientId ? "selected" : ""}`}
              onClick={() => {
                onSelectPatient(item.patientId);
                setShowProfileSelector(false);
              }}
            >
              <span className="po-avatar">{item.avatar}</span>
              <div>
                <h4>{item.name}</h4>
                <p>{item.scenarioLabel}</p>
              </div>
              {item.patientId === currentPatientId ? (
                <span className="tag tag-green" style={{ marginLeft: "auto", fontSize: 9 }}>
                  ACTIVE
                </span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
