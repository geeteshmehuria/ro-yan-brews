import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, getSession, getToken, logout } from "../api.js";
import { beep } from "../alerts.js";
import { ICONS, LABELS, STATUSES, isActive } from "../constants.js";
import { useSocket } from "../useSocket.js";

function OrderCard({ order, onStatus }) {
  const placed = new Date(order.created_at + "Z");
  // Order numbers restart daily, so an order left over from an earlier day shows its date too.
  const time = placed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
    (placed.toDateString() === new Date().toDateString() ? "" : ` · ${placed.toLocaleDateString([], { day: "numeric", month: "short" })}`);
  const setStatus = async (s) => {
    try {
      await api(`/api/admin/orders/${order.id}/status`, { method: "PATCH", body: { status: s } });
      onStatus(order.id, s);
    } catch (e) { alert(e.message); }
  };
  const cancelled = order.status === "cancelled";
  return (
    <div className={`glass mb-3 border-l-4 p-4 ${cancelled ? "opacity-50 !border-l-danger" : order.fresh ? "flash-new !border-l-danger" : "!border-l-accent"}`}>
      <div className="flex justify-between font-extrabold">
        <span>#{order.order_number} · {order.name || order.email}</span>
        <span className="text-accent2">₹{order.total}</span>
      </div>
      {order.name && <div className="text-xs text-muted">{order.email}</div>}
      <div className="my-2 text-sm text-muted">
        {order.items.map((i) => `${i.name}${i.size !== "na" ? ` (${i.size})` : ""} ×${i.qty}`).join(", ")}
        <span className="ml-2 text-xs">· {time}</span>
      </div>
      {order.note && <div className="mb-2 text-sm font-bold text-accent">📝 {order.note}</div>}
      {cancelled ? <div className="font-extrabold text-danger">Cancelled</div> : (
        <div className="flex flex-wrap gap-1.5">
          {STATUSES.map((s) => (
            <button key={s} onClick={() => setStatus(s)}
              className={`press rounded-lg border px-3 py-2 text-xs font-bold ${
                order.status === s ? "border-transparent bg-accent2 text-bg1" : "border-[var(--stroke)] text-muted"
              }`}>
              {LABELS[s]}
            </button>
          ))}
          {isActive(order) && order.status !== "ready" && (
            <button onClick={() => window.confirm("Cancel this order?") && setStatus("cancelled")}
              className="press rounded-lg border border-[var(--stroke)] px-3 py-2 text-xs font-bold text-danger">
              Cancel
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdminApp() {
  const navigate = useNavigate();
  const session = getSession();
  const isAdmin = !!session?.is_admin;

  const [orders, setOrders] = useState([]);
  const [menu, setMenu] = useState([]);
  const [stats, setStats] = useState(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    if (!isAdmin) {
      navigate("/", { replace: true });
    }
  }, [isAdmin, navigate]);

  const load = useCallback(async () => {
    const [o, m, s] = await Promise.all([
      api("/api/admin/orders"), api("/api/menu"), api("/api/admin/stats/today"),
    ]);
    setOrders(o); setMenu(m); setStats(s);
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

  const handleLogout = () => {
    logout();
    navigate("/", { replace: true });
  };

  const toggleStock = async (item) => {
    const r = await api(`/api/admin/menu/${item.id}/availability`, {
      method: "PATCH", body: { is_available: !item.is_available },
    });
    setMenu((m) => m.map((g) => ({
      ...g,
      items: g.items.map((i) => (i.id === item.id ? { ...i, is_available: r.is_available } : i)),
    })));
  };

  return (
    <div className="screen-in px-3 pb-12">
      <header className="glass sticky top-2 z-40 mt-3 flex items-center justify-between px-4 py-3">
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

      <h2 className="mb-2.5 mt-6 px-1 font-black text-accent">Order queue</h2>
      {orders.length === 0 && <p className="glass p-5 text-center text-muted">No orders yet today</p>}
      {orders.map((o) => (
        <OrderCard key={o.id} order={o}
          onStatus={(id, s) => setOrders((os) => os.map((x) => (x.id === id ? { ...x, status: s, fresh: false } : x)))} />
      ))}

      <h2 className="mb-2.5 mt-6 px-1 font-black text-accent">Menu stock</h2>
      {menu.map((g) => g.items.map((item) => (
        <div key={item.id} className="glass mb-2.5 flex items-center justify-between p-3.5">
          <div><b>{item.name}</b><br /><small className="text-muted">{ICONS[g.category]} {g.category}</small></div>
          <button onClick={() => toggleStock(item)}
            className={`relative h-7 w-[52px] rounded-full border transition-colors ${
              item.is_available ? "border-transparent bg-accent2" : "glass-strong border-[var(--stroke)]"
            }`}>
            <span className={`absolute top-[3px] h-5 w-5 rounded-full bg-white transition-all ${item.is_available ? "left-[27px]" : "left-[3px]"}`} />
          </button>
        </div>
      )))}
    </div>
  );
}
