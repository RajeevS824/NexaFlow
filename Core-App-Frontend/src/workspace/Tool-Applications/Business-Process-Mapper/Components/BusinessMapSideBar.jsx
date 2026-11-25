import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  FaProjectDiagram,
  FaChartLine,
  FaMapSigns,
  FaBook,
  FaSignOutAlt,
} from "react-icons/fa";
import { useWorkspaceSideBar } from "../../../context/WorkspaceSideBarContext";
import { useBasePath } from "../../../utils/useBasePath";
import { useBusinessMapLogout } from "../../../hooks/useBusinessMapLogout";
import "../Styles/BusinessMapSidebar.css";

/**
 * BusinessMapSideBar — internal mini-app sidebar shown once the user is
 * inside /BusinessMap (the main NexaFlow sidebar hides itself there).
 *
 * "Business Process Mapper" is a STATIC, non-clickable heading. Its two
 * sub-items — Dashboard (index) and Business Flow (processor) — are always
 * rendered: nothing expands or collapses them. They use normal in-tab
 * navigation (only the initial click from the main NexaFlow sidebar opens a
 * new tab, see WorkspaceSideBar).
 *
 * Collapsed mode follows the Document Parser sidebar: every icon stays
 * visible (heading, Dashboard, Business Flow, Documentation, Logout), only the
 * text labels are hidden, each icon has a tooltip, and clicking an icon
 * expands the sidebar and performs its action (as Document Parser does).
 *
 * Documentation and Logout live in a separate, static `sidebar-bottom` block
 * OUTSIDE the <nav> (same as the Document Parser sidebar), so toggling the
 * "Business Process Mapper" group never moves, hides or nests them.
 * Deliberately has NO Settings button — Business Map settings are reached
 * through the NexaFlow Settings dropdown.
 */
const BusinessMapSideBar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = useBasePath();
  const { docExpanded, setDocExpanded } = useWorkspaceSideBar();
  const expanded = docExpanded;
  const handleLogout = useBusinessMapLogout();

  const bmBase = `${basePath}/BusinessMap`;

  // Same pattern as Document Parser: any sidebar action first expands the
  // sidebar, then runs.
  const handleSidebarAction = (action) => () => {
    setDocExpanded(true);
    action();
  };

  const isIndex = location.pathname === bmBase;
  const isProcessor = location.pathname.startsWith(`${bmBase}/processor`);

  return (
    <aside className={`sidebar ${expanded ? "expanded" : ""} business-map-sidebar`}>
      <div className="sidebar-top">
        <div
          className="logo-button"
          onClick={() => (expanded ? setDocExpanded(false) : setDocExpanded(true))}
          title={expanded ? "Collapse sidebar" : "Expand sidebar"}
        >
          <img src="/Icon.png" alt="OneNextGen" className="logo-img" />
          {expanded && (
            <div className="logo-text">
              <h3>OneNextGen</h3>
              <h5>Automation</h5>
            </div>
          )}
        </div>
      </div>

      <nav className="nav-menu">
        <div className="nav-group">
          {/* Static heading: not a button, no click handler, never toggles anything. */}
          <div
            className="nav-heading"
            role="heading"
            aria-level={2}
            title={!expanded ? "Business Process Mapper" : ""}
          >
            <FaProjectDiagram />
            {expanded && <span className="nav-text">Business Process Mapper</span>}
          </div>

          {/* Always rendered — expanded: icon + label, collapsed: icon only. */}
          <div className={`nav-subgroup ${expanded ? "" : "nav-subgroup-collapsed"}`}>
            <button
              type="button"
              className={`nav-item nav-subitem ${isIndex ? "active" : ""}`}
              onClick={handleSidebarAction(() => navigate(bmBase))}
              title={!expanded ? "Dashboard" : ""}
              aria-current={isIndex ? "page" : undefined}
            >
              <FaChartLine />
              {expanded && <span className="nav-text">Dashboard</span>}
            </button>
            <button
              type="button"
              className={`nav-item nav-subitem ${isProcessor ? "active" : ""}`}
              onClick={handleSidebarAction(() => navigate(`${bmBase}/processor`))}
              title={!expanded ? "Business Flow" : ""}
              aria-current={isProcessor ? "page" : undefined}
            >
              <FaMapSigns />
              {expanded && <span className="nav-text">Business Flow</span>}
            </button>
          </div>
        </div>
      </nav>

      <div className="sidebar-bottom">
        <button
          type="button"
          className="action-btn"
          onClick={handleSidebarAction(() => window.open(`${bmBase}/documentation`, "_blank"))}
          title={!expanded ? "Documentation" : ""}
        >
          <FaBook />
          {expanded && <span className="nav-text">Documentation</span>}
        </button>

        <button
          type="button"
          className="action-btn logout-btn"
          onClick={handleSidebarAction(handleLogout)}
          title={!expanded ? "Logout" : ""}
          style={{ marginTop: 6 }}
        >
          <FaSignOutAlt />
          {expanded && <span className="nav-text">Logout</span>}
        </button>
      </div>
    </aside>
  );
};

export default BusinessMapSideBar;
