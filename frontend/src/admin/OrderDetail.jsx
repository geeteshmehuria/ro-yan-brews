import { useEffect } from "react";

import { useBackToClose } from "../backButton.js";
import { LABELS, STATUSES, isActive } from "../constants.js";

const SIZE_LABELS = { half: "Half", full: "Full" };

export const sizeLabel = (size) => SIZE_LABELS[size] || "";

// "7:42 pm", plus the date for an order left over from an earlier day (numbers restart daily).
export function placedAt(order) {
  const placed = new Date(order.created_at + "Z");
  const time = placed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return placed.toDateString() === new Date().toDateString()
    ? time : `${time} · ${placed.toLocaleDateString([], { day: "numeric", month: "short" })}`;
}

// "just now" / "12 min ago" / "1 h 5 min ago"; `now` comes from the caller so it re-renders.
export function ago(order, now) {
  const mins = Math.max(0, Math.floor((now - new Date(order.created_at + "Z")) / 60000));
  if (mins < 1) return "just now";
  return mins < 60 ? `${mins} min ago` : `${Math.floor(mins / 60)} h ${mins % 60} min ago`;
}

const BADGE = {
  placed: "bg-accent text-bg1",
  preparing: "bg-accent text-bg1",
  ready: "bg-accent2 text-bg1",
  completed: "glass-strong text-muted",
  cancelled: "bg-danger text-bg1",
};

export function StatusBadge({ status }) {
  return <span className={`rounded-full px-3 py-1 text-sm font-black ${BADGE[status]}`}>{LABELS[status]}</span>;
}

// Status buttons shared by the queue card and the detail panel, so both behave the same.
export function StatusActions({ order, setStatus, big = false }) {
  if (order.status === "cancelled") return <div className="font-extrabold text-danger">Cancelled</div>;
  const size = big ? "min-h-[48px] flex-1 px-3 text-base" : "px-3 py-2 text-xs";
  return (
    <div className="flex flex-wrap gap-1.5">
      {STATUSES.map((s) => (
        <button key={s} onClick={() => setStatus(order, s)}
          className={`press rounded-lg border font-bold ${size} ${
            order.status === s ? "border-transparent bg-accent2 text-bg1" : "border-[var(--stroke)] text-muted"
          }`}>
          {LABELS[s]}
        </button>
      ))}
      {isActive(order) && order.status !== "ready" && (
        <button onClick={() => window.confirm("Cancel this order?") && setStatus(order, "cancelled")}
          className={`press rounded-lg border border-[var(--stroke)] font-bold text-danger ${size}`}>
          Cancel
        </button>
      )}
    </div>
  );
}

// Everything about one order. Reads the live order from the queue, so WebSocket updates show here too.
export default function OrderDetail({ order, now, setStatus, onClose }) {
  useBackToClose(onClose);
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden"; // the queue behind shouldn't scroll
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);

  const count = order.items.reduce((n, i) => n + i.qty, 0);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 md:items-center"
      onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={`Order #${order.order_number}`}
        onClick={(e) => e.stopPropagation()}
        className="screen-in max-h-[90vh] w-full max-w-[520px] overflow-y-auto rounded-t-glass border border-[var(--stroke)] p-5 md:rounded-glass"
        style={{ background: "var(--bg2)" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-4xl font-black text-accent">#{order.order_number}</span>
            <StatusBadge status={order.status} />
          </div>
          <button onClick={onClose} aria-label="Close"
            className="press glass-strong h-11 w-11 rounded-full text-lg font-black">✕</button>
        </div>
        <p className="mt-1 text-sm text-muted">Placed {placedAt(order)} · {ago(order, now)}</p>

        <div className="glass mt-4 p-4">
          <div className="text-xl font-extrabold">{order.name || order.email}</div>
          {order.name && <div className="break-all text-sm text-muted">{order.email}</div>}
        </div>

        {order.note && (
          <div className="mt-3 rounded-glass border-2 border-accent p-4">
            <div className="text-xs font-black uppercase tracking-wider text-accent">📝 Special instructions</div>
            <div className="mt-1 text-lg font-bold">{order.note}</div>
          </div>
        )}

        <div className="glass mt-3 p-4">
          <div className="mb-2 text-xs font-black uppercase tracking-wider text-muted">{count} {count === 1 ? "item" : "items"}</div>
          {order.items.map((i, n) => (
            <div key={n} className="flex items-baseline justify-between gap-3 border-b border-[var(--stroke)] py-2.5 last:border-0">
              <div className="text-lg">
                <b className="text-accent">{i.qty} ×</b> {i.name}
                {sizeLabel(i.size) && <span className="ml-1 text-sm text-muted">({sizeLabel(i.size)})</span>}
                <div className="text-sm text-muted">₹{i.price} each</div>
              </div>
              <b className="whitespace-nowrap text-lg">₹{i.price * i.qty}</b>
            </div>
          ))}
          <div className="mt-2 flex justify-between border-t-2 border-[var(--stroke)] pt-3 text-2xl font-black text-accent2">
            <span>Total</span><span>₹{order.total}</span>
          </div>
          <p className="mt-1 text-sm text-muted">💵 Collect cash on pickup</p>
        </div>

        <div className="mt-4">
          <StatusActions order={order} setStatus={setStatus} big />
        </div>
      </div>
    </div>
  );
}
