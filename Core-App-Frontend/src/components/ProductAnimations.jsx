/**
 * components/ProductAnimations.jsx
 * ------------------------------------------------------------
 * Three looping, self-playing product visuals for the Home page
 * "What we build" section (replaces the static placeholder images):
 *
 *   - NextflowAnimation       workflow canvas: trigger -> condition ->
 *                             parallel branches -> sync, edges draw in
 *   - BusinessMapperAnimation screen recording -> step-by-step guide
 *   - DocumentParserAnimation invoice scan -> structured fields -> XLSX/CSV
 *
 * Each runs on a small step-clock (see <Stage>) that only ticks while the
 * card is on screen, and shows its finished state immediately for visitors
 * who prefer reduced motion. Brand tokens only (ink + amber).
 * ------------------------------------------------------------
 */
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useInView, useReducedMotion } from "framer-motion";
import {
  Zap, GitBranch, UserCheck, Mail, Database, CheckCircle2, Play, Circle,
  MousePointer2, FileText, FileSpreadsheet, Download, ScanLine,
} from "lucide-react";

/* ---------- shared shell + step clock ---------- */
function Stage({ title, badge, count, ms = 1100, children }) {
  const ref = useRef(null);
  const inView = useInView(ref, { margin: "-80px" });
  const reduce = useReducedMotion();
  const [s, setS] = useState(0);

  useEffect(() => {
    if (reduce) return setS(count + 2);
    if (!inView) return;
    const t = setInterval(() => setS((v) => (v >= count + 2 ? 0 : v + 1)), ms);
    return () => clearInterval(t);
  }, [inView, reduce, count, ms]);

  return (
    <div ref={ref} className="relative">
      <div className="pointer-events-none absolute -inset-4 -z-10 rounded-[2rem] bg-gradient-to-br from-amber-400/25 via-transparent to-ink-300/30 blur-2xl" />
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-ink-800 shadow-card">
        <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.03] px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
              <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
              <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
            </div>
            <span className="text-xs font-medium text-ink-100/80">{title}</span>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/10 px-2.5 py-1 text-[11px] font-medium text-amber-300 ring-1 ring-amber-400/20">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
            {badge}
          </span>
        </div>
        <div className="p-4 sm:p-5">{children(s)}</div>
      </div>
    </div>
  );
}

/* ---------- 1. Nextflow: workflow automation ---------- */
const NODES = {
  t: { x: 52, y: 120, Icon: Zap, label: "New invoice", at: 0 },
  c: { x: 175, y: 120, Icon: GitBranch, label: "Amount > ₹50k?", at: 1 },
  a: { x: 305, y: 52, Icon: UserCheck, label: "Approval", at: 2 },
  r: { x: 305, y: 188, Icon: Mail, label: "Notify team", at: 2 },
  s: { x: 430, y: 120, Icon: Database, label: "Update ERP", at: 3 },
};
const EDGES = [["t", "c"], ["c", "a"], ["c", "r"], ["a", "s"], ["r", "s"]];
const GAP = 24; // px (in viewBox units) kept clear at each node so lines end at the node edge, never behind it

