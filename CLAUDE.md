# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ro-Yan Brews — a pickup-only food ordering web app for a single fast-food stall. Customers browse a menu, order from their phone via email + OTP (via Gmail SMTP) (cash on pickup, no online payment), and track status. The stall owner uses an admin dashboard with real-time (WebSocket) new-order alerts and stock toggles. `SPEC.md` holds the locked product decisions and the explicit v1/v2 scope split — read it before adding features, since much is deliberately out of scope.

## Commands

Backend (FastAPI, from `backend/`):
```
pip install -r requirements-dev.txt            # requirements.txt = prod only (Render)
uvicorn app.main:app --reload --port 8000     # runs on SQLite, dev OTP, no env vars needed
python -m pytest tests/ -q                     # full suite
python -m pytest tests/test_api.py::test_order_price_snapshot   # single test
```

Frontend (Vite + React, from `frontend/`):
```
npm install
npm run dev        # http://localhost:5173 (proxies to backend at :8000 by default)
npm run build
```

Dev conveniences: OTP is `123456` for any email when `OTP_DEV_MODE=true` **and** `ENV` is not production (real 6-digit code is also logged to the backend console when SMTP isn't configured). Admin is the owner email — logging in with `ADMIN_EMAIL` opens the admin dashboard; there is no separate admin password. Deployment is Render (backend, external Neon Postgres, see `render.yaml`) + Vercel (frontend); see `DEPLOY-STEPS.md`.

## Architecture

**Two independent apps, one JSON+WebSocket API.** No shared code between `frontend/` and `backend/`; the contract is the REST endpoints in `backend/app/main.py` and the WS message shapes below. Frontend routes `/` (customer) and `/admin` are both served from one SPA (`frontend/src/main.jsx`); `vercel.json` rewrites all paths to `index.html` so `/admin` works on refresh.

**One auth model, two privilege levels** (`backend/app/auth.py`):
- Everyone logs in with email + 6-digit OTP → JWT, returned in the response body. The frontend stores it in `localStorage` and sends `Authorization: Bearer` (`frontend/src/api.js`). **Bearer-only — there is no auth cookie** (no CSRF surface, no `allow_credentials`). Tokens last 30 days (owner: 7).
- Admin is *not* a separate account: `require_admin()` checks the token's email is in `ADMIN_EMAILS` (configured via `ADMIN_EMAIL` env var); the admin WebSocket passes the same JWT as `?token=` (`token_is_admin()`). Logging in as the owner email *is* being admin. The owner sees customers' full emails; customers only ever see masked ones (`order_payload(o, admin=...)`).
- **Production guard**: `auth.check_prod_config()` runs in the app lifespan and aborts startup when `ENV=production` and `JWT_SECRET` is the default or `< 32` chars. `OTP_DEV_MODE` is forced off in production, and the placeholder menu is not auto-seeded there (`SEED_MENU` overrides).

**WebSockets — three channels** (`backend/app/ws.py`, single in-process `ConnectionManager`):
- `/ws/admin?token=` — the owner's JWT; receives `{type: "new_order", order}` (full email) and `{type: "status", ...}`. Drives the sound + visual alert.
- `/ws/me?token=` — the logged-in customer's channel (close 4401 on a missing/invalid token); receives `{type: "status", order_id, status}` for **all** of their orders, on every screen. Empty pools are dropped on disconnect. There is no per-order socket — the customer's orders come from `GET /api/orders/mine` and this channel patches them.
- `/ws/menu` — every client's menu; receives `{type: "availability", item_id, is_available}` for instant out-of-stock updates.

Because the manager is in-process, **this only works on a single backend instance** (`render.yaml` pins `--workers 1`; would break if scaled horizontally). Frontend sockets go through `src/useSocket.js`, which auto-reconnects and calls `onReconnect` so callers refetch what they missed.

**Money is stored as integer rupees, never floats.** `OrderItem.price_at_order` is a snapshot taken when the order is placed and is never recomputed — changing a menu price does not alter past orders (tested in `test_order_price_snapshot`). Order totals are summed from these snapshots.

**Order numbering resets daily (IST).** `order_number` is "count of orders since IST midnight + 1", so it restarts at 1 each day and is *not* unique across days (the DB `id` is the stable key). All time goes through `backend/app/clock.py`: `utcnow()` (naive UTC, what the DB stores) and `today_start()` (IST midnight as naive UTC). Never call `datetime.utcnow()` directly. `create_order` is deliberately `async def` with no `await` between counting and committing, which makes numbering atomic on one worker — don't turn it into a plain `def`.

**Status is a forward-only ladder:** `placed → preparing → ready → completed` (`ORDER_STATUSES` in `backend/app/models.py`, also used to validate `StatusIn`). The API rejects any move that isn't strictly forward (`set_status` in `main.py`). The frontend copy is `STATUSES` in `frontend/src/constants.js` — keep them in sync. **`cancelled` is off the ladder** (`CANCELLED` in `models.py`): a customer may cancel only while `placed` (`POST /api/orders/{id}/cancel`), the owner while `placed`/`preparing`; cancelled and completed orders never move again, and cancelled orders are excluded from the daily stats. Every status change goes through `announce()` (customer channel + admin channel). Moving to `ready` also emails the customer via a `BackgroundTasks` job (`notify_ready`) that never raises.

**Failure log (`t_log` table).** `app/request_log.py` + the `log_failures` middleware and exception handlers in `main.py` write one row per failed request (status ≥ 400 — including rejected CORS preflights — and unhandled exceptions, which return a generic 500) and per failed background task (`method="TASK"`): method, path (no query string), status, duration, `error` (message plus the underlying cause, e.g. `Could not send the email… | TimeoutError: timed out`, or the traceback tail for crashes), client IP (first `X-Forwarded-For`), `Origin`, user agent, and the user's email from the bearer token. Successful requests are not logged; bodies, tokens and submitted values (422s keep field names only) never are. Rows older than 30 days are pruned at startup, and a logging failure never breaks a request. Read it with SQL (Neon console or a script): `SELECT created_at, method, path, status, error FROM t_log ORDER BY id DESC LIMIT 20;`. Don't add fields that could hold secrets.

**Profile & order note.** `Customer.name` (optional, ≤60, `GET/PATCH /api/me`) — the owner sees `name || email` (payload has both); customers only ever get their own masked email. `Order.note` (≤200) is the customer's special instructions, shown on the owner's card. Blank strings are stored as `NULL`. Customers see their last 20 orders via `GET /api/orders/mine` (declared above `/api/orders/{order_id}` on purpose).

**OTP** (`backend/app/otp_service.py`): 6 digits from `secrets`, compared with `hmac.compare_digest`, delivered by `deliver()` — through `backend/app/mailer.py` (the single sender: `configured()` / `send_mail()`, also used for the "order ready" email): SMTP when `SMTP_USER`/`SMTP_PASS` are set (Gmail locally; production uses Brevo's relay `smtp-relay.brevo.com` on port **2525** because Render's free tier blocks 25/465/587; `MAIL_FROM` is the visible sender and must be verified in Brevo), else (non-production only) logged to the console; production without SMTP returns 503. `OTP_DEV_MODE` (default false, ignored in production) enables the fixed code `123456`; `/api/auth/mode` returns `{dev_mode}` so the UI only shows the "use 123456" hint when it actually works. Limits: 3 sends / 10 min per email, and 5 wrong guesses per email across *all* codes in that window (resending doesn't reset it). Rows older than a day are deleted on each send. There is no per-IP limit (behind Render's proxy the IP is the proxy's).

**Menu items and sizes.** Prices are `price_half` (nullable — null means the item has no half size) and `price_full`. Ordering `size: "half"` on an item without a half price is a 400. Categories are free-text strings ordered by `sort_order`; the seed data (`backend/app/seed.py`) is **placeholder** until the real stall menu is provided (search for the `TODO real menu` comment).

**DB layer** (`backend/app/db.py`): SQLite locally, Postgres in prod, chosen by `DATABASE_URL`. Tables are auto-created on startup (`Base.metadata.create_all`, in the app lifespan) and the menu is seeded then (dev only, see above) — order queries eager-load via `ORDER_LOAD` in `main.py`. `db.add_missing_columns()` (run right after `create_all`) `ALTER TABLE … ADD COLUMN`s any **nullable** model column an existing database lacks — that is how `customers.name` / `orders.note` reached the local SQLite and Neon databases. It can't add NOT NULL columns, rename, or change types. There are no real migrations, so schema changes to existing prod data must be handled manually.

**Styling is token-driven.** All colors come from the Ocean theme CSS variables in `frontend/src/index.css`; `tailwind.config.js` maps Tailwind color names (`bg1`, `accent`, `ink`, etc.) onto those vars. Change the theme in one place (the CSS `:root`), not in component classes.

## Gotchas

- `ui-prototype-v2.html` is not part of the app — it is only kept as the visual reference for the chosen Ocean look.
- Backend tests use a temp SQLite file (see `tests/conftest.py`), `SEED_MENU=false`, and create their own menu items via the `make_item` fixture — never rely on seeded ids/prices.
- Shared frontend bits: `src/constants.js` (statuses/labels/icons/storage keys/`isActive`), `src/ui.jsx` (Back/BigButton/Field), `src/alerts.js` (`beep`, `flashTitle`), `src/customer/Login.jsx` (used by customer and admin). Customer screens: login → menu ⇄ cart / orders / profile; the menu always shows a banner of in-progress orders.
- Tests must never send real email: `tests/conftest.py` blanks `SMTP_USER/PASS` (an empty env var beats `.env`). Tests that need SMTP "on" enable it *after* logging in (login codes use the mailer too).
- CORS origins come from `CORS_ORIGINS` (comma-separated). In production the frontend's exact Vercel URL must be listed or the menu silently fails to load.
