import { LABELS, STATUSES, isActive } from "../config/constants.js";
import { useNow } from "../hooks/useNow.js";
import { notStartedYet, pickupLabel, placedLabel } from "../utils/pickup.js";
import { FoodBackground } from "../components/ui.jsx";
import { ask } from "../components/dialog.jsx";
import { BackIcon, CheckIcon, ClockIcon, NoteIcon, PhoneIcon, PlusIcon, StarIcon } from "../components/icons.jsx";

function Tracker({ status }) {
  const idx = STATUSES.indexOf(status);
  const pct = (Math.max(idx, 0) / (STATUSES.length - 1)) * 100;
  return (
    <div className="relative mx-1 mb-1 mt-5" aria-label={`Status: ${LABELS[status]}`}>
      {/* the bar runs between the first and last dot */}
      <div className="absolute left-[12.5%] right-[12.5%] top-4 h-1 rounded-full bg-[var(--stroke)]">
        <div className="h-full rounded-full bg-accent2 transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
      <ol className="relative flex">
        {STATUSES.map((s, i) => (
          <li key={s} className="flex flex-1 flex-col items-center text-center">
            <span className={`mb-1.5 flex h-9 w-9 items-center justify-center rounded-full font-display text-sm font-extrabold transition-all ${
              i < idx ? "bg-accent2 text-bg1"
                : i === idx ? "pulse-dot bg-accent text-bg1"
                  : "border border-[var(--stroke)] bg-[var(--card)] text-muted"
            }`}>{i < idx ? <CheckIcon /> : i + 1}</span>
            <small className={`text-xs font-bold ${i <= idx ? "text-ink" : "text-muted"}`}>{LABELS[s]}</small>
          </li>
        ))}
      </ol>
    </div>
  );
}

