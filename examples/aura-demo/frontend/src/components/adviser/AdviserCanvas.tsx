"use client";

import { AdviserWhiteboard } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

export function AdviserCanvas({ whiteboard }: { whiteboard: AdviserWhiteboard }) {
  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-lg font-bold text-aura-text">{whiteboard.client_name}</h3>
        <StatusBadge status={whiteboard.current_status} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <p className="font-mono text-xs uppercase text-aura-text-subtle">Current breaches</p>
          {whiteboard.breaches.length === 0 && (
            <p className="font-mono text-xs text-aura-text-muted">No breaches detected.</p>
          )}
          {whiteboard.breaches.map((b) => (
            <div
              key={b.rule}
              className="p-2 rounded bg-aura-crimson-soft border border-aura-crimson text-aura-crimson text-xs font-mono"
            >
              <span className="font-bold">{b.rule}</span>: {b.explanation}
            </div>
          ))}
        </div>

        <div className="space-y-2">
          <p className="font-mono text-xs uppercase text-aura-text-subtle">Proposed fix</p>
          {whiteboard.proposed_trades.length === 0 && (
            <p className="font-mono text-xs text-aura-text-muted">No trades proposed.</p>
          )}
          {whiteboard.proposed_trades.map((t) => (
            <div
              key={t.ticker}
              className="p-2 rounded bg-aura-emerald-soft border border-aura-emerald text-aura-emerald text-xs font-mono"
            >
              {t.action.toUpperCase()} {t.units.toFixed(2)} {t.ticker} · ${t.value.toLocaleString()}
            </div>
          ))}
          <div className="flex items-center gap-2 pt-2">
            <span className="font-mono text-xs text-aura-text-subtle">Post-status:</span>
            <StatusBadge status={whiteboard.post_status} />
          </div>
        </div>
      </div>
    </div>
  );
}
