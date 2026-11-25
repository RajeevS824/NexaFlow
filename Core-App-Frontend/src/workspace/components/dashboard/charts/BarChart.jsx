import React, { useId, useMemo, useState } from "react";

const WIDTH = 560;
const HEIGHT = 220;
const PAD_TOP = 16;
const PAD_BOTTOM = 28;

/**
 * BarChart
 * Props:
 *  data  {Array<{label:string, value:number}>}
 *  color {string} - solid fallback color (used to build a gradient)
 */
export default function BarChart({ data, color = "#2563EB" }) {
  const gradientId = useId();
  const [hoverIdx, setHoverIdx] = useState(null);

  const { bars, barWidth, gap } = useMemo(() => {
    const max = Math.max(...data.map((d) => d.value), 1) * 1.15;
    const innerH = HEIGHT - PAD_TOP - PAD_BOTTOM;
    const gap = 18;
    const barWidth = (WIDTH - gap * (data.length + 1)) / data.length;

    const bars = data.map((d, i) => {
      const h = (d.value / max) * innerH;
      return {
        ...d,
        x: gap + i * (barWidth + gap),
        y: PAD_TOP + innerH - h,
        h,
      };
    });
    return { bars, barWidth, gap };
  }, [data]);

  return (
    <div className="relative w-full">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full overflow-visible" preserveAspectRatio="none">
        <defs>
          <linearGradient id={`bar-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.55" />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={0}
            x2={WIDTH}
            y1={PAD_TOP + (HEIGHT - PAD_TOP - PAD_BOTTOM) * f}
            y2={PAD_TOP + (HEIGHT - PAD_TOP - PAD_BOTTOM) * f}
            className="stroke-slate-200 dark:stroke-slate-700"
            strokeWidth="1"
            strokeDasharray="4 4"
          />
        ))}

        {bars.map((b, i) => (
          <g key={b.label} onMouseEnter={() => setHoverIdx(i)} onMouseLeave={() => setHoverIdx(null)}>
            <rect
              x={b.x}
              y={b.y}
              width={barWidth}
              height={b.h}
              rx={7}
              fill={hoverIdx === i ? color : `url(#bar-${gradientId})`}
              className="transition-all duration-200"
            />
            <rect x={b.x} y={PAD_TOP} width={barWidth} height={HEIGHT - PAD_TOP - PAD_BOTTOM} fill="transparent" />
            <text
              x={b.x + barWidth / 2}
              y={HEIGHT - 6}
              textAnchor="middle"
              className="fill-slate-400 dark:fill-slate-500 text-[11px] font-medium"
            >
              {b.label}
            </text>
          </g>
        ))}
      </svg>

      {hoverIdx !== null && (
        <div
          className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-lg border border-slate-100 bg-white px-3 py-1.5
            text-xs font-semibold text-slate-700 shadow-lg dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          style={{ left: `${((bars[hoverIdx].x + barWidth / 2) / WIDTH) * 100}%` }}
        >
          {data[hoverIdx].label}: {data[hoverIdx].value}
        </div>
      )}
    </div>
  );
}
