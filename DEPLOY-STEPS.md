# Deploy Steps — do these on YOUR computer/browser (logins live there)

Total time: ~20 minutes. Repo: https://github.com/geeteshmehuria/ro-yan-brews

## 1. Push to GitHub

```
git push origin main
```

(No git? GitHub Desktop → Publish repository.)

## 2. Database (Neon)

Render's free tier allows one Postgres and it is taken, so use a free Neon project: create it, copy the connection string (`postgresql://...`). You paste it into Render in step 3.

## 3. Backend on Render

1. dashboard.render.com → **New → Blueprint** → connect the repo (Render reads `render.yaml`).
2. It creates the `royan-api` web service. Fill the secret variables it asks for:
   - `DATABASE_URL` — the Neon string
   - `SMTP_USER` — your Brevo SMTP login (brevo.com → SMTP & API → SMTP; ends with `@smtp-brevo.com`)
   - `SMTP_PASS` — a Brevo **SMTP key** (starts with `xsmtpsib-`). Login codes are emailed; **without these nobody can log in**.
   - Render's free tier blocks SMTP ports 25/465/587, so `render.yaml` uses Brevo's relay on port **2525** (`SMTP_HOST=smtp-relay.brevo.com`). In Brevo → Senders, verify `geeteshmaihuria@gmail.com` (it must match `MAIL_FROM`).
3. `JWT_SECRET` is generated for you. `ENV=production` is already set, so the app **refuses to start** with a weak secret and never accepts the dev code.
4. When it's live, open `https://<your-service>.onrender.com/api/health` — expect `{"ok":true}`.

The menu starts **empty** in production (the placeholder menu is only for dev). Put the real menu in `backend/app/seed.py` and set `SEED_MENU=true` once, then unset it.

## 4. Frontend on Vercel

1. vercel.com → **Add New → Project** → import the repo.
2. **Root Directory: `frontend`** (critical).
3. Environment variables:
   - `VITE_API_URL` = `https://<your-service>.onrender.com`
   - `VITE_WS_URL` = `wss://<your-service>.onrender.com`
4. Deploy. Note the Vercel URL.

## 5. Connect the two

Render → royan-api → Environment → set `CORS_ORIGINS` = your Vercel URL (exact, `https://`, no trailing slash). Save (auto-redeploys).

## 6. Live smoke test

1. Open the Vercel URL on your phone → enter your email → the code arrives by email → menu loads (first load may take a minute).
2. Add items → place order.
3. On another device open `<vercel-url>/admin`, log in with `ADMIN_EMAIL` → the order appears with a sound alert and the customer's full email.
4. Tap **Preparing** → the customer's tracker updates instantly.

## Something broken?

- Menu doesn't load → `CORS_ORIGINS` doesn't exactly match the Vercel URL.
- `/admin` blank → Root Directory wasn't `frontend`.
- Tracker doesn't update live → `VITE_WS_URL` must be `wss://`.
- "Email service is not configured" / "misconfigured" → `SMTP_USER`/`SMTP_PASS` missing or not an App Password.
- Backend won't start → check logs for the `JWT_SECRET` message.
