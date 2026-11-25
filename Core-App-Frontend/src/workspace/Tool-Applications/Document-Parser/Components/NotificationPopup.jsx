import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useBasePath } from "../../../utils/useBasePath";
import { FaBell, FaCheckCircle, FaTimesCircle, FaSpinner, FaClock, FaTimes, FaTrashAlt } from "react-icons/fa";
import "../Styles/documentParser.css";

/**
 * workspace/components/NotificationPopup.jsx
 * ------------------------------------------------------------
 * Notification popup shown from the Document Parser dashboard
 * header bell. Mirrors the ProfilePopup modal style. Because we
 * cannot change the backend/API/db, notifications are derived
 * from the document processing history the dashboard already
 * loads (GET /document/history) - grouped by status with icons.
 * ------------------------------------------------------------
 */
const STATUS_META = {
  completed: { label: "Processed successfully", icon: <FaCheckCircle />, cls: "done" },
  success: { label: "Processed successfully", icon: <FaCheckCircle />, cls: "done" },
  done: { label: "Processed successfully", icon: <FaCheckCircle />, cls: "done" },
  extracted: { label: "Processed successfully", icon: <FaCheckCircle />, cls: "done" },
  failed: { label: "Failed to process", icon: <FaTimesCircle />, cls: "err" },
  cancelled: { label: "Processing cancelled", icon: <FaTimesCircle />, cls: "err" },
  processing: { label: "Processing in progress", icon: <FaSpinner />, cls: "run" },
  running: { label: "Processing in progress", icon: <FaSpinner />, cls: "run" },
  "in progress": { label: "Processing in progress", icon: <FaSpinner />, cls: "run" },
  pending: { label: "Waiting in queue", icon: <FaClock />, cls: "wait" },
  queued: { label: "Waiting in queue", icon: <FaClock />, cls: "wait" },
};

const FILTERS = [
  { key: "day", label: "Day", days: 1 },
  { key: "week", label: "Week", days: 7 },
  { key: "month", label: "Month", days: 30 },
  { key: "all", label: "All", days: null },
];

function normalize(s) {
  return (s || "").toLowerCase().trim();
}

