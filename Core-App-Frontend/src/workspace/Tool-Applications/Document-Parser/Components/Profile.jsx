import React, { useEffect, useState } from "react";
import { useAuth } from "../../../../context/AuthContext.jsx";
import { useBasePath } from "../../../utils/useBasePath";
import { apiFetch } from "../../../../services/api";
import { FaUser, FaEnvelope, FaIdBadge, FaBuilding, FaQuestionCircle, FaSignOutAlt } from "react-icons/fa";
import "../Styles/documentParser.css";

/**
 * src/Tool-Applications/Document-Parser/Pages/Profile.jsx
 *
 * Full-page profile view for the Document Parser dashboard user.
 * Mirrors the information shown by the header ProfilePopup, but as a
 * standalone page reachable at:
 *   <basePath>/document-parser/profile
 *
 * Data is fetched from the main NexaFlow backend /api/auth/me endpoint;
 * logout is delegated to the shared AuthContext so the session/token is
 * cleared consistently across the whole app.
 */
function Profile() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const { user, logout } = useAuth();
  const basePath = useBasePath();
  const docBase = `${basePath}/document-parser`;

  useEffect(() => {
    let active = true;
    apiFetch("/api/auth/me")
      .then((me) => {
        if (!active) return;
        setProfile({
          fullName: me.full_name ?? user?.fullName ?? "User",
          email: me.email ?? user?.email ?? "—",
          role: me.role ?? user?.role ?? "User",
          orgId: me.org_id ?? user?.orgId ?? "—",
          orgName: me.org_name ?? user?.orgName ?? "—",
        });
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        // Fall back to whatever the client already knows about the user.
        setProfile({
          fullName: user?.fullName || user?.email || "User",
          email: user?.email || "—",
          role: user?.role || "User",
          orgId: user?.id || "—",
          orgName: "—",
        });
        setLoading(false);
      });
    return () => { active = false; };
  }, [user]);

  const fullName = profile?.fullName || "User";
  const email = profile?.email || "—";
  const initial = (fullName || "?").trim().charAt(0).toUpperCase();
  const role = profile?.role
    ? profile.role.charAt(0).toUpperCase() + profile.role.slice(1)
    : "User";
  const orgName = profile?.orgName || "—";
  const orgId = profile?.orgId ?? profile?.id ?? "—";

  if (loading) {
    return (
      <div className="dp-profile-page">
        <div className="dp-profile-popup">Loading profile…</div>
      </div>
    );
  }

  return (
    <div className="dp-profile-page">
      <div className="dp-profile-page-header">
        <h1 className="dp-profile-page-title">Profile</h1>
        <div className="dp-profile-page-actions">
          <button
            type="button"
            className="dp-help-btn"
            title="Help"
            onClick={() => window.open(`${docBase}/documentation`, "_blank")}
          >
            <FaQuestionCircle />
            <span className="nav-text">Help</span>
          </button>
          <button
            type="button"
            className="dp-logout-btn"
            title="Logout"
            onClick={() => logout()}
          >
            <FaSignOutAlt />
            <span className="nav-text">Logout</span>
          </button>
        </div>
      </div>

      <div className="dp-profile-popup">
        <div className="dp-profile-popup-header">
          <div className="dp-profile-popup-avatar">{initial}</div>
          <div className="dp-profile-popup-titles">
            <h3 className="dp-profile-popup-name">{fullName}</h3>
            <p className="dp-profile-popup-email">{email}</p>
            <span className="dp-profile-popup-role">{role}</span>
          </div>
        </div>

        <div className="dp-profile-popup-divider" />

        <div className="dp-profile-popup-fields">
          <div className="dp-profile-field">
            <FaUser className="dp-profile-field-icon" />
            <div>
              <span className="dp-profile-field-label">Full Name</span>
              <span className="dp-profile-field-value">{fullName}</span>
            </div>
          </div>
          <div className="dp-profile-field">
            <FaEnvelope className="dp-profile-field-icon" />
            <div>
              <span className="dp-profile-field-label">Email</span>
              <span className="dp-profile-field-value">{email}</span>
            </div>
          </div>
          <div className="dp-profile-field">
            <FaIdBadge className="dp-profile-field-icon" />
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
              <span className="dp-profile-field-label">Organization ID</span>
              <span className="dp-profile-field-value">{orgId}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="dp-profile-footer">
        <button
          type="button"
          className="dp-profile-logout-btn"
          onClick={() => logout()}
        >
          <FaSignOutAlt />
          Logout
        </button>
      </div>
    </div>
  );
}

export default Profile;
