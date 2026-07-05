# Ro-Yan Brews — Food Ordering App

Pickup-only ordering app for the Ro-Yan fast food stall. Ocean glass UI. Phone + OTP identity, cash on pickup, real-time admin dashboard.

## Structure

- `frontend/` — React (Vite) + Tailwind. Customer app at `/`, admin at `/admin`.
- `backend/` — FastAPI + SQLAlchemy. SQLite locally, PostgreSQL in production. WebSockets for live updates.
- `render.yaml` — Render blueprint (API + Postgres). `frontend/vercel.json` — Vercel SPA config.
- `SPEC.md` — all product decisions. `DEPLOY-STEPS.md` — how to deploy.

## Run locally

Backend (no env vars needed — SQLite + dev OTP by default):

```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```
cd frontend
npm install
npm run dev        # opens http://localhost:5173
```

- OTP in dev: check the backend console for the code, or just use **1234**
- Admin PIN default: **4321** (env `ADMIN_PIN`)

## Tests

```
cd backend && python -m pytest tests/ -q    # 15 tests
```

## Known caveats (accepted for v1)

- Render free tier sleeps after inactivity — first request after idle takes ~30–60s
- Dev-mode OTP (`OTP_DEV_MODE=true`) means anyone can verify with 1234 — replace with a real SMS provider (implement `OtpProvider` in `backend/app/otp_service.py`) before wide public use
- Menu seed data is placeholder until the real stall menu is provided (`backend/app/seed.py`)

## v2 backlog (deliberately not built)

Order history page, repeat-last-order, loyalty flagging, daily summary page, UPI, delivery.
