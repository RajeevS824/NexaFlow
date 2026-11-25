/**
 * pages/Register.jsx
 * ------------------------------------------------------------
 * Registration page, split into two portions:
 *  - Left: brand panel (logo, company name, value proposition)
 *  - Right: the registration form
 *
 * Now backed by the real FastAPI + MS SQL backend via
 * authService. On success, the user is NOT auto-logged in -
 * they're redirected to the login page to sign in with the
 * credentials they just created (Register -> Login -> Workspace).
 * ------------------------------------------------------------
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import InputField from "../components/InputField.jsx";
import FlowMotif from "../components/FlowMotif.jsx";
import { register as authRegister } from "../services/authService";
import {
  validateFullName,
  validateEmail,
  validateCompanyName,
  validatePassword,
  validateConfirmPassword,
} from "../utils/validators.js";

const initialForm = {
  fullName: "",
  email: "",
  companyName: "",
  password: "",
  confirmPassword: "",
};

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverMessage, setServerMessage] = useState(null);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
    setErrors({ ...errors, [e.target.name]: null });
  }

  function validate() {
    const next = {};
    const nameErr = validateFullName(form.fullName);
    if (nameErr) next.fullName = nameErr;

    const emailErr = validateEmail(form.email);
    if (emailErr) next.email = emailErr;

    const companyErr = validateCompanyName(form.companyName);
    if (companyErr) next.companyName = companyErr;

    const passwordErr = validatePassword(form.password);
    if (passwordErr) next.password = passwordErr;

    const confirmErr = validateConfirmPassword(form.password, form.confirmPassword);
    if (confirmErr) next.confirmPassword = confirmErr;

    return next;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setServerMessage(null);

    const validationErrors = validate();
    if (Object.keys(validationErrors).length) {
      setErrors(validationErrors);
      return;
    }

    setIsSubmitting(true);
    try {
      await authRegister(form.fullName.trim(), form.email.trim(), form.companyName.trim(), form.password);
      navigate("/login", {
        replace: true,
        state: {
          registered: true,
          email: form.email.trim(),
        },
      });
    } catch (err) {
      setServerMessage({ type: "error", text: err.message || "Registration failed." });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* ---------------- Left: company / brand panel ---------------- */}
      <div className="relative flex w-full flex-col justify-between overflow-hidden bg-ink-800 px-8 py-10 text-white md:w-1/2 md:px-14 md:py-14">
        <FlowMotif className="pointer-events-none absolute -bottom-20 -right-20 h-[440px] w-[440px] opacity-40" />

        {/* Logo + company name, top-left */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-xl bg-white">
            <img src="/Icon.png" alt="OneNextGen Automation" className="h-full w-full object-contain" />
          </div>
          <span className="font-display text-xl font-semibold tracking-tight">OneNextGen Automation</span>
        </div>

        {/* Value proposition, middle of panel */}
        <div className="relative z-10 max-w-md">
          <h2 className="font-display text-3xl font-semibold leading-tight sm:text-4xl">
            Automation, without the friction.
          </h2>
          <p className="mt-4 text-base text-ink-100/80">
            OneNextGen Automation connects your everyday tools into automated workflows, so your
            team spends less time on repetitive steps and more time on real work.
          </p>

          <ul className="mt-8 space-y-3 text-sm text-ink-100/85">
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-amber-400">●</span>
              Build workflows visually - no code required to get started.
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-amber-400">●</span>
              Connect the apps your team already uses in minutes.
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-amber-400">●</span>
              Monitor every run with clear, real-time activity logs.
            </li>
          </ul>
        </div>

        {/* Footer note */}
        <p className="relative z-10 text-xs text-ink-100/50">
          © {new Date().getFullYear()} OneNextGen Automation, Inc.
        </p>
      </div>

      {/* ---------------- Right: registration form ---------------- */}
      <div className="flex w-full flex-1 items-center justify-center bg-slate-25 px-6 py-12 md:w-1/2 md:px-14">
        <div className="w-full max-w-md">
          <h1 className="text-2xl font-bold text-ink-800 sm:text-3xl">
            Registration required for new users
          </h1>
          <p className="mt-2 text-sm text-ink-400">
            Fill in a few details below to set up your free workspace and start
            automating your first workflow today.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5" id="register-form">
            <InputField
              id="fullName"
              label="Full name"
              value={form.fullName}
              onChange={handleChange}
              placeholder="Jordan Rivera"
              autoComplete="name"
              error={errors.fullName}
            />
            <InputField
              id="email"
              label="Work email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="you@company.com"
              autoComplete="email"
              error={errors.email}
            />
            <InputField
              id="companyName"
              label="Company name"
              value={form.companyName}
              onChange={handleChange}
              placeholder="Acme Corporation"
              autoComplete="organization"
              required={false}
              error={errors.companyName}
            />
            <InputField
              id="password"
              label="Password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="At least 8 characters"
              autoComplete="new-password"
              error={errors.password}
            />
            <InputField
              id="confirmPassword"
              label="Confirm password"
              type="password"
              value={form.confirmPassword}
              onChange={handleChange}
              placeholder="Re-enter your password"
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

            <button
              type="submit"
              id="create-account-btn"
              disabled={isSubmitting}
              className="btn-primary w-full"
            >
              {isSubmitting ? "Creating your account…" : "Create my free account"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-400">
            Already have an account?{" "}
            <Link to="/login" id="go-to-login-link" className="link-action text-ink-700">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}