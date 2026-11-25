/**
 * components/HeroWorkflowAnimation.jsx
 * ------------------------------------------------------------
 * The animated "Nextflow — Workflow Builder" card used as the
 * right-side visual in the homepage hero. A 4-node workflow
 * (Bot Trigger → Bot Runner → IQ Bot → Workspace Sync) with a
 * live "chase" glow running through it, plus a real Manual /
 * Automated toggle that flips the diagram between a paused,
 * dimmed state and a connected, glowing, running one.
 *
 * Colors: recolored to match the hero section's own brand
 * palette (ink navy + amber accent, from tailwind.config.js)
 * instead of the generic emerald/orange/indigo/cyan the source
 * package shipped with. Amber is used for the "live/automated"
 * moment (mirroring the hero's amber CTA/eyebrow), and a muted
 * ink/slate tone represents the paused "manual" state, so the
 * two states stay visually distinct without introducing colors
 * that clash with the rest of the page. Only this file changed -
 * nothing else on the page was touched.
 *
 * Automated mode plays as a sequential flow: a packet travels from one
 * node icon to the next, lighting each node as it arrives (no continuous
 * blinking). Respects prefers-reduced-motion (shows the finished flow).
 * ------------------------------------------------------------
 */
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  Zap,
  PlayCircle,
  Brain,
  LayoutDashboard,
  PauseCircle,
  RefreshCw,
  Gauge,
  Timer,
  CheckCircle2,
  Workflow,
} from "lucide-react";

const NODES = [
  { key: "trigger", label: "Bot Trigger", x: 40, y: 100, Icon: Zap },
  { key: "runner", label: "Bot Runner", x: 150, y: 45, Icon: PlayCircle },
  { key: "iqbot", label: "IQ Bot", x: 260, y: 100, Icon: Brain },
  { key: "sync", label: "Workspace Sync", x: 365, y: 45, Icon: LayoutDashboard },
];
const PATH = NODES.map((n) => `${n.x},${n.y}`).join(" L");

// Hero brand tokens (tailwind.config.js) - used directly as hex values
// inside the SVG, where Tailwind's color classes can't reach.
const AMBER = "#E8A33D"; // amber-400 - automated/live state
const INK_MUTED = "#7C9DA9"; // ink-300 - manual/paused state

