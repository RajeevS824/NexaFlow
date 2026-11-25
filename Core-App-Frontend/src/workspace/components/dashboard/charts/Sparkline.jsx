import React, { useId, useMemo } from "react";

const WIDTH = 220;
const HEIGHT = 64;

export default function Sparkline({ data, color = "#2563EB" }) {
  const gradientId = useId();

  const { path, areaPath } = useMemo(() => {
    const max = Math.max(...data, 1) * 1.1;
    const min = Math.min(...data) * 0.9;
    const range = max - min || 1;
    const step = WIDTH / (data.length - 1 || 1);

    const points = data.map((v, i) => ({
      x: i * step,
      y: HEIGHT - ((v - min) / range) * HEIGHT,
    }));

    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i];
      const p1 = points[i + 1];
      const mx = (p0.x + p1.x) / 2;
      d += ` Q ${p0.x} ${p0.y} ${mx} ${(p0.y + p1.y) / 2}`;
    }
    d += ` T ${points[points.length - 1].x} ${points[points.length - 1].y}`;

    return { path: d, areaPath: `${d} L ${WIDTH} ${HEIGHT} L 0 ${HEIGHT} Z` };
  }, [data]);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`spark-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#spark-${gradientId})`} />
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
