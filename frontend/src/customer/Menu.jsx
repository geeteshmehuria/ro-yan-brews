import { useState } from "react";

import { LABELS, MAX_QTY } from "../config/constants.js";
import { useReveal } from "../hooks/useReveal.js";
import { FoodBackground, Logo, VegMark } from "../components/ui.jsx";
import { BagIcon, CategoryIcon, ClockIcon, LeafIcon, ReceiptIcon, UserIcon } from "../components/icons.jsx";
import { SteamerArt } from "../components/SteamerArt.jsx";

function Header({ activeCount, openOrders, openProfile }) {
  return (
    <header className="sticky top-[calc(var(--sat)+0.5rem)] z-40 mx-3 mt-3 flex items-center justify-between rounded-[20px] border border-[var(--stroke)] bg-bar px-3 py-2.5 backdrop-blur-xl md:px-4">
      <div className="flex items-center gap-2.5">
        <Logo className="h-9 w-9 !rounded-xl md:h-10 md:w-10" />
        <span className="font-display text-xl font-extrabold md:text-[22px]">Mr. <span className="text-accent">MOMO</span></span>
      </div>
      <div className="flex gap-2">
        <button onClick={openOrders}
          className="press relative flex items-center gap-2 rounded-xl bg-[var(--glass-strong)] px-3 py-2 text-sm font-bold">
          <ReceiptIcon className="hidden h-[18px] w-[18px] md:block" />
          My orders
          {activeCount > 0 && (
            <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-accent px-1 text-xs font-extrabold text-bg1 md:static md:ml-0.5">
              {activeCount}
            </span>
          )}
        </button>
        <button onClick={openProfile} aria-label="Profile"
          className="press flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--glass-strong)] md:h-10 md:w-10">
          <UserIcon className="h-[18px] w-[18px]" />
        </button>
      </div>
    </header>
  );
}

// Always-visible status of orders still in progress, so ordering again never hides them.
function ActiveOrders({ orders, open }) {
  if (!orders.length) return null;
  return (
    <button onClick={open}
      className="press mx-3 mt-3 block w-[calc(100%-1.5rem)] rounded-2xl border border-[var(--accent2-soft)] bg-[var(--accent2-tint)] px-4 py-3 text-left">
      {orders.map((o) => (
        <div key={o.id} className="flex items-center gap-3 py-0.5 text-sm">
          <span className="h-2 w-2 flex-none rounded-full bg-accent2 shadow-[0_0_0_4px_var(--accent2-soft)]" />
          <b>Order <span className="text-accent">#{o.order_number}</span></b>
          <span className={o.status === "ready" ? "font-bold text-accent2" : "text-muted"}>{LABELS[o.status]}</span>
          <span className="ml-auto font-bold text-accent2">Track →</span>
        </div>
      ))}
    </button>
  );
}

function Hero({ menu }) {
  const ref = useReveal();
  return (
    <section ref={ref}
      className="reveal relative mx-3 mt-4 overflow-hidden rounded-[24px] border border-[var(--stroke)] bg-gradient-to-br from-[var(--accent-ring)] to-[var(--glass)] px-5 pb-5 pt-6 md:flex md:items-center md:gap-6 md:rounded-[28px] md:px-12 md:py-11">
      <div className="shine" />
      <div className="relative flex flex-col items-start gap-3 md:flex-1 md:gap-4">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-accent2 px-3 py-1 text-[11px] font-bold uppercase tracking-[1.3px] text-accent2 md:text-xs">
          <LeafIcon className="h-3.5 w-3.5" /> 100% Pure Veg
        </span>
        <h1 className="font-display text-[34px] font-extrabold leading-none md:text-[56px]">
          Fresh Momos,<br /><span className="text-accent">Happy You!</span>
        </h1>
        <p className="max-w-[190px] text-[13px] text-muted md:max-w-none md:text-[17px]">
          {menu?.length ? menu.map((g) => g.category).join(" · ") : "Steamed to perfection"}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {menu?.length > 0 && (
            <a href={`#cat-${menu[0].category}`}
              className="press inline-block rounded-xl bg-accent px-5 py-3 font-extrabold text-bg1 shadow-[0_8px_24px_var(--accent-glow)] md:rounded-2xl md:px-7 md:py-3.5">
              Order now ↓
            </a>
          )}
          <span className="hidden items-center gap-2 text-sm text-muted md:flex">
            <ClockIcon className="h-[18px] w-[18px] text-accent" /> Pickup only · pay cash at the counter
          </span>
        </div>
      </div>
      <SteamerArt className="absolute -bottom-3 -right-8 w-[175px] md:static md:w-[340px] md:flex-none" />
    </section>
  );
}

