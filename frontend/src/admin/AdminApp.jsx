import { useCallback, useEffect, useRef, useState } from "react";

import { api, getSession, getToken, logout, WS_BASE } from "../api.js";
import { Login } from "../customer/Checkout.jsx";

const STATUSES = ["placed", "preparing", "ready", "completed"];
const LABELS = { placed: "Placed", preparing: "Preparing", ready: "Ready", completed: "Completed" };
const ICONS = { Shakes: "🥤", Burgers: "🍔", Sandwiches: "🥪", Momos: "🥟", Fries: "🍟" };

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator(); const g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.frequency.value = 880; g.gain.value = 0.15;
    o.start(); setTimeout(() => { o.stop(); ctx.close(); }, 350);
  } catch { /* sound is best-effort */ }
}

function AdminGate({ onOk }) {
  const [err, setErr] = useState("");
  return (
    <div>
      <h2 className="screen-in pt-12 text-center text-xl font-black">Owner login</h2>
      {err && <p className="px-3 text-center text-sm text-danger">{err}</p>}
      <Login cta="Enter dashboard" onDone={({ is_admin }) => {
        if (is_admin) onOk();
        else { logout(); setErr("That email isn't the owner account."); }
      }} />
    </div>
  );
}

function OrderCard({ order, onStatus }) {
  const time = new Date(order.created_at + "Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const setStatus = async (s) => {
    try {
      await api(`/api/admin/orders/${order.id}/status`, { method: "PATCH", body: { status: s } });
      onStatus(order.id, s);
    } catch (e) { alert(e.message); }
  };
  return (
    <div className={`glass mb-3 border-l-4 p-4 ${order.fresh ? "flash-new !border-l-danger" : "!border-l-accent"}`}>
      <div className="flex justify-between font-extrabold">
        <span>#{order.order_number} · {order.email_masked}</span>
        <span className="text-accent2">₹{order.total}</span>
      </div>
      <div className="my-2 text-sm text-muted">
        {order.items.map((i) => `${i.name}${i.size !== "na" ? ` (${i.size})` : ""} ×${i.qty}`).join(", ")}
        <span className="ml-2 text-xs">· {time}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {STATUSES.map((s) => (
          <button key={s} onClick={() => setStatus(s)}
            className={`press rounded-lg border px-3 py-2 text-xs font-bold ${
              order.status === s ? "border-transparent bg-accent2 text-bg1" : "border-[var(--stroke)] text-muted"
            }`}>
            {LABELS[s]}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function AdminApp() {
  const [authed, setAuthed] = useState(() => !!getSession()?.is_admin);
  const [orders, setOrders] = useState([]);
  const [menu, setMenu] = useState([]);
  const [stats, setStats] = useState(null);
  const wsRef = useRef(null);

  const load = useCallback(async () => {
    const [o, m, s] = await Promise.all([
      api("/api/admin/orders"), api("/api/menu"), api("/api/admin/stats/today"),
    ]);
    setOrders(o); setMenu(m); setStats(s);
  }, []);

  useEffect(() => {
    if (!authed) return;
    load().catch(() => { logout(); setAuthed(false); });
    const ws = new WebSocket(`${WS_BASE}/ws/admin?token=${encodeURIComponent(getToken())}`);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "new_order") {
        beep();
        setOrders((os) => [{ ...msg.order, fresh: true }, ...os]);
        load().catch(() => {});
      }
    };
    wsRef.current = ws;
    return () => ws.close();
  }, [authed, load]);

  if (!authed) return <AdminGate onOk={() => setAuthed(true)} />;

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
        <button onClick={() => { logout(); setAuthed(false); }}
          className="glass-strong press rounded-xl px-3 py-1.5 text-xs font-bold">Log out</button>
      </header>

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
