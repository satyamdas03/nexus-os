"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EvidencePack } from "@/lib/types";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { SecondaryButton } from "@/components/ui/SecondaryButton";

interface EvidencePackViewProps {
  clientId: string;
}

export function EvidencePackView({ clientId }: EvidencePackViewProps) {
  const [pack, setPack] = useState<EvidencePack | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.evidence
      .portfolio(clientId)
      .then((data) => {
        if (!cancelled) setPack(data);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <LoadingSpinner label="Assembling evidence pack..." />
      </div>
    );
  }

  if (err || !pack) {
    return (
      <div className="p-4 text-aura-crimson bg-aura-crimson/10 rounded border border-aura-crimson/20 text-sm font-mono">
        {err || "Unable to load evidence pack."}
      </div>
    );
  }

  const statusClass =
    pack.current_attestation.status === "green"
      ? "bg-aura-emerald/10 text-aura-emerald border-aura-emerald/30"
      : pack.current_attestation.status === "orange"
        ? "bg-aura-ochre/10 text-aura-ochre border-aura-ochre/30"
        : "bg-aura-crimson/10 text-aura-crimson border-aura-crimson/30";

  return (
    <div className="space-y-4">
      <div className="bg-aura-crimson text-white px-3 py-2 rounded text-xs font-bold uppercase tracking-wider text-center">
        Synthetic Demonstration Data
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-mono text-lg font-semibold text-aura-navy">{pack.header.client_name}</h3>
          <p className="font-mono text-xs text-aura-slate">
            {pack.header.client_id} · Adviser: {pack.header.adviser} · Day {pack.header.day}
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded text-xs font-bold uppercase tracking-wider border ${statusClass}`}
        >
          {pack.current_attestation.status}
        </span>
      </div>

      <div className="bg-aura-surface-low border border-aura-border rounded p-3">
        <p className="font-mono text-xs text-aura-slate uppercase tracking-wider mb-1">Deterministic Summary</p>
        <p className="font-mono text-sm text-aura-text">{pack.deterministic_summary}</p>
      </div>

      <div className="bg-aura-surface-low border border-aura-border rounded p-3">
        <p className="font-mono text-xs text-aura-slate uppercase tracking-wider mb-2">Compliance Attestation</p>
        <ul className="space-y-1">
          {pack.current_attestation.per_rule.slice(0, 6).map((r) => (
            <li key={r.rule} className="font-mono text-xs flex items-center justify-between">
              <span className="text-aura-text truncate max-w-[60%]">{r.rule}</span>
              <span className={r.pass ? "text-aura-emerald" : "text-aura-crimson"}>
                {r.pass ? "PASS" : "FAIL"}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex items-center justify-between text-xs font-mono text-aura-slate">
        <span>Ref: {pack.header.reference_id}</span>
        <span>Generated {pack.header.generated_at.slice(0, 19)} UTC</span>
      </div>

      <div className="flex gap-2">
        <SecondaryButton
          onClick={() => window.open(api.evidence.portfolioHtmlUrl(clientId), "_blank", "noopener,noreferrer")}
          className="w-full"
        >
          Open Print-Ready Report
        </SecondaryButton>
      </div>
    </div>
  );
}
