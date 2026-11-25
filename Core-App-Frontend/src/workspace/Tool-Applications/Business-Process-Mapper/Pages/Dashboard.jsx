import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { getStats, getJobs } from "../../../config/businessMapApi";
import "../Styles/Dashboard.css";
import "../Styles/bm-common.css";
import uploadIcon from "./uploaded.png"; // <-- Import your image
import processingIcon from "./processing.png"; // <-- Import your image
import completedIcon from "./completed.png";
import cancelIcon from "./cancel.png";

import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, Cell,
  AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import {
  Percent, Search, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, FileVideo,
} from "lucide-react";

const POLL_INTERVAL_MS = 5000;

/* Top summary cards (6). success_rate is computed client-side
   from `stats` if your API doesn't return them yet — see deriveExtraStats(). */
const CARD_CONFIG = [
  { key: "total_uploaded", label: "Total Uploaded", icon: uploadIcon, className: "total", isImage: true },
  { key: "processing", label: "Processing", icon: processingIcon, className: "processing", isImage: true },
  { key: "completed", label: "Completed", icon: completedIcon, className: "completed", isImage: true },
  { key: "cancelled", label: "Cancelled", icon: cancelIcon, className: "cancelled", isImage: true },
  { key: "failed", label: "Failed", icon: "⚠️", className: "failed" },
  { key: "success_rate", label: "Success Rate", icon: <Percent size={20} />, className: "success", suffix: "%" },
];

/* ------------------------------------------------------------------ */
/* TODO: replace with real endpoints once available. Shapes shown here
   (date/uploads, status/count, name/value, hour/uploads/processed) are
   what the chart components below expect — keep them if you swap in
   real data so you don't need to touch the JSX.                       */
/* ------------------------------------------------------------------ */

/* Real replacement for the old mockUploadsSeries(): counts actual jobs
   per day for the last `days` days, using each job's real created_at
   timestamp from GET /jobs. Days with zero uploads correctly show 0
   instead of a random placeholder value. */
/* Local calendar-day key, e.g. "2026-07-27" — deliberately NOT
   toISOString() (which converts to UTC and can shift the date by a day
   for timezones ahead of UTC, e.g. IST), so this matches the day the
   user actually sees on their clock. */
function localDayKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function computeUploadsSeries(jobs, days = 14) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  // dateKey -> count, pre-seeded with every day in range (incl. zeros)
  const counts = new Map();
  const labels = new Map();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(startOfToday);
    d.setDate(d.getDate() - i);
    const key = localDayKey(d);
    counts.set(key, 0);
    labels.set(key, d.toLocaleDateString("en-US", { month: "short", day: "numeric" }));
  }

  for (const job of jobs) {
    if (!job.created_at) continue;
    // job.created_at is a UTC ISO timestamp from the backend; the Date
    // constructor correctly converts it to the right instant, and the
    // local getters used by localDayKey() then give the calendar day
    // the user actually experienced it on.
    const key = localDayKey(new Date(job.created_at));
    if (counts.has(key)) counts.set(key, counts.get(key) + 1);
  }

  return Array.from(counts.entries()).map(([key, uploads]) => ({
    date: labels.get(key),
    uploads,
  }));
}

function mockStatusDistribution(stats) {
  return [
    { status: "Uploaded", count: stats?.total_uploaded ?? 0, fill: "#5B5BF6" },
    { status: "Processing", count: stats?.processing ?? 0, fill: "#D97B0A" },
    { status: "Completed", count: stats?.completed ?? 0, fill: "#0FA968" },
    { status: "Cancelled", count: stats?.cancelled ?? 0, fill: "#93A0B4" },
    { status: "Failed", count: stats?.failed ?? 0, fill: "#E23B4E" },
  ];
}

/* Real replacement for the old mockDailyActivity(): buckets actual jobs
   by hour-of-day (0-23, grouped into 2-hour buckets to match the axis
   labels below), counting "uploads" from created_at and "processed"
   from processed_at. This aggregates across all fetched jobs (not just
   today) — with only a handful of jobs so far this will look sparse,
   but it's real, not a smoothed sine-wave placeholder. */
function computeDailyActivity(jobs) {
  const uploadBuckets = new Array(24).fill(0);
  const processedBuckets = new Array(24).fill(0);

  for (const job of jobs) {
    if (job.created_at) {
      uploadBuckets[new Date(job.created_at).getHours()] += 1;
    }
    if (job.processed_at) {
      processedBuckets[new Date(job.processed_at).getHours()] += 1;
    }
  }

  const out = [];
  for (let h = 0; h < 24; h += 2) {
    const label = h === 0 ? "12a" : h < 12 ? `${h}a` : h === 12 ? "12p" : `${h - 12}p`;
    out.push({
      hour: label,
      uploads: uploadBuckets[h] + uploadBuckets[h + 1],
      processed: processedBuckets[h] + processedBuckets[h + 1],
    });
  }
  return out;
}

