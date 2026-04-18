export default function WelcomeAuthModal({
  status,
  error,
  onContinue,
}) {
  const isBusy = status === "signing_in";

  return (
    <div className="welcome-auth-overlay">
      <div className="welcome-auth-card">
        <div className="welcome-auth-kicker">Secure Session Setup</div>
        <h2>Continue with anonymous session access</h2>
        <p>
          We create a Firebase anonymous login for this browser so your profile,
          incident history, and emergency runs stay linked to the same session.
        </p>

        <div className="welcome-auth-points">
          <div className="welcome-auth-point">Anonymous auth lets Firestore identify this session safely.</div>
          <div className="welcome-auth-point">Firebase persistence should keep the same anonymous user after reloads.</div>
          <div className="welcome-auth-point">No name, email, or password is required for this step.</div>
        </div>

        {error ? <div className="welcome-auth-error">{error}</div> : null}

        <div className="welcome-auth-actions">
          <button className="btn btn-green" onClick={onContinue} disabled={isBusy}>
            {isBusy ? "Connecting..." : "Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
