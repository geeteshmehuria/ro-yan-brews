import { useEffect, useState } from "react";

import { api } from "../services/api.js";
import { FoodBackground } from "../components/ui.jsx";
import { ask } from "../components/dialog.jsx";
import { BackIcon, CheckIcon, MailIcon, UserIcon } from "../components/icons.jsx";

export default function ProfileScreen({ me, onSaved, onLogout, back }) {
  const [name, setName] = useState(me?.name || "");
  const [state, setState] = useState(""); // "" | "saving" | "saved" | error message
  useEffect(() => setName(me?.name || ""), [me]);

  const save = async () => {
    setState("saving");
    try {
      onSaved(await api("/api/me", { method: "PATCH", body: { name } }));
      setState("saved");
    } catch (e) { setState(e.message); }
  };

  const initial = (me?.name || me?.email || "?").trim().charAt(0).toUpperCase();

  return (
    <main className="screen-in mx-auto max-w-[520px] px-3 pb-10 font-body">
      <FoodBackground />
      <button onClick={back} className="press flex items-center gap-1.5 px-1 py-4 font-bold text-accent">
        <BackIcon className="h-[18px] w-[18px]" /> Menu
      </button>

      <section className="relative mt-2">
        <div aria-hidden="true" className="absolute -bottom-3 left-2 right-[-6px] top-5 rotate-[2.5deg] rounded-[28px] bg-accent opacity-90" />
        <div className="relative overflow-hidden rounded-[28px] border border-[var(--stroke)] bg-[var(--card)] shadow-dialog backdrop-blur-xl">
          <div className="flex flex-col items-center px-6 pb-5 pt-7 text-center">
            <span aria-hidden="true"
              className="flex h-20 w-20 items-center justify-center rounded-full bg-accent font-display text-4xl font-extrabold text-bg1 shadow-[0_8px_24px_var(--accent-glow)]">
              {initial}
            </span>
            <h1 className="mt-3 font-display text-[28px] font-extrabold leading-tight">Your profile</h1>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-muted"><MailIcon className="h-4 w-4" /> {me?.email}</p>
          </div>

          <form className="flex flex-col gap-3 px-6 pb-6" onSubmit={(e) => { e.preventDefault(); save(); }}>
            <div className="flex flex-col gap-2">
              <label htmlFor="name" className="text-sm font-bold">Your name <span className="font-medium text-muted">(optional)</span></label>
              <div className="flex h-[54px] items-center gap-2.5 rounded-2xl border-[1.5px] border-[var(--stroke)] bg-[var(--glass)] px-4 focus-within:border-accent focus-within:shadow-[0_0_0_4px_var(--accent-ring)]">
                <UserIcon className="h-5 w-5 flex-none text-accent" />
                <input id="name" type="text" maxLength={60} placeholder="Your name" autoComplete="name" value={name}
                  onChange={(e) => { setName(e.target.value); setState(""); }}
                  className="min-w-0 flex-1 bg-transparent text-base font-medium text-ink placeholder:text-muted focus:outline-none" />
              </div>
              <p className="text-xs text-muted">Shown to the stall when you order, so they can call your name.</p>
            </div>
            {state && state !== "saving" && (
              <p role={state === "saved" ? "status" : "alert"}
                className={`flex items-center gap-1.5 text-sm font-bold ${state === "saved" ? "text-accent2" : "text-danger"}`}>
                {state === "saved" ? <><CheckIcon /> Saved</> : state}
              </p>
            )}
            <button type="submit" disabled={state === "saving"}
              className="press h-14 w-full rounded-2xl bg-accent text-[17px] font-extrabold text-bg1 shadow-[0_10px_28px_var(--accent-glow)] disabled:opacity-50">
              {state === "saving" ? "Saving…" : "Save"}
            </button>
          </form>

          <div className="border-t-2 border-dashed border-[var(--stroke)] px-6 py-4 text-center">
            <button onClick={async () => await ask({ title: "Log out?",
              message: "Your cart is cleared and this phone stops getting your order updates. Log in again with your email any time.",
              confirmLabel: "Log out", cancelLabel: "Stay logged in", tone: "danger" }) && onLogout()} className="press rounded-xl border border-[var(--danger-soft)] px-6 py-2.5 font-bold text-danger">
              Log out
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
