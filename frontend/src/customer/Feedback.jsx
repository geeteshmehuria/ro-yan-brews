import { useEffect, useState } from "react";

import { api } from "../services/api.js";
import { useBackButton } from "../hooks/backButton.js";
import { VegMark } from "../components/ui.jsx";
import { StarIcon } from "../components/icons.jsx";

// A word for the stars picked, so a tap gets an instant reaction.
const WORDS = ["", "Not good", "Could be better", "Okay", "Good", "Loved it!"];

function Stars({ value, onChange, label }) {
  return (
    <div className="mt-2 flex items-center gap-3">
      <div role="radiogroup" aria-label={`Stars for ${label}`} className="flex">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} star${n > 1 ? "s" : ""}`}
            onClick={() => onChange(n)}
            className={`press h-11 w-11 text-[34px] leading-none transition-transform ${n <= value ? "scale-110 text-star" : "text-muted opacity-30"}`}>
            ★
          </button>
        ))}
      </div>
      {value > 0 && <span className="text-sm font-bold text-star">{WORDS[value]}</span>}
    </div>
  );
}

// Rate each product of one collected order (sent once per order). `prompt` = opened by the
// "order completed" nudge rather than by the customer, so the wording asks instead of offers.
export default function FeedbackSheet({ order, prompt = false, onDone, onClose }) {
  // the same product in half and full size is one product to rate
  const products = [...new Map(order.items.map((i) => [i.menu_item_id, i.name])).entries()];
  const [stars, setStars] = useState({});
  const [comments, setComments] = useState({});
  const [allowPublic, setAllowPublic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useBackButton(onClose); // Android Back closes this panel, not the app

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const rated = products.filter(([id]) => stars[id]);
  const send = async () => {
    setBusy(true); setErr("");
    try {
      await api(`/api/orders/${order.id}/feedback`, {
        method: "POST",
        body: {
          allow_public: allowPublic,
          ratings: rated.map(([id]) => ({ menu_item_id: id, rating: stars[id], comment: comments[id] || null })),
        },
      });
      onDone(order.id);
    } catch (e) {
      if (e.status === 409) onDone(order.id); // already rated (e.g. on another device)
      else { setErr(e.message); setBusy(false); }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 font-body md:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Rate your food" onClick={(e) => e.stopPropagation()}
        className="screen-in max-h-[90vh] w-full max-w-[520px] overflow-y-auto rounded-t-[28px] border border-[var(--stroke)] bg-bg2 p-5 pb-[calc(var(--sab)+1.25rem)] shadow-dialog md:rounded-[28px] md:p-6">
        <div className="flex items-start gap-3">
          <span className="flex h-12 w-12 flex-none items-center justify-center rounded-2xl bg-[var(--accent-ring)] text-star">
            <StarIcon className="h-6 w-6" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-2xl font-extrabold leading-tight">{prompt ? "How was your food?" : "Rate your food"}</h2>
            <p className="text-sm text-muted">Order <b className="text-accent">#{order.order_number}</b> · tap the stars</p>
          </div>
          <button onClick={onClose} aria-label="Close"
            className="press flex h-11 w-11 flex-none items-center justify-center rounded-full bg-[var(--glass-strong)] text-lg font-black">✕</button>
        </div>

        {products.map(([id, name]) => (
          <div key={id} className={`mt-3 rounded-[20px] border p-4 transition-colors ${
            stars[id] ? "border-[var(--accent-glow)] bg-[var(--accent-ring)]" : "border-[var(--stroke)] bg-[var(--glass)]"}`}>
            <div className="flex items-center gap-2"><VegMark /><b className="text-lg">{name}</b></div>
            <Stars value={stars[id] || 0} label={name} onChange={(n) => setStars((s) => ({ ...s, [id]: n }))} />
            {stars[id] && (
              <textarea value={comments[id] || ""} maxLength={300} rows={2}
                onChange={(e) => setComments((c) => ({ ...c, [id]: e.target.value }))}
                placeholder="Tell us more (optional)" aria-label={`Comment on ${name}`}
                className="mt-2 w-full resize-none rounded-xl border border-[var(--stroke)] bg-[var(--card)] p-3 text-ink placeholder:text-muted focus:border-accent focus:outline-none" />
            )}
          </div>
        ))}

        <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-2xl px-1">
          <input type="checkbox" checked={allowPublic} onChange={(e) => setAllowPublic(e.target.checked)}
            className="mt-0.5 h-5 w-5 flex-none accent-[var(--accent)]" />
          <span className="text-sm">OK to show my name and review on the Mr. Momo website</span>
        </label>

        {err && <p role="alert" className="mt-3 text-center text-sm text-danger">{err}</p>}
        <button onClick={send} disabled={!rated.length || busy}
          className="press mt-4 h-14 w-full rounded-2xl bg-accent text-[17px] font-extrabold text-bg1 shadow-[0_10px_28px_var(--accent-glow)] disabled:opacity-50">
          {busy ? "Sending…" : rated.length ? "Send feedback" : "Tap the stars to rate"}
        </button>
      </div>
    </div>
  );
}
