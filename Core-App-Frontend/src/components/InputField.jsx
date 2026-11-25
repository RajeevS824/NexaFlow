/**
 * components/InputField.jsx
 * ------------------------------------------------------------
 * Reusable labeled text input with inline error message.
 * Every field across Login / Register / Reset Password uses
 * this so styling and accessibility stay consistent.
 *
 * When `type="password"` is passed, an eye icon button is
 * rendered inside the field that toggles the password between
 * masked and plain text, so users can double-check what
 * they've typed before submitting.
 * ------------------------------------------------------------
 */

import { useState } from "react";

// Open eye - shown when the password is currently hidden (click to reveal)
function EyeIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M1.5 12S5 5 12 5s10.5 7 10.5 7-3.5 7-10.5 7S1.5 12 1.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

// Eye with a slash - shown when the password is currently visible (click to hide)
function EyeOffIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M17.94 17.94A10.94 10.94 0 0 1 12 19.5c-7 0-10.5-7-10.5-7a19.15 19.15 0 0 1 4.22-5.29M9.9 5.24A9.99 9.99 0 0 1 12 5c7 0 10.5 7 10.5 7a19.2 19.2 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24" />
      <path d="M1 1l22 22" />
    </svg>
  );
}

export default function InputField({
  id,
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  error,
  autoComplete,
  required = true,
}) {
  const isPasswordField = type === "password";
  const [isRevealed, setIsRevealed] = useState(false);
  const inputType = isPasswordField ? (isRevealed ? "text" : "password") : type;

  return (
    <div className="w-full">
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-ink-700">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          name={id}
          type={inputType}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          className={`w-full rounded-lg border bg-white px-4 py-2.5 text-ink-800 placeholder:text-ink-300
            focus:border-amber-400 focus:ring-2 focus:ring-amber-400/30 transition-colors
            ${isPasswordField ? "pr-11" : ""}
            ${error ? "border-red-400" : "border-ink-200"}`}
        />
        {isPasswordField && (
          <button
            type="button"
            id={`${id}-toggle-visibility`}
            onClick={() => setIsRevealed((prev) => !prev)}
            aria-label={isRevealed ? "Hide password" : "Show password"}
            aria-pressed={isRevealed}
            tabIndex={-1}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-ink-400 hover:text-ink-700 transition-colors"
          >
            {isRevealed ? <EyeOffIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
          </button>
        )}
      </div>
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-red-500">
          {error}
        </p>
      )}
    </div>
  );
}
