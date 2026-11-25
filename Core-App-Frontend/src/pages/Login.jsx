/**
 * pages/Login.jsx
 * ------------------------------------------------------------
 * Sign-in page. Two fields (email + password), two primary
 * actions (Sign in / Cancel). Clicking "Forgot password?"
 * reveals an inline email field used to request a reset link -
 * it does NOT navigate to a separate page, per the product
 * requirement.
 *
 * Now backed by the real FastAPI + MS SQL backend via
 * authService.
 * ------------------------------------------------------------
 */

import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import InputField from "../components/InputField.jsx";
import FlowMotif from "../components/FlowMotif.jsx";
import { login as authLogin, forgotPassword } from "../services/authService";
import { validateEmail, validateRequired } from "../utils/validators.js";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  // ---- Sign-in form state ----
  const [form, setForm] = useState({ email: location.state?.email || "", password: "" });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverMessage, setServerMessage] = useState(
    location.state?.registered
      ? { type: "success", text: "Account created! Please sign in to continue." }
      : null
  );

  // Clear the "registered" flag from history state so a page refresh
  // or back-navigation doesn't keep re-showing the success message.
  useEffect(() => {
    if (location.state?.registered) {
      navigate(location.pathname, { replace: true, state: {} });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- "Forgot password" inline panel state ----
  const [showForgotPanel, setShowForgotPanel] = useState(false);
  const [recoveryEmail, setRecoveryEmail] = useState("");
  const [recoveryStatus, setRecoveryStatus] = useState(null); // { type: 'success'|'error', text }
  const [isSendingLink, setIsSendingLink] = useState(false);

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
    // Sign-in is against an existing account, so we only check the format
    // here (not likely-typo domains) - a real typo will simply fail auth.
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
      const role = auth.user.role;
      const target = role === "admin" ? "/admin-panel" : "/dashboard";
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

      <div className="relative z-10 w-full max-w-sm max-h-[94vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-card sm:p-8">
        {/* Brand mark */}
        <div className="mb-5 flex flex-col items-center text-center">
          <div className="mb-2.5 flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl bg-ink-800">
            <img src="/Icon.png" alt="OneNextGen Automation" className="h-full w-full object-contain" />
          </div>
          <h1 className="text-xl font-bold text-ink-800">Welcome back</h1>
          <p className="mt-1 text-sm text-ink-400">Sign in to continue to your OneNextGen Automation workspace</p>
        </div>

        {!showForgotPanel ? (
          <form onSubmit={handleSubmit} className="space-y-4" id="login-form">
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
                id="forgot-password-trigger"
                onClick={() => setShowForgotPanel(true)}
                className="text-sm font-medium text-ink-500 hover:text-amber-500"
              >
                Forgot password?
              </button>
            </div>

            {serverMessage && (
              <p
                className={`rounded-lg px-3 py-2 text-sm ${serverMessage.type === "error"
                    ? "bg-red-50 text-red-600"
                    : "bg-green-50 text-green-700"
                  }`}
                role="status"
              >
                {serverMessage.text}
              </p>
            )}

            <div className="flex gap-3 pt-1">
              <button type="submit" id="login-submit-btn" disabled={isSubmitting} className="btn-primary-compact w-full">
                {isSubmitting ? "Signing in…" : "Sign in"}
              </button>
              <button type="button" id="login-cancel-btn" onClick={handleCancel} className="btn-secondary-compact w-full">
                Cancel
              </button>
            </div>
          </form>
        ) : (
          // ---- Inline "verify your email" panel, shown only after clicking Forgot password ----
          <form onSubmit={handleSendResetLink} className="space-y-4" id="forgot-password-form">
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
                className={`space-y-2 rounded-lg px-3 py-2 text-sm ${recoveryStatus.type === "error"
                    ? "bg-red-50 text-red-600"
                    : "bg-green-50 text-green-700"
                  }`}
                role="status"
              >
                <p>{recoveryStatus.text}</p>
              </div>
            )}

            <div className="flex gap-3 pt-1">
              <button
                type="submit"
                id="send-reset-link-btn"
                disabled={isSendingLink}
                className="btn-primary-compact w-full"
              >
                {isSendingLink ? "Sending link…" : "Send reset link"}
              </button>
              <button
                type="button"
                id="back-to-login-btn"
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
          New to OneNextGen Automation?{" "}
          <Link to="/register" id="go-to-register-link" className="link-action text-ink-700">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}