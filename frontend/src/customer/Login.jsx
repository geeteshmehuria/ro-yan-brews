import { useEffect, useState } from "react";
import { GoogleOAuthProvider, GoogleLogin } from "@react-oauth/google";

import { api, setToken } from "../services/api.js";
import { useBackButton } from "../hooks/backButton.js";
import { FoodBackground, Logo } from "../components/ui.jsx";
import { ArrowIcon, BackIcon, BurgerIcon, LeafIcon, MailIcon, MomoIcon, ShakeIcon } from "../components/icons.jsx";

const PRIMARY = "press flex h-14 w-full items-center justify-center gap-2.5 rounded-2xl bg-accent text-[17px] font-extrabold text-bg1 shadow-[0_10px_28px_var(--accent-glow)] disabled:opacity-50";
const INPUT_BOX = "flex h-[54px] items-center gap-2.5 rounded-2xl border-[1.5px] border-[var(--stroke)] bg-[var(--glass)] px-4 focus-within:border-accent focus-within:shadow-[0_0_0_4px_var(--accent-ring)]";

// "Kitchen open" / "Orders paused", from the public GET /api/store. Nothing until it answers.
function StoreStatus({ open, className = "" }) {
  if (open === null) return null;
  return (
    <div className={`flex items-center gap-2 text-sm font-bold ${open ? "text-accent2" : "text-danger"} ${className}`}>
      <span className={`h-2 w-2 rounded-full ${open ? "bg-accent2 shadow-[0_0_0_4px_var(--accent2-soft)]" : "bg-danger"}`} />
      {open ? "Kitchen open · taking orders" : "Orders paused right now"}
    </div>
  );
}

function FoodTag({ icon, label, className }) {
  return (
    <div className={`flex items-center gap-2.5 rounded-2xl bg-ink py-2.5 pl-2.5 pr-4 font-bold text-bg1 shadow-dialog ${className}`}>
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent">{icon}</span>
      {label}
    </div>
  );
}

// The story beside the card: short on phones, the full pitch on wider screens.
function Hero() {
  return (
    <section className="flex flex-col items-center gap-3 text-center md:flex-1 md:items-start md:gap-6 md:text-left">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-accent2 px-3 py-1 text-xs font-bold uppercase tracking-[1.4px] text-accent2">
        <LeafIcon className="h-3.5 w-3.5" /> 100% Pure Veg
      </span>
      <h1 className="font-display text-[40px] font-extrabold leading-none md:text-[52px] lg:text-[60px]">
        Hot momos,<br /><span className="text-accent">steamed to order.</span>
      </h1>
      <p className="text-[15px] text-muted md:hidden">Order now · pick up hot · pay cash</p>
      <p className="hidden max-w-[460px] text-lg leading-relaxed text-muted md:block">
        Order from your phone, skip the queue, and pick it up hot from the stall. Pay cash at the counter.
      </p>
      <div className="hidden flex-wrap gap-3.5 md:flex">
        <FoodTag icon={<MomoIcon className="h-6 w-6 text-bg1" />} label="Momos" className="-rotate-3" />
        <FoodTag icon={<BurgerIcon className="h-6 w-6 text-bg1" />} label="Burgers" className="translate-y-1.5 rotate-2" />
        <FoodTag icon={<ShakeIcon className="h-5 w-5 text-bg1" />} label="Shakes" className="-rotate-1" />
      </div>
      <ol className="mt-2 hidden flex-wrap gap-x-5 gap-y-3 md:flex">
        {["Pick your food", "We steam it fresh", "Collect & pay cash"].map((s, i) => (
          <li key={s} className="flex items-center gap-2 text-sm font-bold">
            <span className="flex h-8 w-8 items-center justify-center rounded-full border-[1.5px] border-accent font-display text-accent">{i + 1}</span>
            {s}
          </li>
        ))}
      </ol>
    </section>
  );
}

// The login card, styled like an order ticket with a yellow card tucked behind it.
function TicketCard({ children }) {
  return (
    <section aria-label="Sign in" className="relative mx-auto w-full max-w-[420px] md:mx-0 md:flex-none">
      <div aria-hidden="true" className="absolute -bottom-3 left-2 right-[-6px] top-5 rotate-[2.5deg] rounded-[28px] bg-accent opacity-90" />
      <div className="relative overflow-hidden rounded-[28px] border border-[var(--stroke)] bg-[var(--card)] shadow-dialog backdrop-blur-xl">
        {children}
      </div>
    </section>
  );
}

function Shell({ open, children }) {
  return (
    <main className="screen-in flex min-h-[calc(100vh-var(--sat)-var(--sab))] flex-col px-4 pb-8 font-body">
      <FoodBackground />
      <header className="hidden items-center justify-between gap-4 py-6 md:flex">
        <div className="flex items-center gap-3">
          <Logo className="h-11 w-11 !rounded-xl" />
          <span className="font-display text-2xl font-extrabold">Mr. <span className="text-accent">MOMO</span></span>
        </div>
        <StoreStatus open={open} className="rounded-full border border-[var(--stroke)] bg-[var(--glass)] px-3.5 py-2" />
      </header>
      <div className="flex flex-1 flex-col justify-center gap-7 py-6 md:flex-row md:items-center md:gap-16 md:py-0">
        <Hero />
        {children}
      </div>
      <StoreStatus open={open} className="mx-auto mt-4 md:hidden" />
    </main>
  );
}

