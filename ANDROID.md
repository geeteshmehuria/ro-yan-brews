# Ro-Yan Admin — Android app

The owner's app. Customers keep using the website; this app is the admin dashboard only.
It is built with **Capacitor**: the same React admin screens as the website, wrapped in a
real Android app. Phase status:

| Phase | What | Status |
|---|---|---|
| 0 | Set up your Windows PC and phone | **you** |
| 1 | Admin app runs on your phone (login, orders, stock, feedback) | built — run it with the steps below |
| 2 | Feel like an app: icon, splash, screen stays awake, back button | next |
| 3 | Push notifications for new and cancelled orders (even when closed) | built — needs the Firebase setup below |
| 4 | Signed release APK installed for daily use | later |

---

## Phase 0 — one-time setup (Windows, ~1–2 hours, ~10 GB download)

**1. Check Node and Git.** Open Command Prompt (Windows key → `cmd`):
```
node -v          (needs v20 or newer — else install the LTS from nodejs.org)
git --version    (else install from git-scm.com)
```

**2. Install Android Studio** from developer.android.com/studio (default options). First
launch → **Standard** setup → accept the licences. It includes its own Java.

**3. Android 16 SDK.** Android Studio → **More Actions → SDK Manager**:
- *SDK Platforms*: tick **Android 16** (API 36)
- *SDK Tools*: tick **Android SDK Build-Tools** and **Android SDK Platform-Tools** → **Apply**

**4. Prepare the iQOO 13.**
1. Settings → About phone → **Software version** → tap it **7 times** ("You are now a developer").
2. Settings → System → **Developer options** → turn on **USB debugging** and **Install via USB**.
3. Plug in with a cable that carries **data** (not charge-only). On the phone tap **Allow**
   and tick **Always allow from this computer**.

**5. Test with Hello world.** Android Studio → **New Project → Empty Activity** → Finish →
wait for Gradle (first time 5–10 min) → pick your iQOO at the top → green **▶ Run**.
"Hello Android" on the phone = your setup works.

> 🎓 Android Studio builds your code into an **APK** (the app file) with **Gradle**, then installs
> it on the phone over USB with **adb**. Every Android app goes through this build → install → run cycle.

---

## Phase 1 — run the Ro-Yan Admin app on your phone

**1. Get the code** (first time only):
```
git clone https://github.com/geeteshmehuria/ro-yan-brews.git
cd ro-yan-brews\frontend
npm install
```
Already cloned? `git pull` in `ro-yan-brews`, then `npm install` in `frontend`.

**2. Build and open it in Android Studio:**
```
npm run android
```
This builds the admin app (`vite build --mode android` into `frontend/dist-android` — kept apart
from the website's `dist`, so a website build can never end up in the app), copies it into the Android project
(`cap sync`) and opens `frontend\android` in Android Studio. Wait for Gradle to finish.

**3. Run:** pick your iQOO at the top → green **▶ Run**. "Ro-Yan" (cold-drink icon) opens on the phone.

**4. Log in** with the owner email → the code arrives by email → the dashboard. (The first
load can take up to a minute while the free Render backend wakes up.)

**Changed some code?** Run `npm run build:android`, then **▶ Run** again in Android Studio.

> 🎓 Capacitor puts your built admin site (`frontend/dist-android`) inside the app and shows it in a
> full-screen browser view; the app's address is `https://localhost`. That's why the backend's
> `CORS_ORIGINS` lists `https://localhost` — without it the app can't load any data.

### If something goes wrong
| Problem | Fix |
|---|---|
| Phone not in the device list | Other cable/port; on the phone pull down the USB notification → **File transfer**; turn USB debugging off and on |
| App opens but login says "Something went wrong" / nothing loads | Render → royan-api → Environment: `CORS_ORIGINS` must be `https://ro-yan-brews.vercel.app,https://localhost` (then redeploy). Or the backend is still waking up — wait a minute |
| "This app is only for the stall owner" | You logged in with a customer email. Use the `ADMIN_EMAIL` one |
| No Google button | On purpose: Google blocks its sign-in inside apps. Use the email code |
| Build fails (red text in Android Studio) | Send a screenshot of the error |

---

## Phase 3 — order notifications when the app is closed (one-time Firebase setup, ~15 min)

The in-app alert comes over a live connection that Android closes with the app. To be woken
up anyway, the backend sends a **push notification through Firebase Cloud Messaging (FCM)**
— free, and the only way Android delivers to a closed app.

**1. Create the Firebase project.** console.firebase.google.com → **Add project** (e.g.
`ro-yan-admin`, Analytics off).

**2. Add the Android app.** In the project → **Add app → Android** → package name
**`com.royanbrews.admin`** (exactly) → **Register** → download **`google-services.json`**
→ put it in `frontend\android\app\` (next to `build.gradle`). Skip the remaining SDK steps —
they're already done.

**3. Give the backend a key.** Project settings (⚙) → **Service accounts** → **Generate new
private key** → a `.json` file downloads. Render → royan-api → Environment → add
`FIREBASE_SERVICE_ACCOUNT` and paste the **whole file content** as the value → Save (redeploys).
This key is a secret: never commit it or send it to anyone.

**4. Rebuild and install the app:** `npm run build:android` → **▶ Run** in Android Studio.

**5. Log in on the phone → tap Allow** when it asks to send notifications. Close the app,
place an order from the website → "New order #N · ₹…" with sound.

| Problem | Fix |
|---|---|
| Never asked to allow notifications / no alerts | Settings → Apps → Ro-Yan → Notifications → on (and the **Orders** category on, with sound) |
| Alerts come late or only when the app is open | vivo/iQOO kill background apps: Settings → Apps → Ro-Yan → **Battery → Allow background activity / Don't restrict**, and turn on **Autostart** |
| Still nothing | Neon: `SELECT * FROM t_log WHERE path = 'push' ORDER BY id DESC LIMIT 5;` shows FCM's error. `SELECT count(*) FROM push_tokens;` = 0 means the phone never registered (missing `google-services.json`, or permission denied) |

### How the app differs from the website
- Opens straight to the **owner login**; customer accounts are refused.
- **No Google sign-in** (email code only).
- Talks to the same live backend (`https://royan-api.onrender.com`), so orders are the same as on `/admin`.
- **Website changes go live by themselves; app changes need a rebuild** (`npm run build:android` → ▶ Run).
