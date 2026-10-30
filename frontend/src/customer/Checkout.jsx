import { useState } from "react";

import { MAX_QTY } from "../constants.js";
import { Back, BigButton } from "../ui.jsx";

export function CartScreen({ totals, back, placeOrder, changeLine, removeLine }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const submit = async () => {
    setBusy(true); setErr("");
    try { await placeOrder(note); }
    catch (e) { setErr(e.message); setBusy(false); }
  };
  return (
    <main className="screen-in px-3 pb-10">
      <Back onClick={back}>← Back to menu</Back>
      <h2 className="mb-3 px-1 text-xl font-black">Your order</h2>
      {totals.lines.length === 0 && (
        <div className="glass p-6 text-center">
          <p className="text-muted">Your cart is empty</p>
          <BigButton onClick={back}>Browse the menu</BigButton>
        </div>
      )}
      {totals.lines.map((l) => {
        const key = `${l.id}_${l.size}`;
        const label = `${l.name}${l.hasHalf ? ` (${l.size === "half" ? "Half" : "Full"})` : ""}`;
        return (
          <div key={key} className="glass mb-2.5 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <b className="break-words">{l.name}</b>
                {l.hasHalf && <small className="ml-1 text-muted">({l.size === "half" ? "Half" : "Full"})</small>}
                <div className="text-sm text-muted">₹{l.price} each</div>
              </div>
              <b className="whitespace-nowrap text-lg text-accent2">₹{l.price * l.qty}</b>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3">
              <div className="glass-strong flex items-center overflow-hidden !rounded-xl border !border-accent">
                <button onClick={() => changeLine(key, -1)} aria-label={`One less ${label}`}
                  className="h-11 w-11 text-xl font-extrabold text-accent">−</button>
                <div className="w-10 text-center text-lg font-extrabold" aria-label={`${label} quantity`}>{l.qty}</div>
                <button onClick={() => changeLine(key, 1)} disabled={l.qty >= MAX_QTY} aria-label={`One more ${label}`}
                  className="h-11 w-11 text-xl font-extrabold text-accent disabled:opacity-30">+</button>
              </div>
              <button onClick={() => removeLine(key)} aria-label={`Remove ${label}`}
                className="press min-h-[44px] rounded-xl border border-[var(--stroke)] px-4 text-sm font-bold text-danger">
                Remove
              </button>
            </div>
          </div>
        );
      })}
      {totals.count > 0 && (
        <>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} rows={2}
            placeholder="Special instructions (optional) — e.g. less spicy"
            className="glass mt-2 w-full p-3 text-ink placeholder:text-muted focus:border-accent focus:outline-none" />
          <div className="flex justify-between px-1.5 py-4 text-xl font-black text-accent">
            <span>Total</span><span>₹{totals.total}</span>
          </div>
          <p className="text-center text-sm text-muted">💵 Pay cash when you collect your order</p>
          {err && <p className="mt-2 text-center text-sm text-danger">{err}</p>}
          <BigButton onClick={submit} disabled={!totals.count || busy}>
            {busy ? "Placing order…" : "Place order"}
          </BigButton>
        </>
      )}
    </main>
  );
}
