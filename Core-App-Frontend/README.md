# NexaFlow — Frontend Only (No Backend Required)

This is the **frontend-only** version of the NexaFlow site. It runs entirely
in the browser — there is no Express server, no MSSQL database, and no
network calls to anywhere. Every "backend" action (register, login, forgot
password, reset password, contact form, demo request) is simulated locally
using the browser's `localStorage`, so nothing ever shows a connection error.

## What's on the site

- **Home (`/`)** — public marketing homepage: header, hero, three product
  cards, a contact section, and a footer. No login required to view it.
- **Header** (shown on Home and product pages) —
  - Company logo + name, top left
  - **Products** dropdown → Nextflow, Business Process Mapper, Document Parser — each opens its own page
  - **Contact us** → smooth-scrolls to the contact section on the Home page
  - **Request demo** button, top right → smooth-scrolls to the same contact section as **Contact us**, with a demo-request message pre-filled
  - An admin-only **Menu** dropdown next to the company name (see "Admin login" below)
  - Collapses into a hamburger menu on mobile
- **Product pages (`/products/nextflow`, `/products/business-process-mapper`, `/products/document-parser`)** — one page per product with a hero, feature grid, and a demo CTA
- **Request a demo** — every "Request demo" / "Request a demo" button (header, hero, footer, profile menu, product pages) uses `components/RequestDemoLink.jsx` to jump to the Home page contact form, which then submits to the demo-request endpoint. The old `/request-demo` URL redirects there.
- **Login / Register / Reset password** — unchanged from before, still fully working against the mock auth service
- **Footer** — brand recap, quick links, copyright, and social icons

## Admin login (demo credentials)

To see the admin-only **Menu** dropdown in the header, sign in with:

- **Email:** `nexflow@gmail.com`
- **Password:** `nex@flow$123`

### Where this is configured
Open `src/services/mockAuthService.js` and look for the block labeled
**"ADMIN CONFIGURATION"** near the top of the file — it defines two
constants, `ADMIN_EMAIL` and `ADMIN_PASSWORD`. The `login()` function checks
these first; if they match, it returns a user object with `role: "admin"`
instead of looking the user up in the mock user list.

`src/components/Header.jsx` then reads `user.role` from `AuthContext` — if
it's `"admin"`, the extra **Menu** dropdown renders next to the company name.
Everyone else (including a normal registered user) never sees it.

> In a real backend, this would be a `role` column on the Users table,
> returned by the login API after checking the database — never a
> hardcoded email/password pair. It's hardcoded here only because this
> build has no server. When you connect a real backend, delete the
> `ADMIN_EMAIL` / `ADMIN_PASSWORD` block and read `user.role` from the API
> response instead.

## How the mock backend works

`src/services/mockAuthService.js` replaces the real API. It:
- Stores registered users in `localStorage` (with bcrypt-hashed passwords, just like a real backend would)
- Issues a mock session token on login, with a special-cased admin login (see above)
- Generates a real password-reset token and expiry when you use "Forgot password?" — and since there's no mail server, it displays the reset link directly in the UI instead of emailing it
- Validates and consumes that token on the Reset Password page
- Stores Contact form and Request Demo submissions locally (`submitContactMessage`) so those forms behave like a real lead-capture endpoint

## Step-by-step setup

**1. Install Node.js** (v18+) if you don't have it: https://nodejs.org

**2. Install dependencies**
```bash
cd nexaflow-frontend-only
npm install
```

**3. Start the dev server**
```bash
npm run dev
```

**4. Open the app**
Visit `http://localhost:5173` in your browser. You'll land on the Home page.

That's it — no `.env` file, no database, no SMTP setup needed.

## Try the full flow

1. Browse the Home page — hero, product cards, Products dropdown in the header, Contact section, footer.
2. Click a product in the **Products** dropdown to see its detail page.
3. Click **Request demo** (top right) — it scrolls to the contact form with a demo message pre-filled; submit it.
4. Click **Contact us** in the header — it scrolls down to the contact form on the Home page.
5. Click **Sign in** → **Create an account**, register, then sign in with those credentials.
6. Sign out, then sign back in with the admin credentials above to see the **Menu** dropdown appear next to the company name.
7. Test password reset from Login → **Forgot password?** → the reset link appears on-screen (no real email is sent) → click it → set a new password.

## Limitations of this mode

- Data lives only in your browser's `localStorage`. Clearing site data / using a different browser resets everything.
- No real email is sent — the reset link is shown on-screen instead.
- Contact and demo-request submissions aren't sent anywhere — they're stored locally so the forms have something to "succeed" against.
- This is meant for UI development, demos, and design review. When you're ready to go live, swap `src/services/mockAuthService.js` back out for a real API client — the components already call it with the same function names and response shapes, so the swap is minimal.

## Project structure
```
nexaflow-frontend-only/
├── src/
│   ├── components/
│   │   ├── Header.jsx          # grid-based nav: products dropdown, contact link, request demo, admin menu
│   │   ├── Footer.jsx          # copyright + social icons
│   │   ├── ContactSection.jsx  # "Contact us" form, shown on Home
│   │   ├── RequestDemoLink.jsx # every "Request demo" button: jumps to the contact form, pre-fills a demo message
│   │   ├── ProductAnimations.jsx # animated visuals for the Home product section
│   │   ├── FlowMotif.jsx       # signature animated brand graphic
│   │   ├── InputField.jsx      # reusable labeled input (with show/hide password)
│   │   └── ProtectedRoute.jsx  # not currently used (Home is public) — ready for a future gated page

---

## Running the backends (full workspace)

The interactive NexaFlow **workspace** (`/dashboard`, `/admin-panel`) talks to
three sibling Python backends, each on its own port, all sharing the one root
`.env`:

| Backend | Port | Start command (from the project root) |
| --- | --- | --- |
| NexaFlow (auth, users, roles) | 8001 | `python nexaflow-backend/run.py` |
| Document Parser | 8000 | `python Document-Parser-Backend/run.py` |
| Business Map (orchestrator + audio + video) | 8020/8021/8022 | `python Business-Map-Backend/run_backend.py` |

The Business Map launcher starts its three services (orchestrator **8020**,
audio **8021**, video **8022**) and waits for them to become healthy; the
frontend only talks to the orchestrator at `http://127.0.0.1:8020`
(`VITE_BUSINESS_MAP_API_BASE_URL`). Install each backend's Python
requirements (e.g. `pip install -r Business-Map-Backend/requirements.txt`
plus the per-service `requirements_*_service.txt` files) before starting.
│   ├── context/
│   │   └── AuthContext.jsx     # session state (user, role, login/logout)
│   ├── data/
│   │   └── products.js         # product copy shared by Home cards + product pages
│   ├── pages/
│   │   ├── Home.jsx            # public marketing homepage
│   │   ├── ProductDetail.jsx   # one page, three products (by URL slug)
│   │   ├── Login.jsx
│   │   ├── Register.jsx
│   │   ├── ResetPassword.jsx
│   │   └── NotFound.jsx
│   ├── services/
│   │   └── mockAuthService.js  # the "fake backend" - all in localStorage
│   ├── App.jsx                 # route table
│   ├── main.jsx
│   └── index.css
├── index.html
├── package.json
├── tailwind.config.js
└── vite.config.js
```
