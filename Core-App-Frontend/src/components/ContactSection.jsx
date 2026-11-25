/**
 * components/ContactSection.jsx
 * ------------------------------------------------------------
 * The "Contact us" section shown on the Home page (id="contact"),
 * scrolled to from the header's "Contact us" link.
 *
 * Fields reuse the same set as the Registration page (full name,
 * work email, company name), plus a message field — a contact
 * form isn't useful without somewhere to say what you need, so
 * that one field was added on top of the requested set.
 * ------------------------------------------------------------
 */

import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import InputField from "./InputField.jsx";
import Reveal from "./Reveal.jsx";
import { submitContactMessage, submitDemoRequest } from "../services/contactService.js";
import { validateFullName, validateEmail, validateCompanyName } from "../utils/validators.js";

const DEMO_MESSAGE = "I'd like to request a demo of OneNextGen Automation.";
const initialForm = { fullName: "", email: "", companyName: "", message: "" };

export default function ContactSection() {
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverMessage, setServerMessage] = useState(null);
  // true once the visitor arrived via a "Request demo" button: the message
  // is pre-filled and the form posts to the demo-request endpoint.
  const [isDemo, setIsDemo] = useState(false);
  const location = useLocation();

  useEffect(() => {
    if (location.state?.demo) {
      setIsDemo(true);
      setServerMessage(null);
      setForm((f) => (f.message.trim() ? f : { ...f, message: DEMO_MESSAGE }));
    }
  }, [location.key]);

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
    if (isDemo && !form.companyName.trim()) next.companyName = "Company name helps us tailor your demo.";

    if (!form.message.trim()) next.message = "Let us know what you need help with.";
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
      const res = await (isDemo ? submitDemoRequest : submitContactMessage)(form);
      setServerMessage({
        type: "success",
        text: res?.message ||
          (isDemo
            ? "Thanks! We'll be in touch shortly to schedule your demo."
            : "Thanks for reaching out! We'll get back to you within one business day."),
      });
      setForm(initialForm);
      setIsDemo(false);
    } catch (err) {
      setServerMessage({
        type: "error",
        text: err.message || "Something went wrong sending your message. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section id="contact" className="scroll-mt-20 bg-slate-25 px-6 py-20 sm:px-10">
      <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-2">
        {/* Left: context copy */}
        <Reveal>
          <p className="font-mono text-xs uppercase tracking-widest text-amber-500">Get in touch</p>
          <h2 className="mt-3 font-display text-3xl font-semibold text-ink-800 sm:text-4xl">
            Let's talk about your workflow
          </h2>
          <p className="mt-4 max-w-md text-ink-400">
            Questions about a product, pricing, or whether OneNextGen Automation fits your
            team? Send us a note and someone from our team will follow up
            within one business day.
          </p>

          <ul className="mt-8 space-y-4 text-sm text-ink-500">
            <li className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-ink-800 text-amber-400">✉</span>
              communications@onenextgenautomation.com
            </li>
            <li className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-ink-800 text-amber-400">☎</span>
              +91 8050278787
            </li>
          </ul>
        </Reveal>

        {/* Right: contact form */}
        <Reveal
          as="form"
          delay={150}
          onSubmit={handleSubmit}
          id="contact-form"
          className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm transition-shadow duration-300 hover:shadow-card sm:p-8"
        >
          <div className="space-y-5">
            <InputField
              id="fullName"
              label="Full name"
              value={form.fullName}
              onChange={handleChange}
              placeholder="Jhon Doe"
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
              placeholder="ONG Inc."
              autoComplete="organization"
              required={false}
              error={errors.companyName}
            />
            <div className="w-full">
              <label htmlFor="message" className="mb-1.5 block text-sm font-medium text-ink-700">
                How can we help?
              </label>
              <textarea
                id="message"
                name="message"
                rows={4}
                value={form.message}
                onChange={handleChange}
                placeholder="Tell us a bit about what you're trying to automate…"
                className={`w-full rounded-lg border bg-white px-4 py-3 text-ink-800 placeholder:text-ink-300
                  focus:border-amber-400 focus:ring-2 focus:ring-amber-400/30 transition-colors
                  ${errors.message ? "border-red-400" : "border-ink-200"}`}
              />
              {errors.message && <p className="mt-1.5 text-sm text-red-500">{errors.message}</p>}
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

            <button type="submit" id="contact-submit-btn" disabled={isSubmitting} className="btn-primary w-full">
              {isSubmitting ? "Sending…" : "Send message"}
            </button>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
