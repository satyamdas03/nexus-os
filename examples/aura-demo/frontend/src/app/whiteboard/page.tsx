"use client";

import { useMemo, useState } from "react";
import { clsx } from "clsx";
import { Panel } from "@/components/ui/Panel";

const TABS = [
  { id: "compound", label: "Compound Growth", icon: "trending_up" },
  { id: "drawdown", label: "Drawdown Recovery", icon: "trending_down" },
  { id: "diversify", label: "Diversification", icon: "donut_large" },
];

type TabId = (typeof TABS)[number]["id"];

export default function WhiteboardPage() {
  const [tab, setTab] = useState<TabId>("compound");

  return (
    <div className="relative p-4 lg:p-gutter max-w-container-max mx-auto pb-32">
      <div className="mb-6">
        <h1 className="font-mono text-2xl font-bold text-aura-text">Investment Math Whiteboard</h1>
        <p className="font-mono text-xs text-aura-text-muted max-w-3xl leading-relaxed">
          Interactive visual explanations of the math that drives long-term wealth:
          compounding, drawdown recovery, and the diversification benefit.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded border font-mono text-sm font-medium transition-colors",
              tab === t.id
                ? "bg-aura-navy text-white border-aura-navy"
                : "border-aura-border text-aura-text-muted hover:bg-aura-surface hover:text-aura-text"
            )}
          >
            <span className="material-symbols-outlined text-[18px]">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "compound" && <CompoundPanel />}
      {tab === "drawdown" && <DrawdownPanel />}
      {tab === "diversify" && <DiversifyPanel />}
    </div>
  );
}

function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  suffix,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
}) {
  return (
    <div>
      <label className="block font-mono text-[10px] uppercase text-aura-text-subtle mb-1">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full px-3 py-2 rounded border border-aura-border bg-aura-background text-sm font-mono"
        />
        {suffix && <span className="font-mono text-xs text-aura-text-muted">{suffix}</span>}
      </div>
    </div>
  );
}

function CompoundPanel() {
  const [initial, setInitial] = useState(100_000);
  const [monthly, setMonthly] = useState(1_000);
  const [rate, setRate] = useState(7);
  const [years, setYears] = useState(20);

  const data = useMemo(() => {
    const r = rate / 100 / 12;
    const points: { year: number; value: number; contributed: number }[] = [];
    let value = initial;
    let contributed = initial;
    for (let m = 0; m <= years * 12; m++) {
      if (m > 0) {
        value = value * (1 + r) + monthly;
        contributed += monthly;
      }
      if (m % 12 === 0) {
        points.push({ year: m / 12, value, contributed });
      }
    }
    return points;
  }, [initial, monthly, rate, years]);

  const final = data[data.length - 1];
  const gain = final.value - final.contributed;

  return (
    <Panel header="Compound Growth" subheader="Small, consistent returns multiplied by time"
      right={<span className="material-symbols-outlined text-aura-emerald text-[20px]">trending_up</span>}>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <NumberInput label="Initial" value={initial} onChange={setInitial} min={0} step={1000} suffix="$" />
        <NumberInput label="Monthly" value={monthly} onChange={setMonthly} min={0} step={100} suffix="$" />
        <NumberInput label="Annual return" value={rate} onChange={setRate} min={-20} max={50} step={0.5} suffix="%" />
        <NumberInput label="Years" value={years} onChange={setYears} min={1} max={60} step={1} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <AreaChart data={data.map((d) => ({ label: d.year, value: d.value, baseline: d.contributed }))} />
        </div>
        <div className="space-y-3">
          <SummaryCard label="Final value" value={final.value} />
          <SummaryCard label="Total contributed" value={final.contributed} />
          <SummaryCard label="Gain from growth" value={gain} tone={gain >= 0 ? "green" : "red"} />
          <p className="font-mono text-xs text-aura-text-muted leading-relaxed">
            At a {rate}% annual return, every dollar invested at the start works for {years} years.
            Monthly contributions add fuel, but the early principal does most of the heavy lifting.
          </p>
        </div>
      </div>
    </Panel>
  );
}

