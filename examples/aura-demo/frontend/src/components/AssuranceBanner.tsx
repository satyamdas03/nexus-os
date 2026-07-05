export function AssuranceBanner({ summary, aiNarrative }: {
  summary: { total: number; counts: Record<string, number>; breach_count: number };
  aiNarrative?: string;
}) {
  const { green = 0, orange = 0, red = 0 } = summary.counts;
  const breach_count = summary.breach_count ?? 0;

  return (
    <div className="bg-aura-surface-low border border-aura-border rounded p-4 mb-6">
      <div className="flex items-start gap-4">
        <div className="p-2 bg-aura-navy rounded text-white flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined material-symbols-filled text-[20px]">fact_check</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h2 className="font-mono text-base font-bold text-aura-text">System Assurance Summary</h2>
            <span className="font-mono text-[10px] uppercase px-1.5 py-0.5 rounded border border-aura-emerald text-aura-emerald">AI-Grounded</span>
          </div>
          <div className="font-mono text-sm text-aura-text-muted space-y-1">
            <p>{summary.total} portfolios loaded // {green} aligned // {orange} attention // {red} breach.</p>
            <p>{breach_count} mandate breaches detected across {red} portfolios.</p>
            {aiNarrative && <p className="text-aura-text">AI summary: {aiNarrative}</p>}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatPill value={green} label="ALIGNED" tone="emerald" />
            <StatPill value={orange} label="ATTENTION" tone="ochre" />
            <StatPill value={red} label="BREACH" tone="crimson" />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatPill({ value, label, tone }: { value: number; label: string; tone: "emerald" | "ochre" | "crimson" }) {
  const map = {
    emerald: "border-aura-emerald text-aura-emerald bg-aura-emerald-soft",
    ochre: "border-aura-ochre text-aura-ochre bg-aura-ochre-soft",
    crimson: "border-aura-crimson text-aura-crimson bg-aura-crimson-soft",
  };
  return (
    <div className={`px-2.5 py-1 rounded border font-mono text-xs flex items-center gap-2 ${map[tone]}`}>
      <span className="font-bold text-sm">{value}</span>
      <span className="opacity-80">{label}</span>
    </div>
  );
}
