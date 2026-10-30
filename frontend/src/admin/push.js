// Push notifications for the owner's Android app (Firebase Cloud Messaging): new and
// cancelled orders show up even when the app is closed. No-op on the website.
// The plugin is imported lazily so the website bundle doesn't carry it.
import { Capacitor } from "@capacitor/core";

import { api } from "../api.js";
import { PUSH_KEY } from "../constants.js";

export async function enablePush() {
  if (!Capacitor.isNativePlatform()) return;
  try {
    const { PushNotifications } = await import("@capacitor/push-notifications");
    // Must match push.CHANNEL_ID in the backend. Importance 5 = heads-up + sound.
    await PushNotifications.createChannel({
      id: "orders", name: "Orders", description: "New and cancelled orders",
      importance: 5, visibility: 1, vibration: true, lights: true,
    });
    let { receive } = await PushNotifications.checkPermissions();
    if (receive === "prompt" || receive === "prompt-with-rationale") {
      ({ receive } = await PushNotifications.requestPermissions());
    }
    if (receive !== "granted") return;
    await PushNotifications.removeAllListeners();
    await PushNotifications.addListener("registration", ({ value }) => {
      localStorage.setItem(PUSH_KEY, value);
      api("/api/admin/push-token", { method: "POST", body: { token: value } }).catch(() => {});
    });
    await PushNotifications.addListener("registrationError", (e) => console.warn("push registration failed", e));
    await PushNotifications.register();
  } catch (e) {
    // e.g. google-services.json missing from the build — the in-app alerts still work
    console.warn("push unavailable", e);
  }
}

// Call before logout (it sends the session token): this phone stops getting order alerts.
// Callers needn't await it — the request is on its way once this returns.
export async function disablePush() {
  const token = localStorage.getItem(PUSH_KEY);
  if (!token) return;
  localStorage.removeItem(PUSH_KEY);
  await api("/api/admin/push-token/remove", { method: "POST", body: { token } }).catch(() => {});
}
