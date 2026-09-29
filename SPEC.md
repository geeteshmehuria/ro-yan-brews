# Ro-Yan Brews — Ordering Web App Spec

Version 1.2 — email login; profile (name), order note, cancel, ready email added; see CLAUDE.md for current architecture
Status: Decisions locked. UI design NOT started (intentionally deferred).

---

## 1. What this is

A web app for the Ro-Yan fast food stall so customers can see the menu, place an order from their phone, and get notified when it's ready. The stall owner (admin) gets orders in real time on a dashboard.

Primary user: customer on a mobile phone, including elderly customers.
Secondary user: admin (stall owner) on phone or laptop.

## 2. Locked decisions

| Decision | Choice |
|---|---|
| Order type | Pickup only. No delivery, no dine-in QR. |
| Profile | Optional display name only (shown to the owner instead of the email). No other profile fields. |
| Payment | Cash on pickup. No UPI in v1. |
| Login | Email + OTP code (sent via Gmail SMTP). No passwords, no signup form. |
| Identity | Order history auto-linked to email address. |
| Stack | React (frontend), Tailwind CSS, Python FastAPI (backend), PostgreSQL (database), WebSockets for admin alerts. |
| UI | Ocean glass theme; `ui-prototype-v2.html` is kept only as the visual reference. |

## 3. Menu categories

Shakes, Burgers, Sandwiches, Momos, Fries.
Momos and Fries have half / full size options. Exact items and prices come from the stall's menu poster — to be entered as seed data during build.

## 4. Customer features (v1)

1. **Menu page** — items grouped by category, name + price, large tap targets, minimal text. Half/full toggle where applicable.
2. **Cart** — add/remove, quantity, running total. Sticky cart bar on mobile.
3. **Checkout** — cart → email → OTP → order placed. Nothing else. No address, no payment step.
4. **Confirmation** — order number + estimated ready time.
5. **Order status** — Placed → Preparing → Ready → Completed (or Cancelled). Always visible: a banner on the menu and a "My orders" screen (last 20 orders), live over one WebSocket. Customer can cancel while Placed; a note field takes special instructions; the device beeps/vibrates and an email is sent when the order is Ready.
6. **Out-of-stock handling** — item greyed out on menu when admin marks it unavailable.

## 5. Customer features (v2 — do NOT build in v1)

- Full order history (beyond the last 20 orders)
- "Repeat last order" button
- Regular-customer flag visible to admin after N orders

## 6. Admin features (v1)

1. **Live order queue** — new order appears instantly (WebSocket push) with sound + visual alert.
2. **Status buttons** — move order through Preparing / Ready / Completed.
3. **Order list** — customer email (full for the owner, masked for customers), items, time placed.
4. **Stock toggle** — mark any item out of stock / back in stock. Reflects on customer menu immediately.

## 7. Admin features (v2)

- Daily summary: total orders, revenue, top-selling items
- Customer list sorted by order frequency (regulars)

## 8. Design requirements (for the UI session later)

- Mobile-first. Desktop is secondary.
- Large fonts, high contrast, big buttons — usable by elderly customers.
- Max 3 steps from opening the app to order placed: pick items → email+OTP → done.
- Theme: **Ocean** (locked 5 July 2026, chosen from v2 prototype) — glass UI on dark blue. Tokens: bg gradient `#0a1420 → #0f2a3a`, accent `#38bdf8`, secondary `#34d399`, text `#f4f1e8`.
- Glass/frosted cards, scroll-reveal animations, floating cart bar — as demonstrated in `ui-prototype-v2.html`.
- English + Hindi labels worth considering — decide during build.

## 9. Data model (first draft)

- **MenuItem**: id, name, category, price_half (nullable), price_full, is_available
- **Customer**: id, email (unique, lowercase), created_at
- **Order**: id, customer_id, status (placed/preparing/ready/completed), total, created_at
- **OrderItem**: id, order_id, menu_item_id, size (half/full/na), qty, price_at_order
- **OtpCode**: email, code, expires_at, verified, attempt_count, created_at

## 10. Build order

1. Menu display (seeded from poster) + cart
2. OTP checkout + order placement saved to DB
3. Admin dashboard with WebSocket new-order alert
4. Order status flow
5. — v1 ends here —
6. Order history (v2)
7. Regular-customer flagging + daily summary (v2)

## 11. Open items (not blockers for build start)

- **OTP delivery** — decided: Gmail SMTP (App Password). Fixed dev code only when `ENV=dev`.
- **Hosting** — where will this run in production? Decide before launch, not before build.
- **Estimated ready time** — fixed (e.g. 15 min) or admin-set per order? Default: fixed for v1.
- **Discovery plan** — the website won't bring customers by itself. QR code at the stall + Google Maps listing + Instagram are the reach channels. Separate from build.

## 12. Explicitly out of scope

UPI/online payment, delivery, dine-in/table QR, password accounts, full profile pages (name only is in), ratings/reviews, coupons, multi-stall support.
