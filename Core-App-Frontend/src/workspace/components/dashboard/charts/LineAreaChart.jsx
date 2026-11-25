import React, { useId, useMemo, useState } from "react";

const WIDTH = 560;
const HEIGHT = 220;
const PAD_X = 8;
const PAD_TOP = 16;
const PAD_BOTTOM = 28;

/** Builds a smooth path (quadratic midpoint smoothing) through points. */
function smoothPath(points) {
  if (points.length < 2) return "";
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i];
    const p1 = points[i + 1];
    const mx = (p0.x + p1.x) / 2;
    const my = (p0.y + p1.y) / 2;
    d += ` Q ${p0.x} ${p0.y} ${mx} ${my}`;
  }
  const last = points[points.length - 1];
  d += ` T ${last.x} ${last.y}`;
  return d;
}

/**
 * LineAreaChart
 * ------------------------------------------------------------
 * Props:
 *  data    {Array<{label:string, [seriesKey]:number}>}
 *  series  {Array<{key:string, label:string, color:string}>}
 *  area    {boolean} - fill under the (first) line with a gradient
 */
export default function LineAreaChart({ data, series, area = true }) {
  const gradientId = useId();
  const [hoverIdx, setHoverIdx] = useState(null);

  const { linesBySeries, xForIndex, yForValue, maxValue } = useMemo(() => {
    const allValues = data.flatMap((d) => series.map((s) => d[s.key] ?? 0));
    const max = Math.max(...allValues, 1) * 1.15;
    const innerW = WIDTH - PAD_X * 2;
    const innerH = HEIGHT - PAD_TOP - PAD_BOTTOM;

    const xFor = (i) => PAD_X + (data.length === 1 ? innerW / 2 : (innerW * i) / (data.length - 1));
    const yFor = (v) => PAD_TOP + innerH - (v / max) * innerH;

    const lines = series.map((s) => ({
      ...s,
      points: data.map((d, i) => ({ x: xFor(i), y: yFor(d[s.key] ?? 0) })),
    }));

    return { linesBySeries: lines, xForIndex: xFor, yForValue: yFor, maxValue: max };
  }, [data, series]);

  const primary = linesBySeries[0];

  return (
    <div className="relative w-full">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full overflow-visible" preserveAspectRatio="none">
        <defs>
          <linearGradient id={`grad-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={primary?.color || "#2563EB"} stopOpacity="0.35" />
            <stop offset="100%" stopColor={primary?.color || "#2563EB"} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* horizontal gridlines */}
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={PAD_X}
            x2={WIDTH - PAD_X}
            y1={PAD_TOP + (HEIGHT - PAD_TOP - PAD_BOTTOM) * f}
            y2={PAD_TOP + (HEIGHT - PAD_TOP - PAD_BOTTOM) * f}
            className="stroke-slate-200 dark:stroke-slate-700"
            strokeWidth="1"
            strokeDasharray="4 4"
          />
        ))}

        {area && primary && (
          <path
            d={`${smoothPath(primary.points)} L ${primary.points[primary.points.length - 1].x} ${
              HEIGHT - PAD_BOTTOM
            } L ${primary.points[0].x} ${HEIGHT - PAD_BOTTOM} Z`}
            fill={`url(#grad-${gradientId})`}
          />
        )}

        {linesBySeries.map((s) => (
          <path
            key={s.key}
            d={smoothPath(s.points)}
            fill="none"
            stroke={s.color}
            strokeWidth="2.5"
            strokeLinecap="round"
            className="drop-shadow-sm"
          />
        ))}

        {/* hover targets */}
        {data.map((d, i) => (
          <g key={i}>
            <rect
              x={xForIndex(i) - (WIDTH / data.length) / 2}
              y={0}
              width={WIDTH / data.length}
              height={HEIGHT}
              fill="transparent"
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
            />
            {hoverIdx === i && (
              <line
                x1={xForIndex(i)}
                x2={xForIndex(i)}
                y1={PAD_TOP}
                y2={HEIGHT - PAD_BOTTOM}
                className="stroke-blue-300 dark:stroke-blue-500/50"
                strokeWidth="1"
              />
            )}
            {linesBySeries.map((s) => (
              <circle
                key={s.key}
                cx={xForIndex(i)}
                cy={yForValue(d[s.key] ?? 0)}
                r={hoverIdx === i ? 4 : 0}
                fill={s.color}
                stroke="white"
                strokeWidth="1.5"
                className="transition-all"
              />
            ))}
          </g>
        ))}

        {/* x labels */}
        {data.map((d, i) => (
          <text
            key={i}
            x={xForIndex(i)}
            y={HEIGHT - 6}
            textAnchor="middle"
            className="fill-slate-400 dark:fill-slate-500 text-[11px] font-medium"
          >
            {d.label}
          </text>
        ))}
      </svg>

      {hoverIdx !== null && (
        <div
          className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-lg border border-slate-100 bg-white px-3 py-2
            text-xs shadow-lg dark:border-slate-700 dark:bg-slate-800"
          style={{ left: `${(xForIndex(hoverIdx) / WIDTH) * 100}%` }}
        >
          <p className="mb-1 font-semibold text-slate-700 dark:text-slate-200">{data[hoverIdx].label}</p>
          {series.map((s) => (
            <p key={s.key} className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.color }} />
              {s.label}: <span className="font-semibold text-slate-700 dark:text-slate-200">{data[hoverIdx][s.key]}</span>
            </p>
          ))}
        </div>
      )}

      {series.length > 1 && (
        <div className="mt-3 flex flex-wrap gap-4">
          {series.map((s) => (
            <span key={s.key} className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
