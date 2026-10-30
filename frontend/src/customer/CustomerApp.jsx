import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, getSession, getToken, logout } from "../api.js";
import { beep, flashTitle } from "../alerts.js";
import { CART_KEY, isActive } from "../constants.js";
import { useSocket } from "../useSocket.js";
import { CartScreen } from "./Checkout.jsx";
import { Login } from "./Login.jsx";
import MenuScreen from "./Menu.jsx";
import OrdersScreen from "./Orders.jsx";
import ProfileScreen from "./Profile.jsx";

const priceOf = (item, size) => (size === "half" ? item.price_half : item.price_full);

// Re-price saved cart lines against the fresh menu; drop items that no longer exist.
function reconcile(cart, menu) {
  const items = Object.fromEntries(menu.flatMap((g) => g.items).map((i) => [i.id, i]));
  const next = {};
  for (const [key, line] of Object.entries(cart)) {
    const item = items[line.id];
    const price = item && priceOf(item, line.size);
    if (price != null) next[key] = { ...line, price, hasHalf: item.price_half != null };
  }
  return next;
}

export default function CustomerApp() {
  const navigate = useNavigate();
  // Log in first: only a valid session opens the menu.
  const [screen, setScreen] = useState(() => (getSession() ? "menu" : "login"));
  const [menu, setMenu] = useState(null); // null = loading
  const [error, setError] = useState("");
  const [cart, setCart] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; } catch { return {}; }
  });
  const [sizes, setSizes] = useState({}); // itemId -> "half" | "full"
  const [orders, setOrders] = useState([]); // this customer's recent orders, newest first
  const [me, setMe] = useState(null); // { email, name }
  const loggedIn = screen !== "login";
  const ordersRef = useRef(orders);
  ordersRef.current = orders;

  // If the owner logs in, send them straight to the admin dashboard.
  useEffect(() => {
    if (getSession()?.is_admin) navigate("/admin", { replace: true });
  }, [screen, navigate]);

  // cart survives refresh
  useEffect(() => { localStorage.setItem(CART_KEY, JSON.stringify(cart)); }, [cart]);

  const loadMenu = useCallback(async () => {
    try {
      const fresh = await api("/api/menu");
      setMenu(fresh);
      setCart((c) => reconcile(c, fresh));
      setError("");
    } catch (e) { setError(e.message); }
  }, []);

  const signOut = useCallback(() => {
    logout();
    setCart({}); setOrders([]); setMe(null);
    setScreen("login");
  }, []);

  // An expired or rejected session goes back to login instead of leaving a half-empty screen.
  const onAuthError = useCallback((e) => { if (e.status === 401) signOut(); }, [signOut]);

  const loadOrders = useCallback(
    () => api("/api/orders/mine").then(setOrders).catch(onAuthError), [onAuthError]);

  useEffect(() => {
    if (!loggedIn) return;
    loadMenu();
    loadOrders();
    api("/api/me").then(setMe).catch(onAuthError);
  }, [loggedIn, loadMenu, loadOrders, onAuthError]);

  // live stock updates (only once logged in)
  useSocket(loggedIn ? "/ws/menu" : null, (msg) => {
    if (msg.type !== "availability") return;
    setMenu((m) => m && m.map((g) => ({
      ...g,
      items: g.items.map((i) => (i.id === msg.item_id ? { ...i, is_available: msg.is_available } : i)),
    })));
  }, loadMenu);

  // live status of all my orders — on any screen, so ordering again never hides the last one
  useSocket(loggedIn ? `/ws/me?token=${encodeURIComponent(getToken())}` : null, (msg) => {
    if (msg.type !== "status") return;
    setOrders((os) => os.map((o) => (o.id === msg.order_id ? { ...o, status: msg.status } : o)));
    if (msg.status === "ready") {
      const order = ordersRef.current.find((o) => o.id === msg.order_id);
      navigator.vibrate?.([200, 100, 200]);
      beep();
      flashTitle(`Order #${order?.order_number ?? ""} is ready!`);
    }
  }, loadOrders);

  const sizeOf = (item) => sizes[item.id] || (item.price_half != null ? "half" : "na");

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
    if (is_admin) navigate("/admin", { replace: true });
    else setScreen("menu");
  };

  // Already authenticated by this point — just place the order.
  const placeOrder = async (note) => {
    const items = totals.lines.map((l) => ({ menu_item_id: l.id, size: l.size, qty: l.qty }));
    try {
      const placed = await api("/api/orders", { method: "POST", body: { items, note } });
      setOrders((os) => [placed, ...os]);
      setCart({});
      setScreen("orders");
    } catch (e) {
      if (e.status === 401) signOut();  // session lapsed
      else throw e;
    }
  };

  const cancelOrder = async (id) => {
    try {
      await api(`/api/orders/${id}/cancel`, { method: "POST" });
    } catch (e) { alert(e.message); }
    loadOrders();  // the server is the source of truth either way
  };

  return (
    <>
      {screen === "login" && <Login onDone={onLoggedIn} />}
      {screen === "menu" && (
        <MenuScreen menu={menu} error={error} retry={loadMenu} cart={cart} totals={totals}
          sizeOf={sizeOf} setSizes={setSizes} changeQty={changeQty}
          activeOrders={orders.filter(isActive)} openOrders={() => setScreen("orders")}
          openProfile={() => setScreen("profile")} openCart={() => setScreen("cart")} />
      )}
      {screen === "cart" && (
        <CartScreen totals={totals} back={() => setScreen("menu")} placeOrder={placeOrder} />
      )}
      {screen === "orders" && (
        <OrdersScreen orders={orders} cancel={cancelOrder} back={() => setScreen("menu")}
          newOrder={() => setScreen("menu")} />
      )}
      {screen === "profile" && (
        <ProfileScreen me={me} onSaved={setMe} onLogout={signOut} back={() => setScreen("menu")} />
      )}
    </>
  );
}
