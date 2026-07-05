# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ro-Yan Brews — a pickup-only food ordering web app for a single fast-food stall. Customers browse a menu, order from their phone via phone-number + OTP (cash on pickup, no online payment), and track status. The stall owner uses an admin dashboard with real-time (WebSocket) new-order alerts and stock toggles. `SPEC.md` holds the locked product decisions and the explicit v1/v2 scope split — read it before adding features, since much is deliberately out of scope.

## Commands

Backend (FastAPI, from `backend/`):
```
pip install -r requirements.txt
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

Dev conveniences: OTP is `1234` for any phone (real code also logged to backend console); admin PIN defaults to `4321` (env `ADMIN_PIN`). Deployment is Render (backend + Postgres via `render.yaml`) + Vercel (frontend); see `DEPLOY-STEPS.md`.

## Architecture

**Two independent apps, one JSON+WebSocket API.** No shared code between `frontend/` and `backend/`; the contract is the REST endpoints in `backend/app/main.py` and the WS message shapes below. Frontend routes `/` (customer) and `/admin` are both served from one SPA (`frontend/src/main.jsx`); `vercel.json` rewrites all paths to `index.html` so `/admin` works on refresh.

**Two auth models, deliberately separate** (`backend/app/auth.py`):
- Customers: JWT after OTP verify. Backend sets an httpOnly cookie *and* returns the token; the frontend actually authenticates with `Authorization: Bearer` from `localStorage` (`frontend/src/api.js`), not the cookie. `current_customer()` accepts either.
- Admin: a shared PIN sent as `x-admin-pin` header (REST) or `?pin=` query param (WebSocket). There is no admin account — knowing the PIN *is* being admin.

**WebSockets — three channels** (`backend/app/ws.py`, single in-process `ConnectionManager`):
- `/ws/admin?pin=` — receives `{type: "new_order", order}` and `{type: "status", ...}`. Drives the sound + visual alert.
- `/ws/orders/{id}` — the customer's live status tracker; receives `{type: "status", status}`.
- `/ws/menu` — every client's menu; receives `{type: "availability", item_id, is_available}` for instant out-of-stock updates.

Because the manager is in-process, **this only works on a single backend instance** (fine for Render free tier; would break if scaled horizontally).

**Money is stored as integer rupees, never floats.** `OrderItem.price_at_order` is a snapshot taken when the order is placed and is never recomputed — changing a menu price does not alter past orders (tested in `test_order_price_snapshot`). Order totals are summed from these snapshots.

**Order numbering resets daily.** `order_number` is a human-facing counter computed as "count of orders since UTC midnight + 1", so it restarts at 1 each day and is *not* unique across days (the DB `id` is the stable key). Note all date math uses **UTC**, not the stall's local timezone.

**Status is a forward-only ladder:** `placed → preparing → ready → completed` (`ORDER_STATUSES` in `backend/app/models.py`). The API rejects any move that isn't strictly forward (`set_status` in `main.py`). The same list is duplicated in the frontend admin — keep them in sync.

**OTP is behind a provider interface** (`backend/app/otp_service.py`). To ship real SMS, implement one `OtpProvider.send()` subclass (MSG91/Twilio/etc.) and swap the `provider` singleton; set `OTP_DEV_MODE=false` so `1234` stops being accepted. Rate limiting (3 sends / 10 min) and attempt capping (5 verifies) already live here.

**Menu items and sizes.** Prices are `price_half` (nullable — null means the item has no half size) and `price_full`. Ordering `size: "half"` on an item without a half price is a 400. Categories are free-text strings ordered by `sort_order`; the seed data (`backend/app/seed.py`) is **placeholder** until the real stall menu is provided (search for the `TODO real menu` comment).

**DB layer** (`backend/app/db.py`): SQLite locally, Postgres in prod, chosen by `DATABASE_URL`. Tables are auto-created on startup (`Base.metadata.create_all`) and the menu is seeded then — there are no migrations, so schema changes to existing prod data must be handled manually.

**Styling is token-driven.** All colors come from the Ocean theme CSS variables in `frontend/src/index.css`; `tailwind.config.js` maps Tailwind color names (`bg1`, `accent`, `ink`, etc.) onto those vars. Change the theme in one place (the CSS `:root`), not in component classes.

## Gotchas

- The two root-level `ui-prototype*.html` files are discarded design mockups, not part of the app — ignore them (`ui-prototype-v2.html` is only kept as the reference for the chosen Ocean look).
- `backend/test_royan.db*` are throwaway test artifacts.
- CORS origins come from `CORS_ORIGINS` (comma-separated). In production the frontend's exact Vercel URL must be listed or the menu silently fails to load.
