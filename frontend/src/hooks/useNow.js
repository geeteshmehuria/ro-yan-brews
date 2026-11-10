import { useEffect, useState } from "react";

// The current time, re-rendering every 30 s so "12 min ago" (and anything timed off it) stays true.
export function useNow(ms = 30000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), ms); return () => clearInterval(t); }, [ms]);
  return now;
}
