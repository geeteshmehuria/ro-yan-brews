// Themed replacements for window.confirm / window.alert, which in the Android app (and the
// browser) show the site address and the system's own colours. Promise-based, so callers read
// like the built-ins:   if (await ask({ title: "Cancel this order?" })) …   /   tell(e.message)
// <DialogHost /> is mounted once (main.jsx); dialogs queue and show one at a time.
import { useEffect, useRef, useState } from "react";

import { useBackButton } from "./backButton.js";

let enqueue = null; // set while <DialogHost /> is mounted
let nextId = 0;

const TONES = {
  accent: { button: "bg-accent text-bg1", icon: "❔" },
  danger: { button: "bg-danger text-bg1", icon: "⚠️" },
  warn: { button: "bg-warn text-bg1", icon: "⚠️" },
};

/** A yes/no question. Resolves true for the confirm button, false for cancel / outside / Back. */
export function ask({ title, message = "", confirmLabel = "OK", cancelLabel = "Cancel", tone = "accent" }) {
  if (!enqueue) return Promise.resolve(window.confirm([title, message].filter(Boolean).join("\n\n")));
  return new Promise((resolve) => enqueue({ title, message, confirmLabel, cancelLabel, tone, resolve }));
}

/** A message with one OK button (errors, mostly). */
export function tell(message, { title = "Something went wrong", tone = "danger" } = {}) {
  if (!enqueue) { window.alert(message); return Promise.resolve(); }
  return new Promise((resolve) => enqueue({ title, message, confirmLabel: "OK", tone, resolve: () => resolve() }));
}

function Dialog({ d, close }) {
  const confirmRef = useRef();
  useBackButton(() => close(false)); // Android Back = cancel, not leave the app
  useEffect(() => {
    confirmRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") close(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);
  const tone = TONES[d.tone] || TONES.accent;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 px-6 pb-[var(--sab)] pt-[var(--sat)]"
      onClick={() => close(false)}>
      <div role="alertdialog" aria-modal="true" aria-labelledby="dlg-title" aria-describedby={d.message ? "dlg-msg" : undefined}
        onClick={(e) => e.stopPropagation()}
        className="screen-in w-full max-w-[400px] rounded-glass border border-[var(--stroke)] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.5)]"
        style={{ background: "var(--bg2)" }}>
        <div className="flex items-start gap-3">
          <span className="text-2xl leading-none" aria-hidden="true">{tone.icon}</span>
          <div className="min-w-0">
            <h2 id="dlg-title" className="text-lg font-black leading-snug">{d.title}</h2>
            {d.message && <p id="dlg-msg" className="mt-1.5 text-sm text-muted">{d.message}</p>}
          </div>
        </div>
        <div className="mt-5 flex gap-2.5">
          {d.cancelLabel && (
            <button onClick={() => close(false)}
              className="press glass-strong min-h-[48px] flex-1 rounded-xl px-3 font-bold">{d.cancelLabel}</button>
          )}
          <button ref={confirmRef} onClick={() => close(true)}
            className={`press min-h-[48px] flex-1 rounded-xl px-3 font-black ${tone.button}`}>{d.confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}

export function DialogHost() {
  const [queue, setQueue] = useState([]);
  useEffect(() => {
    enqueue = (d) => setQueue((q) => [...q, { ...d, id: ++nextId }]);
    return () => { enqueue = null; };
  }, []);
  const current = queue[0];
  if (!current) return null;
  // Each pop-up answers once: a second close before React re-renders (Esc + a tap) must not
  // remove the next queued pop-up unanswered.
  const close = (ok) => {
    if (current.closed) return;
    current.closed = true;
    setQueue((q) => q.filter((d) => d !== current));
    current.resolve(ok);
  };
  return <Dialog key={current.id} d={current} close={close} />;
}
