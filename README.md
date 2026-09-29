# Ro-Yan Brews — Food Ordering App

Pickup-only ordering app for the Ro-Yan fast food stall. Ocean glass UI. Email + OTP login, cash on pickup, live order status that stays visible while ordering again, optional profile name, order notes, cancel-while-placed, a "ready" beep + email, and a real-time owner dashboard.

## Structure

- `frontend/` — React (Vite) + Tailwind. Customer app at `/`, owner dashboard at `/admin`.
- `backend/` — FastAPI + SQLAlchemy. SQLite locally, PostgreSQL in production. WebSockets for live updates.
- `render.yaml` — Render blueprint (API). `frontend/vercel.json` — Vercel SPA config.
- `SPEC.md` — product decisions and v1/v2 scope. `DEPLOY-STEPS.md` — how to deploy. `CLAUDE.md` — architecture notes.

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
cd backend && python -m pytest tests -q
```

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
- Menu seed is placeholder until the real stall menu is provided (`backend/app/seed.py`); production starts with an **empty** menu.

## v2 backlog (deliberately not built)

Order history page, repeat-last-order, loyalty flagging, daily summary page, UPI, delivery.
