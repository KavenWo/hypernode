export default function WelcomeAuthModal({
  status,
  error,
  onContinue,
}) {
  const isBusy = status === "signing_in";

  return (
    <div className="welcome-auth-overlay">
      <div className="welcome-auth-card">
        <div className="welcome-auth-kicker">Clinical Workspace Setup</div>
        <h2>Welcome to HealthGuard AI</h2>
        <p>
          Securely access your autonomous health dashboard to monitor vitals, 
          manage patient profiles, and coordinate emergency responses.
        </p>

        <div className="welcome-auth-points">
          <div className="welcome-auth-point">Anonymous access ensures data privacy and session persistence.</div>
          <div className="welcome-auth-point">No manual registration or password required for this session.</div>
        </div>

        {error ? <div className="welcome-auth-error">{error}</div> : null}

        <div className="welcome-auth-actions">
          <button className="btn btn-green" onClick={onContinue} disabled={isBusy} style={{ minWidth: "120px", display: "flex", justifyContent: "center" }}>
            {isBusy ? "Loading..." : "Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