function formatDate(raw) {
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// Extract a YYYY-MM-DD date string from the backend's stored date value,
// which is typically "YYYY-MM-DD HH:MM:SS" (IST) but may also be DD-MM-YYYY.
function itemDateStr(h) {
  const raw = h.createddate || h.processdate || "";
  let m = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return m[0];
  m = raw.match(/^(\d{2})[-/](\d{2})[-/](\d{4})/);
  if (m) return `${m[3]}-${m[2]}-${m[1]}`;
  return null;
}

// Earliest date (YYYY-MM-DD, computed in IST) that a filter window covers.
function filterWindowStart(days) {
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  const ist = new Date(utcMs + 5.5 * 3600000);
  ist.setDate(ist.getDate() - (days - 1));
  const y = ist.getFullYear();
  const m = String(ist.getMonth() + 1).padStart(2, "0");
  const d = String(ist.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export default function NotificationPopup({ history = [], unread = 0, onClose, userId }) {
  const navigate = useNavigate();
  const basePath = useBasePath();
  const overlayRef = useRef(null);
  const [filter, setFilter] = useState("all");

  // Dismissed notifications live here (per user) so deleting a notification
  // never touches the actual history records / dashboard stats. The original
  // history list passed in is always left unmodified.
  const storageKey = `nexaflow_dp_dismissed_notifications_${userId ?? "default"}`;
  const [dismissed, setDismissed] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));
    } catch {
      return new Set();
    }
  });

  const persistDismissed = (next) => {
    setDismissed(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(Array.from(next)));
    } catch {
      /* ignore storage errors */
    }
  };

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const allItems = Array.isArray(history) ? history : [];

  // Apply the selected Day / Week / Month / All filter AND exclude the
  // notifications the user has already dismissed (notification-side only).
  const activeFilter = FILTERS.find((f) => f.key === filter);
  const filtered = allItems.filter((h) => {
    const id = h.historyid ?? h.job_id ?? h.id;
    if (id != null && dismissed.has(String(id))) return false;
    if (activeFilter?.days) {
      const start = filterWindowStart(activeFilter.days);
      const ds = itemDateStr(h);
      if (!ds || ds < start) return false;
    }
    return true;
  });

  const items = filtered.slice(0, 50);
  const unreadCount = Number(unread) || 0;

  const handleDeleteOne = (historyId) => {
    const found = history.find((h) => String(h.historyid) === String(historyId));
    const name = found?.document_name || "this notification";
    if (!window.confirm(`Delete "${name}"? It will only be removed from your notifications (history is not affected).`)) return;
    const next = new Set(dismissed);
    next.add(String(historyId));
    persistDismissed(next);
  };

  const handleDeleteAll = () => {
    if (filtered.length === 0) return;
    const label = activeFilter?.days
      ? `notifications in the ${activeFilter.key} filter`
      : "ALL notifications";
    if (!window.confirm(`Delete ALL ${label} shown here? They will only be removed from your notifications list (history is not affected).`)) return;
    const next = new Set(dismissed);
    filtered.forEach((h) => {
      const id = h.historyid ?? h.job_id ?? h.id;
      if (id != null) next.add(String(id));
    });
    persistDismissed(next);
    setFilter("all");
  };

  return (
    <div
      className="dp-profile-overlay"
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="dp-profile-popup dp-notification-popup" role="dialog" aria-modal="true" aria-label="Notifications">
        <button type="button" className="dp-profile-popup-close" onClick={onClose} aria-label="Close notifications">
          <FaTimes />
        </button>

        <div className="dp-notification-head">
          <div className="dp-notification-title">
            <FaBell className="dp-notification-title-icon" />
            Notifications
          </div>
          {unreadCount > 0 && <span className="dp-notification-count">{unreadCount} new</span>}
        </div>

        <div className="dp-notification-filters" role="tablist" aria-label="Filter notifications">
          {FILTERS.map((f) => (
            <button
              type="button"
              key={f.key}
              className={`dp-notification-filter-btn ${filter === f.key ? "active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="dp-notification-list">
          {items.length === 0 ? (
            <div className="dp-notification-empty">
              <FaBell className="dp-notification-empty-icon" />
              <p>{filter === "all" ? "You're all caught up" : "No notifications in this period"}</p>
            </div>
          ) : (
            items.map((h) => {
              const s = normalize(h.status);
              const meta = STATUS_META[s] || { label: h.status || "Update", icon: <FaBell />, cls: "info" };
              const id = h.historyid ?? h.job_id ?? h.id;
              return (
                <div key={id} className={`dp-notification-item ${meta.cls}`}>
                  <div className="dp-notification-item-icon">{meta.icon}</div>
                  <div className="dp-notification-item-body">
                    <p className="dp-notification-item-text">{(h.document_name || "Document") + " \u2014 " + meta.label}</p>
                    <span className="dp-notification-item-date">{formatDate(h.createddate || h.processdate)}</span>
                  </div>
                  {id != null && (
                    <button
                      type="button"
                      className="dp-notification-item-delete"
                      title="Delete"
                      aria-label="Delete notification"
                      onClick={() => handleDeleteOne(id)}
                    >
                      <FaTrashAlt />
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="dp-notification-foot">
          {filtered.length > 0 && (
            <button
              type="button"
              className="dp-notification-deleteall"
              onClick={handleDeleteAll}
            >
              <FaTrashAlt /> Delete {filter === "all" ? "All" : `All (${filtered.length})`}
            </button>
          )}
          <button
            type="button"
            className="dp-notification-viewall"
            onClick={() => { onClose(); navigate(`${basePath}/document-parser/history-process-model`); }}
          >
            View all notifications
          </button>
        </div>
      </div>
    </div>
  );
}