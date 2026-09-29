import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Back, BigButton, Field } from "../ui.jsx";

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

  return (
    <main className="screen-in px-3 pb-10">
      <Back onClick={back}>← Menu</Back>
      <div className="px-3 py-4 text-center">
        <h2 className="text-xl font-black">Your profile</h2>
        <p className="mt-1 text-sm text-muted">{me?.email}</p>
        <p className="mt-4 text-sm text-muted">Your name is shown to the stall when you order (optional)</p>
        <Field id="name" type="text" maxLength={60} placeholder="Your name" autoComplete="name"
          style={{ letterSpacing: "normal" }} value={name}
          onChange={(e) => { setName(e.target.value); setState(""); }} />
        {state && state !== "saving" && (
          <p className={`text-sm ${state === "saved" ? "text-accent2" : "text-danger"}`}>
            {state === "saved" ? "Saved ✓" : state}
          </p>
        )}
        <BigButton onClick={save} disabled={state === "saving"}>{state === "saving" ? "Saving…" : "Save"}</BigButton>
        <button onClick={onLogout} className="press glass-strong mt-6 rounded-xl px-6 py-3 font-bold text-danger">
          Log out
        </button>
      </div>
    </main>
  );
}
