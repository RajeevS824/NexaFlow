import { useCallback, useEffect, useState } from "react";

/**
 * useDashboardTheme
 * ------------------------------------------------------------
 * Small, self-contained light/dark toggle for the redesigned
 * Dashboard page. Persists to localStorage and flips the `dark`
 * class on <html> so Tailwind's `dark:` variants apply across
 * the panel. Purely presentational - no routing/auth/API impact.
 * ------------------------------------------------------------
 */
export default function useDashboardTheme() {
  const [isDark, setIsDark] = useState(() => {
    if (typeof window === "undefined") return false;
    const stored = window.localStorage.getItem("nexaflow-theme");
    if (stored) return stored === "dark";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.toggle("dark", isDark);
    window.localStorage.setItem("nexaflow-theme", isDark ? "dark" : "light");
  }, [isDark]);

  const toggle = useCallback(() => setIsDark((prev) => !prev), []);

  return { isDark, toggle };
}
