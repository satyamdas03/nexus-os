import { TopMetricCard } from "@/components/ui/TopMetricCard";

export function SummaryBar({ counts, breach_count, total, totalFum }: {
  counts: Record<string, number>;
  breach_count: number;
  total: number;
  totalFum: number;
}) {
  const aligned = counts.green ?? 0;
  const alignedPct = total ? ((aligned / total) * 100).toFixed(1) : "0.0";
  const fumBillions = totalFum / 1e9;
  const fumLabel = fumBillions >= 1 ? `$${fumBillions.toFixed(2)}B` : `$${(totalFum / 1e6).toFixed(1)}M`;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <TopMetricCard label="Total Managed FUM" value={fumLabel} />
      <TopMetricCard label="Aligned" value={`${alignedPct}%`} sub={`${aligned} of ${total} portfolios`} tone="emerald" />
      <TopMetricCard label="Needs Attention" value={String(counts.orange ?? 0)} sub={`${counts.orange ?? 0} Portfolios`} tone="ochre" />
      <TopMetricCard label="Breached" value={String(counts.red ?? 0)} sub={`${breach_count} mandate breaches`} tone="crimson" />
    </div>
  );
}
