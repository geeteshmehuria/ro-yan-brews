import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, getSession, getToken, logout } from "../services/api.js";
import { beep } from "../utils/alerts.js";
import { useBackButton } from "../hooks/backButton.js";
import { MUTE_KEY, isActive } from "../config/constants.js";
import { useSocket } from "../hooks/useSocket.js";
import { useNow } from "../hooks/useNow.js";
import { pickupLabel } from "../utils/pickup.js";
import { FoodBackground, Logo } from "../components/ui.jsx";
import { BellIcon, ChartIcon, ClockIcon, ListIcon, NoteIcon, ReceiptIcon, StarIcon } from "../components/icons.jsx";
import StallPhone from "./StallPhone.jsx";
import FeedbackSection from "./FeedbackSection.jsx";
import MenuSection from "./MenuSection.jsx";
import TodaySection from "./TodaySection.jsx";
import OrderDetail, { StatusActions, ago, placedAt, sizeLabel } from "./OrderDetail.jsx";
import { disablePush, enablePush } from "../services/push.js";
import { ask, tell } from "../components/dialog.jsx";

// Orders not yet ready turn amber after 10 minutes and red after 20 — or, when the customer said
// they're coming later than that, amber at their arrival time and red 10 minutes after it.
const WAIT_AMBER = 10, WAIT_RED = 20;
const waitLevel = (order, now) => {
  if (order.status !== "placed" && order.status !== "preparing") return null;
  const mins = (now - new Date(order.created_at + "Z")) / 60000;
  const due = order.pickup_minutes || 0;
  return mins >= Math.max(WAIT_RED, due + 10) ? "red" : mins >= Math.max(WAIT_AMBER, due) ? "amber" : null;
};

function OrderCard({ order, now, setStatus, open }) {
  const cancelled = order.status === "cancelled";
  const uncollected = order.status === "not_collected";
  const wait = waitLevel(order, now);
  const count = order.items.reduce((n, i) => n + i.qty, 0);
  const summary = order.items.map((i) => `${i.name}${sizeLabel(i.size) ? ` (${sizeLabel(i.size)})` : ""} ×${i.qty}`).join(", ");
  return (
    <div role="button" tabIndex={0} aria-label={`Open order #${order.order_number}`}
      onClick={open} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && e.target === e.currentTarget && (e.preventDefault(), open())}
      className={`cursor-pointer rounded-[18px] border border-l-4 bg-[var(--card)] p-4 ${
        cancelled ? "border-[var(--stroke)] opacity-50 !border-l-danger" : uncollected ? "border-[var(--stroke)] opacity-60 !border-l-warn"
        : order.fresh ? "flash-new border-danger !border-l-danger shadow-[0_0_0_3px_var(--danger-soft)]"
        : wait === "red" ? "border-[var(--stroke)] !border-l-danger" : wait === "amber" ? "border-[var(--stroke)] !border-l-warn" : "border-[var(--stroke)] !border-l-accent"}`}>
      <div className="flex items-center gap-2">
        <b className="font-display text-2xl leading-none text-accent">#{order.order_number}</b>
        <b className="min-w-0 truncate">{order.name || order.email}</b>
        <span className={`ml-auto flex-none rounded-full px-2.5 py-0.5 text-xs font-extrabold ${
          wait === "red" ? "bg-danger-soft text-danger" : wait === "amber" ? "bg-warn-soft text-warn" : "bg-[var(--glass-strong)] text-muted"}`}>
          {ago(order, now)}
        </span>
      </div>
      <div className="mt-1 text-xs text-muted">{placedAt(order)}</div>
      <div className="my-2 text-sm">
        <b>{count} {count === 1 ? "item" : "items"}</b> <span className="text-muted">· {summary}</span>
      </div>
      {order.note && (
        <div className="mb-2 flex items-center gap-1.5 truncate rounded-lg bg-[var(--accent-ring)] px-2.5 py-1.5 text-sm font-bold text-accent">
          <NoteIcon className="h-4 w-4 flex-none" /> <span className="truncate">{order.note}</span>
        </div>
      )}
      <div className="mb-2.5 flex items-center justify-between gap-2 text-sm">
        {isActive(order) && pickupLabel(order)
          ? <span className="flex items-center gap-1.5 font-bold text-accent2"><ClockIcon className="h-4 w-4" /> {pickupLabel(order)}</span>
          : <span />}
        <b className="font-display text-xl leading-none text-accent2">₹{order.total}</b>
      </div>
      {/* buttons act on the order; they must not also open the detail panel */}
      <div onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <StatusActions order={order} setStatus={setStatus} />
      </div>
      <div className="mt-2 text-right text-xs font-bold text-accent">Tap for details ›</div>
    </div>
  );
}

