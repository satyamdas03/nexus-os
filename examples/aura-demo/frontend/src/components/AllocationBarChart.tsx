"use client";

import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";
import type { Holding, Mandate, RulesResult } from "@/lib/types";
import { api } from "@/lib/api";
import { metricForAssetClass } from "@/lib/explainMetric";
import { Panel } from "@/components/ui/Panel";

const PALETTE = ["#0F172A", "#334155", "#64748B", "#94A3B8", "#CBD5E1", "#E2E8F0"];

export function AllocationBarChart({ holdings, clientId, mandate, rulesResult }: {
  holdings: Holding[];
  clientId?: string;
  mandate?: Mandate;
  rulesResult?: RulesResult;
}) {
  const [explain, setExplain] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const by: Record<string, number> = {};
  for (const h of holdings) by[h.asset_class] = (by[h.asset_class] || 0) + h.market_value;
  const data = Object.entries(by)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const top = data[0];

  const offending = new Set<string>();
  if (rulesResult) {
    for (const b of rulesResult.breaches) {
      if (b.rule.startsWith("max_asset_class_weight:")) offending.add(b.rule.split(":")[1]);
    }
    for (const w of rulesResult.watches) {
      if (w.rule.startsWith("drift:")) offending.add(w.rule.split(":")[1]);
    }
  }

  const explainTop = async () => {
    if (!clientId || !top) return;
    setLoading(true);
    try {
      const metric = metricForAssetClass(rulesResult, top.name);
      const r = await api.explain(clientId, metric ?? undefined);
      setExplain(r.narrative);
    } catch {
      setExplain("Explain unavailable");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel header="Allocation Profile" subheader="Current vs mandate" right={clientId && (
      <button onClick={explainTop} disabled={loading} className="inline-flex items-center gap-1 font-mono text-xs text-aura-navy hover:underline disabled:opacity-50">
        {loading && (
          <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
        )}
        {loading ? "Asking..." : "Explain"}
      </button>
    )}>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 40, bottom: 0 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", fill: "#334155" }} axisLine={{ stroke: "#CBD5E1" }} tickLine={false} />
            <Tooltip
              cursor={{ fill: "#F1F5F9" }}
              contentStyle={{ backgroundColor: "#FFFFFF", border: "1px solid #CBD5E1", borderRadius: "4px", fontSize: "12px", fontFamily: "JetBrains Mono, monospace" }}
              formatter={(value: number) => [`${((value / total) * 100).toFixed(1)}%`, "Weight"]}
              labelFormatter={() => ""}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {data.map((d, i) => (
                <Cell key={i} fill={offending.has(d.name) ? "#DC2626" : PALETTE[i % PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {explain && (
        <div className="mt-3 bg-aura-surface border border-aura-border rounded p-3 font-mono text-xs text-aura-text-muted">
          <span className="text-aura-navy">AI Explain:</span> {explain}
        </div>
      )}
      <div className="mt-4 grid grid-cols-2 gap-2 font-mono text-xs text-aura-text-muted">
        {data.map((d, i) => {
          const cap = mandate?.max_asset_class_weight?.[d.name];
          return (
            <div key={d.name} className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: offending.has(d.name) ? "#DC2626" : PALETTE[i % PALETTE.length] }} />
              <span className={offending.has(d.name) ? "text-aura-crimson font-medium" : i === 0 ? "text-aura-navy font-medium" : ""}>
                {d.name} ({((d.value / total) * 100).toFixed(0)}%{cap ? `/${(cap * 100).toFixed(0)}%` : ""})
              </span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
