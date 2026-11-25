import React, { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import DocumentParserSidebar from "../Components/DocumentParserSiderBar";
import { useWorkspaceSideBar } from "../../../context/WorkspaceSideBarContext";
import "../Styles/commonstyle.css";
import "../Styles/documentParser.css";

function DocumentParserLayout() {
  const location = useLocation();
  const { docExpanded, setDocExpanded, collapseAll } = useWorkspaceSideBar();

  // Set the browser tab title for all Document Parser pages opened in a new tab.
  useEffect(() => {
    document.title = "Document Parser";
  }, []);

  // NOTE: models/history/settings are scoped to the logged-in NexaFlow
  // user automatically, via the Bearer token every Document Parser
  // request now carries (see workspace/config/api.js's authFetch) --
  // no separate "tell the backend who's logged in" call is needed.

  // Process document page takes full width (no doc-parser sidebar padding needed)
  const isProcessDoc = location.pathname.includes("document-processing");

  useEffect(() => {
    if (isProcessDoc) {
      collapseAll();
    }
  }, [collapseAll, isProcessDoc, location.pathname]);

  const handleContentClick = () => {
    if (docExpanded && !isProcessDoc) {
      setDocExpanded(false);
    }
  };

  return (
    <div className="doc-parser-layout">
      <DocumentParserSidebar />
      <div 
        className={`doc-parser-content${isProcessDoc ? " doc-parser-content--full" : ""}`}
        onClick={handleContentClick}
      >
        <Outlet />
      </div>
    </div>
  );
}

export default DocumentParserLayout;