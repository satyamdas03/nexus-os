"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Portfolio } from "@/lib/types";
import { NarrativePanel } from "@/components/NarrativePanel";
import { BreachChips } from "@/components/BreachChips";
import { HoldingsTable } from "@/components/HoldingsTable";
import { AllocationBarChart } from "@/components/AllocationBarChart";
import { PerformanceChart } from "@/components/PerformanceChart";
import { StatusBadge } from "@/components/StatusBadge";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { AboutPopover } from "@/components/guide/AboutPopover";
import { LoadingOverlay } from "@/components/ui/LoadingOverlay";
import { EvidencePackButton } from "@/components/evidence/EvidencePackButton";

export default function Diagnosis({ params }: { params: { id: string } }) {
  const { id } = params;
  const [p, setP] = useState<Portfolio | null>(null);
  const [hl, setHl] = useState<string[]>([]);
  const [err, setErr] = useState(false);

  useEffect(() => {
    api.getPortfolio(id).then((portfolio) => {
      setP(portfolio);
      const offenders = new Set<string>();
      portfolio.rules_result?.breaches.forEach((b) => b.offending_holdings.forEach((t) => offenders.add(t)));
      portfolio.rules_result?.watches.forEach((w) => w.offending_holdings.forEach((t) => offenders.add(t)));
      setHl(Array.from(offenders));
    }).catch(() => setErr(true));
  }, [id]);

  if (err) return <div className="p-8 font-mono text-aura-crimson">Backend unreachable. Check backend and retry.</div>;
  if (!p) {
    return (
      <LoadingOverlay
        label="Loading portfolio data…"
        subLabel={`Reading client ${id} from the assurance book and running deterministic mandate checks.`}
      />
    );
  }
  const rr = p.rules_result!;
  const totalValue = p.holdings.reduce((s, h) => s + h.market_value, 0) + p.cash;

  return (
    <div className="relative p-4 lg:p-6 max-w-[1440px] mx-auto">
      <div className="absolute top-4 right-4 lg:top-6 lg:right-6 z-10">
        <AboutPopover title="About Diagnosis">
          <p>The Assurance Narrative is plain-English AI advisory, written only from breaches the rules engine flagged.</p>
          <p>Breach chips are deterministic rule failures. Click one to highlight offending holdings. The "?" buttons explain the exact mandate rule for that holding or asset class.</p>
          <p>The confidence line shows what is rule-maths (deterministic) vs AI-inferred (advisory).</p>
        </AboutPopover>
      </div>
      <Link href="/" className="inline-flex items-center gap-1.5 text-aura-text-muted hover:text-aura-navy font-mono text-xs mb-4">
        <span className="material-symbols-outlined text-[16px]">arrow_back</span>
        <span className="uppercase tracking-wide">Back to Command Centre</span>
      </Link>

      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-6">
        <div className="w-full">
          <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">Entity // {p.client_id}</p>
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <h1 className="font-mono text-2xl font-bold text-aura-text">{p.client_name}</h1>
            <StatusBadge status={rr.status} />
          </div>
          <div className="flex flex-wrap items-center gap-4 text-aura-text-muted font-mono text-xs">
            <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px]">person</span>Adviser: {p.adviser}</span>
            <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-aura-emerald">verified</span>Deterministic checks + AI narrative advisory</span>
          </div>
        </div>
        <div className="text-right flex flex-col items-end gap-3 w-full md:w-auto">
          <div>
            <p className="font-mono text-[10px] uppercase text-aura-text-subtle mb-0.5">Total Portfolio Value</p>
            <p className="font-mono text-xl font-bold tabular-nums text-aura-navy">${totalValue.toLocaleString()}</p>
          </div>
          <Link href={`/portfolio/${id}/workbench`}>
            <PrimaryButton className="flex items-center gap-2">
              <span className="uppercase tracking-wide">Open Remediation</span>
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            </PrimaryButton>
          </Link>
          <EvidencePackButton clientId={id} />
        </div>
      </div>

      <NarrativePanel clientId={id} rules_result={rr} />

      {rr.breaches.length > 0 && (
        <section className="mb-6" data-tour="breaches">
          <SectionHeader label="Diagnostics" title={`${rr.breaches.length} Mandate Breach${rr.breaches.length > 1 ? "es" : ""}`} />
          <BreachChips items={rr.breaches} onPick={setHl} clientId={id} />
        </section>
      )}

      {rr.watches.length > 0 && (
        <section className="mb-6">
          <SectionHeader label="Watchlist" title={`${rr.watches.length} Drift Watch${rr.watches.length > 1 ? "es" : ""}`} />
          <BreachChips items={rr.watches} onPick={setHl} clientId={id} />
        </section>
      )}

      <div className="mb-6 p-3 rounded bg-aura-surface border border-aura-border font-mono text-xs text-aura-text-muted">
        <span className="text-aura-text">Confidence line:</span> rule checks are{" "}
        <span className="text-aura-emerald font-bold">deterministic (100% rule maths)</span>. The narrative is{" "}
        <span className="text-aura-ochre font-bold">advisory (AI-inferred)</span>. The rules engine decides compliance.
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <HoldingsTable holdings={p.holdings} cash={p.cash} highlight={hl} clientId={id} rulesResult={rr} />
        </div>
        <div className="lg:col-span-1 space-y-6">
          <AllocationBarChart holdings={p.holdings} clientId={id} mandate={p.mandate} rulesResult={rr} />
          <PerformanceChart seed={id.length * 7} />
        </div>
      </div>
    </div>
  );
}
