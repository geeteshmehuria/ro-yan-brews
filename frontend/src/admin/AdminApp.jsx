import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, getSession, getToken, logout } from "../api.js";
import { beep } from "../alerts.js";
import { useBackButton } from "../backButton.js";
import { MUTE_KEY, isActive } from "../constants.js";
import { useSocket } from "../useSocket.js";
import FeedbackSection from "./FeedbackSection.jsx";
import MenuSection from "./MenuSection.jsx";
import OrderDetail, { StatusActions, ago, placedAt, sizeLabel } from "./OrderDetail.jsx";
import { disablePush, enablePush } from "../push.js";

// Orders not yet ready turn amber after 10 minutes and red after 20.
const WAIT_AMBER = 10, WAIT_RED = 20;
const waitLevel = (order, now) => {
  if (order.status !== "placed" && order.status !== "preparing") return null;
  const mins = (now - new Date(order.created_at + "Z")) / 60000;
  return mins >= WAIT_RED ? "red" : mins >= WAIT_AMBER ? "amber" : null;
};

function OrderCard({ order, now, setStatus, open }) {
  const cancelled = order.status === "cancelled";
  const wait = waitLevel(order, now);
  const count = order.items.reduce((n, i) => n + i.qty, 0);
  const summary = order.items.map((i) => `${i.name}${sizeLabel(i.size) ? ` (${sizeLabel(i.size)})` : ""} ×${i.qty}`).join(", ");
  return (
    <div role="button" tabIndex={0} aria-label={`Open order #${order.order_number}`}
      onClick={open} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && e.target === e.currentTarget && (e.preventDefault(), open())}
      className={`glass mb-3 cursor-pointer border-l-4 p-4 ${cancelled ? "opacity-50 !border-l-danger" : order.fresh ? "flash-new !border-l-danger"
        : wait === "red" ? "!border-l-danger" : wait === "amber" ? "!border-l-warn" : "!border-l-accent"}`}>
      <div className="flex justify-between font-extrabold">
        <span>#{order.order_number} · {order.name || order.email}</span>
        <span className="text-accent2">₹{order.total}</span>
      </div>
      <div className="mt-0.5 text-xs text-muted">
        {placedAt(order)} ·{" "}
        <span className={wait === "red" ? "font-black text-danger" : wait === "amber" ? "font-black text-warn" : ""}>
          {wait && "⏱ "}{ago(order, now)}
        </span>
      </div>
      <div className="my-2 text-sm">
        <b>{count} {count === 1 ? "item" : "items"}</b> <span className="text-muted">· {summary}</span>
      </div>
      {order.note && <div className="mb-2 truncate text-sm font-bold text-accent">📝 {order.note}</div>}
      {/* buttons act on the order; they must not also open the detail panel */}
      <div onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <StatusActions order={order} setStatus={setStatus} />
      </div>
      <div className="mt-2 text-right text-xs font-bold text-accent">Tap for details ›</div>
    </div>
  );
}

const TABS = [
  { id: "orders", label: "Orders", icon: "🧾" },
  { id: "menu", label: "Menu", icon: "🍔" },
  { id: "reviews", label: "Reviews", icon: "⭐" },
];

const FILTERS = [
  { id: "all", label: "All" },
  { id: "placed", label: "New" },
  { id: "preparing", label: "Preparing" },
  { id: "ready", label: "Ready" },
];

function readMuted() {
  try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
}

// Re-render every 30 s so "12 min ago" stays true.
function useNow(ms = 30000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), ms); return () => clearInterval(t); }, [ms]);
  return now;
}

