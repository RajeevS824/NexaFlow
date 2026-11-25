import React, { useEffect, useRef, useState } from "react";
import { FaTimes, FaSignOutAlt, FaUser, FaBuilding, FaIdBadge, FaCloudUploadAlt, FaCheckCircle, FaBan } from "react-icons/fa";
import { apiFetch } from "../../../../services/api";
import "../Styles/BusinessMapHeader.css";

/**
 * Profile popup — same interaction and menu as the Document Parser one.
 * User details come from the existing session (AuthContext) refreshed from
 * /api/auth/me; the statistics are Business Map's own (GET /stats).
 * Logout is the shared Business Map logout passed in by the header.
 */
export default function BusinessMapProfilePopup({ user, stats, onClose, onLogout }) {
  const [profile, setProfile] = useState(user || null);
  const overlayRef = useRef(null);

  useEffect(() => {
    let active = true;
    apiFetch("/api/auth/me")
      .then((me) => {
        if (!active) return;
        setProfile({
          id: me.user_id ?? user?.id,
          fullName: me.full_name ?? user?.fullName,
          email: me.email ?? user?.email,
          role: me.role ?? user?.role,
          orgId: me.org_id ?? user?.orgId,
          orgName: me.org_name ?? user?.orgName,
        });
      })
      .catch(() => { if (active) setProfile(user || null); });
    return () => { active = false; };
  }, [user]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const fullName = profile?.fullName || profile?.email || "User";
  const email = profile?.email || "—";
  const initial = fullName.trim().charAt(0).toUpperCase();
  const role = profile?.role ? profile.role.charAt(0).toUpperCase() + profile.role.slice(1) : "User";
  const orgName = profile?.orgName || "—";
  const userId = profile?.orgId ?? profile?.id ?? "—";

  return (
    <div
      className="bm-profile-overlay"
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="bm-profile-popup" role="dialog" aria-modal="true" aria-label="Profile">
        <button type="button" className="bm-profile-popup-close" onClick={onClose} aria-label="Close profile">
          <FaTimes />
        </button>

        <div className="bm-profile-popup-header">
          <div className="bm-profile-popup-avatar">{initial}</div>
          <div className="bm-profile-popup-titles">
            <h3 className="bm-profile-popup-name">{fullName}</h3>
            <p className="bm-profile-popup-email">{email}</p>
          </div>
        </div>

        <div className="bm-profile-popup-divider" />

        <div className="bm-profile-popup-fields">
          <div className="bm-profile-field">
            <FaUser className="bm-profile-field-icon" />
            <div><span className="bm-profile-field-label">Role</span><span className="bm-profile-field-value">{role}</span></div>
          </div>
          <div className="bm-profile-field">
            <FaBuilding className="bm-profile-field-icon" />
            <div><span className="bm-profile-field-label">Organization</span><span className="bm-profile-field-value">{orgName}</span></div>
          </div>
          <div className="bm-profile-field">
            <FaIdBadge className="bm-profile-field-icon" />
            <div><span className="bm-profile-field-label">User ID</span><span className="bm-profile-field-value">{userId}</span></div>
          </div>
        </div>

        {stats && (
          <>
            <div className="bm-profile-popup-divider" />
            <div className="bm-profile-stats">
              <div className="bm-profile-stat">
                <FaCloudUploadAlt className="bm-profile-stat-icon blue" />
                <span className="bm-profile-stat-value">{stats.total_uploaded ?? 0}</span>
                <span className="bm-profile-stat-label">Uploaded</span>
              </div>
              <div className="bm-profile-stat">
                <FaCheckCircle className="bm-profile-stat-icon green" />
                <span className="bm-profile-stat-value">{stats.completed ?? 0}</span>
                <span className="bm-profile-stat-label">Completed</span>
              </div>
              <div className="bm-profile-stat">
                <FaBan className="bm-profile-stat-icon purple" />
                <span className="bm-profile-stat-value">{stats.cancelled ?? 0}</span>
                <span className="bm-profile-stat-label">Cancelled</span>
              </div>
            </div>
          </>
        )}

        <div className="bm-profile-popup-divider" />

        <button type="button" className="bm-profile-logout-btn" onClick={onLogout}>
          <FaSignOutAlt /> Logout
        </button>
      </div>
    </div>
  );
}
