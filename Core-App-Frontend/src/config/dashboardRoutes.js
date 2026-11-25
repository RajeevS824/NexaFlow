/**
 * config/dashboardRoutes.js
 * ------------------------------------------------------------
 * Single source of truth for the dashboard's URLs.
 *
 * Only the workspace's own login page keeps the "community"
 * segment - that's the one URL people need to recognize as
 * "the dashboard sign-in page". The dashboard and admin panel
 * themselves use short, clean URLs:
 *
 *   /community/login   -> dashboard-only sign-in page
 *   /dashboard          -> workspace for regular users
 *   /admin-panel        -> workspace for admin users
 *
 * Admins are always routed to /admin-panel instead of
 * /dashboard (that's the "show admin panel instead of
 * dashboard in the URL" requirement) - see App.jsx for the
 * role-based redirects that enforce this.
 * ------------------------------------------------------------
 */

export const DASHBOARD_BASE = "community";

export const DASHBOARD_LOGIN_PATH = `/${DASHBOARD_BASE}/login`;
export const DASHBOARD_USER_PATH = `/dashboard`;
export const DASHBOARD_ADMIN_PATH = `/admin-panel`;

/** Returns the correct workspace root for a given user's role. */
export function workspacePathForRole(role) {
  return role === "admin" ? DASHBOARD_ADMIN_PATH : DASHBOARD_USER_PATH;
}
