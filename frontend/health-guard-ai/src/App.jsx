import { useEffect, useMemo, useState } from "react";
import Sidebar from "./components/layout/Sidebar";
import Dashboard from "./components/pages/Dashboard";
import ProfilePage from "./components/pages/ProfilePage";
import HistoryPage from "./components/pages/HistoryPage";
import WelcomeAuthModal from "./components/ui/WelcomeAuthModal.jsx";
import { PAGES } from "./constants/pages";
import { fetchSessionHistory, fetchSessionPatients, normalizePatientProfile, saveSessionPatient } from "./lib/patientApi.js";
import { resolveExistingAnonymousSession, bootstrapAnonymousSession } from "./lib/sessionBootstrap.js";

import "./styles/index.css";

export default function App() {
  const [page, setPage] = useState(PAGES.DASHBOARD);
  const [historyLog, setHistoryLog] = useState([]);
  const [authStatus, setAuthStatus] = useState("checking");
  const [authError, setAuthError] = useState("");
  const [authSession, setAuthSession] = useState(null);
  const [dataStatus, setDataStatus] = useState("idle"); // 'idle' | 'loading' | 'ready' | 'error'
  const [patientProfiles, setPatientProfiles] = useState([]);
  const [currentPatientId, setCurrentPatientId] = useState("");

  const currentPatient = useMemo(
    () => patientProfiles.find((patient) => patient.patientId === currentPatientId) || patientProfiles[0] || null,
    [patientProfiles, currentPatientId],
  );

  useEffect(() => {
    let cancelled = false;

    async function hydrateExistingSession() {
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
            setCurrentPatientId(session.patientId || normalized[0]?.patientId || "");
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
    setAuthStatus("signing_in");
    setAuthError("");
    setDataStatus("loading");
    try {
      const session = await bootstrapAnonymousSession(null);
      // Fast-track the UI to ready state as soon as we have a session
      setAuthSession(session);
      setAuthStatus("ready");

      if (session.patients?.length) {
        const normalized = session.patients.map(normalizePatientProfile);
        setPatientProfiles(normalized);
        setCurrentPatientId(session.patientId || normalized[0]?.patientId || "");
        setDataStatus("ready");
      }
    } catch (error) {
      setAuthStatus("awaiting_user");
      setDataStatus("error");
      setAuthError(error.message || "Unable to start the anonymous session.");
    }
  }

  const showWelcomeModal = authStatus !== "ready";

  useEffect(() => {
    let isMounted = true;

    async function hydrateSessionData() {
      const sessionUid = authSession?.backendSession?.session_uid;
      if (!sessionUid) return;
      
      setDataStatus("loading");
      
      const maxAttempts = 10;
      let attempt = 0;
      
      while (attempt < maxAttempts) {
        if (!isMounted) break;

        try {
          const startTime = Date.now();
          const [patients, history] = await Promise.all([
            fetchSessionPatients(sessionUid),
            fetchSessionHistory(sessionUid),
          ]);
          
          if (!isMounted) break;

          if (patients.length > 0) {
            setPatientProfiles(patients);
            setHistoryLog(history);
            if (patients[0]?.patientId) {
              setCurrentPatientId(patients[0].patientId);
            }
            setDataStatus("ready");
            return;
          }
          
          attempt++;
          const elapsed = Date.now() - startTime;
          const waitTime = Math.max(500, 1500 - elapsed);
          
          if (attempt < maxAttempts && isMounted) {
            await new Promise(resolve => setTimeout(resolve, waitTime));
          }
        } catch (err) {
          console.error("Hydration attempt failed:", err);
          attempt++;
          if (attempt >= maxAttempts) {
            if (isMounted) setDataStatus("error");
          } else if (isMounted) {
            await new Promise(resolve => setTimeout(resolve, 2000));
          }
        }
      }
      
      if (isMounted && attempt >= maxAttempts) {
        setDataStatus("ready"); 
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
          {dataStatus === "loading" && !showWelcomeModal && (
            <div className="app-hydration-toast">
              <div className="toast-spinner"></div>
              <div className="toast-content">
                <div className="toast-title">Syncing Clinical Data</div>
                <div className="toast-sub">Updating patient profiles...</div>
              </div>
            </div>
          )}
          {page === PAGES.DASHBOARD && (
            <Dashboard
              onNavigate={setPage}
              historyLog={historyLog}
              setHistoryLog={setHistoryLog}
              authSession={authSession}
              patientProfiles={patientProfiles}
              currentPatientId={currentPatientId}
              onSelectPatient={setCurrentPatientId}
              dataStatus={dataStatus}
            />
          )}
          {page === PAGES.PROFILE && (
            <ProfilePage
              patientProfiles={patientProfiles}
              currentPatientId={currentPatientId}
              onSelectPatient={setCurrentPatientId}
              onSaveProfile={async (patient) => {
                const sessionUid = authSession?.backendSession?.session_uid;
                if (!sessionUid) {
                  throw new Error("Missing session uid.");
                }
                const saved = await saveSessionPatient(patient, sessionUid);
                setPatientProfiles((current) =>
                  current.map((item) => (item.patientId === saved.patientId ? saved : item)),
                );
                return saved;
              }}
            />
          )}
          {page === PAGES.HISTORY && (
            <HistoryPage
              historyLog={historyLog}
              setHistoryLog={setHistoryLog}
              patientProfiles={patientProfiles}
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
