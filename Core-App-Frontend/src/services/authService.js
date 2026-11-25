/**
 * src/services/authService.js
 * ------------------------------------------------------------
 * Frontend auth service: login, register, logout, session restore.
 * Stores token + user in sessionStorage (NOT localStorage) so the
 * session survives an in-tab page refresh but ends when the tab/
 * browser is closed -- a bookmarked workspace URL must always ask
 * for login again after the browser was fully closed and reopened.
 */
import { apiFetch } from "./api";

const STORAGE_KEY = "nexaflow_auth";

export function getStoredAuth() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredAuth(auth) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
}

export function clearStoredAuth() {
  sessionStorage.removeItem(STORAGE_KEY);
  sessionStorage.removeItem("nexaflow_token");
}

export async function login(email, password) {
  const data = await apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  const auth = {
    token: data.token,
    user: {
      id: data.user_id,
      fullName: data.full_name,
      email: data.email,
      role: data.role,
      accountType: data.account_type || "enterprise",
      orgId: data.org_id,
      orgName: data.org_name,
      products: data.products || [],
    },
  };

  sessionStorage.setItem("nexaflow_token", auth.token);
  setStoredAuth(auth);
  return auth;
}

export async function register(fullName, email, companyName, password) {
  const data = await apiFetch("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ full_name: fullName, email, company_name: companyName, password }),
  });

  const auth = {
    token: data.token,
    user: {
      id: data.user_id,
      fullName: data.full_name,
      email: data.email,
      role: data.role,
      accountType: data.account_type || "community",
      orgId: data.org_id,
      orgName: data.org_name,
      products: data.products || [],
    },
  };

  sessionStorage.setItem("nexaflow_token", auth.token);
  setStoredAuth(auth);
  return auth;
}

export function logout() {
  clearStoredAuth();
}

/**
 * Request a password-reset email. Resolves with a generic
 * { message } response regardless of whether the email matched an
 * account (the backend intentionally doesn't reveal that), but
 * throws if the email genuinely failed to send (e.g. SMTP issue).
 */
export async function forgotPassword(email) {
  return apiFetch("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

/** Check whether a reset-password token is still valid (unused + unexpired). */
export async function validateResetToken(token) {
  const data = await apiFetch(`/api/auth/reset-password/${encodeURIComponent(token)}/validate`, {
    method: "GET",
  });
  return !!data?.valid;
}

/** Set a new password using a valid reset token. */
export async function resetPassword(token, newPassword) {
  return apiFetch("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}