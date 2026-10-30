import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api.js";
import { ICONS } from "../constants.js";
import { useSocket } from "../useSocket.js";
import MenuItemForm from "./MenuItemForm.jsx";
import { ask, tell } from "../dialog.jsx";

const UNDO_MS = 6000;

const price = (i) => (i.price_half != null ? `₹${i.price_half} / ₹${i.price_full}` : `₹${i.price_full}`);

// The owner's menu: stock switch, add / edit / remove (hide) / restore, and delete for
// items never ordered. Stays in sync across the owner's devices through /ws/menu.
// `filter`: "all", or "out" = only items marked out of stock (the dashboard's warning opens this).
// `visible`: the dashboard keeps this mounted on its other tabs and only hides the list, so the
// Undo bar for a just-removed item stays on screen after switching tabs.
export default function MenuSection({ visible = true, filter = "all", setFilter = () => {} }) {
  const [items, setItems] = useState(null); // null = loading
  const [err, setErr] = useState("");
  const [form, setForm] = useState(null); // null = closed, {} = add, {item} = edit
  const [showRemoved, setShowRemoved] = useState(false);
  const [undo, setUndo] = useState(null); // the item just removed
  const undoTimer = useRef();
  const retryTimer = useRef();
  const alive = useRef(true);

  // A network error, timeout or 5xx (e.g. the free-tier backend waking up) retries, like the
  // orders do in AdminApp; a rejected session is left to AdminApp, which logs out.
  const load = useCallback(() => {
    clearTimeout(retryTimer.current);
    return api("/api/admin/menu").then((m) => { setItems(m); setErr(""); }).catch((e) => {
      setErr(e.message);
      if (alive.current && (!e.status || e.status >= 500)) retryTimer.current = setTimeout(load, 5000);
    });
  }, []);
  useEffect(() => {
    alive.current = true;
    load();
    return () => {
      alive.current = false;
      clearTimeout(undoTimer.current);
      clearTimeout(retryTimer.current);
    };
  }, [load]);

  useSocket("/ws/menu", (msg) => {
    if (msg.type === "availability") {
      setItems((its) => its && its.map((i) => (i.id === msg.item_id ? { ...i, is_available: msg.is_available } : i)));
    } else if (msg.type === "menu_changed") load();
  }, load);

  const act = async (fn) => {
    try { await fn(); } catch (e) { tell(e.message); }
    load();
  };

  const toggleStock = (item) => act(() => api(`/api/admin/menu/${item.id}/availability`, {
    method: "PATCH", body: { is_available: !item.is_available } }));

  const remove = async (item) => {
    if (!await ask({ title: `Remove ${item.name}?`, message: "It leaves the menu. Past orders keep it, and you can restore it later.",
      confirmLabel: "Remove", tone: "danger" })) return;
    act(async () => {
      await api(`/api/admin/menu/${item.id}/remove`, { method: "POST" });
      clearTimeout(undoTimer.current);
      setUndo(item);
      undoTimer.current = setTimeout(() => setUndo(null), UNDO_MS);
    });
  };

  const restore = (item) => {
    clearTimeout(undoTimer.current);
    setUndo(null);
    act(() => api(`/api/admin/menu/${item.id}/restore`, { method: "POST" }));
  };

  const deleteForever = async (item) => {
    if (!await ask({ title: `Delete ${item.name} for good?`, message: "This can't be undone.",
      confirmLabel: "Delete", tone: "danger" })) return;
    act(() => api(`/api/admin/menu/${item.id}`, { method: "DELETE" }));
  };

  const save = async (body) => {
    const editing = form.item;
    await api(editing ? `/api/admin/menu/${editing.id}` : "/api/admin/menu",
      { method: editing ? "PATCH" : "POST", body });
    setForm(null);
    load();
  };
  const closeForm = useCallback(() => setForm(null), []);

  const live = (items || []).filter((i) => !i.archived);
  const removed = (items || []).filter((i) => i.archived);
  const categories = [...new Set(live.map((i) => i.category))]; // all of them, for the add/edit form
  const outCount = live.filter((i) => !i.is_available).length;
  const onlyOut = filter === "out" && outCount > 0;
  const listed = onlyOut ? live.filter((i) => !i.is_available) : live;
  const listedCategories = [...new Set(listed.map((i) => i.category))];

  return (
    <>
      <div hidden={!visible}>
        <div className="mb-2.5 mt-5 flex items-center justify-between px-1">
          <h2 className="font-black text-accent">Menu{items ? ` (${live.length})` : ""}</h2>
          <button onClick={() => setForm({})}
            className="press rounded-xl bg-accent px-4 py-2.5 text-sm font-black text-bg1">+ Add item</button>
        </div>
        {outCount > 0 && (
          <div className="mb-1 flex gap-1.5" role="tablist" aria-label="Filter menu">
            {[["all", `All ${live.length}`], ["out", `Out of stock ${outCount}`]].map(([id, label]) => (
              <button key={id} role="tab" aria-selected={(id === "out") === onlyOut} onClick={() => setFilter(id)}
                className={`press rounded-full border px-3.5 py-2 text-sm font-bold ${
                  (id === "out") === onlyOut ? "border-transparent bg-accent text-bg1" : "border-[var(--stroke)] text-muted"}`}>
                {label}
              </button>
            ))}
          </div>
        )}
        {err && <p className="glass mb-2.5 p-4 text-center text-sm text-danger">{err}</p>}
        {items && live.length === 0 && (
          <p className="glass p-5 text-center text-muted">The menu is empty — tap “+ Add item” to add your first dish</p>
        )}

        {listedCategories.map((c) => (
          <div key={c}>
            <div className="mb-1.5 mt-4 px-1 text-sm font-black uppercase tracking-wider text-muted">{ICONS[c] || "🍽"} {c}</div>
            {listed.filter((i) => i.category === c).map((item) => (
              <div key={item.id} className={`glass mb-2.5 p-3.5 ${item.is_available ? "" : "opacity-70"}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <b className="break-words">{item.name}</b>
                    <div className="text-sm text-muted">{price(item)}{item.is_available ? "" : " · out of stock"}</div>
                  </div>
                  <button onClick={() => toggleStock(item)} role="switch" aria-checked={item.is_available}
                    aria-label={`${item.name} in stock`}
                    className={`relative h-7 w-[52px] flex-none rounded-full border transition-colors ${
                      item.is_available ? "border-transparent bg-accent2" : "glass-strong border-[var(--stroke)]"}`}>
                    <span className={`absolute top-[3px] h-5 w-5 rounded-full bg-white transition-all ${item.is_available ? "left-[27px]" : "left-[3px]"}`} />
                  </button>
                </div>
                <div className="mt-2.5 flex gap-2">
                  <button onClick={() => setForm({ item })}
                    className="press min-h-[40px] flex-1 rounded-lg border border-[var(--stroke)] text-sm font-bold">Edit</button>
                  <button onClick={() => remove(item)}
                    className="press min-h-[40px] flex-1 rounded-lg border border-[var(--stroke)] text-sm font-bold text-danger">Remove</button>
                </div>
              </div>
            ))}
          </div>
        ))}

        {removed.length > 0 && (
          <>
            <button onClick={() => setShowRemoved((v) => !v)}
              className="press glass-strong mt-3 w-full rounded-xl px-4 py-3 text-left text-sm font-bold text-muted">
              {showRemoved ? "▾" : "▸"} Removed items ({removed.length})
            </button>
            {showRemoved && removed.map((item) => (
              <div key={item.id} className="glass mt-2.5 flex items-center justify-between gap-3 p-3.5 opacity-80">
                <div className="min-w-0">
                  <b className="break-words">{item.name}</b>
                  <div className="text-sm text-muted">{item.category} · {price(item)}</div>
                </div>
                <div className="flex flex-none gap-1.5">
                  <button onClick={() => restore(item)}
                    className="press rounded-lg bg-accent2 px-3 py-2 text-sm font-black text-bg1">Restore</button>
                  {!item.ordered && (
                    <button onClick={() => deleteForever(item)} aria-label={`Delete ${item.name} for good`}
                      className="press rounded-lg border border-[var(--stroke)] px-3 py-2 text-sm font-bold text-danger">Delete</button>
                  )}
                </div>
              </div>
            ))}
          </>
        )}

      </div>

      {undo && (
        <div role="status" className="fixed bottom-[calc(var(--sab)+5.5rem)] left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-[488px] -translate-x-1/2 items-center justify-between gap-3 rounded-glass border border-[var(--stroke)] px-4 py-3 shadow-[0_10px_40px_rgba(0,0,0,0.45)]"
          style={{ background: "var(--bg2)" }}>
          <span className="text-sm"><b>{undo.name}</b> removed from the menu</span>
          <button onClick={() => restore(undo)} className="press rounded-lg bg-accent px-4 py-2 text-sm font-black text-bg1">Undo</button>
        </div>
      )}

      {form && (
        <MenuItemForm item={form.item} categories={categories} onSave={save} onClose={closeForm} />
      )}
    </>
  );
}
