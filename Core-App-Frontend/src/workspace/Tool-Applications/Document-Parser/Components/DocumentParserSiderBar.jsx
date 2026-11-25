import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useWorkspaceSideBar } from "../../../context/WorkspaceSideBarContext";
import { useDPUnsavedChanges } from "../../../context/DP-UnsavedChangesContext";
import { useBasePath } from "../../../utils/useBasePath";
import { useAuth } from "../../../../context/AuthContext.jsx";
import "../Styles/commonstyle.css";
import "../Styles/DocumentParserSidebar.css";
import {
  FaFileAlt,
  FaBook,
  FaPlusSquare,
  FaHistory,
  FaCog,
  FaSignOutAlt,
} from "react-icons/fa";

const DocumentParserSidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { docExpanded, setDocExpanded, toggleDoc } = useWorkspaceSideBar();
  const { checkUnsavedChanges } = useDPUnsavedChanges();
  const { logout } = useAuth();
  const basePath = useBasePath();
  const expanded = docExpanded;

  const docBase = `${basePath}/document-parser`;

  const expandSidebar = () => setDocExpanded(true);

  const handleSidebarAction = (action) => () => {
    expandSidebar();
    action();
  };

  // Show Help + Logout only on the dashboard (exact match, no sub-routes)
  const isDashboard = location.pathname === docBase;

  const isActive = (subPath) => {
    const full = `${docBase}${subPath}`;
    return location.pathname === full || location.pathname.startsWith(full + "/");
  };

  return (
    <aside className={`doc-parser-sidebar ${expanded ? "dp-expanded" : "dp-collapsed"}`}>
      <div className="sidebar-top">
        <div
          className="logo-section dp-clickable"
          onClick={() => {
            if (expanded) {
              setDocExpanded(false);
            } else {
              setDocExpanded(true);
            }
          }}
          title={expanded ? "Collapse sidebar" : "Expand sidebar"}
        >
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
          onClick={handleSidebarAction(() =>
            checkUnsavedChanges(() => {
              localStorage.removeItem("editModelId");
              navigate(docBase);
            })
          )}
          title={!expanded ? "Document Parser" : ""}
        >
          <FaFileAlt />
          {expanded && <span className="nav-text">Document Parser</span>}
        </button>

        <div className={`submenu ${expanded ? "" : "submenu-collapsed"}`}>
          <button
            className={`nav-item ${
              location.pathname === `${docBase}/create-process-model` ||
              location.pathname === `${docBase}/create-process-model/create-process-field`
                ? "active"
                : ""
            }`}
            onClick={handleSidebarAction(() =>
              checkUnsavedChanges(() => {
                localStorage.removeItem("draftExtractionFields");
                localStorage.removeItem("editModelId");
                navigate(`${docBase}/create-process-model`);
              })
            )}
            title={!expanded ? "Create Process Model" : ""}
          >
            <FaPlusSquare />
            {expanded && <span className="nav-text">Create Process Model</span>}
          </button>

          <button
            className={`nav-item ${isActive("/document-process-model") ? "active" : ""}`}
            onClick={handleSidebarAction(() =>
              checkUnsavedChanges(() => {
                navigate(`${docBase}/document-process-model`);
              })
            )}
            title={!expanded ? "Process Extraction Model" : ""}
          >
            <FaCog />
            {expanded && <span className="nav-text">Document Process Model</span>}
          </button>

          <button
            className={`nav-item ${isActive("/history-process-model") ? "active" : ""}`}
            onClick={handleSidebarAction(() =>
              checkUnsavedChanges(() => {
                localStorage.removeItem("historyModelId");
                navigate(`${docBase}/history-process-model`);
              })
            )}
            title={!expanded ? "View Extraction Model" : ""}
          >
            <FaHistory />
            {expanded && <span className="nav-text">History Process Model</span>}
          </button>
        </div>
      </nav>

      <div className="sidebar-bottom">
        {isDashboard && (
          <>
            <button
              type="button"
              className="action-btn"
              onClick={handleSidebarAction(() => window.open(`${docBase}/documentation`, "_blank"))}
              title={!expanded ? "Documentation" : ""}
            >
              <FaBook />
              {expanded && <span className="nav-text">Documentation</span>}
            </button>

            <button
              type="button"
              className="action-btn logout-btn"
              onClick={handleSidebarAction(logout)}
              title={!expanded ? "Logout" : ""}
              style={{ marginTop: 6 }}
            >
              <FaSignOutAlt />
              {expanded && <span className="nav-text">Logout</span>}
            </button>
          </>
        )}
      </div>
    </aside>
  );
};

export default DocumentParserSidebar;