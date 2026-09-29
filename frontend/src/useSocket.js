import { useEffect, useRef } from "react";

import { WS_BASE } from "./api.js";

/**
 * JSON WebSocket that reconnects after drops (e.g. the free-tier backend waking up).
 * `path` like "/ws/menu"; pass null to stay disconnected. `onReconnect` fires after every
 * re-connection (not the first) so callers can refetch anything they missed meanwhile.
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
      ws.onclose = () => { if (!closed) timer = setTimeout(connect, 3000); };
    };
    connect();
    return () => { closed = true; clearTimeout(timer); ws.close(); };
  }, [path]);
}
