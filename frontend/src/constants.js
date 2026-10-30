// Keep STATUSES in sync with ORDER_STATUSES in backend/app/models.py.
export const STATUSES = ["placed", "preparing", "ready", "completed"];
export const LABELS = { placed: "Placed", preparing: "Preparing", ready: "Ready", completed: "Done",
  cancelled: "Cancelled", not_collected: "Not collected" };
// Orders that are finished one way or the other (no more status changes coming).
// Keep in sync with CLOSED in backend/app/models.py. "not_collected": ready but never picked up
// (the owner closes it, no cash).
export const CLOSED = ["completed", "cancelled", "not_collected"];
export const isActive = (order) => !CLOSED.includes(order.status);
export const ICONS = { Shakes: "🥤", Burgers: "🍔", Sandwiches: "🥪", Momos: "🥟", Fries: "🍟" };
// Built as the Android app (npm run build:android, .env.android)? Google sign-in is hidden
// there: Google blocks it inside an app's web view.
export const IN_APP = import.meta.env.VITE_APP_TARGET === "app";
export const MAX_QTY = 50; // per cart line — the backend's OrderItemIn.qty limit
export const MUTE_KEY = "royan_admin_muted"; // the owner's new-order sound, per device
export const TOKEN_KEY = "session_token";
export const CART_KEY = "royan_cart";
export const PUSH_KEY = "royan_push_token"; // the Android app's FCM token, unregistered on logout
