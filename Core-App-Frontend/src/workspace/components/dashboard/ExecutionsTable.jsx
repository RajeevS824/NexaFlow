import React from "react";
import { FiFilter, FiMoreHorizontal } from "react-icons/fi";
import StatusBadge from "./StatusBadge";

const COLUMNS = ["Bot Name", "Department", "Status", "Started", "Duration", "Owner", ""];

export default function ExecutionsTable({ rows }) {
  return (
    <div
      className="dash-fade-in rounded-2xl border border-white/60 bg-white/70 shadow-[0_8px_30px_-14px_rgba(37,99,235,0.15)]
        backdrop-blur-xl dark:border-white/10 dark:bg-slate-800/60 dark:shadow-none"
      style={{ animationDelay: "260ms" }}
    >
      <div className="flex items-center justify-between gap-3 p-5 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Recent Executions</h3>
          <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
            Live feed of the latest automation runs across departments
          </p>
        </div>
        <button
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold
            text-slate-500 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-700/50"
        >
          <FiFilter size={13} /> Filter
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="border-y border-slate-100 dark:border-slate-700/60">
              {COLUMNS.map((col) => (
                <th
                  key={col}
                  className="whitespace-nowrap px-5 py-2.5 text-left text-xs font-semibold uppercase tracking-wide
                    text-slate-400 dark:text-slate-500"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                className="border-b border-slate-50 transition-colors last:border-none hover:bg-blue-50/40
                  dark:border-slate-700/40 dark:hover:bg-slate-700/30"
              >
                <td className="px-5 py-3 font-medium text-slate-800 dark:text-slate-100">{row.botName}</td>
                <td className="px-5 py-3 text-slate-500 dark:text-slate-400">{row.department}</td>
                <td className="px-5 py-3">
                  <StatusBadge status={row.status} />
                </td>
                <td className="px-5 py-3 text-slate-500 dark:text-slate-400">{row.started}</td>
                <td className="px-5 py-3 text-slate-500 dark:text-slate-400">{row.duration}</td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-700 dark:bg-blue-500/20 dark:text-blue-300">
                      {row.owner
                        .split(" ")
                        .map((p) => p[0])
                        .join("")
                        .slice(0, 2)}
                    </span>
                    <span className="text-slate-600 dark:text-slate-300">{row.owner}</span>
                  </div>
                </td>
                <td className="px-5 py-3 text-right">
                  <button className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700">
                    <FiMoreHorizontal size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
