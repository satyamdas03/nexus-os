// frontend/src/components/MarketPanel.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import type { MarketClock, MarketHistoryPoint } from "@/lib/types";
import { useMutationGuard } from "@/components/auth/useMutationGuard";

const COLOR = { green: "#10B981", orange: "#D97706", red: "#DC2626" };

export function MarketPanel({ onTick }: { onTick?: () => void }) {
  const [clock, setClock] = useState<MarketClock | null>(null);
  const [hist, setHist] = useState<MarketHistoryPoint[]>([]);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [advN, setAdvN] = useState(5);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastDay = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, h, p] = await Promise.all([api.market.clock(), api.market.history(), api.market.prices()]);
      setClock(c);
      setHist(h);
      setPrices(p ?? {});
      setErr(null);
      if (lastDay.current != null && lastDay.current !== c.day) onTick?.();
      lastDay.current = c.day;
    } catch (e) {
      setErr(String((e as Error).message ?? "market API error"));
    }
  }, [onTick]);

  useEffect(() => {
    load();
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  useEffect(() => {
    if (clock?.running) {
      pollRef.current = setInterval(load, Math.max(1000, (clock.auto_interval_sec || 5) * 1000));
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [clock?.running, clock?.auto_interval_sec, load]);

  const act = async (fn: () => Promise<MarketClock>) => {
    setBusy(true); setErr(null);
    try { await fn(); } finally { setBusy(false); await load(); }
  };

  const priceEntries = Object.entries(prices).slice(0, 12);
  const guard = useMutationGuard();

  return (
    <div className="bg-aura-surface-low border border-aura-border rounded p-4 flex flex-col gap-3 mb-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-aura-navy">schedule</span>
          <h2 className="font-mono text-lg font-semibold text-aura-text">Market Simulation</h2>
        </div>
        <div className="font-mono text-xs text-aura-text-muted">
          Day <span className="text-aura-navy font-bold">{clock?.day ?? "—"}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button disabled={busy || guard.disabled} title={guard.title} onClick={() => act(() => api.market.tick())}
          className="inline-flex items-center gap-1 px-3 py-1 font-mono text-xs border border-aura-navy text-aura-navy rounded hover:bg-aura-surface disabled:opacity-40 transition">
          {busy && <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>}
          Tick
        </button>
        <button disabled={busy || guard.disabled} title={guard.title} onClick={() => act(() => api.market.autorun(!(clock?.running)))}
          className="inline-flex items-center gap-1 px-3 py-1 font-mono text-xs border border-aura-border text-aura-text rounded hover:border-aura-navy transition">
          {busy && <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>}
          {clock?.running ? "Pause" : "Auto-run"}
        </button>
        <button disabled={busy || guard.disabled} title={guard.title} onClick={() => act(() => api.market.autofix(!(clock?.auto_fix)))}
          className={`inline-flex items-center gap-1 px-3 py-1 font-mono text-xs border rounded ${clock?.auto_fix ? "border-aura-emerald text-aura-emerald" : "border-aura-border text-aura-text-muted"} hover:border-aura-emerald transition disabled:opacity-40`}>
          {busy && <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>}
          Auto-fix {clock?.auto_fix ? "on" : "off"}
        </button>
        <div className="flex items-center gap-1 ml-auto">
          <input type="number" min={1} max={50} value={advN}
            onChange={(e) => setAdvN(Math.max(1, Math.min(50, Number(e.target.value))))}
            className="w-16 bg-white border border-aura-border text-aura-text font-mono text-xs px-2 py-1 rounded" />
          <button disabled={busy || guard.disabled} title={guard.title} onClick={() => act(() => api.market.advance(advN))}
            className="inline-flex items-center gap-1 px-3 py-1 font-mono text-xs border border-aura-border text-aura-text rounded hover:border-aura-navy transition"
          >
            {busy && <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>}
            Advance
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 bg-aura-surface border border-aura-border rounded px-3 py-2">
        {priceEntries.length === 0 && <span className="font-mono text-xs text-aura-text-muted">no prices</span>}
        {priceEntries.map(([t, px]) => (
          <span key={t} className="font-mono text-xs">
            <span className="text-aura-text-muted">{t}</span>{" "}
            <span className="text-aura-text">${px.toFixed(2)}</span>
          </span>
        ))}
      </div>

      {err && (
        <div className="font-mono text-xs text-aura-crimson bg-aura-crimson-soft border border-aura-crimson rounded px-3 py-2">
          Market API error: {err}
        </div>
      )}

      <div className="h-[160px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={hist}>
            <defs>
              <linearGradient id="gGreen" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={COLOR.green} stopOpacity={0.3} />
                <stop offset="95%" stopColor={COLOR.green} stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <XAxis dataKey="day" stroke="#94A3B8" tick={{ fill: "#64748B", fontSize: 11 }} />
            <YAxis stroke="#94A3B8" tick={{ fill: "#64748B", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #CBD5E1", borderRadius: "4px", fontSize: 11 }} />
            <Area type="monotone" dataKey="green" stackId="1" stroke={COLOR.green} fill="url(#gGreen)" fillOpacity={1} />
            <Area type="monotone" dataKey="orange" stackId="1" stroke={COLOR.orange} fill={COLOR.orange} fillOpacity={0.25} />
            <Area type="monotone" dataKey="red" stackId="1" stroke={COLOR.red} fill={COLOR.red} fillOpacity={0.25} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="font-mono text-xs text-aura-text-muted italic">
        Green / orange / red counts × day — drift emergence as prices move
      </div>
    </div>
  );
}
