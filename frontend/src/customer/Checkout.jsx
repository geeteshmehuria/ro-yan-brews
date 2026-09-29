import { useState } from "react";

import { Back, BigButton } from "../ui.jsx";

export function CartScreen({ totals, back, placeOrder }) {
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
      {totals.lines.map((l) => (
        <div key={`${l.id}_${l.size}`} className="glass mb-2.5 flex items-center justify-between p-4">
          <div>
            <b>{l.name}</b>
            {l.hasHalf && <small className="ml-1 text-muted">({l.size === "half" ? "Half" : "Full"})</small>}
            <br />
            <small className="text-muted">₹{l.price} × {l.qty}</small>
          </div>
          <b className="text-accent2">₹{l.price * l.qty}</b>
        </div>
      ))}
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
    </main>
  );
}
