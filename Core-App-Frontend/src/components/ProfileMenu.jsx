/**
 * components/ProfileMenu.jsx
 * ------------------------------------------------------------
 * Signed-in user's profile icon, shown top-right of the header
 * (reference: the Udemy account menu). Renders the user's first
 * initial in a circular badge; hovering (desktop) or tapping
 * (mobile) reveals a card with:
 *   - the initial again, the user's full name and email
 *   - a thin divider
 *   - "Admin Panel" (admin accounts only) above "Go to workspace"
 *   - a thin divider
 *   - Purchases/entitlements — see below
 *   - a thin divider
 *   - "Log out" — the header itself never shows a logout button;
 *     this card is the only place it lives, per requirement.
 *
 * Purchases/entitlements section
 * ------------------------------------------------------------
 * `user.products` (populated at login/register and refreshed via
 * GET /api/auth/me) is the real, licensed product list for this
 * account — it used to be ignored here in favor of always showing
 * every product in the static catalog as "purchased", which was
 * wrong for any account that didn't hold every license.
 *
 * The label and framing differ by account type, since "purchased"
 * doesn't mean the same thing for everyone:
 *   - Admin / enterprise accounts pay for specific product licenses,
 *     so this is a real "Purchases" list — only what's licensed,
 *     marked Active.
 *   - Community-edition sign-ups get every product free as part of
 *     the community plan (nothing was actually bought), so calling
 *     it "Purchases" would be misleading. It's shown instead as
 *     "Community plan" access with a Free tag, plus a link to
 *     request a demo of the paid/enterprise tier.
 * ------------------------------------------------------------
 */

import RequestDemoLink from "./RequestDemoLink.jsx";
import { useRef, useState } from "react";
import { PRODUCTS } from "../data/products.js";
import { DASHBOARD_ADMIN_PATH, DASHBOARD_USER_PATH } from "../config/dashboardRoutes.js";

const PRODUCT_ICON_BY_SLUG = Object.fromEntries(PRODUCTS.map((p) => [p.slug, p.icon]));

export default function ProfileMenu({ user, isAdmin, onLogout, variant = "desktop" }) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef(null);

  const initial = (user.fullName || user.email || "?").trim().charAt(0).toUpperCase();

  function openNow() {
    clearTimeout(closeTimer.current);
    setOpen(true);
  }
  function closeSoon() {
    closeTimer.current = setTimeout(() => setOpen(false), 150);
  }

  if (variant === "mobile") {
    // Inline, always-expanded version used inside the mobile menu panel
    // (there's no hover on touch devices, so no card-on-hover here).
    return (
      <div className="rounded-xl border border-ink-100 bg-white p-4">
        <ProfileCardBody user={user} initial={initial} isAdmin={isAdmin} onLogout={onLogout} />
      </div>
    );
  }

  return (
    <div className="relative" onMouseEnter={openNow} onMouseLeave={closeSoon}>
      <button
        type="button"
        id="profile-menu-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-label="Account menu"
        aria-expanded={open}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-ink-800 font-display text-sm font-semibold text-amber-400 ring-2 ring-transparent transition-all hover:ring-amber-300"
      >
        {initial}
      </button>

      {open && (
        <div
          id="profile-menu-card"
          className="absolute right-0 top-full z-50 mt-2 w-72 rounded-xl border border-ink-100 bg-white p-4 shadow-card"
        >
          <ProfileCardBody user={user} initial={initial} isAdmin={isAdmin} onLogout={onLogout} />
        </div>
      )}
    </div>
  );
}

function ProfileCardBody({ user, initial, isAdmin, onLogout }) {
  return (
    <>
      {/* Icon + name/email */}
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-ink-800 font-display text-base font-semibold text-amber-400">
          {initial}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink-800">{user.fullName}</p>
          <p className="truncate text-xs text-ink-400">{user.email}</p>
        </div>
      </div>

      <div className="my-3 h-px bg-ink-100" />

      {/* Workspace / admin links — admins only ever see "Admin Panel",
          everyone else only ever sees "Go to workspace". */}
      <div className="flex flex-col gap-1">
        {isAdmin ? (
          <a
            href={DASHBOARD_ADMIN_PATH}
            id="profile-admin-panel-link"
            className="rounded-md px-2 py-2 text-sm font-semibold text-ink-800 hover:bg-ink-50"
          >
            Admin Panel
          </a>
        ) : (
          <a
            href={DASHBOARD_USER_PATH}
            id="profile-go-to-workspace-link"
            className="rounded-md px-2 py-2 text-sm font-semibold text-ink-800 hover:bg-ink-50"
          >
            Go to workspace
          </a>
        )}
      </div>

      <div className="my-3 h-px bg-ink-100" />

      <PurchasesSection user={user} />

      <div className="my-3 h-px bg-ink-100" />

      <button
        type="button"
        id="profile-logout-btn"
        onClick={onLogout}
        className="w-full rounded-md px-2 py-2 text-left text-sm font-semibold text-red-500 hover:bg-red-50"
      >
        Log out
      </button>
    </>
  );
}

function PurchasesSection({ user }) {
  const products = user.products || [];
  const isCommunity = user.accountType === "community";

  const title = isCommunity ? "Community plan" : "Purchases";

  if (products.length === 0) {
    return (
      <div>
        <p className="px-2 text-xs font-semibold uppercase tracking-wide text-ink-300">{title}</p>
        <p className="px-2 py-1.5 text-sm text-ink-400">
          No products purchased yet.{" "}
          <RequestDemoLink id="profile-purchases-empty-cta" className="font-semibold text-amber-600 hover:underline">
            Request a demo
          </RequestDemoLink>
        </p>
      </div>
    );
  }

  return (
    <div>
      <p className="px-2 text-xs font-semibold uppercase tracking-wide text-ink-300">{title}</p>
      <ul className="mt-1.5 flex flex-col gap-1">
        {products.map((product) => (
          <li key={product.slug || product.id} className="flex items-center justify-between gap-2 px-2 py-1 text-sm">
            <span className="flex min-w-0 items-center gap-2 text-ink-700">
              <span aria-hidden="true">{PRODUCT_ICON_BY_SLUG[product.slug] || "•"}</span>
              <span className="truncate">{product.name}</span>
            </span>
            {isCommunity ? (
              <span className="flex-none rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-600">
                Free
              </span>
            ) : (
              <span className="flex flex-none items-center gap-1 text-[11px] font-semibold text-green-600">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" aria-hidden="true" />
                Active
              </span>
            )}
          </li>
        ))}
      </ul>

      {isCommunity && (
        <p className="mt-2 px-2 text-xs text-ink-400">
          Included free with the Community plan.{" "}
          <RequestDemoLink id="profile-purchases-upgrade-cta" className="font-semibold text-amber-600 hover:underline">
            Request a demo
          </RequestDemoLink>{" "}
          of Enterprise.
        </p>
      )}
    </div>
  );
}
