import React from "react";

export default function ChartCard({ title, subtitle, action, children, className = "", delay = 0 }) {
  return (
    <div
      className={`dash-fade-in overflow-hidden rounded-2xl border border-white/60 bg-white/70 p-5 shadow-[0_8px_30px_-14px_rgba(37,99,235,0.15)]
        backdrop-blur-xl transition-shadow duration-300 hover:shadow-[0_16px_40px_-16px_rgba(37,99,235,0.22)]
        dark:border-white/10 dark:bg-slate-800/60 dark:shadow-none ${className}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
          {subtitle && (
            <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{subtitle}</p>
          )}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}
