import { useCallback, useEffect, useState } from "react";

import { api } from "../api.js";

const RANGES = [7, 30];
const rupees = (n) => `₹${n.toLocaleString("en-IN")}`;
const dayLabel = (iso, many) => {
  const d = new Date(`${iso}T00:00:00`);
  return many ? String(d.getDate()) : d.toLocaleDateString([], { weekday: "short" });
};
const hourLabel = (h) => `${h % 12 || 12}${h < 12 ? "am" : "pm"}`;

function Stat({ value, label, tone = "text-accent" }) {
  return (
    <div className="glass p-3 text-center">
      <b className={`block text-xl ${tone}`}>{value}</b>
      <small className="text-xs text-muted">{label}</small>
    </div>
  );
}

// Plain CSS bars: tallest = full height. `title` shows the exact figure on hover / long-press.
function Bars({ values, labels, format, highlightLast = false }) {
  const max = Math.max(1, ...values);
  return (
    <div className="flex h-36 items-end gap-1" role="img"
      aria-label={values.map((v, i) => `${labels[i]}: ${format(v)}`).join(", ")}>
      {values.map((v, i) => (
        <div key={i} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end" title={`${labels[i]}: ${format(v)}`}>
          <div className={`w-full rounded-t-md ${highlightLast && i === values.length - 1 ? "bg-accent2" : "bg-accent"} ${v ? "" : "opacity-20"}`}
            style={{ height: `${Math.max(v ? 4 : 2, (v / max) * 100)}%` }} />
          <span className="mt-1 w-full truncate text-center text-[10px] text-muted">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}

// The owner's "Today" tab: today's numbers, then the last 7 or 30 days. Loaded each time it's opened.
export default function TodaySection() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    api(`/api/admin/reports?days=${days}`).then(setData).catch((e) => setErr(e.message));
  }, [days]);
  useEffect(() => { load(); }, [load]);

  if (err) {
    return (
      <div className="glass mt-5 p-5 text-center">
        <p className="text-sm text-danger">{err}</p>
        <button onClick={load} className="press mt-3 rounded-xl bg-accent px-5 py-2 font-bold text-bg1">Try again</button>
      </div>
    );
  }
  if (!data) return <p className="glass mt-5 p-5 text-center text-muted">Loading…</p>;

  const t = data.today, p = data.period;
  const many = data.daily.length > 10;
  const busiest = data.hours.map((n, h) => [h, n]).filter(([, n]) => n > 0);
  // the hours with any orders, from the first to the last (a stall's open hours)
  const first = busiest.length ? busiest[0][0] : 0, last = busiest.length ? busiest[busiest.length - 1][0] : 0;
  const hourRange = busiest.length ? data.hours.slice(first, last + 1) : [];
  const peak = busiest.reduce((best, cur) => (cur[1] > best[1] ? cur : best), [0, 0]);

  return (
    <>
      <h2 className="mb-2.5 mt-5 px-1 font-black text-accent">Today</h2>
      <div className="grid grid-cols-3 gap-2.5">
        <Stat value={rupees(t.cash)} label="Cash collected" tone="text-accent2" />
        <Stat value={t.completed} label="Orders done" />
        <Stat value={t.completed ? rupees(t.average) : "—"} label="Average order" />
      </div>
      <div className="glass mt-2.5 grid grid-cols-4 divide-x divide-[var(--stroke)] py-2.5 text-center text-sm">
        <div><b className="block">{t.orders}</b><small className="text-muted">Placed</small></div>
        <div><b className="block">{t.in_progress}</b><small className="text-muted">In progress</small></div>
        <div><b className={`block ${t.cancelled ? "text-danger" : ""}`}>{t.cancelled}</b><small className="text-muted">Cancelled</small></div>
        <div><b className={`block ${t.not_collected ? "text-warn" : ""}`}>{t.not_collected}</b><small className="text-muted">Not collected</small></div>
      </div>

      <div className="mb-2.5 mt-6 flex items-center justify-between px-1">
        <h2 className="font-black text-accent">Last {data.days} days</h2>
        <div className="flex gap-1.5" role="tablist" aria-label="Report period">
          {RANGES.map((r) => (
            <button key={r} role="tab" aria-selected={days === r} onClick={() => setDays(r)}
              className={`press rounded-full border px-3 py-1.5 text-sm font-bold ${
                days === r ? "border-transparent bg-accent text-bg1" : "border-[var(--stroke)] text-muted"}`}>
              {r} days
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2.5">
        <Stat value={rupees(p.cash)} label="Cash" tone="text-accent2" />
        <Stat value={p.orders} label="Orders" />
        <Stat value={p.completed ? rupees(p.average) : "—"} label="Average order" />
      </div>

      <div className="glass mt-2.5 p-4">
        <div className="mb-3 text-xs font-black uppercase tracking-wider text-muted">Cash per day</div>
        <Bars values={data.daily.map((d) => d.cash)} labels={data.daily.map((d) => dayLabel(d.date, many))}
          format={rupees} highlightLast />
        {p.cash === 0 && <p className="mt-2 text-center text-sm text-muted">No orders marked Done yet in these days</p>}
      </div>

      <div className="glass mt-2.5 p-4">
        <div className="mb-1 text-xs font-black uppercase tracking-wider text-muted">Best sellers (orders done)</div>
        {data.top_items.length === 0 && <p className="py-2 text-sm text-muted">Nothing sold yet in these days</p>}
        {data.top_items.map((i, n) => (
          <div key={i.name} className="flex items-baseline justify-between gap-3 border-b border-[var(--stroke)] py-2.5 last:border-0">
            <div className="min-w-0">
              <b className="text-accent">{n + 1}.</b> <b className="break-words">{i.name}</b>
              <div className="text-xs text-muted">
                {i.qty} sold{i.half > 0 && ` · ${i.half} half, ${i.qty - i.half} full`}
              </div>
            </div>
            <b className="whitespace-nowrap text-accent2">{rupees(i.value)}</b>
          </div>
        ))}
      </div>

      <div className="glass mt-2.5 p-4">
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <span className="text-xs font-black uppercase tracking-wider text-muted">Busiest hours</span>
          {peak[1] > 0 && <span className="text-xs text-muted">peak {hourLabel(peak[0])}–{hourLabel((peak[0] + 1) % 24)}</span>}
        </div>
        {hourRange.length > 0
          ? <Bars values={hourRange} labels={hourRange.map((_, i) => hourLabel(first + i))} format={(v) => `${v} ${v === 1 ? "order" : "orders"}`} />
          : <p className="text-sm text-muted">No orders yet in these days</p>}
      </div>
    </>
  );
}
