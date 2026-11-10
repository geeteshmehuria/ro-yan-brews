import { useState } from "react";

import { ICONS, LABELS, MAX_QTY } from "../config/constants.js";
import { useReveal } from "../hooks/useReveal.js";
import { Logo } from "../components/ui.jsx";

function Header({ activeCount, openOrders, openProfile }) {
  return (
    <header className="glass sticky top-[calc(var(--sat)+0.5rem)] z-40 mx-3 mt-3 flex items-center justify-between px-4 py-3">
      <div className="flex items-center gap-2 text-lg font-black tracking-wide">
        <Logo className="h-9 w-9 !rounded-xl" />
        <span>Mr. <span className="text-accent">MOMO</span></span>
      </div>
      <div className="flex gap-2">
        <button onClick={openOrders} className="glass-strong press relative rounded-xl px-3 py-1.5 text-sm font-bold">
          My orders
          {activeCount > 0 && (
            <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-accent text-xs font-black text-bg1">
              {activeCount}
            </span>
          )}
        </button>
        <button onClick={openProfile} aria-label="Profile" className="glass-strong press rounded-xl px-3 py-1.5 text-sm">👤</button>
      </div>
    </header>
  );
}

// Always-visible status of orders still in progress, so ordering again never hides them.
function ActiveOrders({ orders, open }) {
  if (!orders.length) return null;
  return (
    <button onClick={open} className="glass press mx-3 mt-3 block w-[calc(100%-1.5rem)] p-3 text-left">
      {orders.map((o) => (
        <div key={o.id} className="flex justify-between text-sm font-bold">
          <span>Order <span className="text-accent">#{o.order_number}</span></span>
          <span className={o.status === "ready" ? "text-accent2" : "text-muted"}>{LABELS[o.status]} →</span>
        </div>
      ))}
    </button>
  );
}

function Hero({ menu }) {
  const ref = useReveal();
  return (
    <section ref={ref} className="glass reveal relative mx-3 mt-5 overflow-hidden px-5 py-8 text-center">
      <div className="shine" />
      <span className="inline-block rounded-full border border-accent2 px-3 py-1 text-xs font-black uppercase tracking-wider text-accent2">
        🌿 100% Pure Veg
      </span>
      <h1 className="mt-3 text-3xl font-black leading-tight">
        Fresh Momos,<br /><em className="not-italic text-accent">Happy You!</em>
      </h1>
      <p className="mt-2 text-sm text-muted">
        {menu?.length ? menu.map((g) => g.category).join(" · ") : "Steamed to perfection"}
      </p>
      {menu?.length > 0 && (
        <a href={`#cat-${menu[0].category}`}
          className="press mt-4 inline-block rounded-xl bg-accent px-8 py-3.5 font-black text-bg1 shadow-[0_6px_24px_var(--accent-glow)]">
          Order Now ↓
        </a>
      )}
    </section>
  );
}

