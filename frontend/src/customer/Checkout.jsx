import { useEffect, useRef, useState } from "react";

import { api, WS_BASE } from "../api.js";

const STATUSES = ["placed", "preparing", "ready", "completed"];
const LABELS = { placed: "Placed", preparing: "Preparing", ready: "Ready", completed: "Done" };

function Back({ onClick, children = "← Back" }) {
  return (
    <button onClick={onClick} className="press px-1 py-4 font-extrabold text-accent">{children}</button>
  );
}

function BigButton({ onClick, disabled, children }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="press mt-3 w-full rounded-glass bg-accent p-4 text-lg font-black text-bg1 shadow-[0_8px_30px_rgba(56,189,248,0.35)] disabled:opacity-50">
      {children}
    </button>
  );
}

function Field(props) {
  return (
    <input {...props}
      className="glass my-3 w-full p-4 text-center text-xl tracking-[3px] text-ink placeholder:tracking-normal placeholder:text-muted focus:border-accent focus:outline-none" />
  );
}

export function CartScreen({ totals, back, placeOrder }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async () => {
    setBusy(true); setErr("");
    try { await placeOrder(); }
    catch (e) { setErr(e.message); setBusy(false); }
  };
  return (
    <main className="screen-in px-3 pb-10">
      <Back onClick={back}>← Back to menu</Back>
      <h2 className="mb-3 px-1 text-xl font-black">Your order</h2>
      {totals.lines.map((l) => (
        <div key={`${l.id}_${l.size}`} className="glass mb-2.5 flex items-center justify-between p-4">
          <div>
            <b>{l.name}</b>
            {l.hasHalf && <small className="ml-1 text-muted">({l.size === "half" ? "Half" : "Full"})</small>}
            <br />
            <small className="text-muted">₹{l.price} × {l.qty}</small>
          </div>
          <b className="text-accent2">₹{l.price * l.qty}</b>
        </div>
      ))}
      <div className="flex justify-between px-1.5 py-4 text-xl font-black text-accent">
        <span>Total</span><span>₹{totals.total}</span>
      </div>
      <p className="text-center text-sm text-muted">💵 Pay cash when you collect your order</p>
      {err && <p className="mt-2 text-center text-sm text-danger">{err}</p>}
      <BigButton onClick={submit} disabled={!totals.count || busy}>
        {busy ? "Placing order…" : "Place order"}
      </BigButton>
    </main>
  );
}

export function EmailScreen({ email, setEmail, back, next }) {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) { setErr("Please enter a valid email address"); return; }
    setBusy(true); setErr("");
    try { await api("/api/otp/send", { method: "POST", body: { email } }); next(); }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  };
  return (
    <main className="screen-in px-3 pb-10">
      {back && <Back onClick={back} />}
      <div className="px-3 py-8 text-center">
        <h2 className="text-xl font-black">Your email address</h2>
        <p className="mt-1 text-sm text-muted">We will email you a login code</p>
        <Field id="email" type="email" inputMode="email" maxLength={255} placeholder="you@example.com"
          autoComplete="email" style={{ letterSpacing: "1px" }}
          value={email} onChange={(e) => setEmail(e.target.value.trim())} />
        {err && <p className="text-sm text-danger">{err}</p>}
        <BigButton onClick={send} disabled={busy}>{busy ? "Sending…" : "Send code"}</BigButton>
      </div>
    </main>
  );
}

export function OtpScreen({ email, back, onSubmit, demo, cta = "Verify" }) {
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!/^\d{6}$/.test(code)) { setErr("Please enter the 6-digit code from the email"); return; }
    setBusy(true); setErr("");
    try { await onSubmit(code); }
    catch (e) { setErr(e.message); setBusy(false); }
  };
  return (
    <main className="screen-in px-3 pb-10">
      {back && <Back onClick={back} />}
      <div className="px-3 py-8 text-center">
        <h2 className="text-xl font-black">Enter the code</h2>
        <p className="mt-1 text-sm text-muted">
          Code emailed to <b className="text-ink">{email}</b>{demo && " (test mode: use 123456)"}
        </p>
        <Field id="otp" type="tel" inputMode="numeric" maxLength={6} placeholder="••••••"
          value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
        {err && <p className="text-sm text-danger">{err}</p>}
        <BigButton onClick={submit} disabled={busy}>{busy ? "Verifying…" : cta}</BigButton>
      </div>
    </main>
  );
}

// Full email + 6-digit-OTP login. Verifies, stores the session token, then hands
// the caller { token, is_admin, email }. Used by both the customer and admin apps.
export function Login({ onDone, cta = "Log in" }) {
  const [step, setStep] = useState("email"); // email | otp
  const [email, setEmail] = useState("");
  const [smtpLive, setSmtpLive] = useState(true);
  useEffect(() => {
    api("/api/auth/mode").then((m) => setSmtpLive(!!m.smtp)).catch(() => {});
  }, []);
  const verify = async (code) => {
    const r = await api("/api/otp/verify", { method: "POST", body: { email, code } });
    localStorage.setItem("session_token", r.token);
    onDone({ token: r.token, is_admin: r.is_admin, email });
  };
  return step === "email"
    ? <EmailScreen email={email} setEmail={setEmail} next={() => setStep("otp")} />
    : <OtpScreen email={email} demo={!smtpLive} back={() => setStep("email")}
        onSubmit={verify} cta={cta} />;
}

function Tracker({ status }) {
  const idx = STATUSES.indexOf(status);
  return (
    <div className="relative mx-2 my-7 flex justify-between">
      <span className="absolute left-[10%] right-[10%] top-4 h-0.5 bg-[var(--stroke)]" />
      {STATUSES.map((s, i) => (
        <div key={s} className="relative z-10 flex-1 text-center">
          <div className={`mx-auto mb-1.5 flex h-8 w-8 items-center justify-center rounded-full text-sm font-extrabold transition-all ${
            i < idx ? "bg-accent2 text-bg1"
              : i === idx ? "pulse-dot bg-accent text-bg1"
                : "glass-strong text-muted"
          }`}>{i + 1}</div>
          <small className={`text-xs font-bold ${i <= idx ? "text-ink" : "text-muted"}`}>{LABELS[s]}</small>
        </div>
      ))}
    </div>
  );
}

export function DoneScreen({ order, reset }) {
  const [status, setStatus] = useState(order?.status || "placed");
  const wsRef = useRef(null);
  useEffect(() => {
    if (!order) return;
    const ws = new WebSocket(`${WS_BASE}/ws/orders/${order.id}`);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "status") setStatus(msg.status);
    };
    wsRef.current = ws;
    return () => ws.close();
  }, [order]);
  if (!order) return null;
  return (
    <main className="screen-in px-3 pb-10">
      <div className="px-3 py-9 text-center">
        <div className="text-5xl">✅</div>
        <h2 className="mt-2 text-xl font-black">Order placed!</h2>
        <div className="my-2.5 text-4xl font-black text-accent">#{order.order_number}</div>
        <div className="glass-strong inline-block rounded-3xl px-5 py-2 font-extrabold">
          Ready in about <b className="text-accent2">15 min</b>
        </div>
        <Tracker status={status} />
        <p className="text-sm text-muted">Show this number at the counter and pay cash</p>
        <BigButton onClick={reset}>Order again</BigButton>
      </div>
    </main>
  );
}
