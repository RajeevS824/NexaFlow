/**
 * pages/ResetPassword.jsx
 * ------------------------------------------------------------
 * Reached via the link emailed by the "forgot password" flow:
 * /reset-password/:token
 *
 * Now backed by the real FastAPI + MS SQL backend: the token is
 * validated against the PasswordResetToken table on mount, and
 * submitting actually updates the account's password hash.
 * ------------------------------------------------------------
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import InputField from "../components/InputField.jsx";
import FlowMotif from "../components/FlowMotif.jsx";
import { validateResetToken, resetPassword } from "../services/authService";
import { validatePassword, validateConfirmPassword } from "../utils/validators.js";

export default function ResetPassword() {
  const { token } = useParams();
  const navigate = useNavigate();

  const [tokenState, setTokenState] = useState("checking"); // checking | valid | invalid
  const [form, setForm] = useState({ password: "", confirmPassword: "" });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverMessage, setServerMessage] = useState(null);
  const [isDone, setIsDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setTokenState("invalid");
      return;
    }
    (async () => {
      try {
        const valid = await validateResetToken(token);
        if (!cancelled) setTokenState(valid ? "valid" : "invalid");
      } catch {
        if (!cancelled) setTokenState("invalid");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
    setErrors({ ...errors, [e.target.name]: null });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setServerMessage(null);

    const nextErrors = {};
    const passwordErr = validatePassword(form.password);
    if (passwordErr) nextErrors.password = passwordErr;

    const confirmErr = validateConfirmPassword(form.password, form.confirmPassword);
    if (confirmErr) nextErrors.confirmPassword = confirmErr;

    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await resetPassword(token, form.password);
      setServerMessage({
        type: "success",
        text: res?.message || "Your password has been updated. You can now sign in.",
      });
      setIsDone(true);
      setTimeout(() => navigate("/login"), 1800);
    } catch (err) {
      setServerMessage({ type: "error", text: err.message || "Failed to reset your password. Please try again." });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-x-hidden overflow-y-auto bg-ink-800 px-4 py-6">
      <FlowMotif className="pointer-events-none absolute -right-16 -top-16 h-[420px] w-[420px] opacity-40" />
      <FlowMotif className="pointer-events-none absolute -bottom-24 -left-24 h-[380px] w-[380px] rotate-180 opacity-30" />

      <div className="relative z-10 w-full max-w-sm rounded-2xl bg-white p-6 shadow-card sm:p-7">
        <div className="mb-5 flex flex-col items-center text-center">
          <div className="mb-2.5 flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl bg-ink-800">
            <img src="/Icon.png" alt="OneNextGen Automation" className="h-full w-full object-contain" />
          </div>
          <h1 className="text-xl font-bold text-ink-800">Choose a new password</h1>
          <p className="mt-1 text-sm text-ink-400">
            Your new password must be different from previous passwords.
          </p>
        </div>

        {tokenState === "checking" && (
          <p className="text-center text-sm text-ink-400">Checking your reset link…</p>
        )}

        {tokenState === "invalid" && (
          <div className="space-y-4 text-center">
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
              This reset link is invalid or has expired. Please request a new one.
            </p>
            <Link to="/login" id="back-to-login-invalid" className="btn-primary-compact inline-flex w-full">
              Back to sign in
            </Link>
          </div>
        )}

        {tokenState === "valid" && !isDone && (
          <form onSubmit={handleSubmit} className="space-y-4" id="reset-password-form">
            <InputField
              id="password"
              label="New password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="At least 8 characters"
              autoComplete="new-password"
              error={errors.password}
            />
            <InputField
              id="confirmPassword"
              label="Confirm new password"
              type="password"
              value={form.confirmPassword}
              onChange={handleChange}
              placeholder="Re-enter your new password"
              autoComplete="new-password"
              error={errors.confirmPassword}
            />

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
              <button
                type="submit"
                id="set-new-password-btn"
                disabled={isSubmitting}
                className="btn-primary-compact w-full"
              >
                {isSubmitting ? "Updating…" : "Set new password"}
              </button>
              <Link to="/login" id="cancel-reset-btn" className="btn-secondary-compact w-full text-center">
                Cancel
              </Link>
            </div>
          </form>
        )}

        {isDone && (
          <p className="rounded-lg bg-green-50 px-3 py-3 text-center text-sm text-green-700">
            {serverMessage?.text} Redirecting you to sign in…
          </p>
        )}
      </div>
    </div>
  );
}