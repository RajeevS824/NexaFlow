/**
 * App.jsx
 * ------------------------------------------------------------
 * Top-level route table for the NexaFlow frontend.
 *
 * The Home page ("/") is the public marketing site (header,
 * about, product cards, contact, footer) and does not require
 * login. "/home" is kept as a redirect for backward
 * compatibility with any old links/bookmarks.
 *
 * Only the dashboard's login page carries the "/community"
 * prefix (see config/dashboardRoutes.js). The workspace URLs
 * themselves are plain, as before:
 *
 *   /community/login  -> DashboardLogin (dashboard-only sign-in)
 *   /dashboard/*       -> WorkspaceApp, regular users
 *   /admin-panel/*     -> WorkspaceApp, admins only (no "dashboard" in the URL)
 *
 * ProtectedRoute re-checks the session on every load (so a
 * bookmarked dashboard URL never opens without auth), and
 * RoleRoute keeps admins on /admin-panel and everyone else on
 * /dashboard, redirecting automatically if the two don't match.
 * ------------------------------------------------------------
 */

import { Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import Home from "./pages/Home.jsx";
import ProductDetail from "./pages/ProductDetail.jsx";
import NotFound from "./pages/NotFound.jsx";
import DashboardLogin from "./pages/DashboardLogin.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import RoleRoute from "./components/RoleRoute.jsx";
import WorkspaceApp from "./workspace/WorkspaceApp.jsx";
import {
  DASHBOARD_BASE,
  DASHBOARD_LOGIN_PATH,
  DASHBOARD_USER_PATH,
  DASHBOARD_ADMIN_PATH,
} from "./config/dashboardRoutes.js";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      {/* Backward-compatible alias for the old post-login destination */}
      <Route path="/home" element={<Navigate to="/" replace />} />

      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/reset-password/:token" element={<ResetPassword />} />

      <Route path="/products/:slug" element={<ProductDetail />} />
      {/* Old standalone page: forward bookmarks to the Contact section */}
      <Route path="/request-demo" element={<Navigate to="/#contact" state={{ demo: true }} replace />} />

      {/* Dashboard's own sign-in page - checked fresh on every bookmarked visit */}
      <Route path={DASHBOARD_LOGIN_PATH} element={<DashboardLogin />} />
      {/* Bare "/community" conveniently forwards to the dashboard's login */}
      <Route path={`/${DASHBOARD_BASE}`} element={<Navigate to={DASHBOARD_LOGIN_PATH} replace />} />

      {/* Old "/community/dashboard" and "/community/admin-panel" bookmarks
          from before the URL was shortened still resolve correctly */}
      <Route path={`/${DASHBOARD_BASE}/dashboard/*`} element={<Navigate to={DASHBOARD_USER_PATH} replace />} />
      <Route path={`/${DASHBOARD_BASE}/admin-panel/*`} element={<Navigate to={DASHBOARD_ADMIN_PATH} replace />} />

      {/* Regular-user workspace */}
      <Route
        path={`${DASHBOARD_USER_PATH}/*`}
        element={
          <ProtectedRoute redirectTo={DASHBOARD_LOGIN_PATH}>
            <RoleRoute allow="user">
              <WorkspaceApp />
            </RoleRoute>
          </ProtectedRoute>
        }
      />

      {/* Admin workspace - same app, admin-only nav, admin-only URL */}
      <Route
        path={`${DASHBOARD_ADMIN_PATH}/*`}
        element={
          <ProtectedRoute redirectTo={DASHBOARD_LOGIN_PATH}>
            <RoleRoute allow="admin">
              <WorkspaceApp />
            </RoleRoute>
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
