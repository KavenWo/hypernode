import { useState } from "react";
import MvpTestPage from "./components/MvpTestPage.jsx";
import Sidebar from "./components/layout/Sidebar";
import Dashboard from "./components/pages/Dashboard";
import ProfilePage from "./components/pages/ProfilePage";
import HistoryPage from "./components/pages/HistoryPage";
import { PAGES } from "./constants/pages";
import { HISTORY_SEED } from "./data/mockData";

import "./styles/index.css";

export default function App() {
  const [page, setPage] = useState(PAGES.DASHBOARD);
  const [historyLog, setHistoryLog] = useState([...HISTORY_SEED]);

  return (
    <div className="app">
      <Sidebar page={page} setPage={setPage} />
      <div className="main">
        {page === PAGES.DASHBOARD && (
          <Dashboard
            onNavigate={setPage}
            historyLog={historyLog}
            setHistoryLog={setHistoryLog}
          />
        )}
        {page === PAGES.MVP_TEST && <MvpTestPage />}
        {page === PAGES.PROFILE && <ProfilePage />}
        {page === PAGES.HISTORY && <HistoryPage historyLog={historyLog} setHistoryLog={setHistoryLog} />}
      </div>
    </div>
  );
}
