/**
 * workspace/components/Sidebar.jsx
 * ------------------------------------------------------------
 * Left navigation rail for the NexaFlow workspace.
 *
 * Product visibility is driven by the logged-in user's
 * `products` array returned from the backend on login.
 * ------------------------------------------------------------
 */

import React, { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FaHome, FaUsers, FaCogs, FaBoxes, FaUserShield, FaSignOutAlt, FaChevronRight } from "react-icons/fa";
import { useAuth } from "../../../../context/AuthContext.jsx";
import { useWorkspaceSideBar } from "../../../context/WorkspaceSideBarContext.jsx";
import { DASHBOARD_USER_PATH, DASHBOARD_ADMIN_PATH } from "../../../../config/dashboardRoutes.js";
import "../../Document-Parser/Styles/DocumentParserSidebar.css";
import { PRODUCTS } from "../../../../data/products.js";

const iconMap = {
  "business-process-mapper": FaCogs,
  "document-parser": FaBoxes,
  "nextflow": FaUsers,
};

export default function AdminSideBar({ isDashboard = false, isAdmin = false, basePath = "/dashboard" }) {
  const { user, logout } = useAuth();
  const { mainExpanded, mainVisible, toggleMain, onMainHoverEnter, onMainHoverLeave } = useWorkspaceSideBar();
  const navigate = useNavigate();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const location = useLocation();

  // Product access comes from the backend-issued user payload.
  const accessibleProducts = useMemo(() => {
    const list = Array.isArray(user?.products) ? user.products : [];
    return list.filter((p) => p && p.slug && p.name);
  }, [user?.products]);

  const isProductEnabled = (slug) => accessibleProducts.some((p) => p.slug === slug);

  // Normalize away a trailing slash so equality checks below are exact.
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const isActive = (suffix) => path === `${basePath}${suffix}`.replace(/\/+$/, "");

  const expanded = mainVisible;

  return (
    <aside className="doc-parser-sidebar dp-expanded admin-sidebar">
      <div className="sidebar-top">
        <div className="logo-section dp-clickable" onClick={toggleMain} title={mainExpanded ? "Collapse sidebar" : "Expand sidebar"}>
          <div className="logo-button">
            <img src="/Icon.png" alt="ONENEXTGEN" className="logo-img" />
            {expanded && (
              <div className="logo-text">
                <h3>OneNextGen</h3>
                <h5>Automation</h5>
              </div>
            )}
          </div>
        </div>
      </div>

      <nav className="nav-menu">
        <button
          className={`nav-item ${isActive("") ? "active" : ""}`}
          onClick={() => navigate(basePath)}
          title={!expanded ? "Dashboard" : ""}
        >
          <FaHome size={16} />
          {expanded && <span className="nav-text">Dashboard</span>}
        </button>

        <button
          className={`nav-item ${isActive("/products") ? "active" : ""}`}
          onClick={() => navigate(`${DASHBOARD_ADMIN_PATH}/products`)}
          title={!expanded ? "Products" : ""}
        >
          <FaBoxes size={16} />
          {expanded && <span className="nav-text">Products</span>}
        </button>

        {expanded && <p className="nav-section-label">Manage</p>}

        <div className={`submenu ${expanded ? "" : "submenu-collapsed"}`}>
          <button
            className={`nav-item nav-item-sub ${isActive("/role") ? "active" : ""}`}
            onClick={() => navigate(`${DASHBOARD_ADMIN_PATH}/role`)}
            title={!expanded ? "Role" : ""}
          >
            <FaUserShield size={16} />
            {expanded && <span className="nav-text">Role</span>}
          </button>

          <button
            className={`nav-item nav-item-sub ${isActive("/role-permission") ? "active" : ""}`}
            onClick={() => navigate(`${DASHBOARD_ADMIN_PATH}/role-permission`)}
            title={!expanded ? "Role Permission" : ""}
          >
            <FaCogs size={16} />
            {expanded && <span className="nav-text">Role Permission</span>}
          </button>

          <button
            className={`nav-item nav-item-sub ${isActive("/users") ? "active" : ""}`}
            onClick={() => navigate(`${DASHBOARD_ADMIN_PATH}/users`)}
            title={!expanded ? "Users" : ""}
          >
            <FaUsers size={16} />
            {expanded && <span className="nav-text">Users</span>}
          </button>
        </div>
      </nav>

      {/* Bottom actions */}
      <div className="sidebar-bottom">
          <div className="settings-wrap">
            <button
              type="button"
              className={`action-btn ${settingsOpen ? "active" : ""}`}
              onClick={() => setSettingsOpen((p) => !p)}
              aria-expanded={settingsOpen}
              title={!expanded ? "Settings" : ""}
            >
              <FaCogs size={16} />
              {expanded && <span>Settings</span>}
              {expanded && (
                <span className={`settings-chevron ${settingsOpen ? "open" : ""}`}>
                  <FaChevronRight />
                </span>
              )}
            </button>

            {settingsOpen && (
              <div className="settings-menu" role="menu">
                <div className="settings-menu-label">Product Settings</div>
                {PRODUCTS.map((p) => (
                  <button
                    key={p.slug}
                    type="button"
                    className="settings-menu-item"
                    onClick={() => {
                      // Document Parser has a dedicated settings route inside the workspace
                      if (p.slug === "document-parser") {
                        navigate(`${basePath}/document-parser-settings`);
                      } else if (p.slug === "business-process-mapper") {
                        // Business Map settings opens in the same tab.
                        navigate(`${basePath}/settings/business-process-mapper`);
                      } else {
                        // Show product settings within the admin panel itself,
                        // instead of opening a new browser tab/page.
                        navigate(`${basePath}/settings/${p.slug}`);
                      }
                      setSettingsOpen(false);
                    }}
                    title={`${p.name} settings`}
                  >
                    <span style={{ width: 18, display: "inline-block" }}>{p.icon}</span>
                    <span style={{ marginLeft: 6 }}>{p.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button type="button" className="action-btn" onClick={logout} title={!expanded ? "Logout" : ""}>
            <FaSignOutAlt size={16} />
            {expanded && <span>Logout</span>}
          </button>
      </div>
    </aside>
  );
}