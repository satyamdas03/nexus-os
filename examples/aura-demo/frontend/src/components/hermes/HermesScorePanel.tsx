"use client";

import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";
import { Panel } from "@/components/ui/Panel";
import { TopMetricCard } from "@/components/ui/TopMetricCard";
import type { HermesHeartbeat } from "@/lib/types";

const PRIOR_KEY = "hermes:composite:prior";

export function HermesScorePanel({ heartbeat }: { heartbeat: HermesHeartbeat | null }) {
  const [prior, setPrior] = useState<number | null>(null);
  const lastSeen = useRef<number | null>(null);

  // Track last-known composite across scans for trend delta.
  useEffect(() => {
    if (typeof window !== "undefined") {
      const raw = window.localStorage.getItem(PRIOR_KEY);
      if (raw != null) {
        const n = Number(raw);
        if (!Number.isNaN(n)) setPrior(n);
      }
    }
  }, []);

  useEffect(() => {
    const composite = heartbeat?.score?.composite;
    if (heartbeat && !heartbeat.stale && typeof composite === "number") {
      if (lastSeen.current != null && lastSeen.current !== composite) {
        setPrior(lastSeen.current);
        if (typeof window !== "undefined") window.localStorage.setItem(PRIOR_KEY, String(lastSeen.current));
      }
      lastSeen.current = composite;
    }
  }, [heartbeat]);

  if (!heartbeat || heartbeat.stale) {
    return (
      <Panel header="Book Score">
        <p className="font-mono text-sm text-aura-text-muted">
          {heartbeat?.message ?? "Run a scan to score the book."}
        </p>
      </Panel>
    );
  }

  const c = heartbeat.counts;
  const s = heartbeat.score;

  const compositeTone =
    s.composite >= 0.7 ? "text-aura-emerald" : s.composite >= 0.45 ? "text-aura-ochre" : "text-aura-crimson";

  let trend:
    | { label: string; tone: "muted" }
    | { arrow: string; label: string; tone: "emerald" | "crimson" | "muted" };
  if (prior == null) {
    trend = { label: "baseline", tone: "muted" };
  } else {
    const delta = s.composite - prior;
    const pct = (delta * 100).toFixed(1);
    if (delta > 0.0005) trend = { arrow: "↑", tone: "emerald", label: `+${pct}` };
    else if (delta < -0.0005) trend = { arrow: "↓", tone: "crimson", label: `${pct}` };
    else trend = { arrow: "—", tone: "muted", label: "0.0" };
  }

  const trendToneClass =
    trend.tone === "emerald"
      ? "text-aura-emerald"
      : trend.tone === "crimson"
      ? "text-aura-crimson"
      : "text-aura-text-subtle";

  return (
    <Panel
      header="Book Score"
      right={
        <div className="flex items-end gap-3">
          {"arrow" in trend && (
            <span className={clsx("font-mono text-xs pb-1", trendToneClass)}>
              {trend.arrow} {trend.label}{" "}
              <span className="text-aura-text-subtle">vs last scan</span>
            </span>
          )}
          <span className={clsx("font-mono text-3xl font-bold tabular-nums", compositeTone)}>
            {(s.composite * 100).toFixed(0)}
          </span>
        </div>
      }
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <TopMetricCard label="Alignment" value={`${(s.alignment_rate * 100).toFixed(0)}%`} tone="emerald" />
        <TopMetricCard label="Acceptance" value={`${(s.acceptance_rate * 100).toFixed(0)}%`} tone="emerald" />
        <TopMetricCard label="Avg Trades/Fix" value={s.avg_trades_per_fix.toFixed(1)} />
        <TopMetricCard
          label="Breaches Left"
          value={String(s.breaches_remaining)}
          tone={s.breaches_remaining ? "ochre" : "emerald"}
        />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <TopMetricCard label="Scanned" value={String(c.scanned)} />
        <TopMetricCard label="Green" value={String(c.green)} tone="emerald" />
        <TopMetricCard label="Remediated" value={String(c.remediated)} tone="emerald" />
        <TopMetricCard label="Missed" value={String(c.missed)} tone={c.missed ? "crimson" : "neutral"} />
        <TopMetricCard label="Skipped" value={String(c.skipped)} />
      </div>
    </Panel>
  );
}
