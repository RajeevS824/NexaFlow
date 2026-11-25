/**
 * components/FlowMotif.jsx
 * ------------------------------------------------------------
 * The brand's signature visual: a set of connected "workflow
 * nodes" linked by animated flowing lines, representing
 * automated processes moving data from step to step.
 * Purely decorative - safe to render behind text.
 * ------------------------------------------------------------
 */

export default function FlowMotif({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 480 480"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="flowLine" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#E8A33D" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#E8A33D" stopOpacity="0.1" />
        </linearGradient>
      </defs>

      {/* connecting paths */}
      <path
        d="M60 380 C 140 380, 120 260, 210 250 S 300 140, 380 120"
        stroke="url(#flowLine)"
        strokeWidth="2"
        strokeDasharray="6 8"
      >
        <animate attributeName="stroke-dashoffset" from="0" to="-56" dur="6s" repeatCount="indefinite" />
      </path>
      <path
        d="M90 90 C 150 130, 160 200, 230 220 S 340 300, 410 340"
        stroke="url(#flowLine)"
        strokeWidth="2"
        strokeDasharray="6 8"
      >
        <animate attributeName="stroke-dashoffset" from="0" to="-56" dur="8s" repeatCount="indefinite" />
      </path>

      {/* nodes */}
      {[
        [60, 380],
        [210, 250],
        [380, 120],
        [90, 90],
        [230, 220],
        [410, 340],
      ].map(([cx, cy], i) => (
        <g key={i}>
          <circle cx={cx} cy={cy} r="6" fill="#E8A33D" opacity="0.9" />
          <circle cx={cx} cy={cy} r="14" stroke="#E8A33D" strokeOpacity="0.3" fill="none" />
        </g>
      ))}
    </svg>
  );
}
