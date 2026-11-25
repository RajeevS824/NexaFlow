/**
 * pages/Home.jsx
 * ------------------------------------------------------------
 * Public marketing homepage: header, hero/about, product cards,
 * contact section, footer. Reachable without logging in.
 *
 * Hero is a two-column layout (copy on the left, the animated
 * Nextflow workflow-builder card on the right, see
 * HeroWorkflowAnimation) on a dark navy background, with a
 * full-bleed animated backdrop behind everything (see
 * HeroBackground) — a drifting dot-grid, ambient amber/teal
 * glows, a light sheen sweep, and slow-rising particles, built
 * entirely from the site's existing color tokens. The hero copy
 * and diagram fade/slide in on load, and the product rows below
 * (plus the contact section) fade in as they scroll into view
 * (see components/Reveal.jsx) for a smoother, more professional
 * feel throughout the page.
 *
 * It intentionally does NOT greet a signed-in user by name in
 * the heading — the eyebrow label above it still says "Welcome
 * back" for a signed-in visitor, but the big heading stays the
 * same evergreen copy either way.
 * ------------------------------------------------------------
 */

import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Header from "../components/Header.jsx";
import Footer from "../components/Footer.jsx";
import ContactSection from "../components/ContactSection.jsx";
import HeroWorkflowAnimation from "../components/HeroWorkflowAnimation.jsx";
import HeroBackground from "../components/HeroBackground.jsx";
import Reveal from "../components/Reveal.jsx";
import RequestDemoLink from "../components/RequestDemoLink.jsx";
import { PRODUCTS } from "../data/products.js";
import {
  NextflowAnimation,
  BusinessMapperAnimation,
  DocumentParserAnimation,
} from "../components/ProductAnimations.jsx";

// Animated visual + home-page tagline per product (replaces the old static images).
const VISUALS = {
  nextflow: { Visual: NextflowAnimation, tagline: "Workflow automation" },
  "business-process-mapper": { Visual: BusinessMapperAnimation, tagline: "Video to step-by-step guide" },
  "document-parser": { Visual: DocumentParserAnimation, tagline: "Documents to Excel or CSV" },
};

export default function Home() {
  const { user } = useAuth();
  const location = useLocation();

  // "Contact us" and every "Request demo" button link to /#contact. Scroll
  // to the contact section on arrival, from another page OR when already
  // on Home (location.key changes on every navigation, so this re-runs).
  useEffect(() => {
    if (location.hash === "#contact") {
      // Wait a tick for layout to settle before scrolling.
      requestAnimationFrame(() => {
        document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
      });
    }
  }, [location.key, location.hash]);

  return (
    <div className="min-h-screen bg-slate-25">
      <Header />

      {/* ---------------- Hero: content left, animation right ---------------- */}
      <section className="relative overflow-hidden bg-ink-800 px-6 py-20 text-white sm:px-10 sm:py-28">
        <HeroBackground />
        <div className="relative z-10 mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
          <div>
            <Reveal>
              <p className="font-mono text-xs uppercase tracking-widest text-amber-400">
                {user ? "Welcome back" : "About OneNextGen Automation"}
              </p>
            </Reveal>
            <Reveal delay={100}>
              <h1 className="mt-3 font-display text-4xl font-semibold leading-tight sm:text-5xl lg:text-6xl">
                Automation, without the friction.
              </h1>
            </Reveal>
            <Reveal delay={200}>
              <p className="mt-5 max-w-xl text-base text-ink-100/80 sm:text-lg">
                OneNextGen Automation builds tools that turn repetitive, manual work into
                reliable, self-running processes — from visual workflows to
                video-to-document conversion to invoice data extraction. Less
                time on busywork, more time on the work that matters.
              </p>
            </Reveal>
            <Reveal delay={300}>
              <div className="mt-8 flex flex-wrap gap-3">
                <RequestDemoLink id="hero-request-demo-btn" className="btn-primary">
                  Request a demo
                </RequestDemoLink>
                {!user && (
                  <Link
                    to="/register"
                    id="hero-create-account-btn"
                    className="btn-secondary !bg-transparent !text-white !border-white/30 hover:!bg-white/10"
                  >
                    Create a free account
                  </Link>
                )}
              </div>
            </Reveal>
          </div>

          <Reveal delay={150} className="relative mx-auto flex w-full max-w-md items-center justify-center">
            <HeroWorkflowAnimation />
          </Reveal>
        </div>
      </section>

      {/* ---------------- Products ----------------
          Each product is a full-width row: copy on one side, a
          looping animated product visual on the other, alternating sides row to
          row (reference: make.com's "AI and automation" /
          "Enterprise" sections). Every row fades/slides into
          view as it's scrolled to, and each visual
          plays only while on screen (see components/ProductAnimations.jsx). */}
      <section className="px-6 py-20 sm:px-10">
        <div className="mx-auto max-w-6xl">
          <Reveal className="mx-auto max-w-2xl text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-amber-500">What we build</p>
            <h2 className="mt-3 font-display text-2xl font-semibold text-ink-800 sm:text-3xl">
              Three products, one goal: less manual work
            </h2>
          </Reveal>

          <div className="mt-20 flex flex-col gap-24">
            {PRODUCTS.map((product, i) => {
              const imageFirst = i % 2 === 1;
              const { Visual, tagline } = VISUALS[product.slug];
              return (
                <Reveal
                  key={product.slug}
                  delay={i * 100}
                  className="group grid items-center gap-10 lg:grid-cols-2 lg:gap-16"
                >
                  <div className={imageFirst ? "lg:order-2" : ""}>
                    <p className="font-mono text-xs uppercase tracking-widest text-amber-500">
                      {String(i + 1).padStart(2, "0")} · {tagline}
                    </p>
                    <h3 className="mt-3 font-display text-3xl font-bold leading-tight text-ink-800 sm:text-4xl">
                      {product.name}
                    </h3>
                    <p className="mt-5 max-w-lg text-base text-ink-400">{product.summary}</p>
                    <Link
                      to={product.path}
                      id={`product-card-${product.slug}-link`}
                      className="mt-7 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-400 to-amber-500 px-6 py-3 text-sm font-semibold text-ink-800 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card"
                    >
                      Explore {product.name}
                      <span className="transition-transform duration-200 group-hover:translate-x-1">→</span>
                    </Link>
                  </div>

                  <div className={`w-full ${imageFirst ? "lg:order-1" : ""}`}>
                    <Visual />
                  </div>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* ---------------- Contact ---------------- */}
      <ContactSection />

      <Footer />
    </div>
  );
}
