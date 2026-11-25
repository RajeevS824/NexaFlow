import React, { useMemo, useState } from "react";

const SIZE = 176;
const STROKE = 22;
const RADIUS = (SIZE - STROKE) / 2;
const CIRC = 2 * Math.PI * RADIUS;

/**
 * DonutChart
 * Props:
 *  data {Array<{label:string, value:number, color:string}>}
 *  centerLabel {string}
 */
export default function DonutChart({ data, centerLabel = "Total" }) {
  const [activeIdx, setActiveIdx] = useState(null);
  const total = data.reduce((sum, d) => sum + d.value, 0) || 1;

  const segments = useMemo(() => {
    let offset = 0;
    return data.map((d) => {
      const fraction = d.value / total;
      const seg = { ...d, fraction, offset };
      offset += fraction;
      return seg;
    });
  }, [data, total]);

  const activeValue = activeIdx !== null ? data[activeIdx].value : total;
  const activeLabel = activeIdx !== null ? data[activeIdx].label : centerLabel;

  return (
    <div className="flex min-w-0 items-center gap-4">
      <div className="relative h-28 w-28 shrink-0 sm:h-32 sm:w-32">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-full w-full -rotate-90">
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            strokeWidth={STROKE}
            className="stroke-slate-100 dark:stroke-slate-700"
          />
          {segments.map((seg, i) => (
            <circle
              key={seg.label}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke={seg.color}
              strokeWidth={activeIdx === i ? STROKE + 4 : STROKE}
              strokeDasharray={`${seg.fraction * CIRC} ${CIRC}`}
              strokeDashoffset={-seg.offset * CIRC}
              strokeLinecap="round"
              className="transition-all duration-300 cursor-pointer"
              onMouseEnter={() => setActiveIdx(i)}
              onMouseLeave={() => setActiveIdx(null)}
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center px-1 text-center">
          <span className="text-lg font-bold leading-tight text-slate-900 dark:text-white">{activeValue}</span>
          <span className="truncate text-[10px] font-medium leading-tight text-slate-400 dark:text-slate-500">
            {activeLabel}
          </span>
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        {data.map((d, i) => (
          <div
            key={d.label}
            title={`${d.label}: ${Math.round((d.value / total) * 100)}%`}
            className="flex min-w-0 items-center gap-2 rounded-lg px-2 py-1.5 transition-colors cursor-pointer
              hover:bg-slate-50 dark:hover:bg-slate-700/50"
            onMouseEnter={() => setActiveIdx(i)}
            onMouseLeave={() => setActiveIdx(null)}
          >
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: d.color }} />
            <span className="min-w-0 flex-1 truncate text-sm text-slate-500 dark:text-slate-400">{d.label}</span>
            <span className="shrink-0 text-sm font-semibold text-slate-800 dark:text-slate-100">
              {Math.round((d.value / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
