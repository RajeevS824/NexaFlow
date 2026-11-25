import React, { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { FaHome } from "react-icons/fa";
import BusinessMapDocumentationSidebar from "../../Components/BusinessMapDocumentationSidebar";
import { useBasePath } from "../../../../utils/useBasePath";
import "../../Styles/bm-common.css";
import "../../Styles/header.css";
import "../../Styles/documentation.css";

// Map each documentation sub-route to the title shown in the header.
export const DOC_TITLES = {
  "": "Overview",
  "/dashboard": "Dashboard",
  "/business-flow": "Business Flow",
  "/pipeline": "Processing Pipeline",
  "/settings": "Settings",
  "/faq": "FAQ",
  "/troubleshooting": "Troubleshooting",
};

/**
 * Documentation layout for Business Map — same structure as the Document
 * Parser documentation: its own sidebar + a header + one scrolling page per
 * section (rendered through <Outlet/>). Opened in a new tab from the
 * sidebar's "Documentation" button, at .../BusinessMap/documentation.
 */
export default function BusinessMapDocumentationLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const basePath = useBasePath();
  const bmBase = `${basePath}/BusinessMap`;
  const docsBase = `${bmBase}/documentation`;

  // Same tab title as the other Business Map pages; re-applied on navigation.
  useEffect(() => {
    document.title = "Business Map Processor";
  }, [location.pathname]);

  const subPath = location.pathname.startsWith(docsBase) ? location.pathname.slice(docsBase.length).replace(/\/$/, "") : "";
  const title = `Documentation of ${DOC_TITLES[subPath] || "Business Map"}`;

  return (
    <div className="business-map-app business-map-layout bm-docs-layout">
      <BusinessMapDocumentationSidebar />
      <div className="business-map-content bm-docs-content">
        <header className="global-header bm-docs-header">
          <div className="global-header-left">
            <h1 className="global-header-title">{title}</h1>
          </div>
          <div className="global-header-actions">
            <button type="button" className="bm-docs-home-btn" title="Go to Business Map Home" onClick={() => navigate(bmBase)}>
              <FaHome />
            </button>
          </div>
        </header>
        <div className="bm-docs-scroll">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
