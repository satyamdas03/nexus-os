"use client";

// Command Centre live view. The heatmap colour is the at-a-glance signal Kevin
// reads after fixing a portfolio, so this component refetches the effective
// (post-trade) book state on mount, on window focus, and when the tab becomes
// visible again. That defeats the Next App Router client cache, which would
// otherwise serve a stale red RSC payload for ~30s after a soft-nav back.
//
// aiNarrative is advisory (and a slow Claude call) so it stays from SSR; only
// the deterministic counts + portfolio statuses — the things the heatmap paints
// from — are refreshed live.
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PortfolioSummary, TopSafeguard } from "@/lib/types";
import { Heatmap } from "@/components/Heatmap";
import { MarketPanel } from "@/components/MarketPanel";
import { SummaryBar } from "@/components/SummaryBar";
import { TriageQueue } from "@/components/TriageQueue";
import { AssuranceBanner } from "@/components/AssuranceBanner";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

type Summary = { total: number; counts: Record<string, number>; breach_count: number };

export function CommandCentreView({
  initialPortfolios,
  initialSummary,
  aiNarrative,
  initialTop,
  loading = false,
}: {
  initialPortfolios: PortfolioSummary[];
  initialSummary: Summary;
  aiNarrative?: string;
  initialTop?: TopSafeguard | null;
  loading?: boolean;
}) {
  const [ps, setPs] = useState<PortfolioSummary[]>(initialPortfolios);
  const [summary, setSummary] = useState<Summary>(initialSummary);
  const [top, setTop] = useState<TopSafeguard | null | undefined>(initialTop);
  const [syncing, setSyncing] = useState(false);

  const refresh = useCallback(async () => {
    setSyncing(true);
    try {
      const [p, s, t] = await Promise.all([
        api.listPortfolios(200, 0),
        api.summary(),
        api.portfoliosTop(200).catch(() => null),
      ]);
      setPs(p); setSummary(s); setTop(t);
    } catch {
      // keep last-known state; AppShell already shows a LIVE indicator
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    // Fresh effective state the moment Kevin lands on / returns to Command Centre.
    refresh();
    const onFocus = () => refresh();
    const onVisibility = () => { if (document.visibilityState === "visible") refresh(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [refresh]);

  // When the market is running, MarketPanel polls the clock; on each clock
  // change it calls onTick so the heatmap + summary re-fetch post-drift state.
  const onTick = useCallback(() => { refresh(); }, [refresh]);

  const heatmapPortfolios = top ? top.top : ps;
  const rest = top ? top.rest : undefined;
  const totalFum = heatmapPortfolios.reduce((s, p) => s + p.fum, 0) + (rest?.fum ?? 0);

  return (
    <div className="p-4 lg:p-6 max-w-[1440px] mx-auto">
      <div className="mb-6">
        <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">Command Centre</p>
        <h1 className="font-mono text-2xl font-bold text-aura-text">Global Portfolio Assurance</h1>
      </div>
      {loading ? (
        <LoadingSkeleton label="Loading Command Centre data…">
          <div className="h-20 bg-aura-surface-low border border-aura-border rounded animate-pulse" />
          <div className="h-16 bg-aura-surface-low border border-aura-border rounded animate-pulse" />
          <div className="h-12 bg-aura-surface-low border border-aura-border rounded animate-pulse" />
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 xl:col-span-9 h-[500px] bg-aura-surface-low border border-aura-border rounded animate-pulse" />
            <div className="lg:col-span-4 xl:col-span-3 h-[500px] bg-aura-surface-low border border-aura-border rounded animate-pulse" />
          </div>
        </LoadingSkeleton>
      ) : (
        <>
          <AssuranceBanner summary={summary} aiNarrative={aiNarrative} />
          <MarketPanel onTick={onTick} />
          <SummaryBar
            counts={summary.counts}
            breach_count={summary.breach_count}
            total={summary.total}
            totalFum={totalFum}
          />
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 xl:col-span-9">
              <Heatmap portfolios={heatmapPortfolios} syncing={syncing} rest={rest} />
            </div>
            <div className="lg:col-span-4 xl:col-span-3">
              <TriageQueue portfolios={heatmapPortfolios} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}