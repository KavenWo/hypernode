export default function DashboardProfileCard({
  profile,
  setShowProfileModal,
  onNavigateToProfile,
}) {
  return (
    <div style={{ position: "relative" }}>
      <div className="profile-card">
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 12 }}>
          <div className="profile-avatar" style={{ marginBottom: 0, width: 44, height: 44, fontSize: 22, flexShrink: 0 }}>
            {profile.avatar}
          </div>
          <div className="profile-name" style={{ fontSize: 16, marginBottom: 0, lineHeight: 1 }}>
            {profile.name}
          </div>
        </div>

        <div className="profile-meta" style={{ marginBottom: 16 }}>
          Age {profile.age} · {profile.bloodType} · {profile.gender}
        </div>

        <div style={{ fontSize: 11, color: "var(--text-sub)", lineHeight: 1.5, marginBottom: 16, opacity: 0.9 }}>
          {profile.profileNote}
        </div>

        <div className="profile-actions" style={{ flexDirection: "column", gap: 8 }}>
          <button
            className="btn btn-ghost btn-sm"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={(event) => {
              event.stopPropagation();
              setShowProfileModal(true);
            }}
          >
            View Profile Details
          </button>
          <button
            className="profile-edit-btn"
            style={{ width: "100%" }}
            onClick={(event) => {
              event.stopPropagation();
              onNavigateToProfile();
            }}
          >
            Edit Profile
          </button>
        </div>
      </div>
    </div>
  );
}
