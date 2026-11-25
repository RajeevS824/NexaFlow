/**
 * utils/validators.js
 * ------------------------------------------------------------
 * Shared, reusable field-validation helpers used by every form in
 * the NexaFlow frontend (Register, Login, Dashboard Login, Reset
 * Password, Request Demo, Contact, and the admin Users modal).
 *
 * Each `validateX` function returns `null` when the value is valid,
 * or a short user-facing error string when it isn't - so callers can
 * do `const err = validateEmail(value); if (err) next.email = err;`.
 * ------------------------------------------------------------
 */

// Pragmatic RFC-5322-ish email regex - strict enough to catch obviously
// malformed addresses (no "@", no domain, no TLD) without rejecting real
// addresses that pickier regexes choke on.
const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$/;

// Well-known free-mail providers we can sanity-check the domain against.
// A one- or two-character typo of one of these (e.g. "gmial.com" instead
// of "gmail.com") is almost always a mistake, not a real domain.
const KNOWN_EMAIL_DOMAINS = [
  "gmail.com",
  "yahoo.com",
  "outlook.com",
  "hotmail.com",
  "icloud.com",
  "live.com",
  "aol.com",
  "protonmail.com",
  "rediffmail.com",
];

/** Classic Levenshtein edit-distance between two strings. */
function levenshtein(a, b) {
  const m = a.length;
  const n = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1]
          : 1 + Math.min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1]);
    }
  }
  return dp[m][n];
}

/**
 * If `email`'s domain looks like a near-miss typo of a well-known free-mail
 * provider (e.g. "gmial.com", "yaho.com"), returns the corrected domain
 * (e.g. "gmail.com"). Returns null for domains that are exact matches,
 * unrelated, or too different in length to be a plausible typo.
 */
export function getEmailDomainSuggestion(email) {
  const at = String(email || "").lastIndexOf("@");
  if (at === -1) return null;
  const domain = email
    .slice(at + 1)
    .trim()
    .toLowerCase();
  if (!domain || KNOWN_EMAIL_DOMAINS.includes(domain)) return null;

  for (const known of KNOWN_EMAIL_DOMAINS) {
    if (Math.abs(domain.length - known.length) > 2) continue;
    if (domain !== known && levenshtein(domain, known) <= 2) {
      return known;
    }
  }
  return null;
}

/**
 * Validates an email address's format and (optionally) flags likely
 * typos of well-known provider domains, e.g. "ramya@gmial.com".
 * Pass `{ checkTypo: false }` for sign-in style fields where the address
 * already belongs to an existing account and a typo will simply fail
 * authentication rather than needing to be pre-empted.
 */
export function validateEmail(value, { checkTypo = true } = {}) {
  const email = String(value || "").trim();
  if (!email) return "Email is required.";
  if (!EMAIL_REGEX.test(email)) {
    return "Enter a valid email address (e.g. name@company.com).";
  }
  if (checkTypo) {
    const suggestion = getEmailDomainSuggestion(email);
    if (suggestion) {
      const local = email.slice(0, email.lastIndexOf("@") + 1);
      return `That domain looks like a typo - did you mean "${local}${suggestion}"?`;
    }
  }
  return null;
}

// Letters (including common accented characters), spaces, hyphens and
// apostrophes only - blocks digits and other symbols while still allowing
// names like "Mary-Jane O'Brien".
const FULL_NAME_REGEX = /^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '-][A-Za-zÀ-ÖØ-öø-ÿ]+)*$/;

/** Validates a "full name" field: required, letters only, no digits. */
export function validateFullName(value) {
  const name = String(value || "").trim();
  if (!name) return "Please tell us your name.";
  if (/\d/.test(name)) return "Name can't contain numbers.";
  if (name.length < 2) return "Name must be at least 2 characters.";
  if (!FULL_NAME_REGEX.test(name)) {
    return "Enter a valid name using letters only.";
  }
  return null;
}

/** Validates a password's minimum length (default 8 characters). */
export function validatePassword(value, { minLength = 8 } = {}) {
  if (!value) return "Please create a password.";
  if (value.length < minLength) return `Use at least ${minLength} characters.`;
  return null;
}

/** Validates that a "confirm password" field matches the original. */
export function validateConfirmPassword(password, confirmPassword) {
  if (!confirmPassword) return "Please confirm your password.";
  if (password !== confirmPassword) return "Passwords don't match.";
  return null;
}

/** Generic required-field check with a customizable message. */
export function validateRequired(value, message = "This field is required.") {
  if (!value || !String(value).trim()) return message;
  return null;
}

/** Validates an optional "company name" field: only checked if provided. */
export function validateCompanyName(value) {
  const name = String(value || "").trim();
  if (!name) return null;
  if (name.length < 2) return "Company name is too short.";
  return null;
}
