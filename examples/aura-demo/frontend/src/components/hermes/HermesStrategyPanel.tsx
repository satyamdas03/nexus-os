"use client";

import { useState } from "react";
import { Panel } from "@/components/ui/Panel";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { api } from "@/lib/api";
import type { HermesStrategy, HermesProposal, HermesAdoptResult } from "@/lib/types";
import { useMutationGuard } from "@/components/auth/useMutationGuard";

function fmt(v: unknown): string {
  if (Array.isArray(v)) return v.join(" > ");
  if (typeof v === "number") return String(v);
  return String(v);
}

export function HermesStrategyPanel({
  strategy,
  onAdopted,
}: {
  strategy: HermesStrategy | null;
  onAdopted: (result: HermesAdoptResult) => void;
}) {
  const [proposal, setProposal] = useState<HermesProposal | null>(null);
  const [busy, setBusy] = useState<"reflect" | "adopt" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lastAdopt, setLastAdopt] = useState<HermesAdoptResult | null>(null);
  const [lastDismissMsg, setLastDismissMsg] = useState(false);
  const guard = useMutationGuard();

  const doReflect = (mode: "fallback" | "hermes") => {
    setBusy("reflect");
    setErr(null);
    setLastDismissMsg(false);
    api.hermes
      .reflect(mode)
      .then(setProposal)
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setBusy(null));
  };

  const doAdopt = () => {
    if (!proposal) return;
    setBusy("adopt");
    setErr(null);
    api.hermes
      .adopt({ variable: proposal.variable, to: proposal.to, rationale: proposal.rationale })
      .then((r) => {
        setLastAdopt(r);
        setProposal(null);
        onAdopted(r);
      })
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setBusy(null));
  };

  const doDismiss = () => {
    setProposal(null);
    setLastDismissMsg(true);
  };

  return (
    <Panel
      header="Remediation Strategy"
      subheader={`strategy.yaml · judgment layer · v${strategy?.version ?? "?"}`}
      right={
        <span className="bg-aura-emerald-soft border border-aura-emerald text-aura-emerald text-[10px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded font-mono">
          MANDATE = LAW
        </span>
      }
    >
      <div className="space-y-2 mb-5">
        {strategy &&
          Object.entries(strategy.variables).map(([name, v]) => (
            <div key={name} className="border border-aura-border rounded bg-aura-surface-low p-3">
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <span className="font-mono text-sm font-medium text-aura-emerald">{name}</span>
                <span className="font-mono text-sm font-medium text-aura-text">{fmt(v.value)}</span>
              </div>
              <p className="font-mono text-xs text-aura-text-muted mt-1 leading-snug">{v.rationale}</p>
            </div>
          ))}
      </div>

      {/* Reflection controls */}
      <div className="border-t border-aura-border pt-4">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className="material-symbols-outlined text-aura-navy text-[20px]">auto_awesome</span>
          <span className="font-mono text-sm font-medium text-aura-text">Hermes Reflection</span>
          <span className="font-mono text-xs text-aura-text-subtle">proposes ONE strategy change</span>
        </div>
        <div className="flex gap-2 mb-3 flex-wrap">
          <SecondaryButton onClick={() => doReflect("fallback")} disabled={busy !== null || guard.disabled} title={guard.title} loading={busy === "reflect"}>
            {busy === "reflect" ? "Reflecting…" : "Reflect (deterministic)"}
          </SecondaryButton>
          <SecondaryButton onClick={() => doReflect("hermes")} disabled={busy !== null || guard.disabled} title={guard.title} loading={busy === "reflect"}>
            Reflect (Claude)
          </SecondaryButton>
        </div>

        {proposal && (
          <div className="bg-aura-ochre-soft/50 border border-aura-ochre rounded p-3 mb-3">
            <div className="flex items-baseline justify-between gap-3 flex-wrap mb-1">
              <span className="font-mono text-xs text-aura-ochre uppercase tracking-wider">
                Proposed — {proposal.mode}
              </span>
            </div>
            <p className="font-mono text-sm text-aura-text">
              <span className="text-aura-emerald font-medium">{proposal.variable}</span>:{" "}
              <span className="text-aura-text-subtle">{fmt(proposal.current)}</span>{" "}
              <span className="text-aura-ochre">→</span>{" "}
              <span className="text-aura-emerald font-medium">{fmt(proposal.to)}</span>
            </p>
            <p className="font-mono text-xs text-aura-text-muted mt-1 leading-snug">{proposal.rationale}</p>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <PrimaryButton onClick={doAdopt} disabled={busy !== null || guard.disabled} title={guard.title} loading={busy === "adopt"} className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px]">gavel</span>
                {busy === "adopt" ? "Adopting..." : "Adopt (human gate)"}
              </PrimaryButton>
              <SecondaryButton onClick={doDismiss} disabled={busy !== null} loading={busy === "adopt"} className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px]">close</span>
                Dismiss
              </SecondaryButton>
            </div>
          </div>
        )}

        {lastDismissMsg && !proposal && (
          <div className="bg-aura-surface border border-aura-border rounded p-3 mb-3 font-mono text-xs text-aura-text-muted">
            Dismissed — Hermes will re-reflect next scan.
          </div>
        )}

        {lastAdopt && (
          <div className="bg-aura-emerald-soft/50 border border-aura-emerald rounded p-3 mb-3 font-mono text-xs">
            <span className="text-aura-text font-medium">ADOPTED.</span>{" "}
            <span className="text-aura-text-muted">
              {lastAdopt.variable}: {fmt(lastAdopt.from)} → {fmt(lastAdopt.to)} · strategy v
              {lastAdopt.version} · audit appended.
            </span>
          </div>
        )}
        {err && <p className="font-mono text-xs text-aura-crimson">ERR: {err}</p>}
        <p className="font-mono text-xs text-aura-text-muted mt-2 leading-snug">
          Hermes never self-adopts. Nothing auto-executes. Every strategy change is versioned + reversible
          (history/). Mandate rules + rules_engine.py are law and are unwritable from here.
        </p>
      </div>
    </Panel>
  );
}
