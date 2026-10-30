import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, getSession, getToken, logout } from "../api.js";
import { beep, flashTitle } from "../alerts.js";
import { useBackButton } from "../backButton.js";
import { disablePush, enablePush } from "../push.js";
import { CART_KEY, IN_APP, MAX_QTY, isActive } from "../constants.js";
import { useSocket } from "../useSocket.js";
import { CartScreen } from "./Checkout.jsx";
import FeedbackSheet from "./Feedback.jsx";
import { Login } from "./Login.jsx";
import MenuScreen from "./Menu.jsx";
import OrdersScreen from "./Orders.jsx";
import ProfileScreen from "./Profile.jsx";
import { tell } from "../dialog.jsx";

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
  const [paused, setPaused] = useState(null); // the owner paused orders: their message, else null
  const [rating, setRating] = useState(null); // { id, prompt } of the order being rated
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
    disablePush(); // not awaited: it has already read the session token it needs
    logout();
    setCart({}); setOrders([]); setMe(null); setRating(null);
    setScreen("login");
  }, []);

  const closeRating = useCallback(() => setRating(null), []);
  const rated = (id) => {
    setOrders((os) => os.map((o) => (o.id === id ? { ...o, reviewed: true } : o)));
    setRating(null);
  };
  const ratingOrder = rating && orders.find((o) => o.id === rating.id);

  // An expired or rejected session goes back to login instead of leaving a half-empty screen.
  const onAuthError = useCallback((e) => { if (e.status === 401) signOut(); }, [signOut]);

  const loadOrders = useCallback(
    () => api("/api/orders/mine").then(setOrders).catch(onAuthError), [onAuthError]);

  const loadStore = useCallback(() => api("/api/store")
    .then((st) => setPaused(st.accepting_orders ? null : st.message)).catch(() => {}), []);

  useEffect(() => {
    if (!loggedIn) return;
    loadStore();
    loadMenu();
    loadOrders();
    api("/api/me").then(setMe).catch(onAuthError);
  }, [loggedIn, loadStore, loadMenu, loadOrders, onAuthError]);

  // Android app: this customer's order updates as notifications, even with the app closed.
  // Tapping one opens My orders (and the rating sheet for "Thanks — how was it?").
  useEffect(() => {
    if (!loggedIn || getSession()?.is_admin) return; // the owner is on their way to /admin
    enablePush((data) => {
      const id = Number(data.order_id);
      setScreen("orders");
      loadOrders();
      if (data.kind === "completed") setRating({ id, prompt: true });
    });
  }, [loggedIn, loadOrders]);

  // live stock updates (only once logged in)
  useSocket(loggedIn ? "/ws/menu" : null, (msg) => {
    if (msg.type === "menu_changed") return loadMenu(); // owner added/edited/removed items; re-prices the cart
    if (msg.type === "store") return setPaused(msg.accepting_orders ? null : msg.message);
    if (msg.type !== "availability") return;
    setMenu((m) => m && m.map((g) => ({
      ...g,
      items: g.items.map((i) => (i.id === msg.item_id ? { ...i, is_available: msg.is_available } : i)),
    })));
  }, () => { loadMenu(); loadStore(); });

  // live status of all my orders — on any screen, so ordering again never hides the last one
  useSocket(loggedIn ? `/ws/me?token=${encodeURIComponent(getToken())}` : null, (msg) => {
    if (msg.type !== "status") return;
    setOrders((os) => os.map((o) => (o.id === msg.order_id ? { ...o, status: msg.status } : o)));
    if (msg.status === "completed") {  // just collected: ask once how it was
      const order = ordersRef.current.find((o) => o.id === msg.order_id);
      if (order && !order.reviewed) setRating((r) => r || { id: order.id, prompt: true });
    }
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
      const qty = Math.min(line.qty + delta, MAX_QTY);
      const next = { ...c };
      if (qty <= 0) delete next[key];
      else next[key] = { ...line, qty };
      return next;
    });
  };

  // From the cart screen: change a line's quantity (down to 0 removes it), or remove it.
  const changeLine = (key, delta) => setCart((c) => {
    if (!c[key]) return c;
    const qty = Math.min(c[key].qty + delta, MAX_QTY);
    const next = { ...c };
    if (qty <= 0) delete next[key];
    else next[key] = { ...c[key], qty };
    return next;
  });
  const removeLine = (key) => setCart((c) => {
    const next = { ...c };
    delete next[key];
    return next;
  });

  const totals = useMemo(() => {
    const lines = Object.values(cart);
    return {
      lines,
      count: lines.reduce((n, l) => n + l.qty, 0),
      total: lines.reduce((t, l) => t + l.qty * l.price, 0),
    };
  }, [cart]);

  // Android Back: cart / orders / profile go back to the menu (the menu itself leaves the app).
  useBackButton(() => setScreen("menu"), ["cart", "orders", "profile"].includes(screen));

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
      else if (e.status === 409) { setPaused(e.message); throw e; } // paused while they were in the cart
      else throw e;
    }
  };

  const cancelOrder = async (id) => {
    try {
      await api(`/api/orders/${id}/cancel`, { method: "POST" });
    } catch (e) { tell(e.message); }
    loadOrders();  // the server is the source of truth either way
  };

  return (
    <>
      {screen === "login" && <Login onDone={onLoggedIn} allowGoogle={!IN_APP} />}
      {screen === "menu" && (
        <MenuScreen paused={paused} menu={menu} error={error} retry={loadMenu} cart={cart} totals={totals}
          sizeOf={sizeOf} setSizes={setSizes} changeQty={changeQty}
          activeOrders={orders.filter(isActive)} openOrders={() => setScreen("orders")}
          openProfile={() => setScreen("profile")} openCart={() => setScreen("cart")} />
      )}
      {screen === "cart" && (
        <CartScreen paused={paused} totals={totals} back={() => setScreen("menu")} placeOrder={placeOrder}
          changeLine={changeLine} removeLine={removeLine} />
      )}
      {screen === "orders" && (
        <OrdersScreen orders={orders} cancel={cancelOrder} rate={(o) => setRating({ id: o.id, prompt: false })}
          back={() => setScreen("menu")}
          newOrder={() => setScreen("menu")} />
      )}
      {screen === "profile" && (
        <ProfileScreen me={me} onSaved={setMe} onLogout={signOut} back={() => setScreen("menu")} />
      )}
      {ratingOrder && !ratingOrder.reviewed && loggedIn && (
        <FeedbackSheet order={ratingOrder} prompt={rating.prompt} onDone={rated} onClose={closeRating} />
      )}
    </>
  );
}
