import { useEffect, useRef } from "react";

import { WS_BASE } from "../services/api.js";

/**
 * JSON WebSocket that reconnects after drops (e.g. the free-tier backend waking up).
 * `path` like "/ws/menu"; pass null to stay disconnected. `onReconnect` fires after every
 * re-connection (not the first) so callers can refetch anything they missed meanwhile, and
 * once when the server rejects the token (close 4401) — then it stops reconnecting.
 */
export function useSocket(path, onMessage, onReconnect) {
  const handlers = useRef({});
  handlers.current = { onMessage, onReconnect };

  useEffect(() => {
    if (!path) return;
    let ws, timer, opened = false, closed = false;
    const connect = () => {
      ws = new WebSocket(WS_BASE + path);
      ws.onopen = () => {
        if (opened) handlers.current.onReconnect?.();
        opened = true;
      };
      ws.onmessage = (ev) => handlers.current.onMessage(JSON.parse(ev.data));
      ws.onclose = (ev) => {
        if (closed) return;
        // 4401 = the login expired: retrying with the same token loops forever. Refetch instead;
        // the REST call's 401 makes the caller log out.
        if (ev.code === 4401) return handlers.current.onReconnect?.();
        timer = setTimeout(connect, 3000);
      };
    };
    connect();
    return () => { closed = true; clearTimeout(timer); ws.close(); };
  }, [path]);
}
