/**
 * pages/ProductDetail.jsx
 * ------------------------------------------------------------
 * Renders the detail page for whichever product the header's
 * "Products" dropdown was clicked for. One component covers all
 * three products since their layout is identical — only the
 * copy (from data/products.js) changes.
 * ------------------------------------------------------------
 */

import RequestDemoLink from "../components/RequestDemoLink.jsx";
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import Header from "../components/Header.jsx";
import Footer from "../components/Footer.jsx";
import Reveal from "../components/Reveal.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { getProductBySlug } from "../data/products.js";
import { workspacePathForRole } from "../config/dashboardRoutes.js";
import NotFound from "./NotFound.jsx";

export default function ProductDetail() {
  const { slug } = useParams();
  const product = getProductBySlug(slug);
  const { user } = useAuth();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [slug]);

  if (!product) return <NotFound />;

  // "Try it out" only reads as a first-touch invitation, so it's shown to
  // signed-out visitors and to a user on their very first login. Anyone
  // who has logged in before already knows the workspace, so the button
  // switches to "Go to workspace" instead (see mockAuthService's
  // loginCount tracking for where that number comes from).
  const isReturningUser = !!user && (user.loginCount || 0) > 1;
  const ctaLabel = isReturningUser ? "Go to workspace" : "Try it out";

  return (
    <div className="min-h-screen bg-slate-25">
      <Header />

      {/* ---------------- Hero ---------------- */}
      <section className="bg-ink-800 px-6 py-16 text-white sm:px-10">
        <Reveal className="mx-auto max-w-4xl">
          <span className="text-3xl">{product.icon}</span>
          <p className="mt-3 font-mono text-xs uppercase tracking-widest text-amber-400">{product.tagline}</p>
          <h1 className="mt-2 font-display text-3xl font-semibold sm:text-4xl">{product.name}</h1>
          <p className="mt-4 max-w-2xl text-ink-100/80">{product.heroDescription}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <RequestDemoLink className="btn-primary inline-flex">
              Request a demo
            </RequestDemoLink>
            {user ? (
              // Full page load on purpose — this leaves the marketing site
              // for the separate automation dashboard product.
              <a href={workspacePathForRole(user.role)} id="product-cta-workspace-link" className="btn-secondary !bg-transparent !text-white !border-white/30 hover:!bg-white/10 inline-flex">
                {ctaLabel}
              </a>
            ) : (
              <Link to="/login" id="product-cta-try-it-out-link" className="btn-secondary !bg-transparent !text-white !border-white/30 hover:!bg-white/10 inline-flex">
                {ctaLabel}
              </Link>
            )}
          </div>
        </Reveal>
      </section>

      {/* ---------------- Features ---------------- */}
      <section className="px-6 py-16 sm:px-10">
        <div className="mx-auto max-w-5xl">
          <Reveal as="h2" className="font-display text-2xl font-semibold text-ink-800">
            What it does
          </Reveal>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            {product.features.map((feature, i) => (
              <Reveal
                key={feature.title}
                delay={i * 90}
                className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-card"
              >
                <h3 className="font-display text-base font-semibold text-ink-800">{feature.title}</h3>
                <p className="mt-2 text-sm text-ink-400">{feature.description}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- Other products ---------------- */}
      <section className="border-t border-ink-100 bg-white px-6 py-16 sm:px-10">
        <Reveal className="mx-auto max-w-5xl">
          <h2 className="font-display text-xl font-semibold text-ink-800">Explore other products</h2>
          <p className="mt-1 text-sm text-ink-400">See what else OneNextGen Automation can automate for your team.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/products/nextflow" className="link-action text-sm text-ink-700">Nextflow</Link>
            <span className="text-ink-200">•</span>
            <Link to="/products/business-process-mapper" className="link-action text-sm text-ink-700">Business Process Mapper</Link>
            <span className="text-ink-200">•</span>
            <Link to="/products/document-parser" className="link-action text-sm text-ink-700">Document Parser</Link>
          </div>
        </Reveal>
      </section>

      <Footer />
    </div>
  );
}