export default function HeroWorkflowAnimation({ className = "" }) {
  const [automated, setAutomated] = useState(true);
  const reduceMotion = useReducedMotion();

  // Step clock for the automated run: 0..3 = packet reaches node 0..3,
  // 4..5 = hold on the completed flow, then the loop restarts. One node
  // lights at a time (no continuous blinking) so it reads as a flow
  // travelling icon -> icon.
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (!automated) return setStep(0);
    if (reduceMotion) return setStep(NODES.length + 1);
    setStep(0);
    const t = setInterval(() => setStep((v) => (v >= NODES.length + 1 ? 0 : v + 1)), 1100);
    return () => clearInterval(t);
  }, [automated, reduceMotion]);

  return (
    <motion.div
      animate={reduceMotion ? {} : { y: [0, -10, 0] }}
      transition={{ duration: 5.5, repeat: Infinity, ease: "easeInOut" }}
      className={`w-full max-w-md ${className}`}
    >
      <div className="relative rounded-3xl border border-white/10 bg-white/[0.035] p-6 shadow-2xl backdrop-blur-xl">
        <motion.div
          animate={{ opacity: automated ? 0.5 : 0.3 }}
          transition={{ duration: 0.7 }}
          className={`pointer-events-none absolute -inset-px -z-10 rounded-3xl blur-xl ${
            automated ? "bg-amber-400/20" : "bg-ink-300/10"
          }`}
        />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400/30 to-amber-600/20 ring-1 ring-white/10">
              <Workflow className="h-5 w-5 text-amber-300" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Nextflow — Workflow Builder</p>
              <p className="text-xs text-slate-400">Workspace · Finance Ops</p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/10 px-2.5 py-1 text-[11px] font-medium text-amber-300 ring-1 ring-amber-400/20">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
            Live
          </span>
        </div>

        {/* Manual / Automated toggle - Manual pinned to the left edge,
            Automated pinned to the right edge; the switch itself sits in
            a fixed-size middle grid column flanked by two EQUAL (1fr)
            columns, so it's mathematically centered no matter how long
            either label is. */}
        <div className="mt-6 grid grid-cols-[1fr_auto_1fr] items-center gap-3 rounded-xl border border-white/10 bg-black/20 px-4 py-3">
          <span
            className={`text-left text-xs font-semibold transition-colors ${!automated ? "text-slate-200" : "text-slate-400"}`}
          >
            Manual
          </span>

          <button
            type="button"
            role="switch"
            aria-checked={automated}
            aria-label="Toggle between manual and automated workflow run"
            onClick={() => setAutomated((v) => !v)}
            className={`relative h-6 w-12 shrink-0 appearance-none rounded-full border-0 p-0 leading-none transition-colors duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400 ${
              automated ? "bg-amber-400/80" : "bg-slate-600/60"
            }`}
          >
            {/* Static base position (2px inset) + an animated delta on
                top, so the thumb's resting and traveled positions are
                both driven by the same explicit math as the track/thumb
                sizes (48px track, 20px thumb, 2px margin each side) -
                it can never compute past the track's edge. */}
            <motion.span
              initial={false}
              animate={{ x: automated ? 24 : 0 }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
              className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow"
            />
          </button>

          <span
            className={`text-right text-xs font-semibold transition-colors ${automated ? "text-amber-300" : "text-slate-400"}`}
          >
            Automated
          </span>
        </div>

        {/* 4-node workflow canvas */}
        <div className="relative mt-5 h-40 w-full overflow-hidden rounded-xl border border-white/5 bg-black/20">
          <svg
            viewBox="0 0 400 140"
            className="h-full w-full"
            role="img"
            aria-label={
              automated
                ? "Nextflow workflow running automatically through all steps"
                : "Workflow paused, waiting for manual trigger"
            }
          >
            <defs>
              <linearGradient id="nfGradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#F3D08A" />
                <stop offset="55%" stopColor="#E8A33D" />
                <stop offset="100%" stopColor="#B36F20" />
              </linearGradient>
            </defs>

            {automated ? (
              <>
                {/* connectors: end at each node's border, draw one after another */}
                {NODES.slice(0, -1).map((n, i) => {
                  const m = NODES[i + 1];
                  const len = Math.hypot(m.x - n.x, m.y - n.y);
                  const ux = (m.x - n.x) / len, uy = (m.y - n.y) / len;
                  const x1 = n.x + ux * 17, y1 = n.y + uy * 17, x2 = m.x - ux * 17, y2 = m.y - uy * 17;
                  const d = `M${x1} ${y1} L${x2} ${y2}`;
                  const on = step >= i + 1;
                  return (
                    <g key={`seg-${n.key}`}>
                      <path d={d} stroke="rgba(255,255,255,0.12)" strokeWidth="2.5" strokeLinecap="round" />
                      <motion.path
                        d={d}
                        stroke="url(#nfGradient)"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        initial={false}
                        animate={{ pathLength: on ? 1 : 0, opacity: on ? 1 : 0 }}
                        transition={on ? { duration: 0.7, ease: "easeInOut" } : { duration: 0.25 }}
                      />
                      {step === i + 1 && !reduceMotion && (
                        <motion.circle
                          key={`pkt-${step}`}
                          r="3.5"
                          fill="#FAE8C3"
                          initial={{ cx: x1, cy: y1, opacity: 1 }}
                          animate={{ cx: x2, cy: y2, opacity: [1, 1, 0] }}
                          transition={{ duration: 0.7, ease: "easeInOut" }}
                        />
                      )}
                    </g>
                  );
                })}

                {/* nodes: lit once the packet arrives, steady (no blinking) */}
                {NODES.map((n, i) => {
                  const lit = step >= i;
                  const delay = lit && i > 0 ? 0.6 : 0; // wait for the line to arrive
                  return (
                    <g key={n.key}>
                      {step === i && !reduceMotion && (
                        <motion.circle
                          key={`ring-${step}`}
                          cx={n.x} cy={n.y} fill="none" stroke={AMBER} strokeWidth="1.5"
                          initial={{ r: 13, opacity: 0 }}
                          animate={{ r: 23, opacity: [0, 0.6, 0] }}
                          transition={{ duration: 0.8, delay: i > 0 ? 0.6 : 0 }}
                        />
                      )}
                      <motion.circle
                        cx={n.x} cy={n.y} r="13" strokeWidth="1.5"
                        initial={false}
                        animate={{ fill: lit ? "#2A1D0B" : "#152531", stroke: lit ? AMBER : INK_MUTED }}
                        transition={{ duration: 0.3, delay }}
                      />
                      <foreignObject x={n.x - 7.5} y={n.y - 7.5} width="15" height="15">
                        <n.Icon
                          className={`h-4 w-4 transition-colors duration-300 ${lit ? "text-amber-300" : "text-slate-500"}`}
                          style={{ transitionDelay: `${delay}s` }}
                        />
                      </foreignObject>
                    </g>
                  );
                })}
              </>
            ) : (
              <>
                <path d={`M${PATH}`} fill="none" stroke={INK_MUTED} strokeWidth="2.5" strokeLinecap="round" strokeDasharray="3 5" opacity="0.6" />
                {NODES.map((n) => (
                  <g key={n.key} style={{ color: INK_MUTED }}>
                    <circle cx={n.x} cy={n.y} r="13" fill="#152531" stroke="currentColor" strokeWidth="1.5" />
                    <foreignObject x={n.x - 7.5} y={n.y - 7.5} width="15" height="15">
                      <PauseCircle className="h-4 w-4 text-slate-300" />
                    </foreignObject>
                  </g>
                ))}
              </>
            )}
          </svg>

          <div className="pointer-events-none absolute inset-x-0 bottom-1 flex justify-between px-2">
            {NODES.map((n) => (
              <div key={n.key} className="w-20 text-center">
                <p className={`text-[10px] font-semibold ${automated ? "text-white" : "text-slate-300"}`}>{n.label}</p>
              </div>
            ))}
          </div>

          {!automated && (
            <span className="absolute right-3 top-2 rounded-md bg-white/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300 ring-1 ring-white/15">
              Waiting on trigger
            </span>
          )}
        </div>

        {/* stats */}
        <div className="mt-5 grid grid-cols-3 gap-3">
          <Stat icon={<Gauge className="h-3.5 w-3.5" />} label="Runs/Day" value={automated ? "312" : "18"} good={automated} />
          <Stat icon={<CheckCircle2 className="h-3.5 w-3.5" />} label="Success Rate" value={automated ? "99.4%" : "76%"} good={automated} />
          <Stat icon={<Timer className="h-3.5 w-3.5" />} label="Avg Runtime" value={automated ? "4.2s" : "6+ min"} good={automated} />
        </div>

        <div className="mt-5 flex items-center gap-1.5 text-[11px] text-slate-400">
          <RefreshCw className="h-3 w-3" aria-hidden="true" />
          {automated ? "Run #482 succeeded · auto-triggered" : "Paused · last run 2h ago"}
        </div>
      </div>
    </motion.div>
  );
}

function Stat({ icon, label, value, good }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2.5">
      <div className={`flex items-center gap-1.5 text-[10px] uppercase tracking-wide ${good ? "text-amber-300/90" : "text-slate-400"}`}>
        {icon}
        {label}
      </div>
      <p className="mt-1 text-sm font-semibold text-white">{value}</p>
    </div>
  );
}
