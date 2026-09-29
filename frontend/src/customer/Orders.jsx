import { LABELS, STATUSES } from "../constants.js";
import { Back, BigButton } from "../ui.jsx";

function Tracker({ status }) {
  const idx = STATUSES.indexOf(status);
  return (
    <div className="relative mx-2 my-5 flex justify-between">
      <span className="absolute left-[10%] right-[10%] top-4 h-0.5 bg-[var(--stroke)]" />
      {STATUSES.map((s, i) => (
        <div key={s} className="relative z-10 flex-1 text-center">
          <div className={`mx-auto mb-1.5 flex h-8 w-8 items-center justify-center rounded-full text-sm font-extrabold transition-all ${
            i < idx ? "bg-accent2 text-bg1"
              : i === idx ? "pulse-dot bg-accent text-bg1"
                : "glass-strong text-muted"
          }`}>{i + 1}</div>
          <small className={`text-xs font-bold ${i <= idx ? "text-ink" : "text-muted"}`}>{LABELS[s]}</small>
        </div>
      ))}
    </div>
  );
}

function OrderCard({ order, cancel }) {
  const time = new Date(order.created_at + "Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const cancelled = order.status === "cancelled";
  return (
    <div className={`glass mb-3 p-4 ${cancelled ? "opacity-60" : ""}`}>
      <div className="flex items-baseline justify-between">
        <span className="text-2xl font-black text-accent">#{order.order_number}</span>
        <span className="text-sm text-muted">{time} · <b className="text-accent2">₹{order.total}</b></span>
      </div>
      <div className="mt-1 text-sm text-muted">
        {order.items.map((i) => `${i.name}${i.size !== "na" ? ` (${i.size})` : ""} ×${i.qty}`).join(", ")}
      </div>
      {order.note && <div className="mt-1 text-sm italic text-muted">“{order.note}”</div>}
      {cancelled
        ? <div className="mt-3 font-extrabold text-danger">Cancelled</div>
        : <Tracker status={order.status} />}
      {order.status === "placed" && (
        <button onClick={() => window.confirm("Cancel this order?") && cancel(order.id)}
          className="press glass-strong rounded-xl px-4 py-2 text-sm font-bold text-danger">Cancel order</button>
      )}
    </div>
  );
}

export default function OrdersScreen({ orders, cancel, newOrder, back }) {
  return (
    <main className="screen-in px-3 pb-10">
      <Back onClick={back}>← Menu</Back>
      <h2 className="mb-1 px-1 text-xl font-black">My orders</h2>
      <p className="mb-3 px-1 text-sm text-muted">Pay cash at the counter · show your order number</p>
      <BigButton onClick={newOrder}>+ New order</BigButton>
      <div className="mt-4">
        {orders.length === 0 && <p className="glass p-5 text-center text-muted">No orders yet</p>}
        {orders.map((o) => <OrderCard key={o.id} order={o} cancel={cancel} />)}
      </div>
    </main>
  );
}
