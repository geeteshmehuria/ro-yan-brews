# Ro-Yan Brews — Food Ordering App

Pickup-only ordering app for the Ro-Yan fast food stall. Ocean glass UI. Email + OTP login, cash on pickup, live order status that stays visible while ordering again, optional profile name, order notes, cancel-while-placed, a "ready" beep + email, and a real-time owner dashboard.

## Structure

- `frontend/` — React (Vite) + Tailwind. Customer app at `/`, owner dashboard at `/admin`.
- `backend/` — FastAPI + SQLAlchemy. SQLite locally, PostgreSQL in production. WebSockets for live updates.
- `render.yaml` — Render blueprint (API). `frontend/vercel.json` — Vercel SPA config.
- `docs/` — `SPEC.md` (product decisions, v1/v2 scope), `DEPLOY-STEPS.md` (how to deploy), `ANDROID.md` (the Android app), `ui-prototype-v2.html` (design reference). `CLAUDE.md` — architecture notes.

### Backend layout (`backend/app/`)

Feature-based: everything about one feature sits in one folder — its routes (`*_router.py`),
its logic (`*_service.py`) and its request bodies (`*_schemas.py`).

```
main.py                  creates the FastAPI app: startup, CORS, failure log, routes
router.py                mounts every feature's router
features/
  auth/                  login with an emailed code or Google
    auth_router.py         /api/auth/mode, /api/otp/send, /api/otp/verify, /api/auth/google
    auth_schemas.py
    otp_service.py         codes: create, email, check, rate limits
  profile/               the customer's name            (profile_router, profile_schemas)
  menu/
    menu_router.py         public menu
    menu_admin_router.py   owner: add / edit / remove / restore / delete, stock on/off
    menu_service.py        shared menu helpers
    menu_schemas.py
    menu_seed.py           placeholder menu for local dev
  orders/
    orders_router.py       customer: place, list, cancel
    orders_admin_router.py owner: the queue and status changes
    orders_service.py      order JSON shape, live announcements, "ready" email
    orders_schemas.py
  feedback/              customer ratings + the owner's review list
  store/                 the Open / Paused switch
  reports/               owner: today's numbers and reports
  notifications/         Android push: token routes + Firebase sending
  live/                  WebSocket channels /ws/admin, /ws/me, /ws/menu
  health/                /api/health for Render
middleware/
  failure_log.py         records failed requests in the t_log table
shared/                  used by many features
  database.py            engine, sessions, auto-added columns
  models.py              all database tables (they reference each other, so they stay together)
  auth.py                JWT sessions, owner check, Google token check
  clock.py               all time handling (UTC storage, IST stall day)
  config.py              settings from the environment
  mailer.py              the one email sender (SMTP)
  request_log.py         writes / prunes the failure log
  validation.py          small input-cleaning helpers
  ws_manager.py          WebSocket connection pools
```

### Frontend layout (`frontend/src/`)

```
main.jsx       entry point: routes / (customer) and /admin (owner)
admin/         owner dashboard screens        customer/   customer screens
components/    shared UI (buttons, dialogs)   hooks/      sockets, Android Back, animations
services/      API client, push               config/     constants
utils/         sounds and title alerts        styles/     theme + Tailwind
```

## Run locally

Backend:

```
cd backend
pip install -r requirements-dev.txt
cp .env.example .env               # optional; works with no .env at all
uvicorn app.main:app --reload --port 8000
```

Frontend:

```
cd frontend
npm install
npm run dev        # http://localhost:5173
```

- **Login code in dev**: `123456` (needs `OTP_DEV_MODE=true`, which is the `.env.example` default), or the real code printed in the backend console. Fixed code is **impossible** when `ENV=production`.
- **Owner/admin**: log in with `ADMIN_EMAIL` — no separate password. Owner sessions last 7 days, customers 30.
- **Real emails locally**: fill `SMTP_USER` + `SMTP_PASS` (Gmail App Password) in `backend/.env`.

## Tests

```
cd backend
python -m pytest                          # all tests
python -m pytest tests/features/orders    # one feature
```

`backend/tests/` mirrors `backend/app/`: `tests/features/<feature>/` (auth, profile, menu, orders, feedback,
store, reports, notifications, live), `tests/shared/` and `tests/middleware/`. Shared fixtures are in `tests/conftest.py`.

## Environment variables (backend)

| Var | Purpose |
|---|---|
| `ENV` | `dev` (default) or `production`. Production refuses to start with a weak `JWT_SECRET`, never accepts the dev code, and never auto-seeds the placeholder menu. |
| `JWT_SECRET` | Random string, 32+ chars. |
| `DATABASE_URL` | Postgres URL. Unset = local SQLite. |
| `ADMIN_EMAIL` | The owner's email. |
| `OTP_DEV_MODE` | `true` accepts code `123456` (ignored in production). |
| `SMTP_HOST/PORT/USER/PASS/FROM_NAME` | SMTP for login + "order ready" emails (required in production). Local: Gmail (`smtp.gmail.com:465`, App Password). Render free tier blocks 25/465/587, so production uses Brevo: `smtp-relay.brevo.com`, port **2525**, Brevo SMTP login + key. |
| `MAIL_FROM` | Visible sender address; must be verified in Brevo. Defaults to `SMTP_USER`. |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. |
| `SEED_MENU` | Force the placeholder menu on/off. Default: on in dev, off in production. |

## Known caveats

- Render free tier sleeps when idle — first request takes ~30–60 s (live sockets reconnect by themselves).
- Runs as **one** backend process (live updates and order numbering are in memory).
- "Today" (order numbers, admin stats) is the stall's IST day.
- Login codes are limited per email (3 sends / 10 min, 5 wrong tries), not per IP.
- Menu seed is placeholder until the real stall menu is provided (`backend/app/features/menu/menu_seed.py`); production starts with an **empty** menu.

## v2 backlog (deliberately not built)

Order history page, repeat-last-order, loyalty flagging, daily summary page, UPI, delivery.
