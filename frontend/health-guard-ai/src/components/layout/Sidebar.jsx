import { PAGES } from "../../constants/pages";

export default function Sidebar({ page, setPage }) {
const navItems = [
    { id: PAGES.DASHBOARD, icon: "💓", label: "Dashboard" },
    { id: PAGES.PROFILE, icon: "👤", label: "Profile" },
    { id: PAGES.HISTORY, icon: "📋", label: "History" },
];

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
      </div>
      {navItems.map(item => (
        <button
          key={item.id}
          className={`nav-btn ${page === item.id ? "active" : ""}`}
          onClick={() => setPage(item.id)}
          title={item.label}
        >
          {item.icon}
          {item.id === PAGES.DASHBOARD && page !== PAGES.DASHBOARD && (
            <span className="nav-badge" />
          )}
        </button>
      ))}
    </div>
  );
}
