import React from "react";
import { FiArrowUpRight, FiArrowDownRight } from "react-icons/fi";

/**
 * StatCard
 * ------------------------------------------------------------
 * Reusable glass stat tile for the top statistics row.
 *
 * Props:
 *  icon        {ReactNode}  - icon element (already sized/colored via className)
 *  label       {string}
 *  value       {string|number}
 *  trend       {number}     - signed percentage, e.g. 12.4 or -3.2
 *  accent      {string}     - tailwind gradient classes for the icon chip
 *  delay       {number}     - ms, stagger the entrance animation
 */
export default function StatCard({ icon, label, value, trend, accent, delay = 0 }) {
  const isUp = trend >= 0;

  return (
    <div
      className="dash-fade-in group relative overflow-hidden rounded-2xl border border-white/60 bg-white/70 p-5
        shadow-[0_8px_30px_-12px_rgba(37,99,235,0.18)] backdrop-blur-xl transition-all duration-300
        hover:-translate-y-1 hover:shadow-[0_16px_40px_-14px_rgba(37,99,235,0.28)]
        dark:border-white/10 dark:bg-slate-800/60 dark:shadow-none"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-blue-500/10 blur-2xl
          transition-transform duration-500 group-hover:scale-125 dark:bg-blue-400/10"
      />

      <div className="relative flex items-start justify-between">
        <div
          className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md ${
            accent || "from-blue-600 to-blue-500"
          }`}
        >
          {icon}
        </div>

        {typeof trend === "number" && (
          <span
            className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              isUp
                ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-400/10 dark:text-emerald-400"
                : "bg-rose-50 text-rose-600 dark:bg-rose-400/10 dark:text-rose-400"
            }`}
          >
            {isUp ? <FiArrowUpRight size={12} /> : <FiArrowDownRight size={12} />}
            {Math.abs(trend)}%
          </span>
        )}
      </div>

      <p className="relative mt-4 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
        {value}
      </p>
      <p className="relative mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">
        {label}
      </p>
    </div>
  );
}
