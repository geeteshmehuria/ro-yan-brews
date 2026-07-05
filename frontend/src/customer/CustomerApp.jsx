import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, WS_BASE } from "../api.js";
import { CartScreen, DoneScreen, OtpScreen, PhoneScreen } from "./Checkout.jsx";
import MenuScreen from "./Menu.jsx";

const CART_KEY = "royan_cart";

export default function CustomerApp() {
  const [screen, setScreen] = useState("menu"); // menu | cart | phone | otp | done
  const [menu, setMenu] = useState(null); // null = loading
  const [error, setError] = useState("");
  const [cart, setCart] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; } catch { return {}; }
  });
  const [sizes, setSizes] = useState({}); // itemId -> "half" | "full"
  const [phone, setPhone] = useState("");
  const [order, setOrder] = useState(null);
  const wsRef = useRef(null);

  // cart survives refresh
  useEffect(() => { localStorage.setItem(CART_KEY, JSON.stringify(cart)); }, [cart]);

  const loadMenu = useCallback(async () => {
    try { setMenu(await api("/api/menu")); setError(""); }
    catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { loadMenu(); }, [loadMenu]);

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

  const placeOrder = async (otpCode) => {
    await api("/api/otp/verify", { method: "POST", body: { phone, code: otpCode } })
      .then((r) => localStorage.setItem("session_token", r.token));
    const items = totals.lines.map((l) => ({ menu_item_id: l.id, size: l.size === "na" ? "na" : l.size, qty: l.qty }));
    const placed = await api("/api/orders", { method: "POST", body: { items } });
    setOrder(placed);
    setCart({});
    setScreen("done");
  };

  const reset = () => { setOrder(null); setPhone(""); setScreen("menu"); loadMenu(); };

  return (
    <>
      {screen === "menu" && (
        <MenuScreen menu={menu} error={error} retry={loadMenu} cart={cart} totals={totals}
          sizeOf={sizeOf} setSizes={setSizes} changeQty={changeQty}
          openCart={() => setScreen("cart")} />
      )}
      {screen === "cart" && (
        <CartScreen totals={totals} back={() => setScreen("menu")} next={() => setScreen("phone")} />
      )}
      {screen === "phone" && (
        <PhoneScreen phone={phone} setPhone={setPhone} back={() => setScreen("cart")}
          next={() => setScreen("otp")} />
      )}
      {screen === "otp" && (
        <OtpScreen phone={phone} back={() => setScreen("phone")} placeOrder={placeOrder} />
      )}
      {screen === "done" && <DoneScreen order={order} reset={reset} />}
    </>
  );
}
