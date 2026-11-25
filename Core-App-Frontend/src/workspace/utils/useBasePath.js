/**
 * workspace/utils/useBasePath.js
 * ------------------------------------------------------------
 * Extracts the workspace base path from the current URL.
 *
 * In NexaFlow the workspace is mounted at /dashboard (regular
 * users) or /admin-panel (admins).  The document-parser pages
 * were originally written with absolute paths like
 * "/create-process-model"; when integrated into NexaFlow they
 * need to become "${basePath}/document-parser/create-process-model".
 *
 * This hook inspects the current pathname and returns the first
 * path segment, which is the workspace root.
 * ------------------------------------------------------------
 */
import { useLocation } from "react-router-dom";

export function useBasePath() {
  const location = useLocation();
  // The workspace root is always the first path segment, e.g.
  // "/dashboard/document-parser/..."  ->  "/dashboard"
  // "/admin-panel/document-parser/..."  ->  "/admin-panel"
  const match = location.pathname.match(/^(\/[^/]+)/);
  return match ? match[1] : "/dashboard";
}

/** Convenience: returns "${basePath}/document-parser" */
export function useDocParserBase() {
  const basePath = useBasePath();
  return `${basePath}/document-parser`;
}