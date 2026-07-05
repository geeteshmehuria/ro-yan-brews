# Ro-Yan Brews — Autonomous Loop Build Prompt (build → test → fix → deploy)

## ⚠ Human setup required BEFORE running this prompt (one time, ~10 min)

The agent cannot create accounts or log in for you. Do these first or the deploy phases will stall:

1. GitHub account + an empty repo named `ro-yan-brews` (deploys pull from Git)
2. Vercel account (free) → install CLI locally is NOT needed; agent will use `npx vercel`. Run `npx vercel login` once yourself.
3. Render account (free) → create an API key (Account Settings → API Keys) and put it in a `.env.deploy` file in this folder: `RENDER_API_KEY=xxx`
4. Have this folder's files present: `SPEC.md`, `ui-prototype-v2.html` (visual reference), this prompt.

---

## PASTE EVERYTHING BELOW THIS LINE INTO CLAUDE CODE

You are building, testing, and deploying a complete production web app **autonomously**. Read `SPEC.md` and `ui-prototype-v2.html` in this folder before writing any code — the prototype defines the exact look; the spec defines scope.

# THE LOOP PROTOCOL (follow strictly)

Work in the numbered phases below, in order. For EVERY phase:

1. **PLAN** — list the files you will create/change for this phase.
2. **IMPLEMENT** — write the code.
3. **RUN** — actually start the servers / run the build. Never assume code works.
4. **TEST** — run the phase's test gate (defined per phase). Automated tests must pass, not "should pass".
5. **FIX** — if anything fails, fix and re-run. Loop steps 3–5 until green.
6. **COMMIT** — git commit with message `phase-N: <summary>`.
7. **REPORT** — print a one-line status: `PHASE N DONE — <what works now>`.
8. Move to the next phase. **Never skip ahead with a red test.**

Failure rule: if the same error survives 5 fix attempts, write it to `ISSUES.md` with what you tried, then continue with the rest of the phase if possible. Never silently drop a feature.

Scope rule: build ONLY what is in this prompt. The v2 list at the bottom is forbidden in v1.

# PROJECT

Food ordering web app for the fast food stall **"Ro-Yan Brews"**.
Users: customers on mobile phones (including elderly — this drives the UX rules) and the stall owner (admin).

## Tech stack (fixed — do not substitute)

- Frontend: React (Vite) + Tailwind CSS → deploys to **Vercel**
- Backend: Python FastAPI + SQLAlchemy + Alembic → deploys to **Render** (web service)
- Database: PostgreSQL → **Render** managed Postgres (local dev: Docker Compose)
- Real-time: FastAPI native WebSockets
- Tests: pytest (backend), Playwright (e2e)
- Layout: monorepo — `/frontend`, `/backend`, root README

## Hard constraints

- **Pickup only.** No delivery, addresses, or dine-in logic anywhere.
- **Cash on pickup.** No payment gateway, no UPI, no payment step.
- **Phone + OTP is the ONLY identity.** No email, passwords, signup forms, or profile pages.
- **OTP is dev-mode:** backend generates OTP, logs to console; code `1234` always passes when `OTP_DEV_MODE=true`. Put OTP behind a provider interface so MSG91/Twilio can be added later by changing one file. Rate-limit: max 3 sends/phone/10min, max 5 verify attempts.
- **Elderly-friendly UX:** max 3 steps to order (pick items → phone+OTP → done), base font ≥17px, tap targets ≥44px, plain-language errors ("Please enter your 10-digit mobile number").

## Theme — "Ocean" glass UI (must visually match ui-prototype-v2.html)

All colors derive from these tokens (CSS custom properties wired into Tailwind). No hardcoded colors elsewhere:

```
--bg1:#0a1420  --bg2:#0f2a3a  --accent:#38bdf8  --accent2:#34d399
--text:#f4f1e8  --muted:rgba(244,241,232,.55)
--glass:rgba(255,255,255,.07)  --glass-strong:rgba(255,255,255,.12)
--stroke:rgba(255,255,255,.14)  --danger:#f87171  --radius:18px  --blur:18px
```

Visual language (copy from prototype): fixed gradient background with two blurred floating orbs; glass cards (`backdrop-filter: blur(18px)`, 1px stroke border, 18px radius); sticky glass header; accent CTAs with glow shadows; scroll-reveal fade-up on menu cards via IntersectionObserver (revealed cards never re-animate); hero with shine-sweep + "Order Now" CTA; floating glass cart bar sliding up when cart is non-empty; fade-up screen transitions; pulsing active dot on status tracker; press-scale feedback on buttons; honor `prefers-reduced-motion`.

## Features — customer (mobile-first)

1. Hero + menu grouped by category with emoji icons (🥤 Shakes, 🍔 Burgers, 🥪 Sandwiches, 🥟 Momos, 🍟 Fries); sticky chip bar smooth-scrolls to category; item card = name + price + ADD → qty stepper; Momos & Fries have Half/Full prices with a size toggle; out-of-stock items greyed with tag, not hidden, not addable; menu loads from DB with skeleton loading state.
2. Cart: line items with sizes, per-line totals, grand total, "Pay cash when you collect" note.
3. Checkout: 10-digit phone → 4-digit OTP → order placed. Nothing else.
4. Confirmation: big daily-reset order number, "Ready in about 15 min", live tracker Placed → Preparing → Ready → Completed updated over WebSocket.
5. Cart survives page refresh.

