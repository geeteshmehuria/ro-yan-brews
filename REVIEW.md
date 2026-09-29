# Ro-Yan Brews — Full Project Review

Date: 2026-09-29 · Review only — **no code was changed**. Every item below is a proposal for you to approve.

---

## 1. What the project is (as it actually works)

- **Backend** (`backend/app/`, ~550 lines): FastAPI + SQLAlchemy. SQLite locally, Postgres in prod. Files: `main.py` (all routes + 3 WebSockets), `auth.py` (JWT), `otp_service.py` (email OTP), `models.py`, `schemas.py`, `ws.py`, `seed.py`, `db.py`.
- **Frontend** (`frontend/src/`, ~800 lines): React 18 + Vite + Tailwind 3. `/` = customer (login → menu → cart → tracker), `/admin` = owner dashboard.
- **Flow**: email → 6-digit OTP → JWT (stored in localStorage) → order → live status by WebSocket. Owner = whoever logs in with `ADMIN_EMAIL`.
- **Overall**: the app is small and mostly clean. The problems are (a) a login config bug you are probably hitting right now, (b) a few security defaults that are unsafe in production, and (c) a lot of stale docs/leftover files.

## 2. Terminal / error check (what I ran)

| Check | Result |
|---|---|
| `pytest backend/tests` | **22 passed**, but **175 warnings** (see 2.1) |
| `npm run build` (frontend) | Builds OK (178 KB JS, 58 KB gzip). No errors. |
| Backend import / startup | Imports fine (tests load `app.main`). |
| Your own terminal history | I can't see it. If you have a specific error, paste it and I'll add it here. |

### 2.1 Warnings in the test run
- **`datetime.utcnow()` deprecated** — used in `main.py` (×3), `otp_service.py` (×3), `models.py` (×4 column defaults). Works today, will break in a future Python. Fix: `datetime.now(timezone.utc)`.
- **`InsecureKeyLengthWarning`** — your `backend/.env` `JWT_SECRET` is only **20 bytes** (minimum 32 recommended for HS256). Fix: generate a 64-char random secret.
- **Installed package versions ≠ pinned versions** — installed: fastapi 0.136.3, uvicorn 0.49, PyJWT 2.13, pydantic 2.13. `requirements.txt` pins: fastapi 0.115.6, uvicorn 0.34, PyJWT 2.10.1, pydantic 2.10.4. Tests pass on versions you don't deploy. Render will install the old pins. Also `pydantic-settings` is installed but unused.
- `@app.on_event("startup")` is deprecated in modern FastAPI (use `lifespan`).

### 2.2 The likely "login doesn't work locally" error (real bug)
Your `backend/.env` currently has: `OTP_DEV_MODE=false`, `SMTP_USER` filled, **`SMTP_PASS` empty**, `ENV=dev`.
- `get_provider()` needs *both* user and pass → falls back to `DevOtpProvider` (code only printed in the backend console, no email sent).
- `/api/auth/mode` reports `smtp:false` → the UI shows **"test mode: use 123456"**.
- But `OTP_DEV_MODE=false` → backend **rejects 123456**.
- Result: the screen tells you to use a code that can never work; the real code is only in the uvicorn console log. Nobody gets an email.
- **Fix options**: set `SMTP_PASS` (Gmail App Password) *or* set `OTP_DEV_MODE=true` locally. Code fix: make the UI hint depend on a real `dev_mode` flag, not on "SMTP missing".

## 3. Problems, ranked

### 🔴 High — fix before real users
1. **Insecure defaults can make the owner account takeover-able.** `OTP_DEV_MODE` defaults to `"true"` in code (`otp_service.py`) and `JWT_SECRET` defaults to `"dev-secret-change-me"` (`auth.py`). If either env var is missing in production, anyone can log in as `ADMIN_EMAIL` with `123456` / forge tokens. `render.yaml` sets them correctly, but there is **no startup guard**. Fix: default dev mode to `false`; refuse to start when `ENV=production` and secret is default/short or dev mode is on.
2. **OTP generated with `random`, compared with `==`.** `random.randint` is not cryptographically secure. Use `secrets.randbelow(10**6)` and `secrets.compare_digest`.
3. **Placeholder menu is auto-seeded into production.** `seed_menu` runs on every startup; on a fresh prod DB the fake items/prices go live. (Also the `TODO real menu` is still open.)
4. **`backend/.env.example` contradicts itself**: `ENV=production` together with `OTP_DEV_MODE=true`. Copying it gives an insecure prod config.

