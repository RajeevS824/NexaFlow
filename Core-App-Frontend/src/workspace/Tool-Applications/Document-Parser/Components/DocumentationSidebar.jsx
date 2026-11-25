import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useWorkspaceSideBar } from "../../../context/WorkspaceSideBarContext";
import { useBasePath } from "../../../utils/useBasePath";
import { useAuth } from "../../../../context/AuthContext.jsx";
import "../Styles/DocumentParserSidebar.css";
import {
  FaHome,
  FaTachometerAlt,
  FaPlusSquare,
  FaListUl,
  FaCog,
  FaFileImport,
  FaHistory,
  FaCheckCircle,
  FaQuestionCircle,
  FaWrench,
  FaFileAlt,
  FaSignOutAlt,
} from "react-icons/fa";

/**
 * workspace/components/DocumentationSidebar.jsx
 * ------------------------------------------------------------
 * Dedicated sidebar for the Document Parser documentation pages
 * (opened in a new tab). It reuses the Document Parser sidebar's
 * classes so it looks and behaves identically (dark navy +
 * amber, expand/collapse, logo, bottom buttons) but only shows
 * documentation navigation instead of the management menu.
 * ------------------------------------------------------------
 */
const DOC_NAV = [
  { to: "", label: "Overview", icon: <FaHome /> },
  { to: "/dashboard", label: "Dashboard", icon: <FaTachometerAlt /> },
  { to: "/create-process-model", label: "Create Process Model", icon: <FaPlusSquare /> },
  { to: "/create-process-fields", label: "Create Process Fields", icon: <FaListUl /> },
  { to: "/document-process-model", label: "Document Process Model", icon: <FaCog /> },
  { to: "/document-processing", label: "Document Processing", icon: <FaFileImport /> },
  { to: "/history", label: "History Extraction Model", icon: <FaHistory /> },
  { to: "/validation", label: "Validation", icon: <FaCheckCircle /> },
  { to: "/faq", label: "FAQ", icon: <FaQuestionCircle /> },
  { to: "/troubleshooting", label: "Troubleshooting", icon: <FaWrench /> },
];

const DocumentationSidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = useBasePath();
  const { docExpanded, toggleDoc } = useWorkspaceSideBar();
  const { logout } = useAuth();
  const expanded = docExpanded;

  const docsBase = `${basePath}/document-parser/documentation`;
  const subPath = location.pathname.startsWith(docsBase)
    ? location.pathname.slice(docsBase.length)
    : location.pathname;

  const isActive = (to) => (to === "" ? subPath === "" : subPath === to);

  return (
    <aside className={`doc-parser-sidebar ${expanded ? "dp-expanded" : "dp-collapsed"}`}>
      <div className="sidebar-top">
        <div className="logo-section dp-clickable" onClick={toggleDoc} title={expanded ? "Collapse sidebar" : "Expand sidebar"}>
          <div className="logo-button">
            <img src="/Icon.png" alt="ONENEXTGEN" className="logo-img" />
            {expanded && (
              <div className="logo-text">
                <h3>OneNextGen</h3>
                <h5>Documentation</h5>
              </div>
            )}
          </div>
        </div>
      </div>

      <nav className="nav-menu">
        {expanded && <div className="nav-section-label">Documentation</div>}
        {DOC_NAV.map((item) => (
          <button
            key={item.to}
            type="button"
            className={`nav-item ${isActive(item.to) ? "active" : ""}`}
            onClick={() => navigate(`${docsBase}${item.to}`)}
            title={!expanded ? item.label : ""}
          >
            {item.icon}
            {expanded && <span className="nav-text">{item.label}</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <button
          type="button"
          className="action-btn"
          onClick={() => navigate(`${basePath}/document-parser`)}
          title={!expanded ? "Document Parser" : ""}
        >
          <FaFileAlt />
          {expanded && <span className="nav-text">Document Parser</span>}
        </button>

        <button
          type="button"
          className="action-btn logout-btn"
          onClick={logout}
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

export default DocumentationSidebar;