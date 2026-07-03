"use client";
import { Treemap, ResponsiveContainer, Tooltip } from "recharts";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { PortfolioSummary } from "@/lib/types";

const COLOR: Record<string, string> = {
  green: "#10B981",
  orange: "#D97706",
  red: "#DC2626",
};
const BORDER: Record<string, string> = {
  green: "#059669",
  orange: "#B45309",
  red: "#B91C1C",
};
const TEXT: Record<string, string> = {
  green: "#FFFFFF",
  orange: "#FFFFFF",
  red: "#FFFFFF",
};

const PAGE_SIZE = 20;

export function Heatmap({
  portfolios,
  syncing,
  rest,
}: {
  portfolios: PortfolioSummary[];
  syncing?: boolean;
  rest?: { count: number; fum: number; dominant_status: "green" | "orange" | "red" };
}) {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<string>("All Statuses");
  const [adviserFilter, setAdviserFilter] = useState<string>("All Advisers");
  const [assetClassFilter, setAssetClassFilter] = useState<string>("All Asset Classes");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const advisers = Array.from(new Set(portfolios.map((p) => p.adviser))).sort();
  const assetClasses = Array.from(new Set(portfolios.map((p) => p.top_asset_class).filter(Boolean))) as string[];

  const filtered = portfolios.filter((p) => {
    const matchesSearch = p.client_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === "All Statuses" ||
      (statusFilter === "Breached" && p.status === "red") ||
      (statusFilter === "Attention" && p.status === "orange") ||
      (statusFilter === "Needs Action" && (p.status === "red" || p.status === "orange"));
    const matchesAdviser = adviserFilter === "All Advisers" || p.adviser === adviserFilter;
    const matchesAssetClass = assetClassFilter === "All Asset Classes" || p.top_asset_class === assetClassFilter;
    return matchesSearch && matchesStatus && matchesAdviser && matchesAssetClass;
  });

  const sorted = filtered
    .map((p) => ({
      client_id: p.client_id,
      client_name: p.client_name,
      fum: p.fum,
      status: p.status,
      top_reason: p.top_reason,
    }))
    .sort((a, b) => b.fum - a.fum);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages - 1);
  const start = clampedPage * PAGE_SIZE;
  const pageRows = sorted.slice(start, start + PAGE_SIZE);
  const pageFum = pageRows.reduce((s, p) => s + p.fum, 0) || 1;

  const data = pageRows.map((p) => ({ ...p, size: Math.max(8, (p.fum / pageFum) * 4000) }));

  useEffect(() => {
    setPage(0);
  }, [statusFilter, adviserFilter, assetClassFilter, search]);

  return (
    <div className="flex flex-col gap-3" data-tour="heatmap">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-aura-navy">account_tree</span>
          <h2 className="font-mono text-lg font-semibold text-aura-text">Portfolio FUM Topology</h2>
        </div>
        <div className="flex items-center gap-2">
          {syncing && (
            <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase text-aura-emerald">
              <span className="w-1.5 h-1.5 rounded-full bg-aura-emerald animate-pulse" />
              Sync
            </span>
          )}
          <span className="font-mono text-xs text-aura-text-muted">Box size proportional to FUM // colour = risk state</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between bg-aura-surface border border-aura-border rounded px-4 py-2 gap-3">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider">Filters:</span>
          <select
            value={adviserFilter}
            onChange={(e) => setAdviserFilter(e.target.value)}
            className="text-xs font-mono border-none bg-transparent py-1 pl-0 pr-6 text-aura-text focus:ring-0 cursor-pointer hover:text-aura-navy"
          >
            <option>All Advisers</option>
            {advisers.map((a) => <option key={a}>{a}</option>)}
          </select>
          <div className="w-px h-4 bg-aura-border hidden sm:block" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs font-mono border-none bg-transparent py-1 pl-0 pr-6 text-aura-text focus:ring-0 cursor-pointer hover:text-aura-navy"
          >
            <option>All Statuses</option>
            <option>Breached</option>
            <option>Attention</option>
            <option>Needs Action</option>
          </select>
          <div className="w-px h-4 bg-aura-border hidden sm:block" />
          <select
            value={assetClassFilter}
            onChange={(e) => setAssetClassFilter(e.target.value)}
            className="text-xs font-mono border-none bg-transparent py-1 pl-0 pr-6 text-aura-text focus:ring-0 cursor-pointer hover:text-aura-navy"
          >
            <option>All Asset Classes</option>
            {assetClasses.map((a) => <option key={a}>{a}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2 border-b border-aura-border pb-1">
          <span className="material-symbols-outlined text-[16px] text-aura-text-muted">search</span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-transparent border-none p-0 text-xs font-mono w-32 lg:w-48 focus:ring-0 placeholder:text-aura-text-muted text-aura-text"
            placeholder="find portfolio..."
            type="text"
          />
        </div>
      </div>

      <div className="flex items-center justify-between bg-aura-surface border border-aura-border rounded px-4 py-2">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={clampedPage === 0}
            className="flex items-center gap-1 px-2 py-1 rounded border border-aura-border text-aura-text disabled:opacity-30 hover:border-aura-navy hover:text-aura-navy transition"
            aria-label="previous heatmap page"
          >
            <span className="material-symbols-outlined text-[18px]">chevron_left</span>
            <span className="font-mono text-xs hidden sm:inline">Prev</span>
          </button>
          <span className="font-mono text-xs text-aura-text-muted min-w-[110px] text-center">
            Page {clampedPage + 1}/{totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={clampedPage >= totalPages - 1}
            className="flex items-center gap-1 px-2 py-1 rounded border border-aura-border text-aura-text disabled:opacity-30 hover:border-aura-navy hover:text-aura-navy transition"
            aria-label="next heatmap page"
          >
            <span className="font-mono text-xs hidden sm:inline">Next</span>
            <span className="material-symbols-outlined text-[18px]">chevron_right</span>
          </button>
        </div>
        <div className="font-mono text-xs text-aura-text-muted">
          Showing {start + 1}–{Math.min(start + PAGE_SIZE, sorted.length)} of {sorted.length} top portfolios
          {rest && rest.count > 0
            ? ` (${rest.count.toLocaleString()} more aggregated)`
            : ""}
        </div>
      </div>

      <div className="relative w-full h-[420px] lg:h-[520px] bg-aura-surface-low border border-aura-border rounded p-1 overflow-hidden">
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={data}
            dataKey="size"
            stroke="#CBD5E1"
            content={<Cell onSelect={(id: string) => router.push(`/portfolio/${id}`)} />}
          >
            <Tooltip
              cursor={false}
              content={({ payload }) =>
                payload?.[0]?.payload ? (
                  <div className="rounded bg-white border border-aura-border p-2 text-xs shadow-aura-md">
                    <div className="font-mono font-bold text-aura-text">{payload[0].payload.client_name}</div>
                    <div className="font-mono text-aura-text-muted">FUM ${(payload[0].payload.fum / 1e6).toFixed(2)}M</div>
                    <div className="font-mono text-aura-ochre">{payload[0].payload.top_reason || "aligned"}</div>
                  </div>
                ) : null
              }
            />
          </Treemap>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center gap-4 mt-2 px-2 flex-wrap">
        <span className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider">Legend:</span>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-aura-emerald" />
          <span className="font-mono text-xs text-aura-text">Aligned</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-aura-ochre" />
          <span className="font-mono text-xs text-aura-text">Attention</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-aura-crimson" />
          <span className="font-mono text-xs text-aura-text">Breached</span>
        </div>
        <div className="ml-auto font-mono text-xs text-aura-text-muted italic">Box size proportional to FUM (this page)</div>
      </div>
    </div>
  );
}

function Cell(props: any) {
  const { x, y, width, height, onSelect, client_id, client_name, fum, status } = props;
  if (!client_id || width < 4 || height < 4 || !status) return <g />;
  const isRest = client_id === "__rest__";
  const color = COLOR[status];
  const border = BORDER[status];
  const text = TEXT[status];
  return (
    <g onClick={() => { if (!isRest) onSelect?.(client_id); }} style={{ cursor: isRest ? "default" : "pointer" }}>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        rx={4}
        fill={color}
        stroke={border}
        strokeWidth={1}
      />
      {width > 70 && height > 40 && (
        <>
          <text x={x + 8} y={y + 20} fontSize={11} fill={text} fontWeight={600} fontFamily="JetBrains Mono, monospace">
            {client_name.slice(0, 22)}
          </text>
          <text x={x + 8} y={y + 36} fontSize={11} fill={text} opacity={0.85} fontFamily="JetBrains Mono, monospace">
            ${(fum / 1e6).toFixed(1)}M
          </text>
        </>
      )}
      {status === "red" && width > 24 && height > 24 && (
        <text x={x + width - 14} y={y + 20} fontSize={16} fontWeight={700} fill="#FFFFFF">
          !
        </text>
      )}
    </g>
  );
}
