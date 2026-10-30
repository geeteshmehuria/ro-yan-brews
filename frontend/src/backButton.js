// Android back button in the owner's app: closes the top open panel (order details, the
// menu item form); with nothing open it leaves the app. On the website this does nothing.
import { useEffect } from "react";
import { Capacitor } from "@capacitor/core";

const closers = []; // close functions of the panels that are open, newest last

// Once at startup: from then on the back button never falls back to webview history
// (that would step back to the login screen instead of leaving the app).
export async function initBackButton() {
  if (!Capacitor.isNativePlatform()) return;
  const { App } = await import("@capacitor/app");
  App.addListener("backButton", () => {
    const close = closers[closers.length - 1];
    if (close) close();
    else App.exitApp();
  });
}

// A panel calls this while it's open, next to its Escape-key handling.
export function useBackToClose(onClose) {
  useEffect(() => {
    closers.push(onClose);
    return () => {
      const i = closers.lastIndexOf(onClose);
      if (i !== -1) closers.splice(i, 1);
    };
  }, [onClose]);
}
