/**
 * workspace/WorkspaceApp.jsx
 * ------------------------------------------------------------
 * The real NexaFlow RPA automation workspace. Mounted at both
 * DASHBOARD_USER_PATH and DASHBOARD_ADMIN_PATH in App.jsx,
 * behind ProtectedRoute + RoleRoute, so only a signed-in user
 * of the matching role can reach it.
 *
 * Routes differ by role:
 *   Regular user (relative to /dashboard):
 *     /                 -> WorkspaceDashboard
 *     /BusinessMap      -> BusinessMap
 *     /document-parser  -> DocumentParser
 *     /nextflow         -> Nextflow
 *
 *   Admin (relative to /admin-panel):
 *     /                 -> WorkspaceDashboard
 *     /role             -> RoleManagement
 *     /products         -> ManageProducts
 *     /role-permission  -> RolePermission
 *     /users            -> Users
 * ------------------------------------------------------------
 */

import React from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";

import AdminSideBar from "./Tool-Applications/Admin-pages/components/AdminSideBar";
import WorkspaceSideBar from "./components/WorkspaceSideBar";
import WorkspaceDashboard from "./pages/WorkspaceDashboard";
import BusinessMapLayout from "./Tool-Applications/Business-Process-Mapper/Pages/BusinessMapLayout";
import BusinessMapDashboard from "./Tool-Applications/Business-Process-Mapper/Pages/Dashboard";
import BusinessMapProcessor from "./Tool-Applications/Business-Process-Mapper/Pages/BusinessMap";
import BusinessMapSettings from "./Tool-Applications/Business-Process-Mapper/Pages/BusinessMapSettings";
import BusinessMapDocumentationLayout from "./Tool-Applications/Business-Process-Mapper/Pages/documentation/BusinessMapDocumentationLayout";
import BusinessMapOverview from "./Tool-Applications/Business-Process-Mapper/Pages/documentation/pages/Overview";
import BusinessMapDashboardDocumentation from "./Tool-Applications/Business-Process-Mapper/Pages/documentation/pages/DashboardDocumentation";
import BusinessFlowDocumentation from "./Tool-Applications/Business-Process-Mapper/Pages/documentation/pages/BusinessFlowDocumentation";
import PipelineDocumentation from "./Tool-Applications/Business-Process-Mapper/Pages/documentation/pages/PipelineDocumentation";
import BusinessMapSettingsDocumentation from "./Tool-Applications/Business-Process-Mapper/Pages/documentation/pages/SettingsDocumentation";
import BusinessMapFAQ from "./Tool-Applications/Business-Process-Mapper/Pages/documentation/pages/FAQ";
import BusinessMapTroubleshooting from "./Tool-Applications/Business-Process-Mapper/Pages/documentation/pages/Troubleshooting";
import DocumentParser from "./Tool-Applications/Document-Parser/Pages/DocumentParser";
import DocumentParserLayout from "./Tool-Applications/Document-Parser/Pages/DocumentParserLayout";
import DocumentParserSettings from "./Tool-Applications/Document-Parser/Pages/DocumentParserSettings";
import Nextflow from "./Tool-Applications/WorkFlow-Automation/Nextflow";
import RoleManagement from "./Tool-Applications/Admin-pages/Pages/RoleManagement";
import ManageProducts from "./Tool-Applications/Admin-pages/Pages/ManageProducts";
import RolePermission from "./Tool-Applications/Admin-pages/Pages/RolePermission";
import Users from "./Tool-Applications/Admin-pages/Pages/Users";
import ProductSettings from "./pages/ProductSettings";