### 🟠 Medium
5. **Order-number race**: `count(today) + 1` — two simultaneous orders get the same number. Real risk at a busy stall. Fix: DB-side counter or retry on unique constraint (add unique `(date, order_number)`).
6. **"Today" is UTC, not IST.** Order numbers reset and admin stats roll over at **05:30 IST**, not midnight. Use the stall's timezone.
7. **OTP resend resets the attempt cap** (each send creates a new row with `attempt_count=0`): ~15 guesses per 10 min per email. Also no per-IP limit → anyone can email-bomb any address (3/10 min each). `otp_codes` table is never cleaned.
8. **Cookie is set but never used by the frontend** (it uses Bearer from localStorage). It adds `SameSite=None` complexity, `allow_credentials=True`, and a possible CSRF surface for nothing. Remove cookie + credentials.
9. **JWT lasts 30 days, no revocation**, stored in localStorage (XSS-readable). Acceptable for v1; consider shorter expiry for the admin.
10. **Blocking DB calls inside `async def` handlers** (`create_order`, `set_status`, `set_availability`) block the event loop. Make them plain `def` where no `await` is needed for DB, or keep it small — fine at stall scale, but easy win.
11. **`ws.py` leak**: `manager.orders[order_id]` keeps an empty set forever after disconnect. `/ws/orders/{id}` is unauthenticated (anyone can subscribe to any order id; only status is exposed, low risk).
12. **Admin never sees who ordered** — only a masked email (`ge***@gmail.com`). For "pay on pickup" that's OK, but SPEC says admin sees customer contact. Decide intentionally.
13. **N+1 queries**: `order_payload` lazy-loads customer, items, and each item's menu_item; `stats_today` loops the same way. Use `joinedload`/`selectinload`.
14. **No migrations** (`create_all` only) — any schema change on prod data is manual. Fine for now; needs Alembic before the first real schema change.

### 🟡 Low / UX
15. `AdminApp`: on `new_order` it prepends the order with `fresh:true` and then immediately calls `load()`, which replaces the list → the red "new" flash disappears at once. Either drop the `load()` or preserve `fresh`.
16. Customer app opens the `/ws/menu` socket even on the login screen; cart (with prices) persists in localStorage across different users/logins and can hold stale prices (server recomputes, so only display is off).
17. `frontend/index.html`: no favicon (browser logs a 404 for `/favicon.ico`), no `theme-color`.
18. Frontend has no lint, no tests, no `check` script. `React.StrictMode` double-opens WebSockets in dev (harmless).
19. `verify_otp` returns `True` that nobody uses; concurrent first-login could hit a unique-email violation → 500.

## 4. Unnecessary / dead things (candidates to delete or simplify)

