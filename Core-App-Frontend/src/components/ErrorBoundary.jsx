import React from "react";
import { logError, downloadErrorLog } from "../utils/errorLogger";

/**
 * components/ErrorBoundary.jsx
 * ------------------------------------------------------------
 * Catches React render/lifecycle errors anywhere below it,
 * logs them to the client-side error log (see utils/errorLogger),
 * and shows a calm, on-brand fallback screen instead of a blank
 * white page — the same "graceful degradation" pattern used by
 * enterprise RPA consoles.
 * ------------------------------------------------------------
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    logError("react-error-boundary", error, { componentStack: info?.componentStack });
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 14,
          background: "#0A151C",
          color: "#fff",
          fontFamily: "Inter, sans-serif",
          padding: 24,
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            background: "rgba(232,163,61,0.14)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 26,
            color: "#E8A33D",
          }}
        >
          !
        </div>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Something went wrong</h1>
        <p style={{ maxWidth: 420, color: "rgba(255,255,255,0.65)", fontSize: 14, margin: 0 }}>
          This error has been recorded in the local error log. Reloading the page usually resolves
          it — if it keeps happening, download the log and share it with your admin.
        </p>
        <div style={{ display: "flex", gap: 10, marginTop: 6 }}>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: "#E8A33D",
              color: "#10202B",
              border: "none",
              borderRadius: 10,
              padding: "10px 20px",
              fontWeight: 600,
              fontSize: 13.5,
              cursor: "pointer",
            }}
          >
            Reload
          </button>
          <button
            onClick={downloadErrorLog}
            style={{
              background: "rgba(255,255,255,0.08)",
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.18)",
              borderRadius: 10,
              padding: "10px 20px",
              fontWeight: 600,
              fontSize: 13.5,
              cursor: "pointer",
            }}
          >
            Download error log
          </button>
        </div>
      </div>
    );
  }
}
