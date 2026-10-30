// Keep STATUSES in sync with ORDER_STATUSES in backend/app/models.py.
export const STATUSES = ["placed", "preparing", "ready", "completed"];
export const LABELS = { placed: "Placed", preparing: "Preparing", ready: "Ready", completed: "Done", cancelled: "Cancelled" };
// Orders that are finished one way or the other (no more status changes coming).
export const isActive = (order) => order.status !== "completed" && order.status !== "cancelled";
export const ICONS = { Shakes: "🥤", Burgers: "🍔", Sandwiches: "🥪", Momos: "🥟", Fries: "🍟" };
export const TOKEN_KEY = "session_token";
export const CART_KEY = "royan_cart";
export const PUSH_KEY = "royan_push_token"; // the Android app's FCM token, unregistered on logout
