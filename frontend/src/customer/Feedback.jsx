import { useEffect, useState } from "react";

import { api } from "../api.js";
import { useBackButton } from "../backButton.js";
import { BigButton } from "../ui.jsx";

function Stars({ value, onChange, label }) {
  return (
    <div role="radiogroup" aria-label={`Stars for ${label}`} className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} star${n > 1 ? "s" : ""}`}
          onClick={() => onChange(n)}
          className={`press h-11 w-11 text-3xl leading-none ${n <= value ? "text-[#facc15]" : "text-muted opacity-40"}`}>
          ★
        </button>
      ))}
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
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 md:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Rate your food" onClick={(e) => e.stopPropagation()}
        className="screen-in max-h-[90vh] w-full max-w-[520px] overflow-y-auto rounded-t-glass border border-[var(--stroke)] p-5 pb-[calc(var(--sab)+1.25rem)] md:rounded-glass"
        style={{ background: "var(--bg2)" }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-black">{prompt ? "How was your food?" : "Rate your food"}</h2>
            <p className="text-sm text-muted">Order #{order.order_number} · tap the stars</p>
          </div>
          <button onClick={onClose} aria-label="Close"
            className="press glass-strong h-11 w-11 flex-none rounded-full text-lg font-black">✕</button>
        </div>

        {products.map(([id, name]) => (
          <div key={id} className="glass mt-3 p-4">
            <b className="text-lg">{name}</b>
            <Stars value={stars[id] || 0} label={name} onChange={(n) => setStars((s) => ({ ...s, [id]: n }))} />
            {stars[id] && (
              <textarea value={comments[id] || ""} maxLength={300} rows={2}
                onChange={(e) => setComments((c) => ({ ...c, [id]: e.target.value }))}
                placeholder="Tell us more (optional)"
                className="glass-strong mt-2 w-full p-3 text-ink placeholder:text-muted focus:border-accent focus:outline-none" />
            )}
          </div>
        ))}

        <label className="mt-4 flex cursor-pointer items-start gap-3 px-1">
          <input type="checkbox" checked={allowPublic} onChange={(e) => setAllowPublic(e.target.checked)}
            className="mt-1 h-5 w-5 flex-none accent-[var(--accent)]" />
          <span className="text-sm">OK to show my name and review on the Ro-Yan website</span>
        </label>

        {err && <p className="mt-2 text-center text-sm text-danger">{err}</p>}
        <BigButton onClick={send} disabled={!rated.length || busy}>
          {busy ? "Sending…" : rated.length ? "Send feedback" : "Tap the stars to rate"}
        </BigButton>
      </div>
    </div>
  );
}