/* Maps backend job.status (QUEUED/RUNNING/SUCCESS/PARTIAL/FAILED/ERROR/
   CANCELLED/NEEDS_AUDIO_CONFIRMATION) to the display statuses the
   StatusBadge / summary cards already use. */
function displayStatus(rawStatus) {
  switch (rawStatus) {
    case "SUCCESS":
    case "PARTIAL":
      return "Completed";
    case "QUEUED":
    case "RUNNING":
    case "NEEDS_AUDIO_CONFIRMATION":
      return "Processing";
    case "FAILED":
    case "ERROR":
      return "Failed";
    case "CANCELLED":
      return "Cancelled";
    default:
      return "Uploaded";
  }
}

/* Real jobs -> Data Table rows. File size isn't tracked by the backend
   yet (see patch notes), so that column shows "—" until it is. */
function formatBytes(bytes) {
  if (bytes == null || bytes < 0) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[i]}`;
}

function jobsToTableRows(jobs) {
  return jobs.map((job) => ({
    id: job.job_id,
    filename: job.filename || job.job_name || "untitled",
    uploader: job.uploader || "anonymous",
    status: displayStatus(job.status),
    size: formatBytes(job.size_bytes),
    duration: job.latency_sec != null
      ? `${Math.floor(job.latency_sec / 60)}m ${Math.round(job.latency_sec % 60)}s`
      : "—",
    uploadedAt: job.created_at ? new Date(job.created_at) : new Date(0),
  }));
}

function deriveExtraStats(stats) {
  if (!stats) return { success_rate: 0 };
  const total = (stats.completed ?? 0) + (stats.failed ?? 0) || 1;
  return {
    success_rate: Math.round(((stats.completed ?? 0) / total) * 1000) / 10,
  };
}

/* ------------------------------------------------------------------ */
/* Small presentational pieces                                        */
/* ------------------------------------------------------------------ */

const STATUS_META = {
  Completed: { color: "#0FA968", bg: "#E7F8EF" },
  Processing: { color: "#D97B0A", bg: "#FDF2E1" },
  Failed: { color: "#E23B4E", bg: "#FCEAEC" },
  Cancelled: { color: "#93A0B4", bg: "#F1F3F8" },
  Uploaded: { color: "#5B5BF6", bg: "#EEEEFE" },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.Uploaded;
  return (
    <span className="badge" style={{ color: meta.color, background: meta.bg }}>
      <span className="badge-dot" style={{ background: meta.color }} />
      {status}
    </span>
  );
}

const tooltipStyle = {
  background: "#fff",
  border: "1px solid #e7eaf3",
  borderRadius: 10,
  fontSize: 12.5,
  boxShadow: "0 6px 20px rgba(15,23,42,0.08)",
  padding: "8px 12px",
};

function ChartCard({ title, subtitle, children, height = 260 }) {
  return (
    <div className="dash-card chart-card">
      <div className="chart-card-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      <div style={{ height }}>{children}</div>
    </div>
  );
}

const PAGE_SIZE = 8;

function DataTable({ rows }) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState("uploadedAt");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let out = !q
      ? rows
      : rows.filter(
          (r) =>
            r.filename.toLowerCase().includes(q) ||
            r.uploader.toLowerCase().includes(q) ||
            r.status.toLowerCase().includes(q)
        );
    out = [...out].sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (av instanceof Date) { av = av.getTime(); bv = bv.getTime(); }
      if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return out;
  }, [rows, query, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const toggleSort = useCallback((key) => {
    setPage(1);
    setSortKey((prevKey) => {
      if (prevKey === key) { setSortDir((d) => (d === "asc" ? "desc" : "asc")); return prevKey; }
      setSortDir("desc");
      return key;
    });
  }, []);

  const columns = [
    { key: "filename", label: "File" },
    { key: "uploader", label: "Uploader" },
    { key: "status", label: "Status" },
    { key: "size", label: "Size" },
    { key: "duration", label: "Duration" },
    { key: "uploadedAt", label: "Uploaded" },
  ];

  return (
    <div className="dash-card table-card">
      <div className="table-head">
        <div>
          <h3>Recent Files</h3>
          <p>All uploaded videos across the platform</p>
        </div>
        <div className="table-search">
          <Search size={15} color="#9aa5b8" />
          <input
            placeholder="Search files, uploaders, status…"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            aria-label="Search files"
          />
        </div>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} onClick={() => toggleSort(col.key)}>
                  <span className="th-inner">
                    {col.label}
                    {sortKey === col.key && (sortDir === "asc" ? <ChevronUp size={13} /> : <ChevronDown size={13} />)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r) => (
              <tr key={r.id}>
                <td>
                  <div className="file-cell">
                    <FileVideo size={15} color="#9aa5b8" />
                    {r.filename}
                  </div>
                </td>
                <td>{r.uploader}</td>
                <td><StatusBadge status={r.status} /></td>
                <td className="mono">{r.size}</td>
                <td className="mono">{r.duration}</td>
                <td className="mono">{r.uploadedAt.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</td>
              </tr>
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td colSpan={columns.length}>
                  <div className="empty-state">
                    <Search size={22} color="#9aa5b8" />
                    <p>No files match "{query}"</p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {filtered.length > 0 && (
        <div className="table-footer">
          <span>Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}</span>
          <div className="pager">
            <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft size={15} /></button>
            <span>{page} / {totalPages}</span>
            <button disabled={page === totalPages} onClick={() => setPage((p) => p + 1)} aria-label="Next page"><ChevronRight size={15} /></button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Dashboard — your original polling logic, extended             */
/* ------------------------------------------------------------------ */

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const [jobs, setJobs] = useState([]);
  const [jobsError, setJobsError] = useState(null);
  const [jobsLoading, setJobsLoading] = useState(true);

  const intervalRef = useRef(null);
  const jobsIntervalRef = useRef(null);

  // Charts now computed from real job history (GET /jobs) instead of
  // random placeholder data.
  const uploadsSeries = useMemo(() => computeUploadsSeries(jobs), [jobs]);
  const dailyActivity = useMemo(() => computeDailyActivity(jobs), [jobs]);

  useEffect(() => {
    let cancelled = false;

    async function fetchStats() {
      try {
        const data = await getStats();
        if (!cancelled) {
          setStats(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError("Couldn't reach the backend — is it running?");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchStats();
    intervalRef.current = setInterval(fetchStats, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Powers the Activity Feed + Data Table. Requires GET /api/jobs
  // (see jobs_endpoint_patch.md) — if that endpoint isn't deployed yet,
  // this quietly falls back to an empty list rather than breaking the page.
  useEffect(() => {
    let cancelled = false;

    async function fetchJobs() {
      try {
        const data = await getJobs({ page: 1, pageSize: 50 });
        if (!cancelled) {
          setJobs(data.jobs || []);
          setJobsError(null);
        }
      } catch (err) {
        if (!cancelled) setJobsError("Job list unavailable — couldn't reach GET /jobs on the backend.");
      } finally {
        if (!cancelled) setJobsLoading(false);
      }
    }

    fetchJobs();
    jobsIntervalRef.current = setInterval(fetchJobs, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (jobsIntervalRef.current) clearInterval(jobsIntervalRef.current);
    };
  }, []);

  const extra = deriveExtraStats(stats);
  const mergedStats = stats ? { ...stats, ...extra } : null;
  const statusDist = useMemo(() => mockStatusDistribution(stats), [stats]);
  const tableRows = useMemo(() => jobsToTableRows(jobs), [jobs]);

  return (
    <>
      <main className="main-content">
        <div className="content">
          {error && <p className="dash-error">{error}</p>}
          {jobsError && <p className="dash-error">{jobsError}</p>}

          <div className="dash-stats-grid">
            {CARD_CONFIG.map(({ key, label, icon, className, isImage, suffix }) => (
              <div key={key} className={`dash-stat-card ${className}`}>
                <div className="dash-stat-icon" aria-hidden="true">
                  {isImage ? (
                    <img src={icon} alt={label} className="dash-stat-icon-img" />
                  ) : (
                    icon
                  )}
                </div>
                <div className="dash-stat-body">
                  <span className="dash-stat-value">
                    {loading ? "—" : (mergedStats?.[key] ?? 0)}{!loading && suffix}
                  </span>
                  <span className="dash-stat-label">{label}</span>
                </div>
              </div>
            ))}
          </div>

          <p className="dash-hint">
            Updates automatically every {POLL_INTERVAL_MS / 1000} seconds.
          </p>

          <div className="charts-grid">
            <ChartCard title="Uploads Over Time" subtitle="Last 14 days">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={uploadsSeries} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#e7eaf3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9aa5b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#9aa5b8" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="uploads" stroke="#5B5BF6" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Processing Status Distribution" subtitle="Current file breakdown">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusDist} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#e7eaf3" />
                  <XAxis dataKey="status" tick={{ fontSize: 11, fill: "#9aa5b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#9aa5b8" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f3f4f6" }} />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                    {statusDist.map((d, i) => <Cell key={i} fill={d.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Daily Activity" subtitle="Uploads vs. processed, by hour">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={dailyActivity} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="upG" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#5B5BF6" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#5B5BF6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="prG" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0FA968" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#0FA968" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke="#e7eaf3" />
                  <XAxis dataKey="hour" tick={{ fontSize: 11, fill: "#9aa5b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#9aa5b8" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="uploads" stroke="#5B5BF6" strokeWidth={2} fill="url(#upG)" />
                  <Area type="monotone" dataKey="processed" stroke="#0FA968" strokeWidth={2} fill="url(#prG)" />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <DataTable rows={tableRows} />
        </div>
      </main>
    </>
  );
}

export default Dashboard;