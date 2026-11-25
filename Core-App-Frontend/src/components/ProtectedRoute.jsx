/**
 * components/ProtectedRoute.jsx
 * ------------------------------------------------------------
 * Wraps a page and redirects to a login page if there is no
 * authenticated user in context yet. This runs on every direct
 * load/bookmark of a protected URL, not just on in-app
 * navigation, so a bookmarked dashboard link always gets
 * checked for a valid session first.
 *
 * `redirectTo` defaults to the marketing site's "/login", but
 * the dashboard routes pass DASHBOARD_LOGIN_PATH instead so a
 * bookmarked "/community/dashboard" (or "/community/admin-panel")
 * sends an unauthenticated visitor to the dashboard's own sign-in
 * page rather than the marketing one.
 * ------------------------------------------------------------
 */

import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function ProtectedRoute({ children, redirectTo = "/login" }) {
  const { user, isReady } = useAuth();
  const location = useLocation();

  if (!isReady) return null; // wait for the sessionStorage check to finish
  if (!user) {
    return <Navigate to={redirectTo} state={{ from: location.pathname }} replace />;
  }

  return children;
}
