/**
 * context/AuthContext.jsx
 * ------------------------------------------------------------
 * Global auth state backed by sessionStorage so the session
 * survives page refreshes within a tab, but ends when the tab or
 * browser is closed. On startup it restores the last logged-in
 * user and token, then validates the session by calling
 * GET /api/auth/me.
 *
 * If the stored token is invalid/expired, it clears auth and
 * the user is treated as logged out.
 *
 * CROSS-TAB SYNC: a tab opened with window.open() or "duplicate
 * tab" (e.g. the Document Parser "Process" tab, or a manually
 * duplicated workspace tab) gets its own independent copy of
 * sessionStorage, so signing in or out in one tab does not, by
 * itself, affect any other open tab. A BroadcastChannel is used to
 * tell every open tab from this app "sign in as this user" or
 * "sign out now" the moment login()/logout() runs anywhere, and
 * each tab mirrors the change into its own sessionStorage so a
 * later refresh in that tab keeps it in sync too. Any tab this one
 * opened directly is also closed outright on logout (see
 * workspace/utils/childWindows.js).
 */
import { createContext, useContext, useEffect, useRef, useState } from "react";

import { getStoredAuth, setStoredAuth, clearStoredAuth } from "../services/authService";
import { apiFetch } from "../services/api";
import { closeAllChildWindows } from "../workspace/utils/childWindows.js";
import {
  hasActiveBusinessMapJob,
  cancelBusinessMapJobsBeforeLogout,
} from "../workspace/utils/businessMapLogoutCancel.js";

const AuthContext = createContext(null);
const SYNC_CHANNEL_NAME = "nexaflow-auth";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isReady, setIsReady] = useState(false);
  const channelRef = useRef(null);
  const loggingOutRef = useRef(false);

  // Restore session from sessionStorage on mount
  useEffect(() => {
    const stored = getStoredAuth();
    if (!stored?.token || !stored?.user) {
      setIsReady(true);
      return;
    }

    const savedToken = stored.token;
    const savedUser = stored.user;

    // Lightweight validation: try /api/auth/me with the stored token.
    // If it fails, the session is stale/expired — clear it.
    apiFetch("/api/auth/me")
      .then((me) => {
        const normalized = {
          ...savedUser,
          id: me.user_id ?? savedUser.id,
          fullName: me.full_name ?? savedUser.fullName,
          email: me.email ?? savedUser.email,
          role: me.role ?? savedUser.role,
          accountType: me.account_type ?? savedUser.accountType,
          orgId: me.org_id ?? savedUser.orgId,
          orgName: me.org_name ?? savedUser.orgName,
          products: me.products ?? savedUser.products ?? [],
        };
        setToken(savedToken);
        setUser(normalized);
      })
      .catch(() => {
        clearStoredAuth();
      })
      .finally(() => {
        setIsReady(true);
      });
  }, []);

  // Listen for a login/logout broadcast from any other tab of this app
  // and mirror it here immediately. This is what makes signing in (or
  // out) in one tab also sign in (or out) a duplicated tab, or a
  // Document Parser "Process" tab opened separately.
  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return undefined;

    const channel = new BroadcastChannel(SYNC_CHANNEL_NAME);
    channelRef.current = channel;
    channel.onmessage = (event) => {
      const msg = event.data;
      if (!msg || typeof msg !== "object") return;

      if (msg.type === "login" && msg.token && msg.user) {
        setStoredAuth({ token: msg.token, user: msg.user });
        setToken(msg.token);
        setUser(msg.user);
      } else if (msg.type === "logout") {
        clearStoredAuth();
        setToken(null);
        setUser(null);
      }
    };

    return () => {
      channel.close();
      channelRef.current = null;
    };
  }, []);

  function login(newToken, userData) {
    setToken(newToken);
    setUser(userData);
    // Tell every other open tab of this app to sign in as this user too.
    channelRef.current?.postMessage({ type: "login", token: newToken, user: userData });
  }

  function logout() {
    // If a Business Map job is still running in this browser, cancel it first
    // (the same as Business Map's own Logout buttons), then sign out. Without a
    // running job this stays synchronous, exactly as before.
    if (hasActiveBusinessMapJob()) {
      if (loggingOutRef.current) return Promise.resolve();
      loggingOutRef.current = true;
      return cancelBusinessMapJobsBeforeLogout().finally(() => {
        loggingOutRef.current = false;
        finishLogout();
      });
    }
    finishLogout();
  }

  function finishLogout() {
    setToken(null);
    setUser(null);
    clearStoredAuth();
    // Close any tab this one opened directly (e.g. a Document Parser
    // processing tab) - it holds its own session copy and would
    // otherwise keep running as if still signed in.
    closeAllChildWindows();
    // Tell every other open tab of this app to sign out too.
    channelRef.current?.postMessage({ type: "logout" });
  }

  return (
    <AuthContext.Provider value={{ user, token, isReady, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
