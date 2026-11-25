import React, { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import DocumentationSidebar from "../../Components/DocumentationSidebar";
import Header from "../../../../components/WorkspaceHeader";
import { useBasePath } from "../../../../utils/useBasePath";
import { FaHome } from "react-icons/fa";
import "../../Styles/commonstyle.css";
import "../../Styles/documentParser.css";
import "../../Styles/documentation.css";

// Map each documentation sub-route to the title shown in the header.
const DOC_TITLES = {
  "": "Overview",
  "/dashboard": "Dashboard",
  "/create-process-model": "Create Process Model",
  "/create-process-fields": "Create Process Fields",
  "/document-process-model": "Document Process Model",
  "/document-processing": "Document Processing",
  "/history": "History Extraction Model",
  "/validation": "Validation",
  "/faq": "FAQ",
  "/troubleshooting": "Troubleshooting",
};

function DocumentationLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const basePath = useBasePath();
  const docBase = `${basePath}/document-parser`;

  // Set the browser tab title for all Documentation pages opened in a new tab.
  useEffect(() => {
    document.title = "Documentation | Document Parser";
  }, []);

  // Derive the sub-path after "/documentation" to look up the header title.
  const docsBase = `${docBase}/documentation`;
  const subPath = location.pathname.startsWith(docsBase)
    ? location.pathname.slice(docsBase.length)
    : "";
  const sectionTitle = DOC_TITLES[subPath] || "Documentation";
  const title = `Documentation of ${sectionTitle}`;

  return (
    <div className="doc-parser-layout">
      <DocumentationSidebar />
      <div className="doc-parser-content">
        {/* Common Document Parser header — sticky, with a Home button
            that navigates back to the Document Parser home page. */}
        <Header
          title={title}
          actions={
            <button
              className="dp-home-btn"
              title="Go to Document Parser Home"
              onClick={() => navigate(docBase)}
            >
              <FaHome />
            </button>
          }
        />
        <div className="doc-parser-scroll">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

export default DocumentationLayout;