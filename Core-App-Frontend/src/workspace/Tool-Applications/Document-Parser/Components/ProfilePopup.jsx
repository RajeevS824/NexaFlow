import React, { useEffect, useRef, useState } from "react";
import {
  FaTimes,
  FaSignOutAlt,
  FaUser,
  FaBuilding,
  FaIdBadge,
  FaLayerGroup,
  FaFileAlt,
  FaCheckCircle,
} from "react-icons/fa";
import { apiFetch } from "../../../../services/api";
import "../Styles/documentParser.css";

export default function ProfilePopup({ user, stats, onClose, onLogout }) {
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
      .catch(() => {
        if (active) setProfile(user || null);
      });
    return () => { active = false; };
  }, [user]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const fullName = profile?.fullName || profile?.email || "User";
  const email = profile?.email || "—";
  const initial = (fullName || "?").trim().charAt(0).toUpperCase();
  const role = profile?.role
    ? profile.role.charAt(0).toUpperCase() + profile.role.slice(1)
    : "User";
  const orgName = profile?.orgName || "—";
  const orgId = profile?.orgId ?? profile?.id ?? "—";

  return (
    <div
      className="dp-profile-overlay"
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="dp-profile-popup" role="dialog" aria-modal="true" aria-label="Profile">
        <button type="button" className="dp-profile-popup-close" onClick={onClose} aria-label="Close profile">
          <FaTimes />
        </button>

        <div className="dp-profile-popup-header">
          <div className="dp-profile-popup-avatar">{initial}</div>
          <div className="dp-profile-popup-titles">
            <h3 className="dp-profile-popup-name">{fullName}</h3>
            <p className="dp-profile-popup-email">{email}</p>
          </div>
        </div>

        <div className="dp-profile-popup-divider" />

        <div className="dp-profile-popup-fields">
          <div className="dp-profile-field">
            <FaUser className="dp-profile-field-icon" />
            <div>
              <span className="dp-profile-field-label">Role</span>
              <span className="dp-profile-field-value">{role}</span>
            </div>
          </div>
          <div className="dp-profile-field">
            <FaBuilding className="dp-profile-field-icon" />
            <div>
              <span className="dp-profile-field-label">Organization</span>
              <span className="dp-profile-field-value">{orgName}</span>
            </div>
          </div>
          <div className="dp-profile-field">
            <FaIdBadge className="dp-profile-field-icon" />
            <div>
              <span className="dp-profile-field-label">User ID</span>
              <span className="dp-profile-field-value">{orgId}</span>
            </div>
          </div>
        </div>

        {stats && (
          <>
            <div className="dp-profile-popup-divider" />
            <div className="dp-profile-stats">
              <div className="dp-profile-stat">
                <FaLayerGroup className="dp-profile-stat-icon blue" />
                <span className="dp-profile-stat-value">{stats.totalModels ?? 0}</span>
                <span className="dp-profile-stat-label">Models</span>
              </div>
              <div className="dp-profile-stat">
                <FaFileAlt className="dp-profile-stat-icon green" />
                <span className="dp-profile-stat-value">{stats.totalHistory ?? 0}</span>
                <span className="dp-profile-stat-label">Processed</span>
              </div>
              <div className="dp-profile-stat">
                <FaCheckCircle className="dp-profile-stat-icon purple" />
                <span className="dp-profile-stat-value">{stats.completed ?? 0}</span>
                <span className="dp-profile-stat-label">Extracted</span>
              </div>
            </div>
          </>
        )}

        <div className="dp-profile-popup-divider" />

        <button type="button" className="dp-profile-logout-btn" onClick={onLogout}>
          <FaSignOutAlt />
          Logout
        </button>
      </div>
    </div>
  );
}