## Features — admin (route `/admin`, protected by `ADMIN_PIN` env var)

1. Live order queue: new orders arrive via WebSocket with sound alert + flashing card (order no, masked phone, items, total, time).
2. Status buttons per order (Placed/Preparing/Ready/Completed); changes push live to the customer tracker.
3. Stock toggle per menu item; broadcasts instantly to connected customer menus.
4. Stats row: today's orders, revenue, top item.
5. Same Ocean theme.

## Data model

MenuItem(id, name, category, price_half nullable, price_full, is_available, sort_order) ·
Customer(id, phone_number unique, created_at) ·
Order(id, order_number daily-reset human-readable, customer_id, status enum, total, created_at) ·
OrderItem(id, order_id, menu_item_id, size enum(half/full/na), qty, price_at_order snapshot) ·
OtpCode(phone_number, code, expires_at 5min, verified, attempt_count)

## API

GET /api/menu · POST /api/otp/send · POST /api/otp/verify (returns JWT httpOnly cookie) ·
POST /api/orders · GET /api/orders/{id} (own orders only) ·
WS /ws/orders/{id} · WS /ws/admin ·
PATCH /api/admin/orders/{id}/status · PATCH /api/admin/menu/{id}/availability · GET /api/admin/stats/today
Pydantic validation everywhere; invalid status transitions rejected.

# PHASES

## Phase 1 — Scaffold
Vite React + Tailwind with Ocean tokens; FastAPI skeleton; Docker Compose Postgres; Alembic init; menu seed script (placeholder items marked `# TODO real menu from owner`); git init + first commit; `.env.example` for every variable (`DATABASE_URL, JWT_SECRET, ADMIN_PIN, OTP_DEV_MODE, CORS_ORIGINS, VITE_API_URL, VITE_WS_URL`).
**Test gate:** backend starts and `GET /api/menu` returns seeded data; frontend dev server renders the themed hero.

## Phase 2 — Menu + cart
**Test gate:** pytest for menu endpoint incl. availability; manual-equivalent Playwright check: add item, size toggle changes price, cart total correct, cart survives reload.

## Phase 3 — OTP checkout + order placement
**Test gate:** pytest: OTP send rate-limit, expiry, attempt cap, verify issues JWT, order create writes price snapshots, order number resets daily (test with mocked dates).

## Phase 4 — Admin queue + WebSocket alerts
**Test gate:** pytest WebSocket test: placing an order pushes to /ws/admin; admin auth rejected with wrong PIN.

## Phase 5 — Status flow + stock toggles
**Test gate:** pytest: status change broadcasts to customer socket; invalid transition (Completed→Placed) rejected; stock-off reflected in next `GET /api/menu` and broadcast.

## Phase 6 — Polish + full e2e
Skeleton states, plain-language errors, reduced-motion, empty states.
**Test gate:** Playwright e2e of the WHOLE customer journey (menu → cart → OTP `1234` → order placed → admin changes status → customer tracker updates live) passing headless. Frontend `npm run build` succeeds with zero errors.

## Phase 7 — Deploy prep
- `render.yaml` blueprint: web service (FastAPI, uvicorn, health check `/api/health`) + managed Postgres, env vars wired, Alembic migration run on deploy, seed on first boot
- Vercel config for `/frontend`: `VITE_API_URL` / `VITE_WS_URL` (wss://) pointing at the Render URL
- CORS: backend allows the Vercel domain; cookies `SameSite=None; Secure`
- WebSockets must use `wss://` in production
**Test gate:** local production build of frontend served against local backend works end to end.

## Phase 8 — Deploy + live smoke test
1. Push repo to GitHub (`ro-yan-brews`).
2. Backend: create Render services via `render.yaml` blueprint using `RENDER_API_KEY` from `.env.deploy` (Render API/CLI). Wait for deploy to go live; hit `/api/health`.
3. Frontend: `npx vercel --prod` from `/frontend` with production env vars set via `npx vercel env`.
4. **Live smoke test (must actually run):** against the production URLs — load menu, place an order with OTP `1234`, open `/admin` with the PIN, move the order to Ready, confirm the customer tracker updated. Record results in `DEPLOYED.md` with both URLs.
5. If any deploy step fails due to missing login/permissions, STOP and print exactly what the human must do, then resume.
**Test gate:** `DEPLOYED.md` exists with working URLs and all smoke checks ticked.

# Definition of done
All 8 phases green · `ISSUES.md` empty or only cosmetic items · live Vercel URL serving the Ocean-themed app · live Render API · e2e passing locally · README documents local dev + deploy.

# Forbidden in v1 (v2 backlog — leave clean extension points only)
Order history page, repeat-last-order, loyalty/regular flagging, daily summary page, UPI/payments, delivery, real SMS OTP.

# Known free-tier caveats (do not "fix" these, just note in README)
Render free web services sleep after inactivity (first request slow); free Postgres has expiry limits; dev-mode OTP means anyone with the URL can order — acceptable until SMS provider is added.