export default function AdminApp() {
  const navigate = useNavigate();
  const session = getSession();
  const isAdmin = !!session?.is_admin;

  const [orders, setOrders] = useState([]);
  const [stats, setStats] = useState(null);
  const [offline, setOffline] = useState(false);
  const [openId, setOpenId] = useState(null); // order shown in the detail panel (by id, so live updates show)
  const [showDone, setShowDone] = useState(false);
  const [tab, setTab] = useState("orders");
  const [filter, setFilter] = useState("all");
  const [menuFilter, setMenuFilter] = useState("all"); // "out" = only out-of-stock items
  const [muted, setMuted] = useState(readMuted);
  const [storeBusy, setStoreBusy] = useState(false);
  const mutedRef = useRef(muted);
  mutedRef.current = muted;
  const now = useNow();
  const closeDetail = useCallback(() => setOpenId(null), []);

  useEffect(() => {
    if (!isAdmin) {
      navigate("/", { replace: true });
    }
  }, [isAdmin, navigate]);

  // Android app only: order alerts while the app is closed.
  // Tapping a "New order" notification opens that order.
  useEffect(() => {
    if (isAdmin) enablePush((data) => { setTab("orders"); setOpenId(Number(data.order_id)); });
  }, [isAdmin]);

  // Android Back on the Menu / Reviews tab returns to Orders (the home tab).
  useBackButton(() => setTab("orders"), tab !== "orders");

  // The out-of-stock filter is for that one visit: leaving the Menu tab resets it.
  useEffect(() => { if (tab !== "menu") setMenuFilter("all"); }, [tab]);

  const refreshStats = useCallback(() => api("/api/admin/stats/today").then(setStats).catch(() => {}), []);
  useEffect(() => { if (isAdmin && tab === "orders") refreshStats(); }, [isAdmin, tab, refreshStats]); // e.g. stock changed

  const load = useCallback(async () => {
    const [o, s] = await Promise.all([api("/api/admin/orders"), api("/api/admin/stats/today")]);
    setOrders(o); setStats(s);
  }, []);

  // Only a rejected session logs the owner out. A network error or a 502 while the
  // free-tier backend wakes up just retries.
  useEffect(() => {
    if (!isAdmin) return;
    let timer, stopped = false;
    const attempt = () => load().then(() => setOffline(false)).catch((e) => {
      if (stopped) return;
      if (e.status === 401 || e.status === 403) {
        logout();
        navigate("/", { replace: true });
      } else {
        setOffline(true);
        timer = setTimeout(attempt, 5000);
      }
    });
    attempt();
    return () => { stopped = true; clearTimeout(timer); };
  }, [isAdmin, load, navigate]);

  // Live alerts. After a reconnect, reload so nothing placed while offline is missed.
  useSocket(isAdmin && `/ws/admin?token=${encodeURIComponent(getToken())}`, (msg) => {
    if (msg.type === "store") {  // paused / reopened from another device
      setStats((st) => st && { ...st, accepting_orders: msg.accepting_orders });
      return;
    }
    if (msg.type === "new_order") {
      if (!mutedRef.current) beep();
      setOrders((os) => [{ ...msg.order, fresh: true }, ...os]);
    } else if (msg.type === "status") {  // e.g. the customer cancelled, or another admin device acted
      setOrders((os) => os.map((o) => (o.id === msg.order_id ? { ...o, status: msg.status, fresh: false } : o)));
    }
    refreshStats();
  }, () => load().catch(() => {}));

  if (!isAdmin) return null;

  const setStatus = async (order, status) => {
    try {
      await api(`/api/admin/orders/${order.id}/status`, { method: "PATCH", body: { status } });
      setOrders((os) => os.map((o) => (o.id === order.id ? { ...o, status, fresh: false } : o)));
    } catch (e) { alert(e.message); }
  };

  // Kitchen order: active ones oldest first (next to make on top); finished ones folded below, newest first.
  const byTime = (a, b) => a.created_at.localeCompare(b.created_at);
  const active = orders.filter(isActive).sort(byTime);
  const done = orders.filter((o) => !isActive(o)).sort((a, b) => byTime(b, a));
  const counts = Object.fromEntries(FILTERS.map((f) => [f.id, f.id === "all" ? active.length
    : active.filter((o) => o.status === f.id).length]));
  const shown = filter === "all" ? active : active.filter((o) => o.status === filter);
  const accepting = stats ? stats.accepting_orders !== false : true;
  const openOrder = orders.find((o) => o.id === openId);

  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    try { localStorage.setItem(MUTE_KEY, next ? "1" : "0"); } catch { /* per-device convenience only */ }
  };

  const toggleStore = async () => {
    if (accepting && !window.confirm("Pause new orders? Customers will see “We're not taking orders right now”. Orders already placed carry on.")) return;
    setStoreBusy(true);
    try {
      const r = await api("/api/admin/store", { method: "PATCH", body: { accepting_orders: !accepting } });
      setStats((st) => st && { ...st, accepting_orders: r.accepting_orders });
    } catch (e) { alert(e.message); }
    setStoreBusy(false);
  };

  const showOutOfStock = () => { setMenuFilter("out"); setTab("menu"); };
  const card = (o) => <OrderCard key={o.id} order={o} now={now} setStatus={setStatus} open={() => setOpenId(o.id)} />;

  const handleLogout = () => {
    disablePush(); // not awaited: api() reads the session token synchronously, and a sleeping backend would freeze the button
    logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="screen-in px-3 pb-[calc(var(--sab)+6rem)]">
      <header className="glass sticky top-[calc(var(--sat)+0.5rem)] z-40 mt-3 flex items-center justify-between gap-2 px-4 py-3">
        <div className="text-lg font-black">RO-YAN <span className="text-accent">ADMIN</span></div>
        <div className="flex items-center gap-2">
          <button onClick={toggleMute} aria-label={muted ? "Turn new-order sound on" : "Mute new-order sound"}
            aria-pressed={muted} className="glass-strong press h-9 w-9 rounded-xl text-base">{muted ? "🔕" : "🔔"}</button>
          <button onClick={handleLogout}
            className="glass-strong press rounded-xl px-3 py-1.5 text-xs font-bold">Log out</button>
        </div>
      </header>

      {offline && <p className="glass mt-4 p-3 text-center text-sm text-danger">Can't reach the server — retrying…</p>}

      {tab === "orders" && (
        <>
          {stats && (
            <button onClick={toggleStore} disabled={storeBusy} role="switch" aria-checked={accepting}
              aria-label={accepting ? "Taking orders — tap to pause" : "Orders paused — tap to open"}
              className={`press mt-4 flex w-full items-center justify-between gap-3 rounded-glass border p-3.5 text-left ${
                accepting ? "glass border-[var(--stroke)]" : "border-danger bg-danger-soft"}`}>
              <span>
                <b className={accepting ? "text-accent2" : "text-danger"}>
                  {accepting ? "🟢 Taking orders" : "⏸ Orders paused"}
                </b>
                <br />
                <small className="text-muted">
                  {accepting ? "Tap to pause when you're closed or too busy" : "Customers can't order. Tap to open again"}
                </small>
              </span>
              <span className={`relative h-7 w-[52px] flex-none rounded-full border transition-colors ${
                accepting ? "border-transparent bg-accent2" : "glass-strong border-[var(--stroke)]"}`}>
                <span className={`absolute top-[3px] h-5 w-5 rounded-full bg-white transition-all ${accepting ? "left-[27px]" : "left-[3px]"}`} />
              </span>
            </button>
          )}

          {stats && (
            <div className="mt-3 grid grid-cols-3 gap-2.5">
              <div className="glass p-3 text-center"><b className="block text-xl text-accent2">₹{stats.cash_collected ?? stats.revenue}</b><small className="text-xs text-muted">Cash collected</small></div>
              <div className="glass p-3 text-center"><b className="block text-xl text-accent">{stats.orders}</b><small className="text-xs text-muted">Orders today</small></div>
              <div className="glass p-3 text-center"><b className="block text-xl text-accent">₹{stats.to_collect ?? 0}</b><small className="text-xs text-muted">Still to collect</small></div>
            </div>
          )}

          {stats?.out_of_stock > 0 && (
            <button onClick={showOutOfStock}
              className="press mt-3 flex w-full items-center justify-between rounded-glass border border-warn bg-warn-soft px-4 py-3 text-left text-sm font-bold">
              <span>⚠ {stats.out_of_stock} {stats.out_of_stock === 1 ? "item is" : "items are"} out of stock</span>
              <span className="text-accent">Menu ›</span>
            </button>
          )}

          <h2 className="mb-2 mt-5 px-1 font-black text-accent">Order queue</h2>
          <div className="mb-3 flex gap-1.5 overflow-x-auto" role="tablist" aria-label="Filter orders">
            {FILTERS.map((f) => (
              <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}
                className={`press flex-none rounded-full border px-3.5 py-2 text-sm font-bold ${
                  filter === f.id ? "border-transparent bg-accent text-bg1" : "border-[var(--stroke)] text-muted"}`}>
                {f.label} <span className={filter === f.id ? "" : "text-ink"}>{counts[f.id]}</span>
              </button>
            ))}
          </div>
          {shown.length === 0 && (
            <p className="glass p-5 text-center text-muted">
              {filter === "all" ? "No orders in progress" : `No ${FILTERS.find((f) => f.id === filter).label.toLowerCase()} orders`}
            </p>
          )}
          {shown.map(card)}

          {done.length > 0 && (
            <>
              <button onClick={() => setShowDone((v) => !v)}
                className="press glass-strong mt-2 w-full rounded-xl px-4 py-3 text-left text-sm font-bold text-muted">
                {showDone ? "▾" : "▸"} Finished &amp; cancelled ({done.length})
              </button>
              {showDone && <div className="mt-3">{done.map(card)}</div>}
            </>
          )}
        </>
      )}

      {/* stays mounted on other tabs: its live data and a pending Undo survive a tab switch */}
      <MenuSection visible={tab === "menu"} filter={menuFilter} setFilter={setMenuFilter} />
      {tab === "reviews" && <FeedbackSection alwaysOpen />}

      <nav aria-label="Admin sections"
        className="fixed bottom-[calc(var(--sab)+0.75rem)] left-1/2 z-40 flex w-[calc(100%-1.5rem)] max-w-[496px] -translate-x-1/2 justify-around rounded-glass border border-[var(--stroke)] px-1 py-1.5 shadow-[0_10px_40px_rgba(0,0,0,0.45)] backdrop-blur-xl"
        style={{ background: "rgba(10, 20, 32, 0.85)" }}>
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} aria-current={tab === t.id ? "page" : undefined}
            className={`press relative flex min-h-[48px] flex-1 flex-col items-center justify-center rounded-xl text-xs font-bold ${
              tab === t.id ? "bg-[var(--glass-strong)] text-accent" : "text-muted"}`}>
            <span className="text-lg leading-none">{t.icon}</span>
            {t.label}
            {t.id === "orders" && counts.placed > 0 && (
              <span aria-label={`${counts.placed} new`}
                className="absolute right-[18%] top-1 min-w-[18px] rounded-full bg-danger px-1 text-[11px] font-black leading-[18px] text-bg1">
                {counts.placed}
              </span>
            )}
          </button>
        ))}
      </nav>

      {openOrder && <OrderDetail order={openOrder} now={now} setStatus={setStatus} onClose={closeDetail} />}
    </div>
  );
}