export function NextflowAnimation() {
  return (
    <Stage title="Nextflow — Workflow Builder" badge="Running" count={5} ms={1000}>
      {(s) => (
        <>
          <div className="relative aspect-[2/1] w-full rounded-xl border border-white/5 bg-black/20 bg-flow-grid [background-size:18px_18px]">
            <svg viewBox="0 0 480 240" className="absolute inset-0 h-full w-full" aria-hidden="true">
              {EDGES.map(([a, b]) => {
                const p = NODES[a], q = NODES[b];
                const x1 = p.x + GAP, x2 = q.x - GAP, mx = (x1 + x2) / 2;
                const d = `M${x1} ${p.y} C${mx} ${p.y} ${mx} ${q.y} ${x2} ${q.y}`;
                const on = s >= NODES[b].at;
                return (
                  <g key={a + b}>
                    <path d={d} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="2" />
                    <motion.path
                      d={d} fill="none" stroke="#E8A33D" strokeWidth="2.5" strokeLinecap="round"
                      initial={false}
                      animate={{ pathLength: on ? 1 : 0, opacity: on ? 1 : 0 }}
                      transition={{ duration: 0.6, ease: "easeOut" }}
                    />
                    {on && s < 5 && (
                      <path d={d} fill="none" stroke="#FAE8C3" strokeWidth="2" strokeDasharray="4 16"
                        style={{ animation: "hero-dashflow 1s linear infinite" }} />
                    )}
                  </g>
                );
              })}
            </svg>
            {Object.entries(NODES).map(([k, n]) => {
              const on = s >= n.at;
              return (
                <div key={k} className="absolute -translate-x-1/2 -translate-y-1/2 text-center"
                  style={{ left: `${n.x / 4.8}%`, top: `${n.y / 2.4}%` }}>
                  <motion.div
                    initial={false}
                    animate={{ scale: on ? 1 : 0.9, opacity: on ? 1 : 0.45 }}
                    transition={{ delay: on && n.at > 0 ? 0.5 : 0 }}
                    className={`mx-auto flex h-10 w-10 items-center justify-center rounded-xl border transition-colors duration-500 sm:h-12 sm:w-12 ${
                      on ? "border-amber-400/60 bg-amber-400/15 text-amber-300 shadow-[0_0_24px_-4px_rgba(232,163,61,0.6)]"
                         : "border-white/10 bg-white/5 text-ink-200"}`}
                  >
                    <n.Icon className="h-4 w-4 sm:h-5 sm:w-5" />
                  </motion.div>
                  <p className="mt-1.5 whitespace-nowrap text-[9px] font-medium text-ink-100/80 sm:text-[10px]">{n.label}</p>
                </div>
              );
            })}
          </div>
          <div className="mt-4 flex items-center justify-between rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-xs">
            <span className="text-ink-200">Manual effort: <span className="font-semibold text-white">0 min</span></span>
            <span className={`inline-flex items-center gap-1.5 font-semibold ${s >= 4 ? "text-emerald-400" : "text-amber-300"}`}>
              {s >= 4 ? <><CheckCircle2 className="h-4 w-4" /> Run complete · 1.8s</> : "Running…"}
            </span>
          </div>
        </>
      )}
    </Stage>
  );
}

/* ---------- 2. Business Process Mapper: video -> steps ---------- */
const BPM_STEPS = ["Open the billing portal", "Export the monthly report", "Validate totals", "Email it to Finance"];
const CURSOR = [[17, 40], [83, 27], [50, 76], [84, 80]]; // [x%, y%] per scene

function Scene({ i }) {
  const row = "flex items-center justify-between rounded px-2 py-1";
  if (i === 0)
    return (
      <div className="flex h-full gap-2 p-2 text-[9px]">
        <div className="w-1/4 space-y-1">
          {["Dashboard", "Billing", "Reports"].map((t) => (
            <div key={t} className={`rounded px-2 py-1.5 ${t === "Billing" ? "bg-amber-400/25 text-amber-200" : "bg-white/5 text-ink-200"}`}>{t}</div>
          ))}
        </div>
        <div className="grid flex-1 grid-cols-2 gap-2">
          {["Open invoices · 24", "Paid this month · ₹4.8L"].map((t) => (
            <div key={t} className="rounded bg-white/5 p-2 text-ink-100">{t}</div>
          ))}
          <div className="col-span-2 rounded bg-white/5 p-2 text-ink-200">Billing overview</div>
        </div>
      </div>
    );
  if (i === 1)
    return (
      <div className="p-2 text-[9px]">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-ink-100">Monthly report · Sep 2026</span>
          <span className="rounded bg-amber-400/30 px-2 py-1 text-amber-100">Export CSV</span>
        </div>
        {[["INV-4819", "₹12,400"], ["INV-4820", "₹8,900"], ["INV-4821", "₹48,250"]].map(([a, b]) => (
          <div key={a} className={`${row} mb-1 bg-white/5 text-ink-100`}><span>{a}</span><span>{b}</span></div>
        ))}
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.9 }}
          className="mt-1 inline-flex items-center gap-1 rounded bg-emerald-400/20 px-2 py-1 text-emerald-300">
          <Download className="h-3 w-3" /> report.csv saved
        </motion.div>
      </div>
    );
  if (i === 2)
    return (
      <div className="p-2 text-[9px]">
        <div className="mb-1.5 text-ink-100">Monthly report · Sep 2026</div>
        {[["INV-4819", "₹12,400"], ["INV-4820", "₹8,900"], ["INV-4821", "₹48,250"]].map(([a, b]) => (
          <div key={a} className={`${row} mb-1 bg-white/5 text-ink-100`}><span>{a}</span><span>{b}</span></div>
        ))}
        <div className={`${row} border border-amber-400/70 bg-amber-400/15 text-amber-100`}><span>Total</span><span>₹69,550</span></div>
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}
          className="mt-1.5 inline-flex items-center gap-1 text-emerald-300"><CheckCircle2 className="h-3 w-3" /> Totals match ledger</motion.div>
      </div>
    );
  return (
    <div className="p-2 text-[9px] text-ink-100">
      <div className="mb-1.5 text-ink-200">New message</div>
      {[["To", "finance@onenextgen.com"], ["Subject", "Sep 2026 billing report"]].map(([k, v]) => (
        <div key={k} className="mb-1 flex gap-2 rounded bg-white/5 px-2 py-1"><span className="w-10 text-ink-300">{k}</span>{v}</div>
      ))}
      <div className="mb-1 flex items-center gap-1 rounded bg-white/5 px-2 py-1"><FileSpreadsheet className="h-3 w-3" /> report.csv</div>
      <div className="flex items-center gap-2">
        <span className="rounded bg-amber-400/30 px-3 py-1 text-amber-100">Send</span>
        <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9 }} className="text-emerald-300">Sent ✓</motion.span>
      </div>
    </div>
  );
}

