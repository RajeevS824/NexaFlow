/**
 * components/Header.jsx
 * ------------------------------------------------------------
 * Site header shared by the Home page and every product page.
 * Built as a flexible row — [brand] [primary nav] [actions] —
 * that wraps on narrow screens, specifically so new items can
 * be added later without restructuring anything:
 *   - To add a brand-area item (next to the logo), add it inside
 *     the "brand" cell below.
 *   - To add a primary nav link, add an entry to the <nav>.
 *   - To add a header action/button, add an entry to the
 *     "actions" cell.
 *
 * All items (Products dropdown, Contact us, Sign in / Profile,
 * Request demo) are ALWAYS visible in the main header at every
 * screen size — nothing is hidden behind a hamburger menu.
 *
 * "Products" opens on hover (desktop), matching the reference
 * make.com-style mega-menu behaviour, with a click fallback
 * kept for touch/keyboard use.
 *
 * Admin-only "Menu" dropdown:
 * Shown next to the company name ONLY when the signed-in user's
 * `role` is "admin".
 * It now holds a single "Admin Panel" link that takes the admin
 * to the NexaFlow RPA automation dashboard (a full page load, on
 * purpose — see components/ProfileMenu.jsx for why).
 *
 * Signed-in users no longer see a "Log out" button in the header
 * itself — that now lives inside the profile card (see
 * components/ProfileMenu.jsx). The header's top-right corner
 * instead shows the profile icon (first-letter avatar).
 * ------------------------------------------------------------
 */

import RequestDemoLink from "./RequestDemoLink.jsx";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import ProfileMenu from "./ProfileMenu.jsx";
import { DASHBOARD_ADMIN_PATH } from "../config/dashboardRoutes.js";

// Extensible config for the "Products" dropdown - add a new
// product here and it appears in the dropdown and gets routed.
const PRODUCTS = [
  {
    name: "Nextflow",
    path: "/products/nextflow",
    blurb: "Visual workflow automation",
  },
  {
    name: "Business Process Mapper",
    path: "/products/business-process-mapper",
    blurb: "Turn screen recordings into SOPs",
  },
  {
    name: "Document Parser",
    path: "/products/document-parser",
    blurb: "Invoice data, extracted to CSV",
  },
];

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [productsOpen, setProductsOpen] = useState(false);
  const [adminMenuOpen, setAdminMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const productsCloseTimer = useRef(null);
  const adminCloseTimer = useRef(null);

  const isAdmin = user?.role === "admin";

  // Subtle elevation once the page has scrolled past the top, so the
  // sticky header reads as "lifted" above the content beneath it.
  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function handleLogout() {
    logout();
    navigate("/");
  }

  // "Contact us" scrolls to the #contact section on the home page.
  // From any other page, it navigates home first, then Home.jsx
  // scrolls to #contact on mount (see the useEffect there).
  function handleContactClick(e) {
    e.preventDefault();
    if (location.pathname === "/") {
      document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
    } else {
      navigate("/#contact");
    }
  }

  function openProducts() {
    clearTimeout(productsCloseTimer.current);
    setProductsOpen(true);
  }
  function closeProductsSoon() {
    productsCloseTimer.current = setTimeout(() => setProductsOpen(false), 150);
  }
  function openAdminMenu() {
    clearTimeout(adminCloseTimer.current);
    setAdminMenuOpen(true);
  }
  function closeAdminMenuSoon() {
    adminCloseTimer.current = setTimeout(() => setAdminMenuOpen(false), 150);
  }

  return (
    <header
      className={`sticky top-0 z-40 border-b border-ink-100 bg-white/95 backdrop-blur transition-shadow duration-300 ${
        scrolled ? "header-scrolled" : ""
      }`}
    >
      {/* Flex layout: brand | primary nav | actions (wraps on narrow screens) */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-6 py-4 sm:px-10">
        {/* ---------------- Brand cell ---------------- */}
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2.5" id="brand-home-link">
            <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg bg-ink-800">
              <img src="/Icon.png" alt="OneNextGen Automation" className="h-full w-full object-contain" />
            </div>
            <span className="font-display text-xl font-semibold text-ink-800">OneNextGen Automation</span>
          </Link>

          {/* Admin-only "Menu" dropdown, shown right next to the company name */}
          {isAdmin && (
            <div
              className="relative"
              onMouseEnter={openAdminMenu}
              onMouseLeave={closeAdminMenuSoon}
            >
              <button
                type="button"
                id="admin-menu-trigger"
                onClick={() => setAdminMenuOpen((v) => !v)}
                className="flex items-center gap-1 rounded-md border border-ink-200 px-2.5 py-1.5 text-sm font-medium text-ink-600 hover:bg-ink-50"
              >
                Menu
                <ChevronDown open={adminMenuOpen} />
              </button>
              {adminMenuOpen && (
                <div className="absolute left-0 top-full mt-2 w-52 rounded-xl border border-ink-100 bg-white py-2 shadow-card">
                  <p className="px-4 pb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-300">
                    Admin
                  </p>
                  {/* Full page load on purpose: this leaves the marketing
                      site for the separate automation dashboard app. */}
                  <a
                    href={DASHBOARD_ADMIN_PATH}
                    id="admin-menu-admin-panel-link"
                    className="block px-4 py-2 text-sm font-medium text-ink-600 hover:bg-ink-50 hover:text-ink-800"
                  >
                    Admin Panel
                  </a>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ---------------- Primary nav cell (always visible) ---------------- */}
        <nav className="flex items-center gap-1 justify-self-start pl-4">
          <div className="relative" onMouseEnter={openProducts} onMouseLeave={closeProductsSoon}>
            <button
              type="button"
              id="products-dropdown-trigger"
              onClick={() => setProductsOpen((v) => !v)}
              className="flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium text-ink-600 hover:bg-ink-50 hover:text-ink-800"
            >
              Products
              <ChevronDown open={productsOpen} />
            </button>
            {productsOpen && (
              <div className="absolute left-0 top-full w-72 rounded-xl border border-ink-100 bg-white py-2 shadow-card">
                {/* invisible bridge so the pointer can cross the gap
                    between the trigger and the panel without closing it */}
                <div className="absolute -top-2 left-0 h-2 w-full" />
                {PRODUCTS.map((product) => (
                  <Link
                    key={product.path}
                    to={product.path}
                    id={`products-dropdown-${product.path.split("/").pop()}`}
                    onClick={() => setProductsOpen(false)}
                    className="block px-4 py-2.5 transition-colors hover:bg-ink-50"
                  >
                    <span className="block text-sm font-semibold text-ink-800">{product.name}</span>
                    <span className="block text-xs text-ink-400">{product.blurb}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <a
            href="#contact"
            id="contact-us-nav-link"
            onClick={handleContactClick}
            className="rounded-md px-3 py-2 text-sm font-medium text-ink-600 hover:bg-ink-50 hover:text-ink-800"
          >
            Contact us
          </a>
        </nav>

        {/* ---------------- Actions cell (always visible) ---------------- */}
        <div className="flex items-center gap-4 md:ml-auto">
          {!user && (
            <Link to="/login" id="header-signin-link" className="link-action text-sm text-ink-600">
              Sign in
            </Link>
          )}
          <RequestDemoLink id="request-demo-btn" className="btn-primary !px-4 !py-2 text-sm">
            Request demo
          </RequestDemoLink>
          {user && <ProfileMenu user={user} isAdmin={isAdmin} onLogout={handleLogout} />}
        </div>
      </div>
    </header>
  );
}

function ChevronDown({ open }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
