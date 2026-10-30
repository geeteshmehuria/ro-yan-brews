// Android's back button in the app. Whatever is open on top (a panel, the cart, the code
// screen) registers a handler; Back runs the newest one. With nothing open — the main screen —
// Back leaves the app the way Android does (to the background, so the owner stays logged in
// and connected). No-op on the website, where the browser's own Back applies.
import { Capacitor } from "@capacitor/core";
import { useEffect, useRef } from "react";

const stack = [];

// While `active`, Back calls `handler` instead of leaving the app.
export function useBackButton(handler, active = true) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    if (!active) return;
    const entry = () => ref.current();
    stack.push(entry);
    return () => {
      const i = stack.lastIndexOf(entry);
      if (i >= 0) stack.splice(i, 1);
    };
  }, [active]);
}

export async function installBackButton() {
  if (!Capacitor.isNativePlatform()) return;
  const { App } = await import("@capacitor/app");
  App.addListener("backButton", () => {
    const top = stack[stack.length - 1];
    if (top) top();
    else App.minimizeApp();
  });
}
