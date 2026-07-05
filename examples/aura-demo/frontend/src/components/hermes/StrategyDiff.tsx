"use client";

import { HermesDiff } from "@/lib/types";

export function StrategyDiff({ diff }: { diff: HermesDiff }) {
  return (
    <div className="bg-aura-ochre-soft/30 border border-aura-ochre rounded p-3 space-y-2">
      <p className="font-mono text-xs text-aura-ochre uppercase">Proposed strategy change</p>
      <p className="font-mono text-sm text-aura-text">
        <span className="font-bold">{diff.variable}</span>:{" "}
        <span className="text-aura-text-subtle">{String(diff.from)}</span> →{" "}
        <span className="text-aura-emerald font-bold">{String(diff.to)}</span>
      </p>
      <p className="font-mono text-xs text-aura-text-muted">{diff.rationale}</p>
    </div>
  );
}
