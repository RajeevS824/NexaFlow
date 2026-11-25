import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  FaHome, FaTachometerAlt, FaMapSigns, FaStream, FaCog, FaQuestionCircle, FaWrench,
  FaProjectDiagram, FaSignOutAlt,
} from "react-icons/fa";
import { useWorkspaceSideBar } from "../../../context/WorkspaceSideBarContext";
import { useBasePath } from "../../../utils/useBasePath";
import { useBusinessMapLogout } from "../../../hooks/useBusinessMapLogout";
import "../Styles/BusinessMapSidebar.css";

/**
 * Sidebar of the Business Map documentation pages. Reuses the Business Map
 * sidebar look (dark navy + amber, collapsible, logo, static bottom buttons)
 * but lists documentation sections instead of the app menu.
 */
const DOC_NAV = [
  { to: "", label: "Overview", icon: <FaHome /> },
  { to: "/dashboard", label: "Dashboard", icon: <FaTachometerAlt /> },
  { to: "/business-flow", label: "Business Flow", icon: <FaMapSigns /> },
  { to: "/pipeline", label: "Processing Pipeline", icon: <FaStream /> },
  { to: "/settings", label: "Settings", icon: <FaCog /> },
  { to: "/faq", label: "FAQ", icon: <FaQuestionCircle /> },
  { to: "/troubleshooting", label: "Troubleshooting", icon: <FaWrench /> },
];

export default function BusinessMapDocumentationSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = useBasePath();
  const { docExpanded, toggleDoc } = useWorkspaceSideBar();
  const handleLogout = useBusinessMapLogout();
  const expanded = docExpanded;

  const bmBase = `${basePath}/BusinessMap`;
  const docsBase = `${bmBase}/documentation`;
  const subPath = location.pathname.startsWith(docsBase) ? location.pathname.slice(docsBase.length).replace(/\/$/, "") : "";

  return (
    <aside className={`sidebar ${expanded ? "expanded" : ""} business-map-sidebar`}>
      <div className="sidebar-top">
        <div className="logo-button" onClick={toggleDoc} title={expanded ? "Collapse sidebar" : "Expand sidebar"}>
          <img src="/Icon.png" alt="OneNextGen" className="logo-img" />
          {expanded && (
            <div className="logo-text">
              <h3>OneNextGen</h3>
              <h5>Documentation</h5>
            </div>
          )}
        </div>
      </div>

      <nav className="nav-menu">
        {DOC_NAV.map((item) => (
          <button
            key={item.to}
            type="button"
            className={`nav-item ${subPath === item.to ? "active" : ""}`}
            onClick={() => navigate(`${docsBase}${item.to}`)}
            title={!expanded ? item.label : ""}
          >
            {item.icon}
            {expanded && <span className="nav-text">{item.label}</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <button type="button" className="action-btn" onClick={() => navigate(bmBase)} title={!expanded ? "Business Map" : ""}>
          <FaProjectDiagram />
          {expanded && <span className="nav-text">Business Map</span>}
        </button>
        <button type="button" className="action-btn logout-btn" onClick={handleLogout} title={!expanded ? "Logout" : ""} style={{ marginTop: 6 }}>
          <FaSignOutAlt />
          {expanded && <span className="nav-text">Logout</span>}
        </button>
      </div>
    </aside>
  );
}