### Dead code
| Item | Where | Action |
|---|---|---|
| `MenuItemOut` schema | `schemas.py:43` | delete (unused) |
| `SIZES` constant | `models.py:9` | delete (unused) |
| `wsRef` + `useRef` | `AdminApp.jsx:71,92`, `Checkout.jsx:159,167` | delete (written, never read) |
| `python-multipart` | `requirements.txt` | delete (no form/file endpoints) |
| `pytest`, `httpx` in prod requirements | `requirements.txt` | move to `requirements-dev.txt` (Render installs them needlessly) |
| `is_admin` flag inside JWT | `auth.py` | only the frontend reads it (fine), backend re-checks email — keep or drop, your call |
| Cookie (`set_cookie`, `request.cookies`, CORS credentials) | `main.py`, `auth.py` | delete (see #8) |
| `OtpProvider` ABC | `otp_service.py` | 2 implementations → could be one function with an `if`. Optional. |

### Duplicated logic (single source of truth wanted)
- Order statuses list in **3 places**: `models.py`, `schemas.py` (Literal), `AdminApp.jsx`, `Checkout.jsx` (+ labels twice).
- `ICONS` map duplicated in `Menu.jsx` and `AdminApp.jsx`.
- Email regex in both `schemas.py` and `Checkout.jsx` (acceptable: client + server).
- `today_start` computation copied 3× in `main.py`.
- Login UI lives in `customer/Checkout.jsx` (misnamed) and is imported by the admin app → move to `Login.jsx`.

### Stale / leftover files and folders
| Item | Why |
|---|---|
| `.kilo/` (incl. `.kilo/worktrees/polydactyl-headphones/` — a full second copy of the repo) | leftover from a Kilo agent tool; git-ignored but pollutes searches. Delete. |
| `backend/venv/` (64 MB) **and** root `.venv/` (39 MB) | two virtualenvs; docs say `backend/`. Keep one. |
| `backend/pytest-cache-files-0kwyug75/` | empty junk dir |
| `backend/royan.db`, `backend/test_royan.db` | local DB artifacts (ignored, fine; tests never delete `test_royan.db`) |
| `ui-prototype.html`, `ui-prototype-v2.html` (44 KB, tracked) | design mockups; your own CLAUDE.md says ignore them. Delete `ui-prototype.html`; archive `v2` if wanted as reference. |
| `BUILD-PROMPT.md`, `DEPLOY-LOOP-PROMPT.md` (tracked) | one-off agent prompts, describe an old phone/PIN version, mention "17 tests" and `ISSUES.md`. Obsolete. |
| `.gitignore` entry `nul` | Windows redirect accident; harmless |
| `frontend/package-lock.json` showed as modified at session start | check with `git diff`; likely line-endings |

### Docs that are out of date (these mislead)
- **README.md**: says OTP `1234`, "Admin PIN 4321", "phone + OTP", "15 tests", `ADMIN_PIN` — all wrong now (email OTP `123456`, owner email, 22 tests).
- **DEPLOY-STEPS.md**: PIN steps (`ADMIN_PIN`), phone number + OTP `1234`, says Blueprint creates `royan-db` Postgres (it doesn't — `render.yaml` uses external Neon), old local path `C:\Users\HP\Claude\Projects\Ro-Yan`.
- **SPEC.md**: "phone number" throughout, data model shows `phone_number`, "old prototype discarded" but prototypes still in repo. Needs a v1.1 pass or a note "superseded by CLAUDE.md".
- **`backend/app/otp_service.py` docstring**: says "code 1234".
- **`backend/.env.example`**: see #4.

## 5. Hooks and tooling

- **Git hooks**: only Git's `.sample` files. No pre-commit config in this repo. Nothing to remove; optionally add ruff + a frontend build check later (not needed now).
- **Claude Code hooks (global, `C:\Users\HP\.claude\settings.json`)**: lean-ctx runs on **every tool call** (`PostToolUse .*`, `PreCompact`, `SessionEnd`, plus `PreToolUse` rewrite/redirect on Bash/PowerShell/Read/Grep/Glob). Effects seen in this review: native Grep/Glob are denied, `python -c` and `netstat` were **blocked**, and reads return cached/summarised output (e.g. some files showed no content until read raw). It's a global setting, not part of this repo — but it does add friction and hides content. Consider limiting it to projects where you want it.
- **⚠ Wrong project config leaking in**: `d:\Projects\CLAUDE.md` and `d:\Projects\.claude\settings.local.json` belong to a *different project* (AlgoLens AI: FastAPI/SvelteKit/Alembic/Gemini). Claude loads them for Ro-Yan too because Ro-Yan sits inside `d:\Projects\`. The permission allowlist there is full of AlgoLens curl/pnpm/alembic commands and unrelated `git commit` messages. It doesn't affect Ro-Yan's runtime, but it pollutes context and pre-approves unrelated commands. Fix: move Ro-Yan out of `d:\Projects\` root ownership, or clean that allowlist.

## 6. Tests

- 22 tests, good coverage of auth, order, status, WS, SMTP mock.
- **Fragile**: they hard-code seed IDs/prices (`menu_item_id: 1`, `total == 160`) — changing the real menu breaks them. Create test items in fixtures instead.
- Relative DB path `./test_royan.db` depends on cwd; never cleaned. Use in-memory SQLite (`StaticPool`) or `tmp_path`.
- `test_ws_admin_non_owner_rejected` uses `pytest.raises(Exception)` — too broad.
- Missing: concurrent order numbers, `/api/auth/mode`, production config guard, timezone rollover.

## 7. Suggested simplification plan (in order, each small)

1. **Config safety** (30 min): dev-mode default `false`, prod startup guard, fix `.env.example`, longer JWT secret, fix the UI "use 123456" hint, set `SMTP_PASS` or dev mode locally.
2. **Delete dead stuff**: `MenuItemOut`, `SIZES`, `wsRef`s, `python-multipart`, cookie code, `.kilo/`, `backend/venv` or `.venv`, empty `pytest-cache-files-*`, `ui-prototype.html`, both `*-PROMPT.md`.
3. **Requirements**: split dev/prod, re-pin to versions you actually test with, `pip freeze` check.
4. **Docs**: collapse README + DEPLOY-STEPS + SPEC into README (run, deploy, decisions) — one accurate source; keep CLAUDE.md.
5. **Backend correctness**: `secrets` for OTP, timezone-aware datetimes (IST for "today"), order-number race fix, `lifespan`, drop OTP resend attempt-reset, cleanup old OTP rows.
6. **Frontend tidy**: shared `constants.js` (statuses, labels, icons), move `Login` to its own file, fix `fresh` flash, add favicon.
7. **Tests**: fixture-created menu items, in-memory DB, add missing cases.

## 8. What is already good (leave alone)
- Price snapshot on `OrderItem`, forward-only status ladder, order isolation between customers (404 not 403), OTP attempt/send limits, friendly SMTP errors, indexed FKs/timestamps, token-driven Tailwind theme, small file count, passing tests, clean production build.

---
*Decisions I need from you:* (a) delete the leftover files/docs in §4? (b) keep two prototypes or none? (c) keep the cookie or go Bearer-only? (d) which timezone should "today" use (IST?)

---

## 9. Fix status (applied 2026-09-29, not committed)

Verified: `pytest` 34 passed (0 DeprecationWarnings), `npm run build` OK, `ENV=production` + weak secret → startup aborts, dev smoke flow (login → menu → order) OK.

| # | Item | Status |
|---|---|---|
| 1 | Insecure defaults / no prod guard | Fixed — dev mode default off & impossible in prod; `check_prod_config()` aborts on weak secret |
| 2 | OTP `random` / `==` | Fixed — `secrets` + `hmac.compare_digest` |
| 3 | Placeholder menu seeded in prod | Fixed — seed only in dev unless `SEED_MENU=true` |
| 4 | `.env.example` contradictory | Fixed |
| 5 | Order-number race | Handled differently — already atomic on one async worker; documented in code, `--workers 1` pinned |
| 6 | UTC "today" | Fixed — fixed IST via `app/clock.py` |
| 7 | OTP resend reset attempts / cleanup | Fixed. Per-IP limit **not** added (proxy IP) — documented |
| 8 | Unused cookie | Fixed — Bearer-only, no credentials |
| 9 | JWT lifetime | Owner 7 days, customer 30 |
| 10 | Blocking handlers | Left on purpose (removing `async` would reintroduce #5) |
| 11 | WS pool leak / unauthenticated order WS | Fixed — token + ownership check, empty pools removed |
| 12 | Admin sees only masked email | Fixed — owner sees full email |
| 13 | N+1 queries | Fixed — `ORDER_LOAD` eager loading |
| 14 | No migrations | Unchanged (documented in CLAUDE.md) |
| 15 | "New order" flash vanished | Fixed |
| 16 | Socket on login / stale cart | Fixed — socket only when logged in, cart re-priced, cleared on logout |
| 17 | Favicon / theme-color | Fixed |
| 18 | Frontend lint/tests | Skipped on purpose (extra deps); build + backend tests are the gate |
| 19 | Unused return / concurrent first login | Fixed |
| — | Dead code (`MenuItemOut`, `SIZES`, `wsRef`, `python-multipart`, provider classes) | Removed |
| — | Duplicated statuses/icons/socket code | `constants.js`, `useSocket.js`, `ui.jsx`, `Login.jsx` |
| — | Requirements split + re-pinned | `requirements.txt` (prod) / `requirements-dev.txt` |
| — | Leftover files, stale docs | Deleted / rewritten (README, DEPLOY-STEPS, SPEC, CLAUDE.md) |
| — | AlgoLens config in `d:\Projects\` and global lean-ctx hooks | Not touched (outside this repo) |
