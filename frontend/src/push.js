// Push notifications in the Android app (Firebase Cloud Messaging), for whoever is logged in:
// the owner gets new / cancelled orders, a customer gets their own order's progress — even when
// the app is closed. No-op on the website. The plugin is imported lazily so the website bundle
// doesn't carry it.
import { Capacitor } from "@capacitor/core";

import { api } from "./api.js";
import { PUSH_KEY } from "./constants.js";

// Must match CHANNEL_ID / CUSTOMER_CHANNEL_ID in backend/app/push.py. Importance 5 = heads-up + sound.
const CHANNELS = [
  { id: "orders", name: "New orders (owner)", description: "New and cancelled orders", importance: 5 },
  { id: "status", name: "My order updates", description: "Preparing, ready and other updates on your order", importance: 5 },
];

// Call after login. `onTap(data)` runs when a notification is tapped — `data` is
// { order_id, kind } as strings — including the tap that launched the app.
export async function enablePush(onTap) {
  if (!Capacitor.isNativePlatform()) return;
  try {
    const { PushNotifications } = await import("@capacitor/push-notifications");
    for (const c of CHANNELS) {
      await PushNotifications.createChannel({ ...c, visibility: 1, vibration: true, lights: true });
    }
    let { receive } = await PushNotifications.checkPermissions();
    if (receive === "prompt" || receive === "prompt-with-rationale") {
      ({ receive } = await PushNotifications.requestPermissions());
    }
    if (receive !== "granted") return;
    await PushNotifications.removeAllListeners(); // the owner's and a customer's screens each set their own
    await PushNotifications.addListener("registration", ({ value }) => {
      localStorage.setItem(PUSH_KEY, value);
      // also on every launch: the phone moves to whoever is logged in now
      api("/api/push-token", { method: "POST", body: { token: value } }).catch(() => {});
    });
    await PushNotifications.addListener("registrationError", (e) => console.warn("push registration failed", e));
    await PushNotifications.addListener("pushNotificationActionPerformed", ({ notification }) => {
      if (notification?.data?.order_id) onTap?.(notification.data);
    });
    await PushNotifications.register();
  } catch (e) {
    // e.g. google-services.json missing from the build — the in-app updates still work
    console.warn("push unavailable", e);
  }
}

// Call before logout (it sends the session token): this phone stops getting notifications.
// Callers needn't await it — the request is on its way once this returns.
export async function disablePush() {
  const token = localStorage.getItem(PUSH_KEY);
  if (!token) return;
  localStorage.removeItem(PUSH_KEY);
  await api("/api/push-token/remove", { method: "POST", body: { token } }).catch(() => {});
}
