/**
 * pages/DashboardLogin.jsx
 * ------------------------------------------------------------
 * Dashboard-only sign-in page, served at DASHBOARD_LOGIN_PATH
 * (/community/login by default - see config/dashboardRoutes.js).
 *
 * Now backed by the real FastAPI + MS SQL backend via
 * authService.
 * ------------------------------------------------------------
 */

import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import InputField from "../components/InputField.jsx";
import FlowMotif from "../components/FlowMotif.jsx";
import { workspacePathForRole } from "../config/dashboardRoutes.js";
import { login as authLogin, forgotPassword } from "../services/authService";
import { validateEmail, validateRequired } from "../utils/validators.js";

export default function DashboardLogin() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, user } = useAuth();

  // ---- Sign-in form state ----
  const [form, setForm] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverMessage, setServerMessage] = useState(null);

  // ---- "Forgot password" inline panel state ----
  const [showForgotPanel, setShowForgotPanel] = useState(false);
  const [recoveryEmail, setRecoveryEmail] = useState("");
  const [recoveryStatus, setRecoveryStatus] = useState(null); // { type: 'success'|'error', text }
  const [isSendingLink, setIsSendingLink] = useState(false);

  // Already signed in - skip straight to the right workspace.
  if (user) {
    const target = location.state?.from || workspacePathForRole(user.role);
    return <Navigate to={target} replace />;
  }

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
    setErrors({ ...errors, [e.target.name]: null });
  }

  function handleCancel() {
    setForm({ email: "", password: "" });
    setErrors({});
    setServerMessage(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setServerMessage(null);

    const nextErrors = {};
    const emailErr = validateEmail(form.email, { checkTypo: false });
    if (emailErr) nextErrors.email = emailErr;
    const passwordErr = validateRequired(form.password, "Password is required.");
    if (passwordErr) nextErrors.password = passwordErr;
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    setIsSubmitting(true);
    try {
      const auth = await authLogin(form.email.trim(), form.password);
      login(auth.token, auth.user);
      const target = location.state?.from || workspacePathForRole(auth.user.role);
      navigate(target, { replace: true });
    } catch (err) {
      setServerMessage({ type: "error", text: err.message || "Login failed." });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSendResetLink(e) {
    e.preventDefault();
    setRecoveryStatus(null);

    const emailErr = validateEmail(recoveryEmail, { checkTypo: false });
    if (emailErr) {
      setRecoveryStatus({ type: "error", text: emailErr });
      return;
    }

    setIsSendingLink(true);
    try {
      const res = await forgotPassword(recoveryEmail.trim());
      setRecoveryStatus({
        type: "success",
        text: res?.message || "If an account with that email exists, a reset link has been sent.",
      });
    } catch (err) {
      setRecoveryStatus({ type: "error", text: err.message || "Failed to send reset link. Please try again." });
    } finally {
      setIsSendingLink(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-ink-800 px-4 py-6">
      {/* Ambient signature motif, quiet in the background */}
      <FlowMotif className="pointer-events-none absolute -right-16 -top-16 h-[420px] w-[420px] opacity-40 md:opacity-60" />
      <FlowMotif className="pointer-events-none absolute -bottom-24 -left-24 h-[380px] w-[380px] rotate-180 opacity-30" />

      <div className="relative z-10 w-full max-w-sm max-h-[94vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-card sm:p-7">
        {/* Brand mark */}
        <div className="mb-5 flex flex-col items-center text-center">
          <div className="mb-2.5 flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl bg-ink-800">
            <img src="/Icon.png" alt="OneNextGen Automation" className="h-full w-full object-contain" />
          </div>
          <h1 className="text-xl font-bold text-ink-800">Welcome back</h1>
          <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-amber-500">Workspace Login</p>
          <p className="mt-1.5 text-sm text-ink-400">Sign in to continue to your OneNextGen Automation workspace</p>
        </div>

        {!showForgotPanel ? (
          <form onSubmit={handleSubmit} className="space-y-4" id="dashboard-login-form">
            <InputField
              id="email"
              label="Email address"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="you@company.com"
              autoComplete="email"
              error={errors.email}
            />
            <InputField
              id="password"
              label="Password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="Enter your password"
              autoComplete="current-password"
              error={errors.password}
            />

            <div className="flex justify-end">
              <button
                type="button"
                id="dashboard-forgot-password-trigger"
                onClick={() => setShowForgotPanel(true)}
                className="text-sm font-medium text-ink-500 hover:text-amber-500"
              >
                Forgot password?
              </button>
            </div>

            {serverMessage && (
              <p
                className={`rounded-lg px-3 py-2 text-sm ${serverMessage.type === "error" ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"
                  }`}
                role="status"
              >
                {serverMessage.text}
              </p>
            )}

            <div className="flex gap-3 pt-1">
              <button type="submit" id="dashboard-login-submit-btn" disabled={isSubmitting} className="btn-primary-compact w-full">
                {isSubmitting ? "Signing in…" : "Sign in"}
              </button>
              <button type="button" id="dashboard-login-cancel-btn" onClick={handleCancel} className="btn-secondary-compact w-full">
                Cancel
              </button>
            </div>
          </form>
        ) : (
          // ---- Inline "verify your email" panel, shown only after clicking Forgot password ----
          <form onSubmit={handleSendResetLink} className="space-y-4" id="dashboard-forgot-password-form">
            <div>
              <h2 className="text-lg font-semibold text-ink-800">Reset your password</h2>
              <p className="mt-1 text-sm text-ink-400">
                Enter the email on your account and we'll send you a secure link to choose a new password.
              </p>
            </div>

            <InputField
              id="recoveryEmail"
              label="Email address"
              type="email"
              value={recoveryEmail}
              onChange={(e) => setRecoveryEmail(e.target.value)}
              placeholder="you@company.com"
              autoComplete="email"
            />

            {recoveryStatus && (
              <div
                className={`space-y-2 rounded-lg px-3 py-2 text-sm ${recoveryStatus.type === "error" ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"
                  }`}
                role="status"
              >
                <p>{recoveryStatus.text}</p>
              </div>
            )}

            <div className="flex gap-3 pt-1">
              <button
                type="submit"
                id="dashboard-send-reset-link-btn"
                disabled={isSendingLink}
                className="btn-primary-compact w-full"
              >
                {isSendingLink ? "Sending link…" : "Send reset link"}
              </button>
              <button
                type="button"
                id="dashboard-back-to-login-btn"
                onClick={() => {
                  setShowForgotPanel(false);
                  setRecoveryStatus(null);
                }}
                className="btn-secondary-compact w-full"
              >
                Back
              </button>
            </div>
          </form>
        )}

        <p className="mt-5 text-center text-sm text-ink-400">
          Not a workspace member?{" "}
          <Link to="/" id="dashboard-login-back-home-link" className="link-action text-ink-700">
            Back to OneNextGen Automation home
          </Link>
        </p>
      </div>
    </div>
  );
}