"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { HermesGenerateResult } from "@/lib/types";
import { StrategyDiff } from "./StrategyDiff";
import { GeneratedTestView } from "./GeneratedTestView";
import { PrimaryButton } from "@/components/ui/PrimaryButton";

export function HermesGeneratePanel({ onAdopted }: { onAdopted?: () => void }) {
  const [result, setResult] = useState<HermesGenerateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [adopting, setAdopting] = useState(false);
  const [adoptErr, setAdoptErr] = useState<string | null>(null);

  const generate = async () => {
    setBusy(true);
    setAdoptErr(null);
    try {
      const r = await api.hermes.generate({ days: 7, seed: 42 });
      setResult(r);
    } catch (e: any) {
      setAdoptErr(e.message || "Generate failed");
    }
    setBusy(false);
  };

  const adopt = async () => {
    if (!result?.diff) return;
    setAdopting(true);
    setAdoptErr(null);
    try {
      await api.hermes.adopt({
        variable: result.diff.variable,
        to: result.diff.to,
        rationale: result.diff.rationale,
      });
      onAdopted?.();
    } catch (e: any) {
      setAdoptErr(e.message || "Adopt failed");
    }
    setAdopting(false);
  };

  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="font-mono text-sm font-bold text-aura-text">Synthetic Reality → Code</h3>
          <p className="font-mono text-xs text-aura-text-muted">
            Generate a strategy diff backed by a generated regression test.
          </p>
        </div>
        <PrimaryButton onClick={generate} disabled={busy} loading={busy}>
          Generate strategy diff
        </PrimaryButton>
      </div>

      {adoptErr && (
        <p className="font-mono text-xs text-aura-crimson">{adoptErr}</p>
      )}

      {result && (
        <div className="space-y-3">
          {result.diff ? (
            <>
              <StrategyDiff diff={result.diff} />
              {result.test && <GeneratedTestView source={result.test.source} />}
              <PrimaryButton onClick={adopt} disabled={adopting} loading={adopting}>
                Adopt as next version
              </PrimaryButton>
            </>
          ) : (
            <p className="font-mono text-xs text-aura-text-muted">
              No statistically significant improvement found for the current strategy.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
