"use client";

import type { Trade, Portfolio } from "@/lib/types";
import { Panel } from "@/components/ui/Panel";
import { SecondaryButton } from "@/components/ui/SecondaryButton";

export function WorkbenchTable({
  trades,
  portfolio,
  editable = false,
  onTradesChange,
}: {
  trades: Trade[];
  portfolio?: Portfolio;
  editable?: boolean;
  onTradesChange?: (t: Trade[]) => void;
}) {
  const holdingsTotal = portfolio?.holdings.reduce((s, h) => s + h.market_value, 0) || 0;
  const bookTotal = holdingsTotal + (portfolio?.cash ?? 0);

  const priceFor = (t: Trade): number => {
    if (t.units && t.value) return t.value / t.units;
    const h = portfolio?.holdings.find((x) => x.ticker === t.ticker);
    return h?.price ?? 0;
  };

  const updateUnits = (i: number, units: number) => {
    if (!onTradesChange) return;
    const next = trades.map((t, idx) => {
      if (idx !== i) return t;
      const price = priceFor(t);
      return { ...t, units, value: Math.round(units * price * 100) / 100 };
    });
    onTradesChange(next);
  };

  const updateValue = (i: number, value: number) => {
    if (!onTradesChange) return;
    const next = trades.map((t, idx) => {
      if (idx !== i) return t;
      const price = priceFor(t);
      const units = price ? value / price : 0;
      return { ...t, value, units: Math.round(units * 1e6) / 1e6 };
    });
    onTradesChange(next);
  };

  const csvCell = (v: string | number) => {
    const s = String(v ?? "");
    if (/[",\n\r]|^\s+|\s+$/.test(s)) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };

  const exportCsv = () => {
    const header = ["ticker", "action", "units", "value_usd", "rationale"];
    const rows = trades.map((t) => [
      csvCell(t.ticker),
      csvCell(t.action),
      csvCell(t.units),
      csvCell(t.value),
      csvCell(t.rationale || ""),
    ]);
    const csv = [header.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "proposed_trades.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Panel
      data-tour="trades"
      header="Flagged Ledger Entries"
      right={
        <div className="flex items-center gap-3">
          {editable && (
            <span className="font-mono text-xs text-aura-ochre flex items-center gap-1">
              <span className="material-symbols-outlined text-[16px]">edit</span>Editable - re-verified live
            </span>
          )}
          {trades.length > 0 && (
            <SecondaryButton onClick={exportCsv} className="flex items-center gap-1 px-3 py-1">
              <span className="material-symbols-outlined text-[16px]">download</span>Export CSV
            </SecondaryButton>
          )}
        </div>
      }
    >
      <div className="overflow-x-auto -m-4 p-4">
        <table className="w-full text-left border-collapse">
          <thead className="bg-aura-surface border-b border-aura-border">
            <tr>
              <th className="py-3 px-3 font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold">Holding</th>
              <th className="py-3 px-3 font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold text-right">Trade Wgt %</th>
              <th className="py-3 px-3 font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold">Proposed Action</th>
              <th className="py-3 px-3 font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold text-right">Units</th>
              <th className="py-3 px-3 font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold text-right">Value (USD)</th>
            </tr>
          </thead>
          <tbody className="font-mono text-sm text-aura-text divide-y divide-aura-border">
            {trades.map((t, i) => {
              const isSell = t.action === "sell";
              const isBuy = t.action === "buy";
              const tradeWgt = bookTotal ? ((t.value / bookTotal) * 100).toFixed(1) : "0.0";
              const actionChip = isSell
                ? "bg-aura-crimson-soft border-aura-crimson text-aura-crimson"
                : isBuy
                ? "bg-aura-emerald-soft border-aura-emerald text-aura-emerald"
                : "bg-aura-ochre-soft border-aura-ochre text-aura-ochre";
              return (
                <tr key={i} className="hover:bg-aura-surface transition-colors group even:bg-aura-surface-low">
                  <td className="py-3 px-3 flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-aura-surface border border-aura-border flex items-center justify-center font-bold text-[12px] text-aura-navy">
                      {t.ticker.slice(0, 2)}
                    </div>
                    <div>
                      <div>{t.ticker}</div>
                      <div className="text-[12px] text-aura-text-muted">{isSell ? "Reduce position" : isBuy ? "Add to position" : "Hold position"}</div>
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right tabular-nums">{tradeWgt}%</td>
                  <td className="py-3 px-3">
                    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[12px] font-medium border ${actionChip}`}>
                      <span className="material-symbols-outlined text-[14px]">
                        {isSell ? "arrow_downward" : isBuy ? "add" : "pause"}
                      </span>
                      {isSell ? "SELL" : isBuy ? "BUY" : "HOLD"}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right tabular-nums">
                    {editable ? (
                      <input
                        type="number"
                        min={0}
                        step={0.01}
                        value={t.units}
                        onChange={(e) => updateUnits(i, Math.max(0, parseFloat(e.target.value) || 0))}
                        className="w-24 bg-white border border-aura-border rounded px-2 py-1 text-right text-aura-text focus:border-aura-navy focus:outline-none"
                      />
                    ) : (
                      t.units.toLocaleString()
                    )}
                  </td>
                  <td className="py-3 px-3 text-right tabular-nums text-aura-emerald font-medium">
                    {editable ? (
                      <input
                        type="number"
                        min={0}
                        step={1}
                        value={Math.round(t.value)}
                        onChange={(e) => updateValue(i, Math.max(0, parseFloat(e.target.value) || 0))}
                        className="w-28 bg-white border border-aura-border rounded px-2 py-1 text-right text-aura-emerald font-medium focus:border-aura-navy focus:outline-none"
                      />
                    ) : isSell ? (
                      `(${(t.value / 1e3).toFixed(0)}k)`
                    ) : (
                      `+$${(t.value / 1e3).toFixed(0)}k`
                    )}
                  </td>
                </tr>
              );
            })}
            {trades.length === 0 && (
              <tr>
                <td colSpan={5} className="py-8 text-center font-mono text-xs text-aura-text-muted">
                  No trades proposed - click "Propose a fix"
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