function EmailScreen({ email, setEmail, next, googleClientId, onGoogleSuccess, googleErr, setGoogleErr, title, subtitle }) {
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

  return (
    <TicketCard>
      <div className="flex items-center gap-3.5 px-6 pb-5 pt-6 md:flex-col md:gap-1.5 md:px-8 md:pt-8 md:text-center">
        <Logo className="h-[60px] w-[60px] !rounded-2xl shadow-dialog md:h-[76px] md:w-[76px] md:!rounded-[20px]" />
        <div>
          <h2 className="font-display text-[22px] font-extrabold leading-tight md:mt-3 md:text-[28px]">{title}</h2>
          <p className="text-sm text-muted md:text-[15px]">{subtitle}</p>
        </div>
      </div>

      <form className="flex flex-col gap-4 px-6 pb-7 md:px-8" onSubmit={(e) => { e.preventDefault(); send(); }} noValidate>
        {googleClientId && (
          <>
            <GoogleOAuthProvider clientId={googleClientId}>
              <div className="flex justify-center">
                <GoogleLogin
                  onSuccess={onGoogleSuccess}
                  onError={() => setGoogleErr("Google sign-in was cancelled or failed")}
                  theme="outline"
                  shape="rectangular"
                  size="large"
                  text="continue_with"
                  width="300"
                />
              </div>
            </GoogleOAuthProvider>
            {googleErr && <p className="-mt-2 text-center text-xs text-danger">{googleErr}</p>}

            <div className="flex items-center gap-3 text-xs font-bold uppercase tracking-[1.4px] text-muted">
              <span className="h-px flex-1 bg-[var(--stroke)]" />or use email<span className="h-px flex-1 bg-[var(--stroke)]" />
            </div>
          </>
        )}

        <div className="flex flex-col gap-2">
          <label htmlFor="email" className="text-sm font-bold">Email address</label>
          <div className={INPUT_BOX}>
            <MailIcon className="h-5 w-5 flex-none text-accent" />
            <input
              id="email"
              type="email"
              inputMode="email"
              maxLength={255}
              placeholder="you@example.com"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value.trim())}
              className="min-w-0 flex-1 bg-transparent text-base font-medium text-ink placeholder:text-muted focus:outline-none"
            />
          </div>
          {err && <p className="text-sm text-danger">{err}</p>}
        </div>

        <button type="submit" disabled={busy} className={PRIMARY}>
          {busy ? "Sending code…" : <>Send me a code <ArrowIcon /></>}
        </button>
        <p className="text-center text-[13px] text-muted">We'll email a 6-digit code. No password to remember.</p>
      </form>
    </TicketCard>
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
    <TicketCard>
      <form className="flex flex-col gap-4 px-6 pb-7 pt-5 md:px-8 md:pt-6" onSubmit={(e) => { e.preventDefault(); submit(); }} noValidate>
        <button type="button" onClick={back} className="press -ml-1 flex items-center gap-1.5 self-start py-1 text-sm font-bold text-accent">
          <BackIcon className="h-4 w-4" /> Change email
        </button>
        <div className="text-center">
          <h2 className="font-display text-[26px] font-extrabold leading-tight">Enter the code</h2>
          <p className="mt-1 text-sm text-muted">
            Code emailed to <b className="text-ink">{email}</b>
            {devMode && " (test mode: use 123456)"}
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="otp" className="sr-only">6-digit code</label>
          <input
            id="otp"
            type="tel"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="••••••"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className="h-16 w-full rounded-2xl border-[1.5px] border-[var(--stroke)] bg-[var(--glass)] text-center text-2xl font-bold tracking-[10px] text-ink placeholder:text-muted focus:border-accent focus:shadow-[0_0_0_4px_var(--accent-ring)] focus:outline-none"
          />
          {err && <p className="text-center text-sm text-danger">{err}</p>}
        </div>
        <button type="submit" disabled={busy} className={PRIMARY}>
          {busy ? "Verifying…" : <>{cta} <ArrowIcon /></>}
        </button>
      </form>
    </TicketCard>
  );
}

// Google OAuth + Email 6-digit OTP login.
// Used by both customer and admin apps.
// allowGoogle=false in the Android app: Google refuses to sign in inside an app's web view.
export function Login({ onDone, cta = "Log in", allowGoogle = true,
  title = "Welcome to Mr. Momo", subtitle = "Sign in to order and track your food" }) {
  const [step, setStep] = useState("email"); // email | otp
  useBackButton(() => setStep("email"), step === "otp"); // Android Back: re-enter the email
  const [email, setEmail] = useState("");
  const [devMode, setDevMode] = useState(false);
  // Only the backend's client ID: the button never shows while the backend refuses Google logins.
  const [googleClientId, setGoogleClientId] = useState("");
  const [googleErr, setGoogleErr] = useState("");
  const [open, setOpen] = useState(null); // store open? null until /api/store answers

  useEffect(() => {
    api("/api/auth/mode")
      .then((m) => {
        setDevMode(!!m.dev_mode);
        setGoogleClientId(allowGoogle ? m.google_client_id || "" : "");
      })
      .catch(() => {});
  }, [allowGoogle]);

  useEffect(() => {
    api("/api/store").then((s) => setOpen(!!s.accepting_orders)).catch(() => {});
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

  return (
    <Shell open={open}>
      {step === "email" ? (
        <EmailScreen
          email={email}
          setEmail={setEmail}
          next={() => setStep("otp")}
          googleClientId={googleClientId}
          onGoogleSuccess={handleGoogleSuccess}
          googleErr={googleErr}
          setGoogleErr={setGoogleErr}
          title={title}
          subtitle={subtitle}
        />
      ) : (
        <OtpScreen
          email={email}
          devMode={devMode}
          back={() => setStep("email")}
          onSubmit={verifyOtp}
          cta={cta}
        />
      )}
    </Shell>
  );
}
