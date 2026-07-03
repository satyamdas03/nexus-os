"use client";

import { useRef, useState, Fragment } from "react";
import { clsx } from "clsx";
import type { Holding, RulesResult } from "@/lib/types";
import { api } from "@/lib/api";
import { metricForHolding } from "@/lib/explainMetric";
import { Panel } from "@/components/ui/Panel";

export function HoldingsTable({ holdings, cash, highlight = [], clientId, rulesResult }: {
  holdings: Holding[];
  cash: number;
  highlight?: string[];
  clientId?: string;
  rulesResult?: RulesResult;
}) {
  const total = holdings.reduce((s, h) => s + h.market_value, 0) + cash;
  const [explainFor, setExplainFor] = useState<string | null>(null);
  const [explainText, setExplainText] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const metricFor = (h: Holding): string | undefined =>
    metricForHolding(rulesResult, h) ?? undefined;

  const ask = async (h: Holding) => {
    if (!clientId) return;
    if (explainFor === h.ticker) {
      setExplainFor(null);
      abortRef.current?.abort();
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const metric = metricFor(h);
    setExplainFor(h.ticker);
    setLoading(true);
    setExplainText("");
    try {
      const r = await api.explain(clientId, metric, controller.signal);
      if (!controller.signal.aborted) setExplainText(r.narrative);
    } catch {
      if (!controller.signal.aborted) setExplainText("Explain unavailable");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };

  return (
    <Panel
      header="Holdings Ledger"
      right={
        <span className="text-aura-text-muted font-mono text-xs flex items-center gap-1">
          <span className="material-symbols-outlined text-[16px]">info</span>
          click "?" to explain a metric
        </span>
      }
    >
      <div className="overflow-x-auto -m-4 p-4">
        <table className="w-full text-left font-mono text-sm">
          <thead className="bg-aura-surface border-b border-aura-border">
            <tr>
              <th className="px-3 py-2.5 text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold">Ticker</th>
              <th className="px-3 py-2.5 text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold">Name</th>
              <th className="px-3 py-2.5 text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold">Class</th>
              <th className="px-3 py-2.5 text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold text-right">Weight%</th>
              <th className="px-3 py-2.5 text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold text-right">Value USD</th>
              <th className="px-3 py-2.5 text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold text-center">State</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-aura-border">
            {holdings.map((h) => {
              const weight = (h.market_value / total) * 100;
              const isHighlighted = highlight.includes(h.ticker);
              return (
                <Fragment key={h.ticker}>
                  <tr
                    className={clsx(
                      "transition-colors group",
                      isHighlighted ? "bg-aura-crimson-soft" : "even:bg-aura-surface-low hover:bg-aura-surface"
                    )}
                  >
                    <td className={clsx(
                      "px-3 py-3 font-bold text-aura-text border-l-4",
                      isHighlighted ? "border-aura-crimson" : "border-transparent group-hover:border-aura-navy"
                    )}>{h.ticker}</td>
                    <td className="px-3 py-3 text-aura-text-muted text-xs">{h.name}</td>
                    <td className="px-3 py-3 text-aura-text-muted text-xs">
                      {h.asset_class}
                      {isHighlighted && (
                        <span className="material-symbols-outlined text-[14px] text-aura-crimson ml-1.5 align-text-bottom" title="Contributes to breach">
                          warning
                        </span>
                      )}
                    </td>
                    <td className={clsx("px-3 py-3 text-right tabular-nums", isHighlighted ? "font-bold text-aura-crimson" : "text-aura-text")}>
                      {weight.toFixed(1)}%
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-aura-text">${h.market_value.toLocaleString()}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <span
                          className={clsx(
                            "w-2.5 h-2.5 rounded-sm group-hover:scale-110 transition-transform",
                            isHighlighted ? "bg-aura-crimson" : "bg-aura-emerald"
                          )}
                          title={isHighlighted ? "Breach contributor" : "Compliant"}
                        />
                        {clientId && (
                          <button
                            onClick={() => ask(h)}
                            title="Explain this metric"
                            disabled={loading}
                            className="inline-flex items-center justify-center text-aura-navy/70 hover:text-aura-navy text-[12px] w-5 h-5 rounded border border-aura-border hover:border-aura-navy/50 transition-colors disabled:opacity-50"
                          >
                            ?
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {explainFor === h.ticker && (
                    <tr className="bg-aura-surface">
                      <td colSpan={6} className="px-3 py-3 border-b border-aura-border">
                        <div className="font-mono text-xs text-aura-text-muted">
                          <span className="text-aura-navy">AI Explain [{metricFor(h) ?? "summary"}]:{" "}</span>
                          {loading ? (
                            <span className="inline-flex items-center gap-1">
                              <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
                              Asking...
                            </span>
                          ) : (
                            explainText
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            <tr className="bg-aura-surface font-bold">
              <td className="px-3 py-3 text-aura-emerald" colSpan={4}>Cash Reserve</td>
              <td className="px-3 py-3 text-right tabular-nums text-aura-text">${cash.toLocaleString()}</td>
              <td className="px-3 py-3"></td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
