/**
 * components/Footer.jsx
 * ------------------------------------------------------------
 * Shared site footer: brand recap, quick links, copyright, and
 * social media icon links. Used on the Home page and every
 * product page.
 * ------------------------------------------------------------
 */

import RequestDemoLink from "./RequestDemoLink.jsx";

const SOCIAL_LINKS = [
  { name: "LinkedIn", href: "https://www.linkedin.com/company/onenextgen-automation-pvt-ltd/about/", icon: "linkedin" },
  { name: "X (Twitter)", href: "https://www.x.com", icon: "x" },
  { name: "YouTube", href: "https://www.youtube.com", icon: "youtube" },
  { name: "GitHub", href: "https://www.github.com", icon: "github" },
];

export default function Footer() {
  return (
    <footer className="border-t border-ink-100 bg-ink-800 px-6 py-12 text-ink-100/80 sm:px-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 md:flex-row md:justify-between">
        {/* Brand recap */}
        <div className="max-w-sm">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg bg-white">
              <img src="/Icon.png" alt="OneNextGen Automation" className="h-full w-full object-contain" />
            </div>
            <span className="font-display text-lg font-semibold text-white">OneNextGen Automation</span>
          </div>
          <p className="mt-3 text-sm text-ink-100/60">
            Automation, without the friction. OneNextGen Automation helps teams turn repetitive
            work into reliable, self-running processes.
          </p>
        </div>

        {/* Quick links */}
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-100/40">Products</p>
            <ul className="mt-3 space-y-2 text-sm">
              <li><a href="/products/nextflow" className="hover:text-amber-400">Nextflow</a></li>
              <li><a href="/products/business-process-mapper" className="hover:text-amber-400">Business Process Mapper</a></li>
              <li><a href="/products/document-parser" className="hover:text-amber-400">Document Parser</a></li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-100/40">Company</p>
            <ul className="mt-3 space-y-2 text-sm">
              <li><a href="/#contact" className="hover:text-amber-400">Contact us</a></li>
              <li><RequestDemoLink className="hover:text-amber-400">Request a demo</RequestDemoLink></li>
              <li><a href="/register" className="hover:text-amber-400">Create an account</a></li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-100/40">Follow us</p>
            <div className="mt-3 flex gap-3">
              {SOCIAL_LINKS.map((social) => (
                <a
                  key={social.name}
                  href={social.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={social.name}
                  id={`social-link-${social.icon}`}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 text-ink-100/70 transition-colors hover:border-amber-400 hover:text-amber-400"
                >
                  <SocialIcon name={social.icon} className="h-4 w-4" />
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto mt-10 max-w-6xl border-t border-white/10 pt-6 text-xs text-ink-100/50">
        © {new Date().getFullYear()} OneNextGen Automation, Inc. All rights reserved.
      </div>
    </footer>
  );
}

function SocialIcon({ name, className }) {
  const common = { viewBox: "0 0 24 24", fill: "currentColor", className };
  switch (name) {
    case "linkedin":
      return (
        <svg {...common}>
          <path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9h4v12H3V9Zm7 0h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.4c0-1.29-.02-2.94-1.79-2.94-1.8 0-2.08 1.4-2.08 2.85V21h-4V9Z" />
        </svg>
      );
    case "x":
      return (
        <svg {...common}>
          <path d="M18.9 3H21l-6.5 7.4L22 21h-6.3l-4.9-6.4L5.2 21H3l6.9-7.9L2 3h6.4l4.4 5.8L18.9 3Zm-1.1 16h1.2L7.3 4.9H6L17.8 19Z" />
        </svg>
      );
    case "youtube":
      return (
        <svg {...common}>
          <path d="M22 12s0-3.2-.4-4.7a2.9 2.9 0 0 0-2-2.1C17.9 5 12 5 12 5s-5.9 0-7.6.2a2.9 2.9 0 0 0-2 2C2 8.8 2 12 2 12s0 3.2.4 4.7a2.9 2.9 0 0 0 2 2C6.1 19 12 19 12 19s5.9 0 7.6-.2a2.9 2.9 0 0 0 2-2c.4-1.5.4-4.8.4-4.8ZM10 15.3V8.7L15.8 12 10 15.3Z" />
        </svg>
      );
    case "github":
      return (
        <svg {...common}>
          <path d="M12 2a10 10 0 0 0-3.16 19.5c.5.1.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.46-1.15-1.11-1.46-1.11-1.46-.9-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.52 2.34 1.08 2.91.83.09-.65.35-1.08.63-1.33-2.22-.25-4.56-1.11-4.56-4.95 0-1.1.39-2 1.03-2.7-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.4 9.4 0 0 1 5 0c1.91-1.3 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.6 1.03 2.7 0 3.85-2.35 4.7-4.58 4.94.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" />
        </svg>
      );
    default:
      return null;
  }
}
