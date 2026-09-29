import { useEffect, useState } from "react";

import { api, setToken } from "../api.js";
import { Back, BigButton, Field } from "../ui.jsx";

function EmailScreen({ email, setEmail, next }) {
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

function OtpScreen({ email, back, onSubmit, devMode, cta }) {
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
      <Back onClick={back} />
      <div className="px-3 py-8 text-center">
        <h2 className="text-xl font-black">Enter the code</h2>
        <p className="mt-1 text-sm text-muted">
          Code emailed to <b className="text-ink">{email}</b>{devMode && " (test mode: use 123456)"}
        </p>
        <Field id="otp" type="tel" inputMode="numeric" maxLength={6} placeholder="••••••"
          value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
        {err && <p className="text-sm text-danger">{err}</p>}
        <BigButton onClick={submit} disabled={busy}>{busy ? "Verifying…" : cta}</BigButton>
      </div>
    </main>
  );
}

// Email + 6-digit-OTP login. Verifies, stores the session token, then hands the caller
// { is_admin }. Used by both the customer and admin apps.
export function Login({ onDone, cta = "Log in" }) {
  const [step, setStep] = useState("email"); // email | otp
  const [email, setEmail] = useState("");
  const [devMode, setDevMode] = useState(false);
  useEffect(() => {
    api("/api/auth/mode").then((m) => setDevMode(!!m.dev_mode)).catch(() => {});
  }, []);
  const verify = async (code) => {
    const r = await api("/api/otp/verify", { method: "POST", body: { email, code } });
    setToken(r.token);
    onDone({ is_admin: r.is_admin });
  };
  return step === "email"
    ? <EmailScreen email={email} setEmail={setEmail} next={() => setStep("otp")} />
    : <OtpScreen email={email} devMode={devMode} back={() => setStep("email")}
        onSubmit={verify} cta={cta} />;
}
