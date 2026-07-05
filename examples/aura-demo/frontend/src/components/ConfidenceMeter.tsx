"use client";

export function ConfidenceMeter({ value, label }: { value: number; label: string }) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.85 ? "bg-aura-emerald" : value >= 0.6 ? "bg-aura-ochre" : "bg-aura-crimson";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs font-mono text-aura-text-subtle">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 w-full bg-aura-surface-low rounded overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
