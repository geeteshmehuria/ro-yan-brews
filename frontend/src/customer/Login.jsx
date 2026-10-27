import { useEffect, useState } from "react";
import { GoogleOAuthProvider, GoogleLogin } from "@react-oauth/google";

import { api, setToken } from "../api.js";
import { Back, BigButton, Field } from "../ui.jsx";

const ENV_GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

function EmailScreen({ email, setEmail, next, googleClientId, onGoogleSuccess, googleErr, setGoogleErr }) {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
      setErr("Please enter a valid email address");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      await api("/api/otp/send", { method: "POST", body: { email } });
      next();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const activeClientId = googleClientId || ENV_GOOGLE_CLIENT_ID;

  return (
    <main className="screen-in px-3 pb-10">
      <div className="px-3 py-8 text-center max-w-sm mx-auto">
        <h2 className="text-xl font-black">Welcome to Ro-Yan</h2>
        <p className="mt-1 text-sm text-muted">Sign in to order or track your brew</p>

        {activeClientId ? (
          <div className="mt-6 mb-6">
            <GoogleOAuthProvider clientId={activeClientId}>
              <div className="flex justify-center">
                <GoogleLogin
                  onSuccess={onGoogleSuccess}
                  onError={() => setGoogleErr("Google sign-in was cancelled or failed")}
                  theme="filled_black"
                  shape="pill"
                  size="large"
                  text="continue_with"
                  width="280"
                />
              </div>
            </GoogleOAuthProvider>
            {googleErr && <p className="mt-2 text-xs text-danger">{googleErr}</p>}

            <div className="my-6 flex items-center gap-3">
              <div className="h-[1px] flex-1 bg-[var(--stroke)]" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted">
                or email code
              </span>
              <div className="h-[1px] flex-1 bg-[var(--stroke)]" />
            </div>
          </div>
        ) : (
          <div className="mt-6" />
        )}

        <Field
          id="email"
          type="email"
          inputMode="email"
          maxLength={255}
          placeholder="you@example.com"
          autoComplete="email"
          style={{ letterSpacing: "1px" }}
          value={email}
          onChange={(e) => setEmail(e.target.value.trim())}
        />
        {err && <p className="text-sm text-danger">{err}</p>}
        <BigButton onClick={send} disabled={busy}>
          {busy ? "Sending code…" : "Send code"}
        </BigButton>
      </div>
    </main>
  );
}

function OtpScreen({ email, back, onSubmit, devMode, cta }) {
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!/^\d{6}$/.test(code)) {
      setErr("Please enter the 6-digit code from the email");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      await onSubmit(code);
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  };

  return (
    <main className="screen-in px-3 pb-10">
      <Back onClick={back} />
      <div className="px-3 py-8 text-center max-w-sm mx-auto">
        <h2 className="text-xl font-black">Enter the code</h2>
        <p className="mt-1 text-sm text-muted">
          Code emailed to <b className="text-ink">{email}</b>
          {devMode && " (test mode: use 123456)"}
        </p>
        <Field
          id="otp"
          type="tel"
          inputMode="numeric"
          maxLength={6}
          placeholder="••••••"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
        />
        {err && <p className="text-sm text-danger">{err}</p>}
        <BigButton onClick={submit} disabled={busy}>
          {busy ? "Verifying…" : cta}
        </BigButton>
      </div>
    </main>
  );
}

// Google OAuth + Email 6-digit OTP login.
// Used by both customer and admin apps.
export function Login({ onDone, cta = "Log in" }) {
  const [step, setStep] = useState("email"); // email | otp
  const [email, setEmail] = useState("");
  const [devMode, setDevMode] = useState(false);
  const [googleClientId, setGoogleClientId] = useState(ENV_GOOGLE_CLIENT_ID);
  const [googleErr, setGoogleErr] = useState("");

  useEffect(() => {
    api("/api/auth/mode")
      .then((m) => {
        setDevMode(!!m.dev_mode);
        if (m.google_client_id) setGoogleClientId(m.google_client_id);
      })
      .catch(() => {});
  }, []);

  const handleGoogleSuccess = async (credentialResponse) => {
    setGoogleErr("");
    try {
      const r = await api("/api/auth/google", {
        method: "POST",
        body: { credential: credentialResponse.credential },
      });
      setToken(r.token);
      onDone({ is_admin: r.is_admin });
    } catch (e) {
      setGoogleErr(e.message || "Google sign-in failed — please try again");
    }
  };

  const verifyOtp = async (code) => {
    const r = await api("/api/otp/verify", {
      method: "POST",
      body: { email, code },
    });
    setToken(r.token);
    onDone({ is_admin: r.is_admin });
  };

  return step === "email" ? (
    <EmailScreen
      email={email}
      setEmail={setEmail}
      next={() => setStep("otp")}
      googleClientId={googleClientId}
      onGoogleSuccess={handleGoogleSuccess}
      googleErr={googleErr}
      setGoogleErr={setGoogleErr}
    />
  ) : (
    <OtpScreen
      email={email}
      devMode={devMode}
      back={() => setStep("email")}
      onSubmit={verifyOtp}
      cta={cta}
    />
  );
}