export function BusinessMapperAnimation() {
  return (
    <Stage title="Business Process Mapper" badge="Generating" count={4} ms={1800}>
      {(s) => {
        const scene = Math.min(Math.max(s - 1, 0), 3);
        const cur = CURSOR[scene];
        const pos = Math.min(s, 4);
        return (
          <div className="grid gap-4 sm:grid-cols-[1.25fr_1fr]">
            <div>
              <div className="relative aspect-video overflow-hidden rounded-xl border border-white/10 bg-ink-700">
                <div className="flex h-5 items-center gap-2 border-b border-white/5 bg-white/5 px-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-red-400/70" />
                  <span className="rounded bg-black/20 px-2 text-[8px] text-ink-300">billing.onenextgen.com</span>
                  <span className="ml-auto inline-flex items-center gap-1 text-[8px] font-semibold text-red-300">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-400" /> REC
                  </span>
                </div>
                <AnimatePresence mode="wait">
                  <motion.div key={scene} className="absolute inset-x-0 bottom-0 top-5"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
                    <Scene i={scene} />
                  </motion.div>
                </AnimatePresence>
                <motion.div className="absolute z-10" initial={false}
                  animate={{ left: `${cur[0]}%`, top: `${cur[1]}%` }} transition={{ type: "spring", stiffness: 90, damping: 16 }}>
                  <motion.span key={scene} className="absolute -left-2 -top-2 h-4 w-4 rounded-full border border-amber-300"
                    initial={{ scale: 0, opacity: 0.8 }} animate={{ scale: 2, opacity: 0 }} transition={{ delay: 0.8, duration: 0.5 }} />
                  <MousePointer2 className="h-4 w-4 fill-white text-ink-800" />
                </motion.div>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <Play className="h-4 w-4 fill-amber-400 text-amber-400" />
                <div className="relative h-1.5 flex-1 rounded-full bg-white/10">
                  <motion.div className="h-full rounded-full bg-amber-400" initial={false}
                    animate={{ width: `${pos * 25}%` }} transition={{ duration: s === 0 ? 0.3 : 1.8, ease: "linear" }} />
                  <motion.span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white" initial={false}
                    animate={{ left: `${pos * 25}%` }} transition={{ duration: s === 0 ? 0.3 : 1.8, ease: "linear" }} />
                </div>
                <span className="font-mono text-[10px] text-ink-200">0:0{pos * 2} / 0:08</span>
              </div>
            </div>

            <ol className="space-y-2">
              {BPM_STEPS.map((t, i) => {
                const done = s > i + 1, active = s === i + 1;
                return (
                  <motion.li key={t} initial={false}
                    animate={{ opacity: done || active ? 1 : 0.25, x: done || active ? 0 : 10 }}
                    className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 text-xs transition-colors duration-500 ${
                      active ? "border-amber-400/60 bg-amber-400/15 text-white" : done ? "border-amber-400/20 bg-amber-400/5 text-white" : "border-white/5 bg-white/[0.03] text-ink-200"}`}>
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                      {done ? <CheckCircle2 className="h-5 w-5 text-amber-400" /> : active ? <span className="h-3 w-3 animate-pulse rounded-full bg-amber-400" /> : <Circle className="h-4 w-4" />}
                    </span>
                    <span><span className="font-mono text-[10px] text-amber-300">Step {i + 1}</span><br />{t}</span>
                  </motion.li>
                );
              })}
            </ol>
          </div>
        );
      }}
    </Stage>
  );
}

/* ---------- 3. Document Parser: document -> XLSX / CSV ---------- */
const FIELDS = [
  ["Vendor", "OneNextGen Automation Pvt Ltd"],
  ["Invoice no.", "INV-4821"],
  ["Date", "12 Oct 2026"],
  ["Line items", "3 rows"],
  ["Total", "₹48,250.00"],
];

export function DocumentParserAnimation() {
  return (
    <Stage title="Document Parser" badge="Extracting" count={7} ms={850}>
      {(s) => (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="relative overflow-hidden rounded-xl bg-white p-4 text-ink-800">
            <div className="flex items-center justify-between text-[11px] font-bold tracking-wide">
              <span className="flex items-center gap-2"><FileText className="h-4 w-4 text-ink-400" /> INVOICE</span>
              <span className="font-mono text-[9px] font-medium text-ink-300">Page 1/1</span>
            </div>
            <div className="mt-3 space-y-1.5 text-[10px] leading-tight">
              {[
                <><p className="font-semibold">OneNextGen Automation Pvt Ltd</p><p className="text-ink-300">14 Peenya Industrial Area, Bengaluru</p></>,
                <p>Invoice No: <span className="font-semibold">INV-4821</span></p>,
                <p>Date: <span className="font-semibold">12 Oct 2026</span></p>,
                <div className="space-y-0.5">
                  {[["Steel bolts M8 × 200", "₹12,000"], ["Safety gloves × 50", "₹9,250"], ["Machine oil 20L × 10", "₹27,000"]].map(([a, b]) => (
                    <p key={a} className="flex justify-between"><span>{a}</span><span>{b}</span></p>
                  ))}
                </div>,
                <p className="flex justify-between text-[11px] font-bold"><span>Total</span><span>₹48,250.00</span></p>,
              ].map((node, i) => (
                <div key={i} className={`rounded px-1.5 py-1 transition-all duration-500 ${s > i + 1 ? "bg-amber-300/50 ring-1 ring-amber-400" : ""}`}>{node}</div>
              ))}
            </div>
            {s < 7 && (
              <motion.div className="absolute inset-x-0 h-10 bg-gradient-to-b from-transparent via-amber-400/30 to-transparent"
                initial={false} animate={{ top: s < 2 ? "-20%" : `${Math.min(s - 1, 5) * 17 - 6}%` }}
                transition={{ duration: 0.8, ease: "easeInOut" }}>
                <ScanLine className="absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-amber-500" />
              </motion.div>
            )}
          </div>

          <div className="flex flex-col">
            <div className="flex-1 overflow-hidden rounded-xl border border-white/10 text-xs">
              <div className="grid grid-cols-2 bg-white/5 px-3 py-2 font-mono text-[10px] uppercase tracking-wider text-ink-200">
                <span>Field</span><span>Value</span>
              </div>
              {FIELDS.map(([k, v], i) => (
                <motion.div key={k} initial={false}
                  animate={{ opacity: s > i + 1 ? 1 : 0, y: s > i + 1 ? 0 : 6 }}
                  className="grid grid-cols-2 border-t border-white/5 px-3 py-2">
                  <span className="text-ink-200">{k}</span>
                  <span className="font-medium leading-snug text-white">{v}</span>
                </motion.div>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <AnimatePresence>
                {s >= 7 && ["XLSX", "CSV"].map((f, i) => (
                  <motion.span key={f}
                    initial={{ opacity: 0, scale: 0.8, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0 }} transition={{ delay: i * 0.12 }}
                    className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-amber-400 px-3 py-2 text-xs font-semibold text-ink-800">
                    {f === "XLSX" ? <FileSpreadsheet className="h-4 w-4" /> : <Download className="h-4 w-4" />} {f}
                  </motion.span>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>
      )}
    </Stage>
  );
}
