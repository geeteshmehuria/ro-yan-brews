import { CART_KEY, TOKEN_KEY } from "./constants.js";

export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
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
}

export async function api(path, { method = "GET", body, headers = {} } = {}) {
  const token = getToken();
  const res = await fetch(API + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = typeof data.detail === "string" ? data.detail : "Something went wrong — please try again";
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return data;
}
