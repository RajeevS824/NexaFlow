import React, { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FaBell, FaHome } from "react-icons/fa";
import { useAuth } from "../../../../context/AuthContext.jsx";
import { useBasePath } from "../../../utils/useBasePath";
import { useBusinessMapLogout } from "../../../hooks/useBusinessMapLogout";
import { getJobs, getStats } from "../../../config/businessMapApi";
import BusinessMapNotificationPopup from "./BusinessMapNotificationPopup";
import BusinessMapProfilePopup from "./BusinessMapProfilePopup";
import "../Styles/header.css";
import "../Styles/BusinessMapHeader.css";

/**
 * BusinessMapHeader — the ONE header of the Business Map mini-app, rendered by
 * BusinessMapLayout (not by individual pages), so it is mounted once and stays
 * put while the user moves between Dashboard and Business Flow.
 *
 * Left:  the name of the current page as plain, non-clickable text
 *        ("Dashboard" or "Business Flow"). Switching pages is done only from
 *        the sidebar.
 * Right: Notification (bell), Home, User Profile — same look as Document Parser.
 */
const NOTIF_POLL_MS = 5000;

export default function BusinessMapHeader() {
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = useBasePath();
  const { user } = useAuth();
  const handleLogout = useBusinessMapLogout();

  const bmBase = `${basePath}/BusinessMap`;
  const onFlow = location.pathname.startsWith(`${bmBase}/processor`);
  const pageTitle = onFlow ? "Business Flow" : "Dashboard";

  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState(null);

  const userInitial = (user?.fullName || user?.email || "U").trim().charAt(0).toUpperCase();

  // Business Map notifications come from the Business Map backend (GET /jobs).
  const loadJobs = useCallback(async () => {
    try {
      const data = await getJobs();
      setJobs(Array.isArray(data?.jobs) ? data.jobs : []);
    } catch {
      /* keep the last known list */
    }
  }, []);

  useEffect(() => {
    if (!showNotifications) return undefined;
    loadJobs();
    const id = setInterval(loadJobs, NOTIF_POLL_MS);
    return () => clearInterval(id);
  }, [showNotifications, loadJobs]);

  useEffect(() => {
    if (!showProfile) return;
    getStats().then(setStats).catch(() => setStats(null));
  }, [showProfile]);

  return (
    <>
      <header className="global-header bm-header">
        <div className="global-header-left">
          <h1 className="global-header-title">{pageTitle}</h1>
        </div>

        <div className="global-header-actions bm-header-actions">
          <button type="button" className="bm-notification-btn" title="Notifications" onClick={() => setShowNotifications(true)}>
            <FaBell />
          </button>
          <button type="button" className="bm-home-btn" title="Go to Business Flow Home" onClick={() => navigate(basePath)}>
            <FaHome />
          </button>
          <button
            type="button"
            className="bm-profile-avatar"
            title={user?.fullName || user?.email || "Profile"}
            onClick={() => setShowProfile(true)}
          >
            {userInitial}
          </button>
        </div>
      </header>

      {showNotifications && (
        <BusinessMapNotificationPopup
          jobs={jobs}
          userId={user?.id}
          onClose={() => setShowNotifications(false)}
          onViewAll={() => {
            setShowNotifications(false);
            navigate(bmBase);
          }}
        />
      )}
      {showProfile && (
        <BusinessMapProfilePopup
          user={user}
          stats={stats}
          onClose={() => setShowProfile(false)}
          onLogout={handleLogout}
        />
      )}
    </>
  );
}
