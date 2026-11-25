import React, { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import BusinessMapSideBar from "../Components/BusinessMapSideBar";
import BusinessMapHeader from "../Components/BusinessMapHeader";
import "../Styles/bm-common.css";

/**
 * BusinessMapLayout — mini-app layout for the Business Map product, shaped
 * exactly like Document Parser's DocumentParserLayout: its own internal
 * sidebar + an <Outlet/> for the Dashboard (index) and Business Map
 * (processor) sub-pages. Rendered for the /BusinessMap route.
 *
 * The common header (current page name + Notification, Home and Profile
 * buttons) is rendered HERE, once, above the <Outlet/>, so it stays mounted
 * and unchanged when navigating between the two pages. Switching pages is
 * done only from the sidebar.
 */
function BusinessMapLayout() {
  const { pathname } = useLocation();

  // Browser tab title for every Business Map page (Dashboard, Business Flow).
  // Re-applied on each navigation so it can never revert to an older title.
  useEffect(() => {
    document.title = "Business Map Processor";
  }, [pathname]);

  return (
    <div className="business-map-app business-map-layout">
      <BusinessMapSideBar />
      <div className="business-map-content">
        <BusinessMapHeader />
        <Outlet />
      </div>
    </div>
  );
}

export default BusinessMapLayout;
