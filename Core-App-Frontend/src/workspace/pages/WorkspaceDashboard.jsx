import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FiFileText,
  FiUsers,
  FiMap,
  FiArrowRight,
  FiCheckCircle,
  FiLayers,
  FiAlertTriangle,
  FiZap,
} from "react-icons/fi";

import Header from "../components/WorkspaceHeader";
import StatCard from "../components/dashboard/StatCard";
import ChartCard from "../components/dashboard/ChartCard";
import LineAreaChart from "../components/dashboard/charts/LineAreaChart";
import DonutChart from "../components/dashboard/charts/DonutChart";
import { CHART_COLORS } from "../components/dashboard/chartPalette";
import { useAuth } from "../../context/AuthContext.jsx";
import { apiFetch } from "../../services/api";

import "../styles/dashboard.css";

/* ------------------------------------------------------------
 * Real-time admin analytics
 * ------------------------------------------------------------
 * The Admin Panel dashboard's numbers come from a live call to
 * GET /api/admin/analytics/dashboard on every load, scoped to only
 * the products this organization has actually licensed (an
 * unlicensed product simply isn't present in the response at all).
 * There is no mock/hardcoded data anywhere in this file.
 * ------------------------------------------------------------ */

// Palette + friendly labels for the job-status values that come back
// from the Document Parser / Business Map databases. Falls back
// gracefully for any status string not explicitly listed here, so a
// new/unexpected status still renders instead of disappearing.
const STATUS_STYLE = {
  completed: { label: "Completed", color: CHART_COLORS.success },
  success: { label: "Success", color: CHART_COLORS.success },
  partial: { label: "Partial", color: CHART_COLORS.warning },
  failed: { label: "Failed", color: CHART_COLORS.danger },
  error: { label: "Failed", color: CHART_COLORS.danger },
  cancelled: { label: "Cancelled", color: CHART_COLORS.danger },
  marked_as_invalid: { label: "Marked Invalid", color: CHART_COLORS.danger },
  processing: { label: "Processing", color: CHART_COLORS.primary },
  running: { label: "Running", color: CHART_COLORS.primary },
  pending: { label: "Pending", color: CHART_COLORS.tertiary },
  queued: { label: "Queued", color: CHART_COLORS.tertiary },
};

function statusToDonutSegment(entry) {
  const key = String(entry.status || "").toLowerCase();
  const known = STATUS_STYLE[key];
  return {
    label: known?.label || String(entry.status || "Unknown"),
    value: entry.count,
    color: known?.color || CHART_COLORS.tertiary,
  };
}

function numberFormat(n) {
  return new Intl.NumberFormat("en-US").format(n ?? 0);
}

