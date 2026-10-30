import { useEffect, useState } from "react";

import { useBackToClose } from "../backButton.js";
import { BigButton } from "../ui.jsx";

const toPrice = (v) => (/^\d+$/.test(v) ? Number(v) : NaN);

function Switch({ on, onChange, label }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={`relative h-7 w-[52px] flex-none rounded-full border transition-colors ${
        on ? "border-transparent bg-accent2" : "glass-strong border-[var(--stroke)]"}`}>
      <span className={`absolute top-[3px] h-5 w-5 rounded-full bg-white transition-all ${on ? "left-[27px]" : "left-[3px]"}`} />
    </button>
  );
}

const input = "glass-strong w-full p-3 text-lg text-ink placeholder:text-muted focus:border-accent focus:outline-none";

// Add (item = null) or edit a menu item. The server checks everything again; this just
// catches mistakes early with friendly messages.
export default function MenuItemForm({ item, categories, onSave, onClose }) {
  const [name, setName] = useState(item?.name || "");
  const [category, setCategory] = useState(item?.category || "");
  const [full, setFull] = useState(item ? String(item.price_full) : "");
  const [hasHalf, setHasHalf] = useState(item ? item.price_half != null : false);
  const [half, setHalf] = useState(item?.price_half != null ? String(item.price_half) : "");
  const [available, setAvailable] = useState(item ? item.is_available : true);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setErr(""), [name, category, full, hasHalf, half]); // fixing a field clears its message
  useBackToClose(onClose);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);

  const problem = () => {
    if (name.trim().length < 2) return "Please enter the item name";
    if (!category.trim()) return "Please choose or type a category";
    const f = toPrice(full);
    if (!(f >= 1 && f <= 10000)) return "Full price must be a whole number of rupees (1–10000)";
    if (hasHalf) {
      const h = toPrice(half);
      if (!(h >= 1 && h <= 10000)) return "Half price must be a whole number of rupees";
      if (h >= f) return "The half price must be lower than the full price";
    }
    return "";
  };

  const save = async () => {
    const p = problem();
    if (p) return setErr(p);
    setBusy(true); setErr("");
    try {
      await onSave({
        name: name.trim(), category: category.trim(), price_full: toPrice(full),
        price_half: hasHalf ? toPrice(half) : null, is_available: available,
      });
    } catch (e) {
      setErr(e.message); setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 md:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={item ? "Edit item" : "Add item"} onClick={(e) => e.stopPropagation()}
        className="screen-in max-h-[92vh] w-full max-w-[520px] overflow-y-auto rounded-t-glass border border-[var(--stroke)] p-5 md:rounded-glass"
        style={{ background: "var(--bg2)" }}>
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-black">{item ? "Edit item" : "Add a menu item"}</h2>
          <button onClick={onClose} aria-label="Close"
            className="press glass-strong h-11 w-11 rounded-full text-lg font-black">✕</button>
        </div>

        <label className="mt-4 block text-sm font-bold text-muted" htmlFor="mi-name">Item name</label>
        <input id="mi-name" className={`${input} mt-1`} value={name} maxLength={80}
          placeholder="e.g. Peri Peri Momos" onChange={(e) => setName(e.target.value)} />
        {item && (
          <p className="mt-1 text-xs text-muted">
            Renaming also changes the name on past orders. To replace a product, remove it and add a new one.
          </p>
        )}

        <label className="mt-4 block text-sm font-bold text-muted" htmlFor="mi-cat">Category</label>
        {categories.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1.5">
            {categories.map((c) => (
              <button key={c} type="button" onClick={() => setCategory(c)}
                className={`press rounded-lg border px-3 py-2 text-sm font-bold ${
                  category.trim().toLowerCase() === c.toLowerCase()
                    ? "border-transparent bg-accent text-bg1" : "border-[var(--stroke)] text-muted"}`}>
                {c}
              </button>
            ))}
          </div>
        )}
        <input id="mi-cat" className={`${input} mt-2`} value={category} maxLength={40}
          placeholder={categories.length ? "…or type a new category" : "e.g. Momos"}
          onChange={(e) => setCategory(e.target.value)} />

        <label className="mt-4 block text-sm font-bold text-muted" htmlFor="mi-full">
          {hasHalf ? "Full price (₹)" : "Price (₹)"}
        </label>
        <input id="mi-full" className={`${input} mt-1`} value={full} inputMode="numeric" maxLength={5}
          placeholder="e.g. 120" onChange={(e) => setFull(e.target.value.replace(/\D/g, ""))} />

        <div className="glass mt-4 flex items-center justify-between gap-3 p-3.5">
          <div><b>Has a half size</b><br /><small className="text-muted">e.g. momos, fries</small></div>
          <Switch on={hasHalf} onChange={setHasHalf} label="Has a half size" />
        </div>
        {hasHalf && (
          <>
            <label className="mt-3 block text-sm font-bold text-muted" htmlFor="mi-half">Half price (₹)</label>
            <input id="mi-half" className={`${input} mt-1`} value={half} inputMode="numeric" maxLength={5}
              placeholder="e.g. 70" onChange={(e) => setHalf(e.target.value.replace(/\D/g, ""))} />
          </>
        )}

        <div className="glass mt-3 flex items-center justify-between gap-3 p-3.5">
          <div><b>In stock now</b><br /><small className="text-muted">Off = shown greyed out, can't be ordered</small></div>
          <Switch on={available} onChange={setAvailable} label="In stock now" />
        </div>

        {err && <p className="mt-3 text-center text-sm text-danger">{err}</p>}
        <BigButton onClick={save} disabled={busy}>
          {busy ? "Saving…" : item ? "Save changes" : "Add to menu"}
        </BigButton>
      </div>
    </div>
  );
}
