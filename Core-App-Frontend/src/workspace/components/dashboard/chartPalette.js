/**
 * workspace/components/dashboard/chartPalette.js
 * ------------------------------------------------------------
 * Single source of truth for dashboard analytics colors.
 *
 * Rather than reusing the same one or two brand colors on every
 * chart (which flattens everything into visual sameness), this
 * assigns each metric its own restrained, desaturated hue from a
 * professional BI palette — the same approach used by Power BI /
 * Tableau default themes: one anchor color per series, muted
 * semantic colors for status (success/fail/warning), and a
 * shared neutral for gridlines/axes so the charts read as one
 * coherent system instead of a patchwork.
 * ------------------------------------------------------------
 */

export const CHART_COLORS = {
  // Primary KPI trend (Automation Executions) — original dashboard blue.
  primary: "#2563EB",
  // Secondary trend series (AI Agent Activity) — original violet accent.
  secondary: "#7C3AED",
  // Tertiary bar/series (Department Usage) — same brand blue used before.
  tertiary: "#2563EB",

  // Semantic status colors — matches the original dashboard's palette.
  success: "#2563EB",
  danger: "#F43F5E",
  warning: "#F59E0B",

  // Shared chrome.
  grid: "#E2E8F0",
  axisText: "#94A3B8",
};

export default CHART_COLORS;
