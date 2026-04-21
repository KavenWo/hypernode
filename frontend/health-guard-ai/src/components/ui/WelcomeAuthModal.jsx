export default function WelcomeAuthModal({
  status,
  error,
  onContinue,
}) {
  const isBusy = status === "signing_in";

  return (
    <div className="welcome-auth-overlay">
      <div className="welcome-auth-card">
        <h2>Welcome to ElderGuard AI</h2>
        <p>
          Securely access the health dashboard to monitor vitals, 
          manage patient profiles, and coordinate emergency responses.
        </p>

        <p>
          <br/>From Hypernode
        </p>


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
