/**
 * src/services/contactService.js
 * ------------------------------------------------------------
 * Frontend service for the marketing site's "Contact us" section
 * and "Request a demo" page. Both are unauthenticated endpoints:
 * the backend stores the submission and emails the details to
 * the team.
 */
import { apiFetch } from "./api";

/** Submit the "Contact us" form. Resolves with { message }. */
export async function submitContactMessage({ fullName, email, companyName, message }) {
  return apiFetch("/api/contact/message", {
    method: "POST",
    body: JSON.stringify({
      full_name: fullName,
      email,
      company_name: companyName,
      message,
    }),
  });
}

/** Submit the "Request a demo" form. Resolves with { message }. */
export async function submitDemoRequest({ fullName, email, companyName, message }) {
  return apiFetch("/api/contact/request-demo", {
    method: "POST",
    body: JSON.stringify({
      full_name: fullName,
      email,
      company_name: companyName,
      message,
    }),
  });
}
