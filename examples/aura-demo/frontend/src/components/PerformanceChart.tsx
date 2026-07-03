"use client";

import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from "recharts";
import { Panel } from "@/components/ui/Panel";

export function PerformanceChart({ seed }: { seed: number }) {
  const pts = Array.from({ length: 60 }, (_, i) => {
    const base = 100;
    const drift = i * 0.15;
    const noise = Math.sin(i * 0.7 + seed) * 4;
    return { t: i, v: +(base + drift + noise).toFixed(2) };
  });

  return (
    <Panel header="Performance Vector" subheader="Trailing 6 months">
      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={pts} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`auraGradient-${seed}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0F172A" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#0F172A" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="4 4" stroke="#E2E8F0" vertical={false} />
            <XAxis dataKey="t" hide />
            <YAxis domain={["dataMin - 2", "dataMax + 2"]} hide />
            <Area
              type="monotone"
              dataKey="v"
              stroke="#0F172A"
              strokeWidth={2}
              fill={`url(#auraGradient-${seed})`}
              dot={false}
              activeDot={{ r: 4, stroke: "#0F172A", strokeWidth: 2, fill: "#FFFFFF" }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#FFFFFF",
                border: "1px solid #CBD5E1",
                borderRadius: "4px",
                fontSize: "12px",
                fontFamily: "JetBrains Mono, monospace",
                color: "#1B1B1D",
              }}
              formatter={(value: number) => [`Index ${value}`, "Value"]}
              labelFormatter={() => ""}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
