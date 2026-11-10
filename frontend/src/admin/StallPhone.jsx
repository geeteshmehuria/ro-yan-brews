import { useEffect, useState } from "react";

import { api } from "../services/api.js";
import { useBackButton } from "../hooks/backButton.js";
import { prettyPhone } from "../utils/pickup.js";

// The number customers see as "Call the stall" on their orders. The owner sets it here;
// blank removes it (then customers get no call button).
export default function StallPhone({ phone, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useBackButton(() => setEditing(false), editing); // Android Back closes the editor, not the app
  useEffect(() => { if (editing) { setValue(phone || ""); setErr(""); } }, [editing, phone]);

  const save = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api("/api/admin/store/phone", { method: "PATCH", body: { phone: value } });
      onSaved(r.phone);
      setEditing(false);
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };

  if (!editing) {
    return (
      <button onClick={() => setEditing(true)}
        className={`press mt-3 flex w-full items-center justify-between gap-3 rounded-glass border px-4 py-3 text-left text-sm font-bold ${
          phone ? "glass border-[var(--stroke)]" : "border-warn bg-warn-soft"}`}>
        <span>
          📞 {phone ? <>Customers can call <b className="text-accent2">{prettyPhone(phone)}</b></>
            : "Add the stall's phone number so customers can call you"}
        </span>
        <span className="flex-none text-accent">{phone ? "Change ›" : "Add ›"}</span>
      </button>
    );
  }
  return (
    <div className="glass mt-3 p-4">
      <label htmlFor="stall-phone" className="text-sm font-bold">📞 Stall phone number</label>
      <p className="mt-0.5 text-xs text-muted">Shown to customers on their order as “Call the stall”. Leave empty to hide it.</p>
      <input id="stall-phone" type="tel" inputMode="tel" autoComplete="tel" maxLength={20} autoFocus
        placeholder="98765 43210" value={value} onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && save()}
        className="glass-strong mt-3 w-full p-3 text-lg font-bold tracking-wider text-ink placeholder:font-normal placeholder:text-muted focus:border-accent focus:outline-none" />
      {err && <p className="mt-2 text-sm text-danger">{err}</p>}
      <div className="mt-3 flex gap-2">
        <button onClick={save} disabled={busy}
          className="press min-h-[44px] flex-1 rounded-xl bg-accent px-4 font-black text-bg1 disabled:opacity-50">
          {busy ? "Saving…" : "Save"}
        </button>
        <button onClick={() => setEditing(false)} disabled={busy}
          className="press min-h-[44px] rounded-xl border border-[var(--stroke)] px-4 font-bold text-muted">
          Cancel
        </button>
      </div>
    </div>
  );
}
