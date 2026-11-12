import { CART_KEY, CHECKOUT_KEY, TOKEN_KEY } from "../config/constants.js";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const WS_BASE = import.meta.env.VITE_WS_URL || API.replace(/^http/, "ws");

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

// Decode the JWT payload locally so screens can tell "logged in?" / "admin?"
// without a round-trip. Returns null (and clears the token) if missing/expired.
export function getSession() {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.removeItem(TOKEN_KEY);
      return null;
    }
    return payload; // { cid, email, is_admin, exp }
  } catch {
    return null;
  }
}

// The saved cart goes too, so the next person on this device doesn't inherit it.
export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(CART_KEY);
  localStorage.removeItem(CHECKOUT_KEY);
}

// Render's free tier puts the backend to sleep after ~15 idle minutes; the next request waits
// 30–60 s while it starts (502/503 or a dropped connection on the way). So wait up to WAKE_MS,
// and quietly retry reads (GET) until then. Writes get one long try: retrying a POST could
// send a login code twice, and orders already recover through their checkout key.
// The timeout also stops a server that never answers from leaving the screen waiting forever.
const WAKE_MS = 90000;
const RETRY_MS = 3000;
const WAKING = new Set([502, 503, 504]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function api(path, { method = "GET", body, headers = {} } = {}) {
  const token = getToken();
  const deadline = Date.now() + WAKE_MS;
  let res;
  for (;;) {
    const left = deadline - Date.now();
    try {
      res = await fetch(API + path, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout?.(left), // missing before Safari 16: then no timeout, not a crash
      });
    } catch (e) {
      if (e.name === "TimeoutError") throw new Error("The server is taking too long — please try again");
      if (method !== "GET" || left <= RETRY_MS) throw e; // e.g. no internet at all, after the wait
      await sleep(RETRY_MS);
      continue;
    }
    if (method === "GET" && WAKING.has(res.status) && deadline - Date.now() > RETRY_MS) {
      await sleep(RETRY_MS);
      continue;
    }
    break;
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = typeof data.detail === "string" ? data.detail : "Something went wrong — please try again";
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return data;
}
