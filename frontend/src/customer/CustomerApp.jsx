import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, getSession, logout, WS_BASE } from "../api.js";
import { CartScreen, DoneScreen, Login } from "./Checkout.jsx";
import MenuScreen from "./Menu.jsx";

const CART_KEY = "royan_cart";

export default function CustomerApp() {
  // Log in first: only a valid session opens the menu.
  const [screen, setScreen] = useState(() => (getSession() ? "menu" : "login"));
  const [menu, setMenu] = useState(null); // null = loading
  const [error, setError] = useState("");
  const [cart, setCart] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; } catch { return {}; }
  });
  const [sizes, setSizes] = useState({}); // itemId -> "half" | "full"
  const [order, setOrder] = useState(null);
  const wsRef = useRef(null);

  // If the owner logs in, send them straight to the admin dashboard.
  useEffect(() => {
    if (getSession()?.is_admin) window.location.href = "/admin";
  }, [screen]);

  // cart survives refresh
  useEffect(() => { localStorage.setItem(CART_KEY, JSON.stringify(cart)); }, [cart]);

  const loadMenu = useCallback(async () => {
    try { setMenu(await api("/api/menu")); setError(""); }
    catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { if (screen !== "login") loadMenu(); }, [loadMenu, screen]);

  // live stock updates
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/menu`);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "availability") {
        setMenu((m) => m && m.map((g) => ({
          ...g,
          items: g.items.map((i) =>
            i.id === msg.item_id ? { ...i, is_available: msg.is_available } : i),
        })));
      }
    };
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  const sizeOf = (item) => sizes[item.id] || (item.price_half != null ? "half" : "na");
  const priceOf = (item, size) => (size === "half" ? item.price_half : item.price_full);

  const changeQty = (item, delta) => {
    const size = sizeOf(item);
    const key = `${item.id}_${size}`;
    setCart((c) => {
      const line = c[key] || { id: item.id, name: item.name, size, hasHalf: item.price_half != null, price: priceOf(item, size), qty: 0 };
      const qty = line.qty + delta;
      const next = { ...c };
      if (qty <= 0) delete next[key];
      else next[key] = { ...line, qty };
      return next;
    });
  };

  const totals = useMemo(() => {
    const lines = Object.values(cart);
    return {
      lines,
      count: lines.reduce((n, l) => n + l.qty, 0),
      total: lines.reduce((t, l) => t + l.qty * l.price, 0),
    };
  }, [cart]);

  const onLoggedIn = ({ is_admin }) => {
    if (is_admin) window.location.href = "/admin";
    else setScreen("menu");
  };

  // Already authenticated by this point — just place the order.
  const placeOrder = async () => {
    const items = totals.lines.map((l) => ({ menu_item_id: l.id, size: l.size === "na" ? "na" : l.size, qty: l.qty }));
    try {
      const placed = await api("/api/orders", { method: "POST", body: { items } });
      setOrder(placed);
      setCart({});
      setScreen("done");
    } catch (e) {
      if (e.status === 401) { logout(); setScreen("login"); }  // session lapsed
      else throw e;
    }
  };

  const reset = () => { setOrder(null); setScreen("menu"); loadMenu(); };

  return (
    <>
      {screen === "login" && <Login onDone={onLoggedIn} />}
      {screen === "menu" && (
        <MenuScreen menu={menu} error={error} retry={loadMenu} cart={cart} totals={totals}
          sizeOf={sizeOf} setSizes={setSizes} changeQty={changeQty}
          openCart={() => setScreen("cart")} />
      )}
      {screen === "cart" && (
        <CartScreen totals={totals} back={() => setScreen("menu")} placeOrder={placeOrder} />
      )}
      {screen === "done" && <DoneScreen order={order} reset={reset} />}
    </>
  );
}
