import React from "react";
import { FiCheckCircle, FiXCircle, FiLoader, FiClock } from "react-icons/fi";

const STATUS_STYLES = {
  Success: {
    className:
      "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-400 dark:ring-emerald-400/20",
    Icon: FiCheckCircle,
  },
  Failed: {
    className:
      "bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-200 dark:bg-rose-400/10 dark:text-rose-400 dark:ring-rose-400/20",
    Icon: FiXCircle,
  },
  Running: {
    className:
      "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200 dark:bg-blue-400/10 dark:text-blue-400 dark:ring-blue-400/20",
    Icon: FiLoader,
  },
  Queued: {
    className:
      "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200 dark:bg-amber-400/10 dark:text-amber-400 dark:ring-amber-400/20",
    Icon: FiClock,
  },
};

export default function StatusBadge({ status }) {
  const config = STATUS_STYLES[status] || STATUS_STYLES.Queued;
  const { Icon } = config;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold whitespace-nowrap ${config.className}`}
    >
      <Icon className={status === "Running" ? "animate-spin" : ""} size={12} />
      {status}
    </span>
  );
}
