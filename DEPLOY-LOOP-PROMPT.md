# Ro-Yan Brews — Deploy → Test → Fix Loop Prompt

Use this prompt (with Claude/any AI agent that has browser + shell access) whenever deploying or re-deploying. It assumes the repo is https://github.com/geeteshmehuria/ro-yan-brews and accounts exist on Render + Vercel.

---

## THE LOOP (repeat until every check passes)

1. **DEPLOY** — Render blueprint for backend+Postgres, Vercel for frontend (first time only; afterwards every git push auto-deploys both).
2. **WAIT** — until Render shows "Live" and Vercel shows "Ready". Render free tier: cold start up to 60s.
3. **TEST** — run the full live checklist below against the production URLs. Record each ✅/❌.
4. **DIAGNOSE** — for every ❌: check Render logs, Vercel build logs, browser console/network tab. Identify root cause — never guess-fix.
5. **FIX** —
   - Env/config issue → change in Render/Vercel dashboard directly
   - Code issue → fix locally, run `python -m pytest backend/tests -q` (all 17 must pass) and `npm run build` (must succeed), then `git add -A && git commit -m "fix: <what>" && git push`
6. **GO TO 2.** Never declare done with any ❌ remaining. If the same failure survives 5 fix attempts, write it in ISSUES.md with everything tried and ask a human.

## LIVE TEST CHECKLIST (production URLs, real browser)

### Customer flow
- [ ] Menu loads with all 5 categories, prices visible (cold start may need one retry after ~60s)
- [ ] Add items, half/full toggle changes price correctly, cart total correct
- [ ] Cart survives a page refresh
- [ ] Phone entry rejects <10 digits with a friendly message
- [ ] OTP screen: **enter 1234** (dev mode — real SMS is NOT sent; that is expected, not a bug. Real SMS = MSG91/Twilio account + implement `OtpProvider.send()` in `backend/app/otp_service.py` + set `OTP_DEV_MODE=false`)
- [ ] Wrong OTP (e.g. 0000) shows error, doesn't crash
- [ ] Order placed → order number shown, tracker on "Placed"
- [ ] OTP resend more than 3× in 10 min → friendly rate-limit error

### Admin flow (URL/admin)
- [ ] Wrong PIN rejected; correct PIN enters
- [ ] The placed order is in the queue with masked phone + correct total
- [ ] Place a NEW order from a second device/incognito → appears in admin instantly WITH sound (no refresh)
- [ ] Tap Preparing → customer's tracker updates live (this proves wss:// works)
- [ ] Backward status (Completed → Placed) is refused
- [ ] Toggle an item out of stock → greys out on customer menu instantly; ordering it is blocked
- [ ] Stats row shows correct order count and revenue

### Security checks (must all hold)
- [ ] `GET <api>/api/orders/1` without auth → 401
- [ ] Customer A's order fetched with customer B's token → 404 (isolation between customers)
- [ ] Admin endpoints with wrong/no PIN → 401
- [ ] `/ws/admin` with wrong pin → connection refused
- [ ] OTP verify 6th wrong attempt → 429 (brute force capped)
- [ ] CORS: API rejects requests from other origins

### Config sanity
- [ ] `CORS_ORIGINS` on Render == exact Vercel URL (https, no trailing slash)
- [ ] `VITE_WS_URL` uses `wss://` (not https)
- [ ] `ADMIN_PIN` changed from default 4321
- [ ] `JWT_SECRET` is generated, not the dev default

## KNOWN FAILURE → FIX MAP

| Symptom | Cause | Fix |
|---|---|---|
| Menu never loads, console shows CORS error | CORS_ORIGINS mismatch | Fix env on Render, redeploy |
| Menu loads after long wait first time | Render free tier cold start | Expected — not a bug |
| /admin gives 404 on refresh | vercel.json rewrite missing / wrong root dir | Root Directory must be `frontend` |
| Tracker/admin never update live | ws:// vs wss:// or proxy | VITE_WS_URL=wss://… |
| "No OTP received on phone" | Dev mode by design | Use 1234; real SMS is a v2 provider task |
| 500 on first order after deploy | DB tables missing | Check Render logs for startup create_all/seed errors |

## FUTURE GUARD (when order history is built in v2)
Any order-history endpoint MUST filter by the authenticated customer's id from the JWT — never accept a phone number or customer id from the client. Add an isolation test like `test_order_isolation_between_customers` for it before shipping.
