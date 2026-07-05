"use client";

import Link from "next/link";
import type { PortfolioSummary } from "@/lib/types";

export function TriageQueue({ portfolios }: { portfolios: PortfolioSummary[] }) {
  const urgent = portfolios
    .filter((p) => p.status === "red" || p.status === "orange")
    .sort((a, b) => {
      const order: Record<string, number> = { red: 0, orange: 1, green: 2 };
      return order[a.status] - order[b.status] || b.fum - a.fum;
    });

  return (
    <div className="bg-aura-surface-low border border-aura-border rounded h-full flex flex-col" data-tour="triage">
      <div className="p-4 border-b border-aura-border flex items-center justify-between bg-aura-surface">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-aura-crimson text-[20px]">emergency</span>
          <h2 className="font-mono text-lg font-semibold text-aura-text">Urgent Triage</h2>
        </div>
        <span className="bg-aura-crimson-soft border border-aura-crimson text-aura-crimson text-[12px] px-2 py-0.5 rounded font-mono font-bold">
          {urgent.filter((p) => p.status === "red").length} Critical
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2 max-h-[420px] lg:max-h-none">
        {urgent.map((p) => {
          const isRed = p.status === "red";
          return (
            <Link
              key={p.client_id}
              href={`/portfolio/${p.client_id}`}
              className={`relative p-3 border-l-4 border-r border-y border-aura-border rounded transition-all cursor-pointer group hover:bg-aura-surface ${
                isRed ? "border-l-aura-crimson bg-aura-crimson-soft/50" : "border-l-aura-ochre bg-aura-ochre-soft/30"
              }`}
            >
              <div className="flex justify-between items-start mb-1">
                <h4 className="font-mono font-bold text-aura-text group-hover:text-aura-navy transition-colors line-clamp-1">
                  {p.client_name}
                </h4>
                <span
                  className={`font-mono text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0 border ${
                    isRed
                      ? "bg-aura-crimson-soft border-aura-crimson text-aura-crimson"
                      : "bg-aura-ochre-soft border-aura-ochre text-aura-ochre"
                  }`}
                >
                  {isRed ? "Critical" : "Attention"}
                </span>
              </div>
              <div className="font-mono text-xs text-aura-text-muted tabular-nums mb-2">${(p.fum / 1e6).toFixed(1)}M FUM // ID_{p.client_id}</div>
              {p.top_reason && (
                <p className="font-mono text-xs leading-tight border-l-2 pl-2 text-aura-text-muted border-aura-border-strong">
                  {p.top_reason}
                </p>
              )}
            </Link>
          );
        })}
      </div>
      <div className="p-3 border-t border-aura-border bg-aura-surface">
        <Link
          href="/hermes"
          className="block w-full py-2 bg-aura-surface-low border border-aura-border text-aura-navy font-mono text-sm rounded hover:border-aura-navy hover:bg-aura-surface transition-all text-center"
        >
          View all ({urgent.length})
        </Link>
      </div>
    </div>
  );
}
