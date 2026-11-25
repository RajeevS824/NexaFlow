import React, { useEffect, useMemo, useRef, useState } from "react";
import { FaBell, FaCheckCircle, FaTimesCircle, FaBan, FaCloudUploadAlt, FaTimes, FaTrashAlt } from "react-icons/fa";
import "../Styles/BusinessMapHeader.css";

/**
 * Business Map notifications only. They are derived from the Business Map
 * backend's job list (GET /jobs), one event per milestone of a job:
 *   - upload started          (every job, at its creation time)
 *   - processing completed    (status SUCCESS / PARTIAL)
 *   - processing failed       (status FAILED / ERROR)
 *   - processing cancelled    (status CANCELLED)
 * Dismissing a notification only hides it here (stored per user); the jobs and
 * dashboard statistics are never touched.
 */
const FILTERS = [
  { key: "day", label: "Day", ms: 24 * 3600 * 1000 },
  { key: "week", label: "Week", ms: 7 * 24 * 3600 * 1000 },
  { key: "month", label: "Month", ms: 30 * 24 * 3600 * 1000 },
  { key: "all", label: "All", ms: null },
];

const META = {
  upload: { label: "Upload started", icon: <FaCloudUploadAlt />, cls: "run" },
  completed: { label: "Processing completed", icon: <FaCheckCircle />, cls: "done" },
  failed: { label: "Processing failed", icon: <FaTimesCircle />, cls: "err" },
  cancelled: { label: "Processing cancelled", icon: <FaBan />, cls: "wait" },
};

function finalKind(status) {
  if (status === "SUCCESS" || status === "PARTIAL") return "completed";
  if (status === "FAILED" || status === "ERROR") return "failed";
  if (status === "CANCELLED") return "cancelled";
  return null;
}

export function buildNotifications(jobs) {
  const events = [];
  for (const j of Array.isArray(jobs) ? jobs : []) {
    const name = j.filename || j.job_name || "Untitled";
    if (j.created_at) {
      events.push({ id: `${j.job_id}:upload`, kind: "upload", name, at: new Date(j.created_at) });
    }
    const kind = finalKind(j.status);
    if (kind) {
      const at = new Date(j.processed_at || j.created_at || 0);
      events.push({ id: `${j.job_id}:${kind}`, kind, name, at });
    }
  }
  return events
    .filter((e) => !Number.isNaN(e.at.getTime()))
    .sort((a, b) => b.at.getTime() - a.at.getTime());
}

function formatDate(d) {
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function BusinessMapNotificationPopup({ jobs = [], userId, onClose, onViewAll }) {
  const overlayRef = useRef(null);
  const [filter, setFilter] = useState("all");
  const storageKey = `nexaflow_bm_dismissed_notifications_${userId ?? "default"}`;
  const [dismissed, setDismissed] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));
    } catch {
      return new Set();
    }
  });

  const persist = (next) => {
    setDismissed(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(Array.from(next)));
    } catch {
      /* storage unavailable */
    }
  };

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const active = FILTERS.find((f) => f.key === filter);
  const filtered = useMemo(() => {
    const now = Date.now();
    return buildNotifications(jobs).filter((e) => {
      if (dismissed.has(e.id)) return false;
      if (active?.ms && now - e.at.getTime() > active.ms) return false;
      return true;
    });
  }, [jobs, dismissed, active]);
  const items = filtered.slice(0, 50);

  const deleteOne = (e) => {
    if (!window.confirm(`Delete "${e.name}"? It will only be removed from your notifications.`)) return;
    persist(new Set(dismissed).add(e.id));
  };
  const deleteAll = () => {
    if (filtered.length === 0) return;
    if (!window.confirm("Delete all notifications shown here? Your files and statistics are not affected.")) return;
    const next = new Set(dismissed);
    filtered.forEach((e) => next.add(e.id));
    persist(next);
    setFilter("all");
  };

  return (
    <div
      className="bm-profile-overlay"
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="bm-profile-popup bm-notification-popup" role="dialog" aria-modal="true" aria-label="Notifications">
        <button type="button" className="bm-profile-popup-close" onClick={onClose} aria-label="Close notifications">
          <FaTimes />
        </button>

        <div className="bm-notification-head">
          <div className="bm-notification-title">
            <FaBell className="bm-notification-title-icon" /> Notifications
          </div>
        </div>

        <div className="bm-notification-filters" role="tablist" aria-label="Filter notifications">
          {FILTERS.map((f) => (
            <button
              type="button"
              key={f.key}
              className={`bm-notification-filter-btn ${filter === f.key ? "active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="bm-notification-list">
          {items.length === 0 ? (
            <div className="bm-notification-empty">
              <FaBell className="bm-notification-empty-icon" />
              <p>{filter === "all" ? "You're all caught up" : "No notifications in this period"}</p>
            </div>
          ) : (
            items.map((e) => {
              const meta = META[e.kind];
              return (
                <div key={e.id} className={`bm-notification-item ${meta.cls}`}>
                  <div className="bm-notification-item-icon">{meta.icon}</div>
                  <div className="bm-notification-item-body">
                    <p className="bm-notification-item-text">{e.name} — {meta.label}</p>
                    <span className="bm-notification-item-date">{formatDate(e.at)}</span>
                  </div>
                  <button type="button" className="bm-notification-item-delete" title="Delete" aria-label="Delete notification" onClick={() => deleteOne(e)}>
                    <FaTrashAlt />
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div className="bm-notification-foot">
          {filtered.length > 0 && (
            <button type="button" className="bm-notification-deleteall" onClick={deleteAll}>
              <FaTrashAlt /> Delete {filter === "all" ? "All" : `All (${filtered.length})`}
            </button>
          )}
          <button type="button" className="bm-notification-viewall" onClick={onViewAll}>
            View all files
          </button>
        </div>
      </div>
    </div>
  );
}
