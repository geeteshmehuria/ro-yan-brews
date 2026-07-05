import { useCallback, useEffect, useRef, useState } from "react";

import { api, WS_BASE } from "../api.js";

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

function PinGate({ onOk }) {
  const [pin, setPin] = useState("");
  const [err, setErr] = useState("");
  const submit = async () => {
    try {
      await api("/api/admin/stats/today", { headers: { "x-admin-pin": pin } });
      sessionStorage.setItem("admin_pin", pin);
      onOk(pin);
    } catch { setErr("Wrong PIN"); }
  };
  return (
    <main className="screen-in px-3 py-16 text-center">
      <h2 className="text-xl font-black">Admin PIN</h2>
      <input type="password" inputMode="numeric" value={pin}
        onChange={(e) => setPin(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        className="glass mx-auto my-4 block w-56 p-4 text-center text-2xl tracking-[6px] text-ink focus:border-accent focus:outline-none" />
      {err && <p className="text-danger">{err}</p>}
      <button onClick={submit} className="press mt-2 rounded-glass bg-accent px-10 py-3.5 font-black text-bg1">Enter</button>
    </main>
  );
}

function OrderCard({ order, pin, onStatus }) {
  const time = new Date(order.created_at + "Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const setStatus = async (s) => {
    try {
      await api(`/api/admin/orders/${order.id}/status`, {
        method: "PATCH", body: { status: s }, headers: { "x-admin-pin": pin },
      });
      onStatus(order.id, s);
    } catch (e) { alert(e.message); }
  };
  return (
    <div className={`glass mb-3 border-l-4 p-4 ${order.fresh ? "flash-new !border-l-danger" : "!border-l-accent"}`}>
      <div className="flex justify-between font-extrabold">
        <span>#{order.order_number} · {order.phone_masked}</span>
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
  const [pin, setPin] = useState(() => sessionStorage.getItem("admin_pin") || "");
  const [orders, setOrders] = useState([]);
  const [menu, setMenu] = useState([]);
  const [stats, setStats] = useState(null);
  const wsRef = useRef(null);

  const load = useCallback(async (p) => {
    const h = { headers: { "x-admin-pin": p } };
    const [o, m, s] = await Promise.all([
      api("/api/admin/orders", h), api("/api/menu"), api("/api/admin/stats/today", h),
    ]);
    setOrders(o); setMenu(m); setStats(s);
  }, []);

  useEffect(() => {
    if (!pin) return;
    load(pin).catch(() => { sessionStorage.removeItem("admin_pin"); setPin(""); });
    const ws = new WebSocket(`${WS_BASE}/ws/admin?pin=${encodeURIComponent(pin)}`);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "new_order") {
        beep();
        setOrders((os) => [{ ...msg.order, fresh: true }, ...os]);
        load(pin).catch(() => {});
      }
    };
    wsRef.current = ws;
    return () => ws.close();
  }, [pin, load]);

  if (!pin) return <PinGate onOk={setPin} />;

  const toggleStock = async (item) => {
    const r = await api(`/api/admin/menu/${item.id}/availability`, {
      method: "PATCH", body: { is_available: !item.is_available }, headers: { "x-admin-pin": pin },
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
        <button onClick={() => { sessionStorage.removeItem("admin_pin"); setPin(""); }}
          className="glass-strong press rounded-xl px-3 py-1.5 text-xs font-bold">Lock</button>
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
        <OrderCard key={o.id} order={o} pin={pin}
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
