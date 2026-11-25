/**
 * components/RoleRoute.jsx
 * ------------------------------------------------------------
 * Sits inside ProtectedRoute (so `user` is guaranteed to exist)
 * and enforces which workspace URL a role is allowed on:
 *   - admins   -> always /community/admin-panel
 *   - everyone else -> always /community/dashboard
 *
 * This is what makes the URL itself say "admin panel" for
 * admins instead of "dashboard" - if an admin somehow lands on
 * the user URL (or vice versa) they're bounced to the correct
 * one automatically.
 * ------------------------------------------------------------
 */

import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { workspacePathForRole } from "../config/dashboardRoutes.js";

export default function RoleRoute({ allow, children }) {
  const { user } = useAuth();
  const role = user?.role === "admin" ? "admin" : "user";

  if (role !== allow) {
    return <Navigate to={workspacePathForRole(role)} replace />;
  }

  return children;
}