/** Fetches real analytics for the admin's org. Only runs when `enabled`. */
function useAdminDashboardAnalytics(enabled) {
  const [state, setState] = useState({ loading: enabled, error: null, data: null });

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    setState({ loading: true, error: null, data: null });

    apiFetch("/api/admin/analytics/dashboard")
      .then((data) => {
        if (!cancelled) setState({ loading: false, error: null, data });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({ loading: false, error: err.message || "Failed to load analytics.", data: null });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return state;
}

const QUICK_LINKS = [
  {
    key: "BusinessMap",
    slug: "business-process-mapper",
    icon: <FiMap size={19} />,
    title: "Business Process",
    description: "Map out and document your team's business processes.",
    accent: "from-blue-600 to-blue-500",
  },
  {
    key: "document-parser",
    slug: "document-parser",
    icon: <FiFileText size={19} />,
    title: "Document Parser",
    description: "Extract structured data from invoices and PDFs.",
    accent: "from-cyan-600 to-cyan-500",
  },
  {
    key: "nextflow",
    slug: "nextflow",
    icon: <FiZap size={19} />,
    title: "Nextflow",
    description: "Build and run visual automation workflows.",
    accent: "from-indigo-600 to-indigo-500",
  },
];

function Dashboard({ isAdmin = false, basePath = "/dashboard" }) {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Card *visibility* is intentionally NOT gated by license - every user
  // sees all product cards. Only *opening* a product is gated by what's
  // actually licensed to their organization (accessibleProductSlugs,
  // sourced from the backend), matching how the sidebar's product links
  // behave: click through, but block navigation with a clear message if
  // the org doesn't have that product.
  const accessibleProductSlugs = useMemo(() => {
    const list = Array.isArray(user?.products) ? user.products : [];
    return new Set(list.filter((p) => p && p.slug).map((p) => p.slug));
  }, [user?.products]);

  const isProductEnabled = (slug) => accessibleProductSlugs.has(slug);

  // Real, live analytics for the admin dashboard - fetched only when
  // this is actually the admin view (regular users never trigger this
  // call at all).
  const { loading, error, data } = useAdminDashboardAnalytics(isAdmin);

  function handleQuickLinkClick(link) {
    if (!isProductEnabled(link.slug)) {
      alert(`Access denied: Your organization doesn't have access to ${link.title}.`);
      return;
    }
    navigate(`${basePath}/${link.key}`);
  }

  // Regular users get a clean, simple landing dashboard with quick links to
  // their tools — the full analytics view below is admin-only.
  if (!isAdmin) {
    return (
      <>
        <Header
          title="Dashboard"
          description="Jump back into your automations, document parsing, and process maps."
        />
        <main className="main-content !bg-gradient-to-b !from-slate-50 !to-blue-50/40 dark:!bg-none dark:!bg-slate-900">
          <div className="content mx-auto max-w-[1100px]">
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {QUICK_LINKS.map((link, i) => {
                const hasAccess = isProductEnabled(link.slug);
                return (
                  <button
                    key={link.key}
                    onClick={() => handleQuickLinkClick(link)}
                    className={`dash-fade-in group flex flex-col items-start rounded-2xl border border-white/60 bg-white/70 p-6 text-left
                      shadow-[0_8px_30px_-14px_rgba(16,32,43,0.15)] backdrop-blur-xl transition-all duration-300
                      hover:-translate-y-1 hover:shadow-[0_16px_40px_-14px_rgba(16,32,43,0.25)]
                      dark:border-white/10 dark:bg-slate-800/60 ${!hasAccess ? "opacity-60" : ""}`}
                    style={{ animationDelay: `${i * 70}ms` }}
                  >
                    <div
                      className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md ${link.accent}`}
                    >
                      {link.icon}
                    </div>
                    <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">{link.title}</h3>
                    <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">{link.description}</p>
                    <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 dark:text-blue-400">
                      {hasAccess ? (
                        <>
                          Open <FiArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                        </>
                      ) : (
                        <span className="text-slate-400 dark:text-slate-500">Not licensed for your organization</span>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </main>
      </>
    );
  }

  // ---- Admin Panel dashboard: real-time analytics only ----
  const licensedProducts = data?.licensed_products || [];
  const hasDocumentParser = Boolean(data?.products?.["document-parser"]);
  const hasBusinessMap = Boolean(data?.products?.["business-process-mapper"]);
  const hasAnyProductData = hasDocumentParser || hasBusinessMap;

  const topStats = data
    ? [
        {
          icon: <FiUsers size={20} />,
          label: "Active Users",
          value: numberFormat(data.active_users),
          accent: "from-sky-600 to-sky-500",
        },
        {
          icon: <FiLayers size={20} />,
          label: "Licensed Products",
          value: numberFormat(data.licensed_product_count),
          accent: "from-indigo-600 to-indigo-500",
        },
        ...(hasDocumentParser
          ? [
              {
                icon: <FiFileText size={20} />,
                label: "Documents Processed",
                value: numberFormat(data.products["document-parser"].documents_total),
                accent: "from-cyan-600 to-cyan-500",
              },
            ]
          : []),
        ...(hasBusinessMap
          ? [
              {
                icon: <FiMap size={20} />,
                label: "Business Maps Processed",
                value: numberFormat(data.products["business-process-mapper"].jobs_total),
                accent: "from-blue-600 to-blue-500",
              },
            ]
          : []),
      ]
    : [];

  return (
    <>
      <Header
        title="Admin Panel"
        description="Manage roles, products, and permissions across the workspace."
      />

      <main className="main-content !bg-gradient-to-b !from-slate-50 !to-blue-50/40 dark:!bg-none dark:!bg-slate-900">
        <div className="content mx-auto max-w-[1280px]">
          {loading && (
            <div className="dash-fade-in flex items-center justify-center rounded-2xl border border-white/60 bg-white/70 p-12 text-sm text-slate-500 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-slate-800/60 dark:text-slate-400">
              Loading real-time analytics…
            </div>
          )}

          {!loading && error && (
            <div className="dash-fade-in flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-5 text-sm text-rose-700 shadow-sm backdrop-blur-xl dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
              <FiAlertTriangle size={18} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">Couldn't load dashboard analytics</p>
                <p className="mt-0.5 text-rose-600 dark:text-rose-400">{error}</p>
              </div>
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Top statistics — real counts only */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4">
                {topStats.map((s, i) => (
                  <StatCard key={s.label} {...s} delay={i * 60} />
                ))}
              </div>

              {!hasAnyProductData && (
                <div className="dash-fade-in mt-6 rounded-2xl border border-white/60 bg-white/70 p-8 text-center shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-slate-800/60">
                  <FiLayers size={28} className="mx-auto text-slate-300 dark:text-slate-600" />
                  <p className="mt-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
                    No product analytics available yet
                  </p>
                  <p className="mx-auto mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">
                    {licensedProducts.length === 0
                      ? "This organization doesn't have any licensed products yet."
                      : "None of this organization's currently licensed products have usage data to report yet."}
                  </p>
                </div>
              )}

              {/* Document Parser analytics — only rendered if licensed */}
              {hasDocumentParser && (
                <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-5">
                  <ChartCard
                    title="Document Parser: Processing Trend"
                    subtitle="Jobs queued per day, last 7 days"
                    className="lg:col-span-3"
                    delay={80}
                  >
                    {data.products["document-parser"].available === false ? (
                      <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
                        Document Parser's database is unavailable right now.
                      </p>
                    ) : (
                      <LineAreaChart
                        data={data.products["document-parser"].trend}
                        series={[{ key: "value", label: "Jobs", color: CHART_COLORS.primary }]}
                      />
                    )}
                  </ChartCard>

                  <ChartCard
                    title="Document Parser: Job Status"
                    subtitle="All-time breakdown"
                    className="lg:col-span-2"
                    delay={140}
                  >
                    {data.products["document-parser"].status_breakdown?.length ? (
                      <DonutChart
                        data={data.products["document-parser"].status_breakdown.map(statusToDonutSegment)}
                        centerLabel="Total Jobs"
                      />
                    ) : (
                      <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
                        No Document Parser jobs yet.
                      </p>
                    )}
                  </ChartCard>
                </div>
              )}

              {/* Business Map analytics — only rendered if licensed */}
              {hasBusinessMap && (
                <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-5">
                  <ChartCard
                    title="Business Map: Processing Trend"
                    subtitle="Jobs created per day, last 7 days"
                    className="lg:col-span-3"
                    delay={180}
                  >
                    {data.products["business-process-mapper"].available === false ? (
                      <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
                        Business Map's database is unavailable right now.
                      </p>
                    ) : (
                      <LineAreaChart
                        data={data.products["business-process-mapper"].trend}
                        series={[{ key: "value", label: "Jobs", color: CHART_COLORS.secondary }]}
                      />
                    )}
                  </ChartCard>

                  <ChartCard
                    title="Business Map: Job Status"
                    subtitle="All-time breakdown"
                    className="lg:col-span-2"
                    delay={220}
                  >
                    {data.products["business-process-mapper"].status_breakdown?.length ? (
                      <DonutChart
                        data={data.products["business-process-mapper"].status_breakdown.map(statusToDonutSegment)}
                        centerLabel="Total Jobs"
                      />
                    ) : (
                      <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
                        No Business Map jobs yet.
                      </p>
                    )}
                  </ChartCard>
                </div>
              )}

              {licensedProducts.length > 0 && (
                <div
                  className="dash-fade-in mt-5 flex flex-wrap items-center gap-2 rounded-2xl border border-white/60 bg-white/70 p-4 text-xs text-slate-500 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-slate-800/60 dark:text-slate-400"
                  style={{ animationDelay: "260ms" }}
                >
                  <FiCheckCircle size={14} className="text-emerald-500" />
                  <span className="font-medium text-slate-600 dark:text-slate-300">Licensed products:</span>
                  {licensedProducts.map((p) => (
                    <span
                      key={p.slug}
                      className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-600 dark:bg-slate-700/60 dark:text-slate-300"
                    >
                      {p.name}
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}

export default Dashboard;
