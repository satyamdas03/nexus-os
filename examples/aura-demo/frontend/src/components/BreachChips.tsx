"use client";

import { useRef, useState } from "react";
import { clsx } from "clsx";
import type { Breach } from "@/lib/types";
import { api } from "@/lib/api";

export function BreachChips({
  items,
  onPick,
  clientId,
}: {
  items: Breach[];
  onPick: (tickers: string[]) => void;
  clientId?: string;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [explainFor, setExplainFor] = useState<string | null>(null);
  const [explainText, setExplainText] = useState<string>("");
  const [loadingExplain, setLoadingExplain] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  if (!items.length) return null;

  const askExplain = async (b: Breach) => {
    if (!clientId) return;
    if (explainFor === b.rule) {
      setExplainFor(null);
      abortRef.current?.abort();
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setExplainFor(b.rule);
    setLoadingExplain(true);
    setExplainText("");
    try {
      const r = await api.explain(clientId, b.rule, controller.signal);
      if (!controller.signal.aborted) setExplainText(r.narrative);
    } catch {
      if (!controller.signal.aborted) setExplainText("Explain unavailable");
    } finally {
      if (!controller.signal.aborted) setLoadingExplain(false);
    }
  };

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {items.map((b) => {
        const isRed = b.severity === "red";
        const selected = active === b.rule;
        return (
          <div key={b.rule} className="relative flex flex-col">
            <div className={clsx(
              "flex items-center gap-2 px-3 py-1.5 rounded font-mono text-xs transition-all border",
              isRed
                ? "bg-aura-crimson-soft border-aura-crimson text-aura-crimson hover:border-aura-crimson"
                : "bg-aura-ochre-soft border-aura-ochre text-aura-ochre hover:border-aura-ochre",
              selected && "ring-1 ring-aura-navy ring-offset-1 ring-offset-aura-background"
            )}>
              <button
                onClick={() => {
                  const next = selected ? null : b.rule;
                  setActive(next);
                  onPick(next ? b.offending_holdings : []);
                }}
                className="flex items-center gap-2 focus:outline-none"
              >
                <span className="material-symbols-outlined text-[16px]">
                  {isRed ? "pie_chart" : "warning"}
                </span>
                <span>{b.plain}</span>
              </button>
              {clientId && (
                <button
                  onClick={() => askExplain(b)}
                  disabled={loadingExplain}
                  className="ml-1 inline-flex items-center gap-1 underline decoration-current/30 hover:decoration-current transition-colors focus:outline-none focus:ring-1 focus:ring-current rounded disabled:opacity-60"
                  aria-label={`Explain ${b.rule}`}
                >
                  {loadingExplain && explainFor === b.rule && (
                    <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
                  )}
                  Explain
                </button>
              )}
            </div>
            {clientId && explainFor === b.rule && (
              <div className="absolute top-full left-0 mt-1 z-20 max-w-xs bg-aura-surface border border-aura-border rounded p-3 font-mono text-xs text-aura-text-muted shadow-aura-md">
                <span className="text-aura-navy">AI Explain [{b.rule}]:{" "}</span>
                {loadingExplain ? (
                  <span className="inline-flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
                    Asking...
                  </span>
                ) : (
                  explainText
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