// Document Parser sub-pages
import CreateExtractionModel from "./Tool-Applications/Document-Parser/Pages/CreateExtractionModel";
import SubCreateExtractionModel from "./Tool-Applications/Document-Parser/Pages/SubCreateExtractionModel";
import ProcessExtractionModel from "./Tool-Applications/Document-Parser/Pages/ProcessExtractionModel";
import ViewExtractionModel from "./Tool-Applications/Document-Parser/Pages/ViewExtractionModel";
import ProcessDocument from "./Tool-Applications/Document-Parser/Pages/ProcessDocument";
import DocumentationLayout from "./Tool-Applications/Document-Parser/Pages/documentation/DocumentationLayout";
import Overview from "./Tool-Applications/Document-Parser/Pages/documentation/pages/Overview";
import DashboardDocumentation from "./Tool-Applications/Document-Parser/Pages/documentation/pages/DashboardDocumentation";
import CreateProcessModelDocumentation from "./Tool-Applications/Document-Parser/Pages/documentation/pages/CreateProcessModelDocumentation";
import CreateProcessFieldsDocumentation from "./Tool-Applications/Document-Parser/Pages/documentation/pages/CreateProcessFieldsDocumentation";
import DocumentProcessModelDocumentation from "./Tool-Applications/Document-Parser/Pages/documentation/pages/DocumentProcessModelDocumentation";
import DocumentProcessingDocumentation from "./Tool-Applications/Document-Parser/Pages/documentation/pages/DocumentProcessingDocumentation";
import HistoryExtractionModelDocumentation from "./Tool-Applications/Document-Parser/Pages/documentation/pages/HistoryExtractionModelDocumentation";
import ValidationDocumentation from "./Tool-Applications/Document-Parser/Pages/documentation/pages/ValidationDocumentation";
import FAQ from "./Tool-Applications/Document-Parser/Pages/documentation/pages/FAQ";
import Troubleshooting from "./Tool-Applications/Document-Parser/Pages/documentation/pages/Troubleshooting";

import { BusinessMapProvider } from "./context/BusinessMapContext";
import { WorkspaceSideBarProvider } from "./context/WorkspaceSideBarContext";
import { AdminRoleProvider } from "./context/AdminRoleContext";
import { DPUnsavedChangesProvider } from "./context/DP-UnsavedChangesContext";
import { useAuth } from "../context/AuthContext.jsx";
import { DASHBOARD_USER_PATH, DASHBOARD_ADMIN_PATH } from "../config/dashboardRoutes.js";

import "./styles/commonstyle.css";

