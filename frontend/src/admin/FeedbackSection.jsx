import { useEffect, useState } from "react";

import { api } from "../api.js";

const stars = (n) => "★".repeat(n) + "☆".repeat(5 - n);

// Read-only for now: what customers think of each product. Loaded when opened.
// `alwaysOpen`: shown as its own tab — no fold, loaded straight away.
export default function FeedbackSection({ alwaysOpen = false }) {
  const [open, setOpen] = useState(alwaysOpen);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [lowOnly, setLowOnly] = useState(false); // only 1–2★ reviews: what to fix first

  useEffect(() => {
    if (alwaysOpen) api("/api/admin/feedback").then(setData).catch((e) => setErr(e.message));
  }, [alwaysOpen]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      setErr("");
      api("/api/admin/feedback").then(setData).catch((e) => setErr(e.message));
    }
  };

  return (
    <>
      {alwaysOpen ? (
        <h2 className="mb-2.5 mt-5 px-1 font-black text-accent">Customer feedback{data ? ` (${data.recent.length})` : ""}</h2>
      ) : (
        <button onClick={toggle}
          className="press glass-strong mt-6 w-full rounded-xl px-4 py-3 text-left font-black text-accent">
          {open ? "▾" : "▸"} Customer feedback{data ? ` (${data.recent.length})` : ""}
        </button>
      )}
      {open && (
        <div className="mt-3">
          {err && <p className="glass p-4 text-center text-sm text-danger">{err}</p>}
          {!data && !err && <p className="glass p-4 text-center text-muted">Loading…</p>}
          {data && data.recent.length === 0 && (
            <p className="glass p-5 text-center text-muted">No feedback yet — customers can rate an order once they've collected it</p>
          )}
          {data && data.items.length > 0 && (
            <div className="glass mb-3 p-4">
              <div className="mb-1 text-xs font-black uppercase tracking-wider text-muted">Average per item</div>
              {data.items.map((i) => (
                <div key={i.menu_item_id} className="flex justify-between border-b border-[var(--stroke)] py-2 last:border-0">
                  <b>{i.name}</b>
                  <span><b className="text-star">★ {i.average}</b> <small className="text-muted">({i.count})</small></span>
                </div>
              ))}
            </div>
          )}
          {data && data.recent.length > 0 && (
            <div className="mb-2.5 flex gap-1.5" role="tablist" aria-label="Filter reviews">
              {[[false, `All ${data.recent.length}`], [true, `Low 1–2★ ${data.recent.filter((f) => f.rating <= 2).length}`]].map(([low, label]) => (
                <button key={label} role="tab" aria-selected={lowOnly === low} onClick={() => setLowOnly(low)}
                  className={`press rounded-full border px-3.5 py-2 text-sm font-bold ${
                    lowOnly === low ? "border-transparent bg-accent text-bg1" : "border-[var(--stroke)] text-muted"}`}>
                  {label}
                </button>
              ))}
            </div>
          )}
          {data && lowOnly && data.recent.every((f) => f.rating > 2) && (
            <p className="glass p-5 text-center text-muted">No low ratings 🎉</p>
          )}
          {data && data.recent.filter((f) => !lowOnly || f.rating <= 2).map((f) => (
            <div key={f.id} className="glass mb-2.5 p-4">
              <div className="flex items-baseline justify-between gap-3">
                <b>{f.item}</b>
                <span className="whitespace-nowrap text-star" aria-label={`${f.rating} of 5 stars`}>{stars(f.rating)}</span>
              </div>
              {f.comment && <p className="mt-1">“{f.comment}”</p>}
              <div className="mt-1 text-xs text-muted">
                {f.name || f.email} · {new Date(f.created_at + "Z").toLocaleDateString([], { day: "numeric", month: "short" })}
                {f.allow_public ? <span className="ml-1 font-bold text-accent2">· OK to show publicly</span> : " · private"}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