const TABS = [
  { id: "orders", label: "Orders", Icon: ReceiptIcon },
  { id: "menu", label: "Menu", Icon: ListIcon },
  { id: "today", label: "Today", Icon: ChartIcon },
  { id: "reviews", label: "Reviews", Icon: StarIcon },
];

// The three kitchen columns shown side by side on wide screens.
const COLUMNS = [
  { id: "placed", label: "New", dot: "bg-danger", box: "border-danger-soft bg-[var(--glass)]" },
  { id: "preparing", label: "Preparing", dot: "bg-accent", box: "border-[var(--accent-ring)] bg-[var(--glass)]" },
  { id: "ready", label: "Ready", dot: "bg-accent2", box: "border-[var(--accent2-soft)] bg-[var(--glass)]" },
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
  const [phone, setPhone] = useState(null); // the stall's number customers can call (null = none set)
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
    const [o, s, store] = await Promise.all([api("/api/admin/orders"), api("/api/admin/stats/today"), api("/api/store")]);
    setOrders(o); setStats(s); setPhone(store.phone ?? null);
  }, []);

  // Only a rejected session logs the owner out. A network error or a 502 while the
  // free-tier backend wakes up just retries.
  // Used at start and after every socket reconnect — including the one call useSocket makes when
  // /ws/admin closes with 4401 (login expired) and stops reconnecting, so that refetch must keep
  // retrying until it either works or gets the 401 that logs out; a dead feed must never stay up.
  const retry = useRef();
  const alive = useRef(true);
  const sync = useCallback(() => load().then(() => setOffline(false)).catch((e) => {
    if (!alive.current) return;
    if (e.status === 401 || e.status === 403) {
      logout();
      navigate("/", { replace: true });
      return;
    }
    setOffline(true);
    clearTimeout(retry.current);
    retry.current = setTimeout(sync, 5000);
  }), [load, navigate]);
  useEffect(() => {
    if (!isAdmin) return;
    alive.current = true;
    sync();
    return () => { alive.current = false; clearTimeout(retry.current); };
  }, [isAdmin, sync]);

  // Live alerts. After a reconnect, reload so nothing placed while offline is missed.
  useSocket(isAdmin && `/ws/admin?token=${encodeURIComponent(getToken())}`, (msg) => {
    if (msg.type === "store") {  // paused / reopened / phone changed from another device
      setStats((st) => st && { ...st, accepting_orders: msg.accepting_orders });
      setPhone(msg.phone ?? null);
      return;
    }
    if (msg.type === "new_order") {
      if (!mutedRef.current) beep();
      setOrders((os) => [{ ...msg.order, fresh: true }, ...os]);
    } else if (msg.type === "status") {  // e.g. the customer cancelled, or another admin device acted
      setOrders((os) => os.map((o) => (o.id === msg.order_id ? { ...o, status: msg.status, fresh: false } : o)));
    }
    refreshStats();
  }, sync);

  if (!isAdmin) return null;

  const setStatus = async (order, status) => {
    try {
      await api(`/api/admin/orders/${order.id}/status`, { method: "PATCH", body: { status } });
      setOrders((os) => os.map((o) => (o.id === order.id ? { ...o, status, fresh: false } : o)));
    } catch (e) { tell(e.message); }
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
    if (accepting && !await ask({ title: "Pause new orders?",
      message: "Customers will see “We're not taking orders right now”. Orders already placed carry on.",
      confirmLabel: "Pause orders", cancelLabel: "Keep open", tone: "warn" })) return;
    setStoreBusy(true);
    try {
      const r = await api("/api/admin/store", { method: "PATCH", body: { accepting_orders: !accepting } });
      setStats((st) => st && { ...st, accepting_orders: r.accepting_orders });
    } catch (e) { tell(e.message); }
    setStoreBusy(false);
  };

  const showOutOfStock = () => { setMenuFilter("out"); setTab("menu"); };
  const card = (o) => <OrderCard key={o.id} order={o} now={now} setStatus={setStatus} open={() => setOpenId(o.id)} />;

  const handleLogout = async () => {
    if (!await ask({ title: "Log out?",
      message: "This phone stops getting new-order alerts until you log in again with the owner email.",
      confirmLabel: "Log out", cancelLabel: "Stay logged in", tone: "danger" })) return;
    disablePush(); // not awaited: api() reads the session token synchronously, and a sleeping backend would freeze the button
    logout();
    navigate("/", { replace: true });
  };

  const muteButton = (extra = "") => (
    <button onClick={toggleMute} aria-label={muted ? "Turn new-order sound on" : "Mute new-order sound"} aria-pressed={muted}
      className={`press flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-[var(--glass-strong)] ${muted ? "text-muted" : "text-ink"} ${extra}`}>
      <BellIcon off={muted} />
    </button>
  );
  const brand = (
    <div className="flex items-center gap-2.5">
      <Logo className="h-9 w-9 !rounded-xl md:h-10 md:w-10" />
      <span className="font-display text-lg font-extrabold leading-none md:text-xl">
        Mr. MOMO<br /><span className="font-body text-[10px] font-bold tracking-[2px] text-accent md:text-[11px]">OWNER</span>
      </span>
    </div>
  );
  const tabLabel = TABS.find((t) => t.id === tab).label;
  const column = (c) => {
    const list = active.filter((o) => o.status === c.id);
    return (
      <section key={c.id} aria-label={c.label} className={`flex flex-col gap-2.5 rounded-[22px] border p-2.5 ${c.box}`}>
        <h3 className="flex items-center gap-2 px-1.5 pt-1 font-bold">
          <span className={`h-2.5 w-2.5 rounded-full ${c.dot}`} />{c.label}
          <span className="ml-auto text-muted">{list.length}</span>
        </h3>
        {list.length ? list.map(card) : <p className="px-1.5 pb-2 text-sm text-muted">Nothing here</p>}
      </section>
    );
  };

  return (
    <div className="admin-wide screen-in px-3 pb-[calc(var(--sab)+6rem)] font-body md:flex md:items-start md:gap-5 md:pb-10 md:pt-4">
      <FoodBackground />

      {/* desktop / tablet: sidebar instead of the bottom tab bar */}
      <aside className="sticky top-[calc(var(--sat)+1rem)] hidden w-[210px] flex-none flex-col gap-1.5 rounded-[24px] border border-[var(--stroke)] bg-bar p-3.5 backdrop-blur-xl md:flex">
        <div className="px-1.5 pb-4 pt-1">{brand}</div>
        <nav aria-label="Admin sections" className="flex flex-col gap-1">
          {TABS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setTab(id)} aria-current={tab === id ? "page" : undefined}
              className={`press flex items-center gap-3 rounded-2xl px-3.5 py-3 text-left font-bold ${
                tab === id ? "bg-accent text-bg1" : "text-muted hover:bg-[var(--glass)]"}`}>
              <Icon className="h-5 w-5" />{label}
              {id === "orders" && counts.placed > 0 && (
                <span aria-label={`${counts.placed} new`}
                  className={`ml-auto min-w-[22px] rounded-full px-1.5 text-center text-xs font-extrabold leading-[22px] ${tab === id ? "bg-bg1 text-accent" : "bg-danger text-bg1"}`}>
                  {counts.placed}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="mt-5 flex gap-2">
          {muteButton("h-11 w-11")}
          <button onClick={handleLogout}
            className="press h-11 flex-1 rounded-xl border border-[var(--stroke)] text-sm font-bold">Log out</button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
      <header className="sticky top-[calc(var(--sat)+0.5rem)] z-40 mt-3 flex items-center justify-between gap-2 rounded-[20px] border border-[var(--stroke)] bg-bar px-3 py-2.5 backdrop-blur-xl md:hidden">
        {brand}
        <div className="flex items-center gap-2">
          {muteButton()}
          <button onClick={handleLogout}
            className="press h-10 rounded-xl bg-[var(--glass-strong)] px-3 text-[13px] font-bold">Log out</button>
        </div>
      </header>

      <div className="hidden md:block">
        <p className="text-sm text-muted">{new Date(now).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" })}</p>
        <h1 className="font-display text-4xl font-extrabold leading-tight">{tab === "orders" ? "Order queue" : tabLabel}</h1>
      </div>

      {offline && <p className="glass mt-4 p-3 text-center text-sm text-danger">Can't reach the server — retrying…</p>}

      {tab === "orders" && (
        <>
          {stats && (
            <button onClick={toggleStore} disabled={storeBusy} role="switch" aria-checked={accepting}
              aria-label={accepting ? "Taking orders — tap to pause" : "Orders paused — tap to open"}
              className={`press mt-4 flex w-full items-center justify-between gap-3 rounded-2xl border p-3.5 text-left ${
                accepting ? "border-[var(--accent2-soft)] bg-[var(--accent2-tint)]" : "border-danger bg-danger-soft"}`}>
              <span>
                <b className={accepting ? "text-accent2" : "text-danger"}>
                  {accepting ? "Taking orders" : "⏸ Orders paused"}
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

          {stats && <StallPhone phone={phone} onSaved={setPhone} />}

          {stats && (
            <div className="mt-3 grid grid-cols-3 gap-2.5 md:gap-3">
              <div className="rounded-2xl border border-[var(--accent2-soft)] bg-[var(--accent2-tint)] p-3 text-center md:p-4 md:text-left">
                <b className="block font-display text-[22px] leading-tight text-accent2 md:text-3xl">₹{stats.cash_collected}</b><small className="text-xs text-muted md:text-[13px]">Cash collected</small>
              </div>
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--glass)] p-3 text-center md:p-4 md:text-left">
                <b className="block font-display text-[22px] leading-tight text-accent md:text-3xl">{stats.orders}</b><small className="text-xs text-muted md:text-[13px]">Orders today</small>
              </div>
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--glass)] p-3 text-center md:p-4 md:text-left">
                <b className="block font-display text-[22px] leading-tight text-accent md:text-3xl">₹{stats.to_collect ?? 0}</b><small className="text-xs text-muted md:text-[13px]">Still to collect</small>
              </div>
            </div>
          )}

          {stats?.out_of_stock > 0 && (
            <button onClick={showOutOfStock}
              className="press mt-3 flex w-full items-center justify-between rounded-2xl border border-warn bg-warn-soft px-4 py-3 text-left text-sm font-bold">
              <span>⚠ {stats.out_of_stock} {stats.out_of_stock === 1 ? "item is" : "items are"} out of stock</span>
              <span className="text-accent">Menu ›</span>
            </button>
          )}

          {/* wide screens: New / Preparing / Ready side by side */}
          <div className="mt-5 hidden items-start gap-3.5 lg:grid lg:grid-cols-3">{COLUMNS.map(column)}</div>

          <div className="lg:hidden">
          <h2 className="mb-2 mt-5 px-1 font-display text-xl font-extrabold">Order queue</h2>
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
          <div className="flex flex-col gap-3">{shown.map(card)}</div>
          </div>

          {done.length > 0 && (
            <>
              <button onClick={() => setShowDone((v) => !v)}
                className="press glass-strong mt-3 w-full rounded-xl px-4 py-3 text-left text-sm font-bold text-muted">
                {showDone ? "▾" : "▸"} Finished, cancelled &amp; not collected ({done.length})
              </button>
              {showDone && <div className="mt-3 flex flex-col gap-3 lg:grid lg:grid-cols-3 lg:items-start">{done.map(card)}</div>}
            </>
          )}
        </>
      )}

      {/* stays mounted on other tabs: its live data and a pending Undo survive a tab switch */}
      <MenuSection visible={tab === "menu"} filter={menuFilter} setFilter={setMenuFilter} />
      {tab === "today" && <TodaySection />}
      {tab === "reviews" && <FeedbackSection alwaysOpen />}
      </div>

      <nav aria-label="Admin sections"
        className="fixed bottom-[calc(var(--sab)+0.75rem)] left-1/2 z-40 flex w-[calc(100%-1.5rem)] max-w-[496px] -translate-x-1/2 justify-around gap-1 rounded-[20px] border border-[var(--stroke)] bg-bar p-1.5 shadow-float backdrop-blur-xl md:hidden">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} aria-current={tab === t.id ? "page" : undefined}
            className={`press relative flex min-h-[52px] flex-1 flex-col items-center justify-center gap-0.5 rounded-2xl text-xs font-bold ${
              tab === t.id ? "bg-accent text-bg1" : "text-muted"}`}>
            <t.Icon className="h-5 w-5" />
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