function Chips({ menu, active, setActive }) {
  return (
    <div className="sticky top-[calc(var(--sat)+4.25rem)] z-30 flex gap-2 overflow-x-auto px-3 py-3 [scrollbar-width:none] bg-gradient-to-b from-bar to-transparent">
      {menu.map((g) => (
        <button key={g.category}
          onClick={() => {
            setActive(g.category);
            document.getElementById(`cat-${g.category}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
          className={`press flex-none whitespace-nowrap rounded-3xl border px-4 py-2.5 text-sm font-bold transition-all ${
            active === g.category
              ? "-translate-y-0.5 border-transparent bg-accent text-bg1"
              : "glass-strong border-[var(--stroke)] text-ink"
          }`}>
          {ICONS[g.category] || "🍽"} {g.category}
        </button>
      ))}
    </div>
  );
}

function ItemCard({ item, size, setSize, qty, changeQty }) {
  const ref = useReveal();
  const price = size === "half" ? item.price_half : item.price_full;
  return (
    <div ref={ref} className={`glass reveal mb-3 flex items-center justify-between gap-3 p-4 ${item.is_available ? "" : "opacity-40"}`}>
      <div>
        <div className="font-extrabold">{item.name}</div>
        <div className="mt-1 font-extrabold text-accent2">
          ₹{price}
          {!item.is_available && <span className="ml-2 text-xs font-bold text-danger">Out of stock</span>}
        </div>
        {item.price_half != null && (
          <div className="mt-2 flex gap-1.5">
            {["half", "full"].map((s) => (
              <button key={s} onClick={() => setSize(s)}
                className={`press rounded-lg border px-3 py-1 text-xs font-bold ${
                  size === s ? "border-transparent bg-accent2 text-bg1" : "border-[var(--stroke)] text-muted"
                }`}>
                {s === "half" ? `Half ₹${item.price_half}` : `Full ₹${item.price_full}`}
              </button>
            ))}
          </div>
        )}
      </div>
      {item.is_available && (qty > 0 ? (
        <div className="glass-strong flex flex-none items-center overflow-hidden !rounded-xl border !border-accent">
          <button onClick={() => changeQty(-1)} aria-label={`One less ${item.name}`} className="h-11 w-10 text-xl font-extrabold text-accent">−</button>
          <div className="w-9 text-center text-lg font-extrabold">{qty}</div>
          <button onClick={() => changeQty(1)} disabled={qty >= MAX_QTY} aria-label={`One more ${item.name}`}
            className="h-11 w-10 text-xl font-extrabold text-accent disabled:opacity-30">+</button>
        </div>
      ) : (
        <button onClick={() => changeQty(1)}
          className="press flex-none rounded-xl bg-accent px-5 py-3 text-sm font-black text-bg1 shadow-[0_4px_18px_var(--accent-glow)]">
          ADD
        </button>
      ))}
    </div>
  );
}

function Skeletons() {
  return (
    <div className="px-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="skeleton glass mb-3 h-20 border-none" />
      ))}
    </div>
  );
}

export default function MenuScreen({ paused, menu, error, retry, cart, totals, sizeOf, setSizes, changeQty,
  activeOrders, openOrders, openProfile, openCart }) {
  const [picked, setActive] = useState(null); // the chip tapped last; until then the first category
  const active = picked ?? menu?.[0]?.category;
  return (
    <div className="screen-in pb-32">
      <Header activeCount={activeOrders.length} openOrders={openOrders} openProfile={openProfile} />
      <ActiveOrders orders={activeOrders} open={openOrders} />
      {paused && (
        <div role="status" className="mx-3 mt-3 rounded-glass border border-danger bg-danger-soft p-4 text-center">
          <b className="text-danger">⏸ {paused}</b>
          <p className="mt-1 text-sm text-muted">You can still look at the menu and track your orders.</p>
        </div>
      )}
      <Hero menu={menu} />
      {error && (
        <div className="glass mx-3 mt-4 p-4 text-center">
          <p className="text-danger">{error}</p>
          <button onClick={retry} className="press mt-2 rounded-xl bg-accent px-5 py-2 font-bold text-bg1">Try again</button>
        </div>
      )}
      {!menu && !error && <div className="mt-5"><Skeletons /></div>}
      {menu && (
        <>
          <Chips menu={menu} active={active} setActive={setActive} />
          <main className="px-3">
            {menu.map((g) => (
              <section key={g.category}>
                <div id={`cat-${g.category}`} className="mb-3 mt-6 flex items-center gap-2 text-lg font-black [scroll-margin-top:calc(var(--sat)+8.5rem)]">
                  <span className="text-xl">{ICONS[g.category] || "🍽"}</span>{g.category}
                  <span className="h-px flex-1 bg-gradient-to-r from-[var(--stroke)] to-transparent" />
                </div>
                {g.items.map((item) => {
                  const size = sizeOf(item);
                  const line = cart[`${item.id}_${size}`];
                  return (
                    <ItemCard key={item.id} item={item} size={size}
                      setSize={(s) => setSizes((z) => ({ ...z, [item.id]: s }))}
                      qty={line ? line.qty : 0}
                      changeQty={(d) => changeQty(item, d)} />
                  );
                })}
              </section>
            ))}
          </main>
        </>
      )}
      {/* floating cart bar */}
      <div onClick={totals.count ? openCart : undefined}
        className={`cartbar-anim fixed bottom-[calc(var(--sab)+0.875rem)] left-1/2 z-50 flex w-[calc(100%-1.75rem)] max-w-[492px] -translate-x-1/2 cursor-pointer items-center justify-between rounded-glass border border-[var(--stroke)] bg-bar-soft px-4 py-3.5 shadow-float backdrop-blur-xl ${
          totals.count ? "translate-y-0" : "translate-y-[calc(100%+var(--sab)+1.5rem)]"
        }`}>
        <div>
          <b className="text-accent">{totals.count} {totals.count === 1 ? "item" : "items"}</b>
          <span className="ml-1.5">₹{totals.total}</span>
        </div>
        <div className="rounded-xl bg-accent px-4 py-2.5 text-sm font-black text-bg1">View cart →</div>
      </div>
    </div>
  );
}
