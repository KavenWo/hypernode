import { useEffect, useMemo, useState } from "react";
import MvpTestPage from "./components/MvpTestPage.jsx";
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
    try {
      const session = await bootstrapAnonymousSession(null);
      setAuthSession(session);
      if (session.patients?.length) {
        const normalized = session.patients.map(normalizePatientProfile);
        setPatientProfiles(normalized);
        setCurrentPatientId(session.patientId || normalized[0]?.patientId || "");
      }
      setAuthStatus("ready");
    } catch (error) {
      setAuthStatus("awaiting_user");
      setAuthError(error.message || "Unable to start the anonymous session.");
    }
  }

  const showWelcomeModal = authStatus !== "ready";

  useEffect(() => {
    let cancelled = false;

    async function hydrateSessionData() {
      const sessionUid = authSession?.backendSession?.session_uid;
      if (!sessionUid) {
        return;
      }

      try {
        const [patients, history] = await Promise.all([
          fetchSessionPatients(sessionUid),
          fetchSessionHistory(sessionUid),
        ]);

        if (cancelled) {
          return;
        }

        setPatientProfiles(patients);
        setCurrentPatientId((current) => current || authSession.patientId || patients[0]?.patientId || "");
        setHistoryLog(history);
      } catch (error) {
        if (cancelled) {
          return;
        }
        console.error("Failed to hydrate session data", error);
      }
    }

    hydrateSessionData();

    return () => {
      cancelled = true;
    };
  }, [authSession]);

  return (
    <>
      <div className="app">
        <Sidebar page={page} setPage={setPage} />
        <div className="main">
          {page === PAGES.DASHBOARD && (
            <Dashboard
              onNavigate={setPage}
              historyLog={historyLog}
              setHistoryLog={setHistoryLog}
              authSession={authSession}
              patientProfiles={patientProfiles}
              currentPatientId={currentPatientId}
              onSelectPatient={setCurrentPatientId}
            />
          )}
          {page === PAGES.MVP_TEST && <MvpTestPage />}
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