function DrawdownPanel() {
  const [value, setValue] = useState(1_000_000);
  const [drawdown, setDrawdown] = useState(30);
  const [recoveryRate, setRecoveryRate] = useState(8);

  const remaining = value * (1 - drawdown / 100);
  const r = recoveryRate / 100;
  // Years to recover back to original value at given return: ln(original/remaining) / ln(1+r)
  const years = r > 0 && remaining > 0 ? Math.log(value / remaining) / Math.log(1 + r) : 0;

  const data = useMemo(() => {
    const pts: { year: number; value: number }[] = [{ year: 0, value: remaining }];
    let v = remaining;
    const maxY = Math.max(years, 5);
    for (let y = 1; y <= maxY; y++) {
      v = v * (1 + r);
      pts.push({ year: y, value: v });
    }
    return pts;
  }, [remaining, r, years]);

  return (
    <Panel header="Drawdown Recovery" subheader="Why losses hurt more than equivalent gains"
      right={<span className="material-symbols-outlined text-aura-crimson text-[20px]">trending_down</span>}>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <NumberInput label="Portfolio value" value={value} onChange={setValue} min={0} step={10000} suffix="$" />
        <NumberInput label="Drawdown" value={drawdown} onChange={setDrawdown} min={0} max={100} step={1} suffix="%" />
        <NumberInput label="Recovery return" value={recoveryRate} onChange={setRecoveryRate} min={0} max={50} step={0.5} suffix="%" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <LineChart data={data.map((d) => ({ label: d.year, value: d.value }))} target={value} />
        </div>
        <div className="space-y-3">
          <SummaryCard label="Value after shock" value={remaining} tone="red" />
          <SummaryCard label="Required gain" value={value - remaining} tone="red" />
          <SummaryCard label="Years to recover" value={Number.isFinite(years) ? years.toFixed(1) : "∞"} />
          <p className="font-mono text-xs text-aura-text-muted leading-relaxed">
            A {drawdown}% drop requires a {((1 / (1 - drawdown / 100) - 1) * 100).toFixed(1)}% gain just to get back to even.
            That is why risk management — and the ASSURE rules engine — matters as much as return chasing.
          </p>
        </div>
      </div>
    </Panel>
  );
}

function DiversifyPanel() {
  const [wA, setWA] = useState(50);
  const [retA, setRetA] = useState(8);
  const [volA, setVolA] = useState(15);
  const [retB, setRetB] = useState(5);
  const [volB, setVolB] = useState(8);
  const [corr, setCorr] = useState(0.2);

  const wB = 100 - wA;
  const expRet = (wA / 100) * retA + (wB / 100) * retB;
  const portVol = Math.sqrt(
    Math.pow((wA / 100) * volA, 2) +
      Math.pow((wB / 100) * volB, 2) +
      2 * (wA / 100) * (wB / 100) * volA * volB * corr
  );

  const data = useMemo(() => {
    const pts: { label: number; value: number }[] = [];
    for (let w = 0; w <= 100; w += 5) {
      const er = (w / 100) * retA + ((100 - w) / 100) * retB;
      const v = Math.sqrt(
        Math.pow((w / 100) * volA, 2) +
          Math.pow(((100 - w) / 100) * volB, 2) +
          2 * (w / 100) * ((100 - w) / 100) * volA * volB * corr
      );
      pts.push({ label: w, value: v });
    }
    return pts;
  }, [retA, retB, volA, volB, corr]);

  return (
    <Panel header="Diversification" subheader="Two imperfectly correlated assets can lower risk without sacrificing return"
      right={<span className="material-symbols-outlined text-aura-ochre text-[20px]">donut_large</span>}>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <NumberInput label="Weight A" value={wA} onChange={setWA} min={0} max={100} step={5} suffix="%" />
        <NumberInput label="Asset A return" value={retA} onChange={setRetA} min={0} max={50} step={0.5} suffix="%" />
        <NumberInput label="Asset A volatility" value={volA} onChange={setVolA} min={0} max={100} step={1} suffix="%" />
        <NumberInput label="Asset B return" value={retB} onChange={setRetB} min={0} max={50} step={0.5} suffix="%" />
        <NumberInput label="Asset B volatility" value={volB} onChange={setVolB} min={0} max={100} step={1} suffix="%" />
        <NumberInput label="Correlation" value={corr} onChange={setCorr} min={-1} max={1} step={0.1} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <LineChart data={data.map((d) => ({ label: d.label, value: d.value }))} xLabel="Weight in Asset A (%)" yLabel="Portfolio volatility (%)" />
        </div>
        <div className="space-y-3">
          <SummaryCard label="Expected return" value={`${expRet.toFixed(1)}%`} />
          <SummaryCard label="Portfolio volatility" value={`${portVol.toFixed(1)}%`} tone="ochre" />
          <p className="font-mono text-xs text-aura-text-muted leading-relaxed">
            At {wA}% A / {wB}% B with correlation {corr}, the combined portfolio is usually less volatile
            than the weighted average of the two assets. That risk reduction is the diversification benefit.
          </p>
        </div>
      </div>
    </Panel>
  );
}

function SummaryCard({
  label,
  value,
  tone = "navy",
}: {
  label: string;
  value: number | string;
  tone?: "navy" | "green" | "red" | "ochre";
}) {
  const toneClass =
    tone === "green"
      ? "text-aura-emerald"
      : tone === "red"
      ? "text-aura-crimson"
      : tone === "ochre"
      ? "text-aura-ochre"
      : "text-aura-text";
  return (
    <div className="border border-aura-border rounded p-3 bg-aura-surface-low">
      <span className="block font-mono text-[10px] uppercase text-aura-text-subtle">{label}</span>
      <span className={clsx("font-mono text-lg font-semibold", toneClass)}>
        {typeof value === "number" ? formatCurrency(value) : value}
      </span>
    </div>
  );
}