export default function WorkspaceApp() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const basePath = isAdmin ? DASHBOARD_ADMIN_PATH : DASHBOARD_USER_PATH;
  const location = useLocation();

  // When on a document-parser route, hide the main sidebar so only the
  // DocumentParserSidebar (rendered inside DocumentParserLayout) is visible.
  // NOTE: must match "/document-parser" itself or its sub-routes only —
  // a plain startsWith("/document-parser") also matches the unrelated
  // "/document-parser-settings" page, which incorrectly hid the main
  // sidebar there too.
  const docParserBase = `${basePath}/document-parser`;
  const isDocParserRoute =
    location.pathname === docParserBase || location.pathname.startsWith(`${docParserBase}/`);

  // Same for Business Map: hide the main sidebar while inside the Business
  // Map mini-app so only BusinessMapSideBar (rendered inside
  // BusinessMapLayout) shows. NOTE: "/business-process-mapper/settings" is
  // NOT matched here — that stays under the regular settings flow with the
  // main sidebar visible.
  const businessMapBase = `${basePath}/BusinessMap`;
  const isBusinessMapRoute =
    location.pathname === businessMapBase || location.pathname.startsWith(`${businessMapBase}/`);

  // Product access is now driven by the logged-in user's product list
  // returned from the backend on login, not by the static PRODUCTS catalog.
  const accessibleProductSlugs = new Set((user?.products || []).map((p) => p.slug));
  const isProductEnabled = (slug) => accessibleProductSlugs.has(slug);

  return (
    <WorkspaceSideBarProvider>
      <AdminRoleProvider>
        <BusinessMapProvider>
          <DPUnsavedChangesProvider>
            <div className="dashboard">
              {!isDocParserRoute && !isBusinessMapRoute && (isAdmin ? <AdminSideBar isDashboard={true} isAdmin={isAdmin} basePath={basePath} /> : <WorkspaceSideBar isDashboard={true} isAdmin={isAdmin} basePath={basePath} />)}
              <div className="right-section">
                <Routes>
                  <Route path="/" element={<WorkspaceDashboard isAdmin={isAdmin} basePath={basePath} />} />
                  <Route path="settings/business-process-mapper" element={<BusinessMapSettings />} />
                  <Route path="settings/:slug" element={<ProductSettings />} />
                  <Route path="document-parser-settings" element={<DocumentParserSettings />} />
                  {isAdmin ? (
                    <>
                      <Route path="role" element={<RoleManagement />} />
                      <Route path="products" element={<ManageProducts />} />
                      <Route path="role-permission" element={<RolePermission />} />
                      <Route path="users" element={<Users />} />
                    </>
                  ) : (
                    <>
                      <Route
                        path="BusinessMap"
                        element={isProductEnabled("business-process-mapper") ? <BusinessMapLayout /> : <Navigate to={basePath} replace />}
                      >
                        {/* Business Map mini-app — layout renders its own
                            internal sidebar; index = Dashboard, sub-route =
                            the upload/process Business Map screen */}
                        <Route index element={<BusinessMapDashboard />} />
                        <Route path="processor" element={<BusinessMapProcessor />} />
                      </Route>
                      {/* Document Parser — layout provides the doc-parser sidebar,
                          index route renders the dashboard, sub-routes render
                          the create/process/history pages inside the layout's Outlet */}
                      <Route
                        path="document-parser"
                        element={isProductEnabled("document-parser") ? <DocumentParserLayout /> : <Navigate to={basePath} replace />}
                      >
                        <Route index element={<DocumentParser />} />
                        <Route path="create-process-model" element={<CreateExtractionModel />} />
                        <Route path="create-process-model/create-process-field" element={<SubCreateExtractionModel />} />
                        <Route path="document-process-model" element={<ProcessExtractionModel />} />
                        <Route path="history-process-model" element={<ViewExtractionModel />} />
                        <Route path="document-processing" element={<ProcessDocument />} />
                      </Route>
                      <Route
                        path="nextflow"
                        element={isProductEnabled("nextflow") ? <Nextflow /> : <Navigate to={basePath} replace />}
                      />
                      <Route path="BusinessMap/documentation" element={isProductEnabled("business-process-mapper") ? <BusinessMapDocumentationLayout /> : <Navigate to={basePath} replace />}>
                        <Route index element={<BusinessMapOverview />} />
                        <Route path="dashboard" element={<BusinessMapDashboardDocumentation />} />
                        <Route path="business-flow" element={<BusinessFlowDocumentation />} />
                        <Route path="pipeline" element={<PipelineDocumentation />} />
                        <Route path="settings" element={<BusinessMapSettingsDocumentation />} />
                        <Route path="faq" element={<BusinessMapFAQ />} />
                        <Route path="troubleshooting" element={<BusinessMapTroubleshooting />} />
                      </Route>
                      <Route path="document-parser/documentation" element={<DocumentationLayout />}>
                        <Route index element={<Overview />} />
                        <Route path="dashboard" element={<DashboardDocumentation />} />
                        <Route path="create-process-model" element={<CreateProcessModelDocumentation />} />
                        <Route path="create-process-fields" element={<CreateProcessFieldsDocumentation />} />
                        <Route path="document-process-model" element={<DocumentProcessModelDocumentation />} />
                        <Route path="document-processing" element={<DocumentProcessingDocumentation />} />
                        <Route path="history" element={<HistoryExtractionModelDocumentation />} />
                        <Route path="validation" element={<ValidationDocumentation />} />
                        <Route path="faq" element={<FAQ />} />
                        <Route path="troubleshooting" element={<Troubleshooting />} />
                      </Route>
                    </>
                  )}
                </Routes>
              </div>
            </div>
          </DPUnsavedChangesProvider>
        </BusinessMapProvider>
      </AdminRoleProvider>
    </WorkspaceSideBarProvider>
  );
}