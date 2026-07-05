import { clsx } from "clsx";

export function TopMetricCard({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "emerald" | "ochre" | "crimson";
}) {
  const toneClasses = {
    neutral: "border-aura-border",
    emerald: "border-aura-emerald bg-aura-emerald-soft/30",
    ochre: "border-aura-ochre bg-aura-ochre-soft/30",
    crimson: "border-aura-crimson bg-aura-crimson-soft/30",
  };
  const valueClasses = {
    neutral: "text-aura-text",
    emerald: "text-aura-emerald",
    ochre: "text-aura-ochre",
    crimson: "text-aura-crimson",
  };

  return (
    <div className={clsx("border rounded p-4 flex flex-col justify-between", toneClasses[tone])}>
      <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider">{label}</p>
      <div className={clsx("font-mono text-2xl font-bold mt-2 tabular-nums", valueClasses[tone])}>{value}</div>
      {sub && <p className="font-mono text-xs text-aura-text-muted mt-1">{sub}</p>}
    </div>
  );
}
