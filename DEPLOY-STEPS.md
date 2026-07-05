# Deploy Steps — do these on YOUR computer/browser (logins live there)

Everything is committed to git locally. Total time: ~15 minutes.

## 1. Push to GitHub (3 min)

✅ Repo already created: https://github.com/geeteshmehuria/ro-yan-brews

Open a terminal (Command Prompt) in this folder (`C:\Users\HP\Claude\Projects\Ro-Yan`) and run:

```
git init
git add -A
git commit -m "Ro-Yan Brews v1"
git branch -M main
git remote add origin https://github.com/geeteshmehuria/ro-yan-brews.git
git push -u origin main
```

No git on Windows? Use GitHub Desktop instead: File → Add local repository → this folder → create the commit → Publish repository (uncheck "keep private" only if you want it public).

## 2. Backend on Render (5 min)

1. dashboard.render.com → **New → Blueprint**
2. Connect the `ro-yan-brews` repo — Render reads `render.yaml` automatically
3. Approve. It creates `royan-api` (web service) + `royan-db` (Postgres)
4. Wait for deploy to go green, then open `https://royan-api.onrender.com/api/health` — expect `{"ok":true}`
   (your exact URL is shown on the service page; note it down)

## 3. Frontend on Vercel (5 min)

1. vercel.com → **Add New → Project** → import `ro-yan-brews`
2. **Root Directory: `frontend`** (critical — don't skip)
3. Environment variables:
   - `VITE_API_URL` = `https://royan-api.onrender.com` (your Render URL)
   - `VITE_WS_URL` = `wss://royan-api.onrender.com` (same URL, wss scheme)
4. Deploy. Note your Vercel URL.

## 4. Connect the two (2 min)

1. Render → royan-api → Environment → set `CORS_ORIGINS` = your Vercel URL (exact, `https://`, no trailing slash)
2. While there, **change `ADMIN_PIN`** from 4321 to your own
3. Save — Render redeploys automatically

## 5. Live smoke test

1. Open the Vercel URL on your phone → menu loads (first load may take up to a minute — Render free tier waking up)
2. Add items → phone number → OTP `1234` → order placed
3. Open `YOUR-VERCEL-URL/admin` on another device → enter your PIN → the order is there, sound alert works
4. Tap Preparing → the customer's tracker should update instantly

## Something broken?

- Menu doesn't load → CORS_ORIGINS doesn't exactly match the Vercel URL
- /admin shows blank page → Root Directory wasn't set to `frontend` (vercel.json rewrite missing)
- Tracker doesn't update live → VITE_WS_URL must be `wss://` not `https://`
