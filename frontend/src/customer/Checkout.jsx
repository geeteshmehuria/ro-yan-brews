import { useState } from "react";

import { MAX_QTY } from "../config/constants.js";
import { FoodBackground, VegMark } from "../components/ui.jsx";
import { ArrowIcon, BackIcon, CashIcon, ClockIcon, PlusIcon, TrashIcon } from "../components/icons.jsx";
import { PICKUP_OPTIONS } from "../utils/pickup.js";

const CARD = "rounded-[22px] border border-[var(--stroke)] bg-[var(--glass)] backdrop-blur-md";

// "~6:45 pm": roughly when "in N minutes" is, so the choice reads as a time. Display only.
const clockIn = (minutes) =>
  new Date(Date.now() + minutes * 60000).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true });

const sizeLabel = (l) => (l.hasHalf ? (l.size === "half" ? "Half" : "Full") : "");

export function CartScreen({ paused, totals, back, placeOrder, changeLine, removeLine }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [pickup, setPickup] = useState(0); // minutes until they reach the stall (0 = now)
  const submit = async () => {
    setBusy(true); setErr("");
    try { await placeOrder(note, pickup); }
    catch (e) { setErr(e.message); setBusy(false); }
  };
  const empty = totals.lines.length === 0;
  const pickupText = pickup === 0 ? "Now" : `in ${pickup} min`;

  return (
    <main className={`screen-in mx-auto max-w-[1040px] px-3 font-body ${empty ? "pb-10" : "pb-[calc(var(--sab)+13rem)] md:pb-12"}`}>
      <FoodBackground />
      <button onClick={back} className="press flex items-center gap-1.5 px-1 py-4 font-bold text-accent">
        <BackIcon className="h-[18px] w-[18px]" /> Back to menu
      </button>
      <h1 className="px-1 font-display text-[32px] font-extrabold leading-none md:text-[44px]">Your order</h1>
      <p className="mb-5 mt-1.5 hidden px-1 text-muted md:block">Check it, choose when you'll arrive, and we'll start making it.</p>

      {empty && (
        <div className={`${CARD} mx-auto mt-4 max-w-[480px] p-6 text-center`}>
          <p className="text-muted">Your cart is empty</p>
          <button onClick={back} className="press mt-4 h-12 w-full rounded-2xl bg-accent font-extrabold text-bg1">Browse the menu</button>
        </div>
      )}

      {!empty && (
        <div className="mt-4 flex flex-col gap-6 md:mt-0 md:flex-row md:items-start">
          {/* left: lines, pickup time, note */}
          <div className="flex min-w-0 flex-1 flex-col gap-3 md:gap-4">
            <section aria-label="Items" className={`${CARD} overflow-hidden`}>
              {totals.lines.map((l) => {
                const key = `${l.id}_${l.size}`;
                const label = `${l.name}${l.hasHalf ? ` (${sizeLabel(l)})` : ""}`;
                return (
                  <div key={key} className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-[var(--stroke)] px-4 py-3.5 md:flex-nowrap md:gap-4 md:px-5 md:py-4">
                    <div className="min-w-0 flex-1 basis-full md:basis-auto">
                      <div className="flex items-start gap-2">
                        <span className="mt-1"><VegMark /></span>
                        <b className="break-words leading-snug md:text-[17px]">{l.name}</b>
                        {l.hasHalf && <span className="mt-0.5 flex-none rounded-md bg-[var(--accent2-tint)] px-2 py-0.5 text-xs font-bold text-accent2">{sizeLabel(l)}</span>}
                      </div>
                      <span className="ml-[22px] text-[13px] text-muted md:text-sm">₹{l.price} each</span>
                    </div>
                    <div className="flex flex-none items-center overflow-hidden rounded-xl border-[1.5px] border-accent">
                      <button onClick={() => changeLine(key, -1)} aria-label={`One less ${label}`}
                        className="h-11 w-10 text-xl font-extrabold text-accent">−</button>
                      <div className="w-8 text-center text-[17px] font-extrabold" aria-label={`${label} quantity`}>{l.qty}</div>
                      <button onClick={() => changeLine(key, 1)} disabled={l.qty >= MAX_QTY} aria-label={`One more ${label}`}
                        className="h-11 w-10 text-xl font-extrabold text-accent disabled:opacity-30">+</button>
                    </div>
                    <b className="ml-auto whitespace-nowrap font-display text-xl text-accent md:ml-0 md:w-20 md:text-right md:text-[22px]">₹{l.price * l.qty}</b>
                    <button onClick={() => removeLine(key)} aria-label={`Remove ${label}`}
                      className="press flex h-11 w-11 flex-none items-center justify-center rounded-xl border border-[var(--danger-soft)] text-danger">
                      <TrashIcon />
                    </button>
                  </div>
                );
              })}
              <button onClick={back} className="press flex w-full items-center gap-2 px-4 py-3.5 text-left font-bold text-accent md:px-5 md:py-4">
                <PlusIcon /> Add more food
              </button>
            </section>

            <section className={`${CARD} p-4 md:p-5`}>
              <h2 id="pickup-label" className="flex items-center gap-2 font-bold md:text-[17px]">
                <ClockIcon className="h-5 w-5 text-accent" /> When will you reach the stall?
              </h2>
              <p className="mb-3 mt-1 text-xs text-muted md:text-sm">The stall times your order so it is hot when you arrive.</p>
              <div className="grid grid-cols-4 gap-1.5 md:gap-2.5" role="radiogroup" aria-labelledby="pickup-label">
                {PICKUP_OPTIONS.map((o) => (
                  <button key={o.minutes} role="radio" aria-checked={pickup === o.minutes} onClick={() => setPickup(o.minutes)}
                    className={`press flex min-h-[48px] flex-col items-center justify-center rounded-xl border text-sm font-bold md:min-h-[64px] md:rounded-2xl md:text-base ${
                      pickup === o.minutes ? "border-transparent bg-accent2 text-bg1" : "border-[var(--stroke)] text-ink"}`}>
                    {o.label}
                    <span className={`hidden text-xs font-medium md:block ${pickup === o.minutes ? "" : "text-muted"}`}>
                      {o.minutes === 0 ? "on my way" : `~${clockIn(o.minutes)}`}
                    </span>
                  </button>
                ))}
              </div>
            </section>

            <section className={`${CARD} flex flex-col gap-2 p-4 md:p-5`}>
              <label htmlFor="order-note" className="font-bold md:text-[17px]">
                Special instructions <span className="font-medium text-muted">(optional)</span>
              </label>
              <textarea id="order-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} rows={2}
                placeholder="e.g. less spicy, extra chutney"
                className="resize-none rounded-xl border border-[var(--stroke)] bg-[var(--glass)] p-3 text-ink placeholder:text-muted focus:border-accent focus:outline-none" />
            </section>
          </div>

          {/* bill: a sheet pinned to the bottom on phones, a receipt card beside the order on wider screens */}
          <aside aria-label="Bill"
            className="fixed inset-x-0 bottom-0 z-40 mx-auto max-w-[520px] md:sticky md:top-6 md:z-auto md:mx-0 md:w-[340px] md:max-w-none md:flex-none">
            <div aria-hidden="true" className="absolute -bottom-3 left-2.5 right-[-10px] top-4 hidden rotate-[2.5deg] rounded-[24px] bg-accent md:block" />
            <div className="relative rounded-t-[26px] bg-ink px-5 pb-[calc(var(--sab)+1.25rem)] pt-4 text-bg1 shadow-float md:rounded-[24px] md:px-6 md:pb-6 md:pt-5">
              <div className="hidden items-center justify-between md:flex">
                <b className="font-display text-[22px]">Bill</b>
                <span className="text-[13px] opacity-70">Pickup · {pickupText}</span>
              </div>
              <div className="mt-3 hidden flex-col gap-2 text-[15px] md:flex">
                {totals.lines.map((l) => (
                  <div key={`${l.id}_${l.size}`} className="flex justify-between gap-3">
                    <span>{l.qty} × {l.name}{l.hasHalf && <span className="opacity-60"> ({sizeLabel(l)})</span>}</span>
                    <b className="whitespace-nowrap">₹{l.price * l.qty}</b>
                  </div>
                ))}
              </div>
              <div className="flex items-baseline justify-between md:mt-4 md:border-t-2 md:border-dashed md:border-[var(--line-on-light)] md:pt-4">
                <span className="font-bold">Total <span className="font-medium opacity-60 md:hidden">· {totals.count} {totals.count === 1 ? "item" : "items"}</span></span>
                <b className="font-display text-[30px] leading-none md:text-[34px]">₹{totals.total}</b>
              </div>
              <div className="mb-3 mt-2 flex items-center gap-2 rounded-xl text-[13px] font-bold md:mt-4 md:bg-[var(--accent2-soft)] md:px-3.5 md:py-3 md:text-sm">
                <CashIcon className="h-[18px] w-[18px]" /> Pay cash when you collect
              </div>
              {paused ? <p role="status" className="mb-3 rounded-xl bg-danger px-3 py-2 text-center text-sm font-bold text-bg1">⏸ {paused}</p>
                : err && <p role="alert" className="mb-3 rounded-xl bg-danger px-3 py-2 text-center text-sm font-bold text-bg1">{err}</p>}
              <button onClick={submit} disabled={!totals.count || busy || !!paused}
                className="press flex h-14 w-full items-center justify-center gap-2.5 rounded-2xl bg-bg1 text-lg font-extrabold text-accent disabled:opacity-50">
                {busy ? "Placing order…" : <>Place order <ArrowIcon /></>}
              </button>
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}
