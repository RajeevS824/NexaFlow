/**
 * pages/RequestDemo.jsx
 * ------------------------------------------------------------
 * Reached via the "Request demo" button in the header (top
 * right, on every page). Same field set as the registration /
 * contact forms, submitted through the same mock service.
 * ------------------------------------------------------------
 */

import { useState } from "react";
import Header from "../components/Header.jsx";
import Footer from "../components/Footer.jsx";
import InputField from "../components/InputField.jsx";
import { submitDemoRequest } from "../services/contactService.js";
import { validateFullName, validateEmail, validateCompanyName } from "../utils/validators.js";

const initialForm = { fullName: "", email: "", companyName: "", message: "" };

export default function RequestDemo() {
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

    if (!form.companyName.trim()) {
      next.companyName = "Company name helps us tailor your demo.";
    } else {
      const companyErr = validateCompanyName(form.companyName);
      if (companyErr) next.companyName = companyErr;
    }
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
      const res = await submitDemoRequest(form);
      setServerMessage({
        type: "success",
        text: res?.message || "Thanks! A member of our team will reach out to schedule your demo shortly.",
      });
      setForm(initialForm);
    } catch (err) {
      setServerMessage({
        type: "error",
        text: err.message || "Something went wrong submitting your request. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-25">
      <Header />

      <section className="px-6 py-16 sm:px-10">
        <div className="mx-auto grid max-w-5xl gap-12 lg:grid-cols-2">
          {/* Left: context copy */}
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-amber-500">See it in action</p>
            <h1 className="mt-3 font-display text-3xl font-semibold text-ink-800 sm:text-4xl">
              Request a personalized demo
            </h1>
            <p className="mt-4 max-w-md text-ink-400">
              Tell us a bit about your team and what you'd like to automate.
              We'll walk you through Nextflow, Business Process Mapper, and
              Document Parser using examples relevant to your workflow.
            </p>
            <ul className="mt-8 space-y-3 text-sm text-ink-500">
              <li className="flex items-start gap-2">
                <span className="mt-0.5 text-amber-500">●</span>
                A 30-minute walkthrough tailored to your use case
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 text-amber-500">●</span>
                Time to ask questions with a product specialist
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 text-amber-500">●</span>
                No pressure — just a clear look at what's possible
              </li>
            </ul>
          </div>

          {/* Right: form */}
          <form onSubmit={handleSubmit} id="request-demo-form" className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm sm:p-8">
            <div className="space-y-5">
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
                error={errors.companyName}
              />
              <div className="w-full">
                <label htmlFor="message" className="mb-1.5 block text-sm font-medium text-ink-700">
                  What would you like to automate? (optional)
                </label>
                <textarea
                  id="message"
                  name="message"
                  rows={3}
                  value={form.message}
                  onChange={handleChange}
                  placeholder="e.g. Invoice processing, employee onboarding, report generation…"
                  className="w-full rounded-lg border border-ink-200 bg-white px-4 py-3 text-ink-800 placeholder:text-ink-300 focus:border-amber-400 focus:ring-2 focus:ring-amber-400/30 transition-colors"
                />
              </div>

              {serverMessage && (
                <p
                  className={`rounded-lg px-3 py-2 text-sm ${
                    serverMessage.type === "error" ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"
                  }`}
                  role="status"
                >
                  {serverMessage.text}
                </p>
              )}

              <button type="submit" id="request-demo-submit-btn" disabled={isSubmitting} className="btn-primary w-full">
                {isSubmitting ? "Submitting…" : "Request my demo"}
              </button>
            </div>
          </form>
        </div>
      </section>

      <Footer />
    </div>
  );
}