function Chips({ menu, active, setActive }) {
  return (
    <div className="sticky top-[calc(var(--sat)+4.25rem)] z-30 flex gap-2 overflow-x-auto bg-gradient-to-b from-bar to-transparent px-3 py-3 [scrollbar-width:none]">
      {menu.map((g) => (
        <button key={g.category}
          onClick={() => {
            setActive(g.category);
            document.getElementById(`cat-${g.category}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
          className={`press flex flex-none items-center gap-2 whitespace-nowrap rounded-full border px-4 py-2.5 text-sm font-bold transition-all ${
            active === g.category
              ? "border-transparent bg-accent text-bg1"
              : "border-[var(--stroke)] bg-[var(--glass)] text-ink"
          }`}>
          <CategoryIcon category={g.category} className="h-[18px] w-[18px]" />
          {g.category}
        </button>
      ))}
    </div>
  );
}

function ItemCard({ item, size, setSize, qty, changeQty }) {
  const ref = useReveal();
  const price = size === "half" ? item.price_half : item.price_full;
  return (
    <div ref={ref}
      className={`reveal mb-3 flex gap-3.5 rounded-[20px] border border-[var(--stroke)] bg-[var(--glass)] p-3.5 backdrop-blur-md md:mb-0 md:p-4 ${item.is_available ? "" : "opacity-40"}`}>
      <span className="flex h-14 w-14 flex-none items-center justify-center rounded-2xl bg-[var(--accent-ring)] text-accent md:h-16 md:w-16">
        <CategoryIcon category={item.category} className="h-8 w-8 md:h-9 md:w-9" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start gap-2">
          <span className="mt-1"><VegMark /></span>
          <b className="text-[15px] leading-snug md:text-base">{item.name}</b>
        </div>
        {item.price_half != null && (
          <div className="flex gap-1.5">
            {["half", "full"].map((s) => (
              <button key={s} onClick={() => setSize(s)}
                className={`press rounded-lg border px-2.5 py-1 text-xs font-bold md:text-[13px] ${
                  size === s ? "border-transparent bg-accent2 text-bg1" : "border-[var(--stroke)] text-muted"
                }`}>
                {s === "half" ? `Half ₹${item.price_half}` : `Full ₹${item.price_full}`}
              </button>
            ))}
          </div>
        )}
        <div className="mt-auto flex items-center justify-between gap-2">
          <span className="font-display text-[22px] font-extrabold leading-none text-accent">₹{price}</span>
          {!item.is_available ? (
            <span className="text-xs font-bold text-danger">Out of stock</span>
          ) : qty > 0 ? (
            <div className="flex flex-none items-center overflow-hidden rounded-xl border-[1.5px] border-accent">
              <button onClick={() => changeQty(-1)} aria-label={`One less ${item.name}`} className="h-10 w-10 text-xl font-extrabold text-accent">−</button>
              <div className="w-8 text-center text-lg font-extrabold">{qty}</div>
              <button onClick={() => changeQty(1)} disabled={qty >= MAX_QTY} aria-label={`One more ${item.name}`}
                className="h-10 w-10 text-xl font-extrabold text-accent disabled:opacity-30">+</button>
            </div>
          ) : (
            <button onClick={() => changeQty(1)}
              className="press h-10 flex-none rounded-xl bg-accent px-5 text-sm font-extrabold text-bg1 shadow-[0_4px_18px_var(--accent-glow)]">
              ADD +
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Skeletons() {
  return (
    <div className="px-3 md:grid md:grid-cols-2 md:gap-3 lg:grid-cols-3">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="skeleton mb-3 h-28 rounded-[20px] md:mb-0" />
      ))}
    </div>
  );
}

export default function MenuScreen({ paused, menu, error, retry, cart, totals, sizeOf, setSizes, changeQty,
  activeOrders, openOrders, openProfile, openCart }) {
  const [picked, setActive] = useState(null); // the chip tapped last; until then the first category
  const active = picked ?? menu?.[0]?.category;
  return (
    <div className="screen-in pb-32 font-body">
      <FoodBackground />
      <Header activeCount={activeOrders.length} openOrders={openOrders} openProfile={openProfile} />
      <ActiveOrders orders={activeOrders} open={openOrders} />
      {paused && (
        <div role="status" className="mx-3 mt-3 rounded-2xl border border-danger bg-danger-soft p-4 text-center">
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
                <h2 id={`cat-${g.category}`}
                  className="mb-3 mt-5 flex items-center gap-3 font-display text-2xl font-extrabold [scroll-margin-top:calc(var(--sat)+8.5rem)] md:mt-8 md:text-[30px]">
                  {g.category}
                  <span className="h-0.5 flex-1 bg-gradient-to-r from-[var(--accent-glow)] to-transparent" />
                </h2>
                <div className="md:grid md:grid-cols-2 md:gap-3.5 lg:grid-cols-3">
                {g.items.map((item) => {
                  const size = sizeOf(item);
                  const line = cart[`${item.id}_${size}`];
                  return (
                    <ItemCard key={item.id} item={{ ...item, category: g.category }} size={size}
                      setSize={(s) => setSizes((z) => ({ ...z, [item.id]: s }))}
                      qty={line ? line.qty : 0}
                      changeQty={(d) => changeQty(item, d)} />
                  );
                })}
                </div>
              </section>
            ))}
          </main>
        </>
      )}
      {/* floating cart bar */}
      <div onClick={totals.count ? openCart : undefined}
        className={`cartbar-anim fixed bottom-[calc(var(--sab)+0.875rem)] left-1/2 z-50 flex w-[calc(100%-1.75rem)] max-w-[560px] -translate-x-1/2 cursor-pointer items-center justify-between gap-3 rounded-[20px] border border-[var(--accent-glow)] bg-bar px-3 py-2.5 pl-4 shadow-float backdrop-blur-xl ${
          totals.count ? "translate-y-0" : "translate-y-[calc(100%+var(--sab)+1.5rem)]"
        }`}>
        <div className="flex items-center gap-3">
          <span className="hidden h-10 w-10 items-center justify-center rounded-xl bg-[var(--accent-ring)] text-accent sm:flex">
            <BagIcon />
          </span>
          <div className="leading-tight">
            <b className="text-accent">{totals.count} {totals.count === 1 ? "item" : "items"}</b>
            <span className="text-muted"> · </span><b>₹{totals.total}</b>
            <div className="text-xs text-muted">Pay cash at pickup</div>
          </div>
        </div>
        <div className="rounded-xl bg-accent px-4 py-3 text-sm font-extrabold text-bg1">View cart →</div>
      </div>
    </div>
  );
}
