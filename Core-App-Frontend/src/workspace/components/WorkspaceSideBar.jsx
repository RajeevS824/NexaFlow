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
import { useAuth } from "../../context/AuthContext.jsx";
import { useWorkspaceSideBar } from "../context/WorkspaceSideBarContext.jsx";
import { DASHBOARD_USER_PATH, DASHBOARD_ADMIN_PATH } from "../../config/dashboardRoutes.js";
import "../Tool-Applications/Document-Parser/Styles/DocumentParserSidebar.css";
import { PRODUCTS } from "../../data/products.js";

const iconMap = {
  "business-process-mapper": FaCogs,
  "document-parser": FaBoxes,
  "nextflow": FaUsers,
};

export default function WorkspaceSideBar({ isDashboard = false, isAdmin = false, basePath = "/dashboard" }) {
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
    <aside className="doc-parser-sidebar dp-expanded user-sidebar">
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
        {/* Navigation */}
        <button
          className={`nav-item ${isActive("") ? "active" : ""}`}
          onClick={() => navigate(basePath)}
          title={!expanded ? "Dashboard" : ""}
        >
          <FaHome size={16} />
          {expanded && <span className="nav-text">Dashboard</span>}
        </button>

          {/* Product links - show all products for community/regular users,
              but block navigation for products the user doesn't have access to */}
          {PRODUCTS.map((product) => {
            const Icon = iconMap[product.slug];
            if (!Icon) return null;
            const to = `${basePath}/${product.slug === "business-process-mapper" ? "BusinessMap" : product.slug}`;
            const hasAccess = isProductEnabled(product.slug);

            const handleClick = () => {
              if (!hasAccess) {
                alert(`Access denied: You don't have access to ${product.name}`);
                return;
              }

              if (product.slug === "business-process-mapper") {
                // Deliberate exception (per request): Business Map opens in a
                // NEW browser tab, unlike every other product link.
                // NOTE: no "noopener" here — required so the browser copies
                // this tab's sessionStorage (where the NexaFlow auth token
                // lives) into the new tab, letting the user land straight on
                // the Business Map dashboard without a second login prompt.
                window.open(to, "_blank");
                return;
              }

              // Open every other product within the same workspace panel —
              // Document Parser used to open in a separate browser tab here,
              // which was inconsistent with every other product link.
              navigate(to);
            };

            return (
              <button
                key={product.slug}
                className={`nav-item ${isActive(`/${product.slug === "business-process-mapper" ? "BusinessMap" : product.slug}`) ? "active" : ""}`}
                onClick={handleClick}
                title={!expanded ? product.name : ""}
              >
                <Icon size={16} />
                {expanded && <span className="nav-text">{product.name}</span>}
              </button>
            );
          })}
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
                        // Show product settings within the panel itself,
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