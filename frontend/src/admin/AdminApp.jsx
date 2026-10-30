import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, getSession, getToken, logout } from "../api.js";
import { beep } from "../alerts.js";
import { isActive } from "../constants.js";
import { useSocket } from "../useSocket.js";
import FeedbackSection from "./FeedbackSection.jsx";
import MenuSection from "./MenuSection.jsx";
import OrderDetail, { StatusActions, ago, placedAt, sizeLabel } from "./OrderDetail.jsx";
import { disablePush, enablePush } from "../push.js";

function OrderCard({ order, now, setStatus, open }) {
  const cancelled = order.status === "cancelled";
  const count = order.items.reduce((n, i) => n + i.qty, 0);
  const summary = order.items.map((i) => `${i.name}${sizeLabel(i.size) ? ` (${sizeLabel(i.size)})` : ""} ×${i.qty}`).join(", ");
  return (
    <div role="button" tabIndex={0} aria-label={`Open order #${order.order_number}`}
      onClick={open} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && e.target === e.currentTarget && (e.preventDefault(), open())}
      className={`glass mb-3 cursor-pointer border-l-4 p-4 ${cancelled ? "opacity-50 !border-l-danger" : order.fresh ? "flash-new !border-l-danger" : "!border-l-accent"}`}>
      <div className="flex justify-between font-extrabold">
        <span>#{order.order_number} · {order.name || order.email}</span>
        <span className="text-accent2">₹{order.total}</span>
      </div>
      <div className="mt-0.5 text-xs text-muted">{placedAt(order)} · {ago(order, now)}</div>
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
  const now = useNow();
  const closeDetail = useCallback(() => setOpenId(null), []);

  useEffect(() => {
    if (!isAdmin) {
      navigate("/", { replace: true });
    }
  }, [isAdmin, navigate]);

  // Android app only: order alerts while the app is closed.
  // Tapping a "New order" notification opens that order.
  useEffect(() => { if (isAdmin) enablePush((data) => setOpenId(Number(data.order_id))); }, [isAdmin]);

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
    if (msg.type === "new_order") {
      beep();
      setOrders((os) => [{ ...msg.order, fresh: true }, ...os]);
    } else if (msg.type === "status") {  // e.g. the customer cancelled, or another admin device acted
      setOrders((os) => os.map((o) => (o.id === msg.order_id ? { ...o, status: msg.status, fresh: false } : o)));
    }
    api("/api/admin/stats/today").then(setStats).catch(() => {});
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
  const openOrder = orders.find((o) => o.id === openId);
  const card = (o) => <OrderCard key={o.id} order={o} now={now} setStatus={setStatus} open={() => setOpenId(o.id)} />;

  const handleLogout = () => {
    disablePush(); // not awaited: api() reads the session token synchronously, and a sleeping backend would freeze the button
    logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="screen-in px-3 pb-12">
      <header className="glass sticky top-[calc(var(--sat)+0.5rem)] z-40 mt-3 flex items-center justify-between px-4 py-3">
        <div className="text-lg font-black">RO-YAN <span className="text-accent">ADMIN</span></div>
        <button onClick={handleLogout}
          className="glass-strong press rounded-xl px-3 py-1.5 text-xs font-bold">Log out</button>
      </header>

      {offline && <p className="glass mt-4 p-3 text-center text-sm text-danger">Can't reach the server — retrying…</p>}

      {stats && (
        <div className="mt-4 grid grid-cols-3 gap-2.5">
          <div className="glass p-3 text-center"><b className="block text-2xl text-accent">{stats.orders}</b><small className="text-xs text-muted">Orders today</small></div>
          <div className="glass p-3 text-center"><b className="block text-2xl text-accent">₹{stats.revenue}</b><small className="text-xs text-muted">Revenue</small></div>
          <div className="glass p-3 text-center"><b className="block text-2xl text-accent">{stats.top_item || "—"}</b><small className="text-xs text-muted">Top item</small></div>
        </div>
      )}

      <h2 className="mb-2.5 mt-6 px-1 font-black text-accent">Order queue{active.length > 0 && ` (${active.length})`}</h2>
      {active.length === 0 && <p className="glass p-5 text-center text-muted">No orders in progress</p>}
      {active.map(card)}

      {done.length > 0 && (
        <>
          <button onClick={() => setShowDone((v) => !v)}
            className="press glass-strong mt-2 w-full rounded-xl px-4 py-3 text-left text-sm font-bold text-muted">
            {showDone ? "▾" : "▸"} Finished &amp; cancelled ({done.length})
          </button>
          {showDone && <div className="mt-3">{done.map(card)}</div>}
        </>
      )}

      <FeedbackSection />

      <MenuSection />

      {openOrder && <OrderDetail order={openOrder} now={now} setStatus={setStatus} onClose={closeDetail} />}
    </div>
  );
}