// "Call the stall" on an order in progress. It stands out once the order has sat at "placed"
// for a while (`urgent`): the owner may not have seen it, and a call gets it started.
function CallStall({ order, phone, urgent }) {
  return (
    <div className={`mt-4 rounded-2xl border p-3 ${urgent ? "border-warn bg-warn-soft" : "border-[var(--stroke)] bg-[var(--glass)]"}`}>
      {urgent && <p className="mb-2 text-sm font-bold text-warn">The stall hasn't started your order yet — give them a call.</p>}
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-muted">Tell them: <b className="text-ink">order #{order.order_number}</b></span>
        <a href={`tel:${phone}`} aria-label={`Call the stall about order #${order.order_number}`}
          className={`press flex flex-none items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-extrabold ${urgent ? "bg-accent text-bg1" : "bg-[var(--glass-strong)] text-accent"}`}>
          <PhoneIcon /> Call the stall
        </a>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const tone = status === "ready" ? "bg-accent2 text-bg1"
    : status === "cancelled" ? "bg-danger-soft text-danger"
    : status === "not_collected" || status === "completed" ? "bg-[var(--glass-strong)] text-muted"
    : "bg-[var(--accent-ring)] text-accent";
  return <span className={`rounded-full px-2.5 py-1 text-xs font-extrabold ${tone}`}>{LABELS[status]}</span>;
}

function OrderCard({ order, cancel, rate, phone, now }) {
  const time = placedLabel(order, now);
  const cancelled = order.status === "cancelled";
  const uncollected = order.status === "not_collected"; // the stall closed it: it was ready but never picked up
  const active = isActive(order);
  return (
    <div className={`rounded-[22px] border border-[var(--stroke)] p-4 backdrop-blur-md md:p-5 ${
      active ? "bg-[var(--card)] shadow-dialog" : "bg-[var(--glass)]"} ${cancelled || uncollected ? "opacity-60" : ""}`}>
      <div className="flex items-center gap-3">
        <span className={`font-display font-extrabold leading-none text-accent ${active ? "text-[34px]" : "text-2xl"}`}>#{order.order_number}</span>
        <StatusPill status={order.status} />
        <span className="ml-auto text-right text-sm text-muted">{time}<br /><b className="font-display text-lg text-accent2">₹{order.total}</b></span>
      </div>
      <div className="mt-2 text-sm text-muted">
        {order.items.map((i) => `${i.name}${i.size !== "na" ? ` (${i.size})` : ""} ×${i.qty}`).join(", ")}
      </div>
      {order.note && (
        <div className="mt-2 flex items-center gap-1.5 rounded-lg bg-[var(--accent-ring)] px-2.5 py-1.5 text-sm text-accent">
          <NoteIcon className="h-4 w-4 flex-none" /> <span className="italic">“{order.note}”</span>
        </div>
      )}
      {active && pickupLabel(order) && (
        <div className="mt-2 flex items-center gap-1.5 text-sm font-bold text-accent2"><ClockIcon className="h-4 w-4" /> {pickupLabel(order)}</div>
      )}
      {!cancelled && !uncollected && active && <Tracker status={order.status} />}
      {order.status === "completed" && (order.reviewed
        ? <p className="mt-3 flex items-center gap-1.5 text-sm font-bold text-accent2"><CheckIcon /> Thanks for your feedback</p>
        : <button onClick={() => rate(order)}
            className="press mt-3 flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-extrabold text-bg1">
            <StarIcon className="h-4 w-4" /> Rate your food
          </button>)}
      {active && phone && <CallStall order={order} phone={phone} urgent={notStartedYet(order, now)} />}
      {order.status === "placed" && (
        <button onClick={async () => await ask({ title: `Cancel order #${order.order_number}?`,
          message: "The stall hasn't started it yet. You can order again any time.",
          confirmLabel: "Cancel order", cancelLabel: "Keep it", tone: "danger" }) && cancel(order.id)}
          className="press mt-3 rounded-xl border border-[var(--danger-soft)] px-4 py-2 text-sm font-bold text-danger">Cancel order</button>
      )}
    </div>
  );
}

export default function OrdersScreen({ orders, phone, cancel, rate, newOrder, back }) {
  const now = useNow();
  const current = orders.filter(isActive);
  const past = orders.filter((o) => !isActive(o));
  const card = (o) => <OrderCard key={o.id} order={o} cancel={cancel} rate={rate} phone={phone} now={now} />;
  return (
    <main className="screen-in mx-auto max-w-[860px] px-3 pb-10 font-body">
      <FoodBackground />
      <button onClick={back} className="press flex items-center gap-1.5 px-1 py-4 font-bold text-accent">
        <BackIcon className="h-[18px] w-[18px]" /> Menu
      </button>
      <div className="flex flex-wrap items-end justify-between gap-3 px-1">
        <div>
          <h1 className="font-display text-[32px] font-extrabold leading-none md:text-[44px]">My orders</h1>
          <p className="mt-1.5 text-sm text-muted">Pay cash at the counter · show your order number</p>
        </div>
        <button onClick={newOrder}
          className="press flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-accent px-5 font-extrabold text-bg1 shadow-[0_8px_24px_var(--accent-glow)] sm:w-auto">
          <PlusIcon /> New order
        </button>
      </div>

      {orders.length === 0 && (
        <p className="mt-5 rounded-[22px] border border-[var(--stroke)] bg-[var(--glass)] p-6 text-center text-muted">No orders yet</p>
      )}

      {current.length > 0 && (
        <section className="mt-6">
          <h2 className="mb-3 px-1 font-display text-xl font-extrabold">In progress</h2>
          <div className="flex flex-col gap-3.5">{current.map(card)}</div>
        </section>
      )}

      {past.length > 0 && (
        <section className="mt-7">
          <h2 className="mb-3 px-1 font-display text-xl font-extrabold">Past orders</h2>
          <div className="flex flex-col gap-3 md:grid md:grid-cols-2 md:items-start">{past.map(card)}</div>
        </section>
      )}
    </main>
  );
}
