import { useEffect, useRef, useState } from "react";
import Sidebar from "./components/layout/Sidebar";
import Dashboard from "./components/pages/Dashboard";
import ProfilePage from "./components/pages/ProfilePage";
import HistoryPage from "./components/pages/HistoryPage";
import WelcomeAuthModal from "./components/ui/WelcomeAuthModal.jsx";
import { PAGES } from "./constants/pages";
import { fetchSessionIncidents, fetchSessionPatients, normalizePatientProfile, saveSessionPatient } from "./lib/patientApi.js";
import { resolveExistingAnonymousSession, bootstrapAnonymousSession } from "./lib/sessionBootstrap.js";

import "./styles/index.css";

export default function App() {
  const [page, setPage] = useState(PAGES.DASHBOARD);
  const [incidentLog, setIncidentLog] = useState([]);
  const [authStatus, setAuthStatus] = useState("checking");
  const [authError, setAuthError] = useState("");
  const [authSession, setAuthSession] = useState(null);
  const [dataStatus, setDataStatus] = useState("idle"); // 'idle' | 'loading' | 'ready' | 'error'
  const [isSyncing, setIsSyncing] = useState(false);
  const [patientProfiles, setPatientProfiles] = useState([]);
  const sessionRestoreStartedRef = useRef(false);
  const currentPatientId = patientProfiles[0]?.patientId || "";

  useEffect(() => {
    let cancelled = false;

    if (sessionRestoreStartedRef.current) {
      return () => {
        cancelled = true;
      };
    }
    sessionRestoreStartedRef.current = true;

    async function hydrateExistingSession() {
      // On reload we first try to recover the anonymous Firebase-backed session
      // so the user can resume the same patient workspace and incident history
      // without going through the welcome modal again.
      try {
        const session = await resolveExistingAnonymousSession();
        if (cancelled) {
          return;
        }
        if (session) {
          setAuthSession(session);
          if (session.patients?.length) {
            const normalized = session.patients.map(normalizePatientProfile);
            setPatientProfiles(normalized);
          }
          setAuthStatus("ready");
          setAuthError("");
          return;
        }
        setAuthStatus("awaiting_user");
      } catch (error) {
        if (cancelled) {
          return;
        }
        setAuthStatus("awaiting_user");
        setAuthError(error.message || "Unable to restore the anonymous session.");
      }
    }

    hydrateExistingSession();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleWelcomeContinue() {
    // The welcome flow intentionally moves the UI to "ready" as soon as a
    // session exists, then lets slower patient/history hydration finish in the
    // background so the demo feels immediate.
    setAuthStatus("signing_in");
    setAuthError("");
    setDataStatus("loading");
    setIsSyncing(true);
    try {
      const session = await bootstrapAnonymousSession(null);
      // Fast-track the UI to ready state as soon as we have a session
      setAuthSession(session);
      setAuthStatus("ready");

      if (session.patients?.length) {
        const normalized = session.patients.map(normalizePatientProfile);
        setPatientProfiles(normalized);
        setDataStatus("ready");
      }
    } catch (error) {
      setAuthStatus("awaiting_user");
      setDataStatus("error");
      setIsSyncing(false);
      setAuthError(error.message || "Unable to start the anonymous session.");
    }
  }

  const showWelcomeModal = authStatus !== "ready";

  useEffect(() => {
    let isMounted = true;

    async function hydrateSessionData() {
      // Session hydration fetches the durable patient list and incident history
      // after auth succeeds. The dashboard itself stays mounted so its local
      // simulation state is not lost when switching pages.
      const sessionUid = authSession?.backendSession?.session_uid;
      if (!sessionUid) return;

      const hasImmediatePatients = patientProfiles.length > 0;
      setDataStatus(hasImmediatePatients ? "ready" : "loading");
      setIsSyncing(true);

      try {
        const [patients, history] = await Promise.all([
          fetchSessionPatients(sessionUid),
          fetchSessionIncidents(sessionUid),
        ]);

        if (!isMounted) return;

        if (patients.length > 0) {
          setPatientProfiles(patients);
        }
        setIncidentLog(history);
        setDataStatus("ready");
        setIsSyncing(false);
      } catch (err) {
        console.error("Session hydration failed:", err);
        if (!isMounted) return;
        setIsSyncing(false);
        setDataStatus(hasImmediatePatients ? "ready" : "error");
      }
    }

    hydrateSessionData();

    return () => {
      isMounted = false;
    };
  }, [authSession]);

  return (
    <>
      <div className="app">
        <Sidebar page={page} setPage={setPage} />
        <div className="main">
          {isSyncing && !showWelcomeModal && (
            <div className="app-hydration-toast">
              <div className="toast-spinner"></div>
              <div className="toast-content">
                <div className="toast-title">Syncing Clinical Data</div>
                <div className="toast-sub">Updating patient profiles...</div>
              </div>
            </div>
          )}
          {/* Keep the dashboard mounted between page switches so active session
              sync, local timers, and demo state are not torn down. */}
          <div style={{ display: page === PAGES.DASHBOARD ? "contents" : "none" }}>
            <Dashboard
              isActive={page === PAGES.DASHBOARD}
              onNavigate={setPage}
              incidentLog={incidentLog}
              setIncidentLog={setIncidentLog}
              authSession={authSession}
              patientProfiles={patientProfiles}
              currentPatientId={currentPatientId}
              dataStatus={dataStatus}
            />
          </div>
          {page === PAGES.PROFILE && (
            <ProfilePage
              patientProfiles={patientProfiles}
              currentPatientId={currentPatientId}
              onSaveProfile={async (patient) => {
                const sessionUid = authSession?.backendSession?.session_uid;
                if (!sessionUid) {
                  throw new Error("Missing session uid.");
                }
                const saved = await saveSessionPatient(patient, sessionUid);
                setPatientProfiles([saved]);
                return saved;
              }}
            />
          )}
          {page === PAGES.HISTORY && (
            <HistoryPage
              incidentLog={incidentLog}
              setIncidentLog={setIncidentLog}
              patientProfiles={patientProfiles}
              authSession={authSession}
            />
          )}
        </div>
      </div>
      {showWelcomeModal ? (
        <WelcomeAuthModal
          status={authStatus}
          error={authError}
          onContinue={handleWelcomeContinue}
        />
      ) : null}
    </>
  );
}