function AreaChart({
  data,
}: {
  data: { label: number; value: number; baseline: number }[];
}) {
  const width = 600;
  const height = 240;
  const pad = { top: 10, right: 10, bottom: 30, left: 60 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const maxY = Math.max(...data.map((d) => d.value));
  const minY = Math.min(...data.map((d) => d.baseline));
  const yRange = Math.max(maxY - minY, 1);
  const xScale = (i: number) => pad.left + (i / (data.length - 1)) * innerW;
  const yScale = (v: number) => pad.top + innerH - ((v - minY) / yRange) * innerH;

  const areaPath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d.value)}`)
    .join(" ");
  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d.baseline)}`)
    .join(" ");

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-64">
        <rect x={0} y={0} width={width} height={height} fill="transparent" />
        {[0, 0.25, 0.5, 0.75, 1].map((p) => {
          const y = pad.top + innerH * p;
          const val = minY + yRange * (1 - p);
          return (
            <g key={p}>
              <line x1={pad.left} y1={y} x2={width - pad.right} y2={y} stroke="#E2E8F0" strokeDasharray="2" />
              <text x={pad.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill="#64748B" className="font-mono">
                {formatCurrencyCompact(val)}
              </text>
            </g>
          );
        })}
        <path d={`${areaPath} L ${xScale(data.length - 1)} ${yScale(minY)} L ${xScale(0)} ${yScale(minY)} Z`}
          fill="#0F172A" fillOpacity={0.08} />
        <path d={areaPath} fill="none" stroke="#0F172A" strokeWidth={2} />
        <path d={linePath} fill="none" stroke="#F59E0B" strokeWidth={2} strokeDasharray="4" />
        {data.filter((_, i) => i % 5 === 0 || i === data.length - 1).map((d, i) => (
          <text key={i} x={xScale(i)} y={height - 8} textAnchor="middle" fontSize={10} fill="#64748B" className="font-mono">
            Y{d.label}
          </text>
        ))}
      </svg>
      <div className="flex items-center gap-4 font-mono text-[10px] text-aura-text-muted mt-1">
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-aura-navy" /> Total value
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 border-t-2 border-dashed border-aura-ochre" /> Contributions
        </span>
      </div>
    </div>
  );
}

function LineChart({
  data,
  target,
  xLabel,
  yLabel,
}: {
  data: { label: number; value: number }[];
  target?: number;
  xLabel?: string;
  yLabel?: string;
}) {
  const width = 600;
  const height = 240;
  const pad = { top: 10, right: 10, bottom: 30, left: 60 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const maxY = Math.max(...data.map((d) => d.value), target ?? 0);
  const minY = Math.min(...data.map((d) => d.value), target ?? 0);
  const yRange = Math.max(maxY - minY, 1);
  const xScale = (i: number) => pad.left + (i / (data.length - 1)) * innerW;
  const yScale = (v: number) => pad.top + innerH - ((v - minY) / yRange) * innerH;

  const path = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d.value)}`)
    .join(" ");

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-64">
        {[0, 0.25, 0.5, 0.75, 1].map((p) => {
          const y = pad.top + innerH * p;
          const val = minY + yRange * (1 - p);
          return (
            <g key={p}>
              <line x1={pad.left} y1={y} x2={width - pad.right} y2={y} stroke="#E2E8F0" strokeDasharray="2" />
              <text x={pad.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill="#64748B" className="font-mono">
                {formatCurrencyCompact(val)}
              </text>
            </g>
          );
        })}
        {target != null && (
          <>
            <line
              x1={pad.left}
              y1={yScale(target)}
              x2={width - pad.right}
              y2={yScale(target)}
              stroke="#10B981"
              strokeDasharray="4"
            />
            <text
              x={width - pad.right}
              y={yScale(target) - 6}
              textAnchor="end"
              fontSize={10}
              fill="#10B981"
              className="font-mono"
            >
              target
            </text>
          </>
        )}
        <path d={path} fill="none" stroke="#B91C1C" strokeWidth={2} />
        {data.filter((_, i) => i % 2 === 0 || i === data.length - 1).map((d, i) => (
          <text key={i} x={xScale(i)} y={height - 8} textAnchor="middle" fontSize={10} fill="#64748B" className="font-mono">
            {d.label}
          </text>
        ))}
      </svg>
      <div className="flex justify-between font-mono text-[10px] text-aura-text-muted mt-1">
        <span>{xLabel ?? "Year"}</span>
        <span>{yLabel ?? "Value"}</span>
      </div>
    </div>
  );
}

function formatCurrency(n: number): string {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function formatCurrencyCompact(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n.toFixed(0)}`;
}
