/**
 * components/HeroBackground.jsx
 * ------------------------------------------------------------
 * Full-bleed animated backdrop for the Home page hero, sitting
 * behind both the copy and the FlowMotif diagram. Two layers:
 *
 *   1. A faint drifting dot-grid (reuses the app's `flow-grid`
 *      background-image token) that slowly pans, for a
 *      technical "canvas" feel.
 *   2. A handful of small amber particles that drift upward and
 *      fade, scattered across the full width of the section (not
 *      just behind the diagram on the right), for a sense of
 *      motion across the whole hero.
 *
 * A sweeping diagonal "sheen" and pulsing ambient glows were
 * also tried here and then removed after feedback that they
 * read as flashing-light effects — the particles below were
 * kept since they're a gentle, continuous fade rather than a
 * brightness flash.
 *
 * Purely decorative, aria-hidden, and disabled under
 * prefers-reduced-motion (see index.css).
 * ------------------------------------------------------------
 */

const PARTICLES = [
  { left: "6%", top: "72%", size: 3, duration: "9s", delay: "0s" },
  { left: "16%", top: "38%", size: 4, duration: "11s", delay: "-3s" },
  { left: "30%", top: "82%", size: 3, duration: "8s", delay: "-6s" },
  { left: "46%", top: "24%", size: 5, duration: "12.5s", delay: "-2s" },
  { left: "58%", top: "64%", size: 3, duration: "10s", delay: "-5s" },
  { left: "70%", top: "18%", size: 4, duration: "9.5s", delay: "-1s" },
  { left: "84%", top: "68%", size: 3, duration: "10.5s", delay: "-7s" },
  { left: "40%", top: "52%", size: 3, duration: "8.5s", delay: "-4s" },
];

export default function HeroBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* 1. Drifting dot-grid */}
      <div className="animate-grid-drift absolute inset-0 bg-flow-grid opacity-30 [background-size:28px_28px]" />

      {/* 2. Slow-rising particles across the full section width */}
      {PARTICLES.map((p, i) => (
        <span
          key={i}
          className="hero-particle"
          style={{
            left: p.left,
            top: p.top,
            width: p.size,
            height: p.size,
            animationDuration: p.duration,
            animationDelay: p.delay,
          }}
        />
      ))}
    </div>
  );
}
