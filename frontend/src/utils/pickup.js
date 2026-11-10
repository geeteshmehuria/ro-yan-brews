// Pickup time: at checkout the customer says how soon they'll reach the stall
// (order.pickup_minutes, counted from when the order was placed; null = an older app, not asked).

export const PICKUP_OPTIONS = [
  { minutes: 0, label: "Now" },
  { minutes: 15, label: "15 min" },
  { minutes: 30, label: "30 min" },
  { minutes: 45, label: "45 min" },
];

export const minutesSince = (order, now) => (now - new Date(order.created_at + "Z")) / 60000;

// "Coming now" / "Coming ~6:45 pm", or null when the order has no pickup time.
export function pickupLabel(order) {
  if (order.pickup_minutes == null) return null;
  if (order.pickup_minutes === 0) return "Coming now";
  const at = new Date(new Date(order.created_at + "Z").getTime() + order.pickup_minutes * 60000);
  return `Coming ~${at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

// Still "placed" this long after ordering = the stall hasn't seen it: time to suggest a call.
// 3 minutes, or 10 minutes before the customer said they'd arrive, whichever is later.
export const notStartedYet = (order, now) =>
  order.status === "placed" && minutesSince(order, now) >= Math.max(3, (order.pickup_minutes || 0) - 10);

// "9876543210" -> "98765 43210" (other lengths are shown as saved).
export const prettyPhone = (phone) =>
  /^\d{10}$/.test(phone || "") ? `${phone.slice(0, 5)} ${phone.slice(5)}` : phone || "";
