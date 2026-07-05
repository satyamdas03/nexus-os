"use client";

import { ConfidenceResult } from "@/lib/types";
import { ConfidenceMeter } from "./ConfidenceMeter";

export function ConfidenceCard({ result }: { result: ConfidenceResult }) {
  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs uppercase text-aura-text-subtle">AI Confidence</span>
        {result.human_review_recommended ? (
          <span className="px-2 py-1 rounded bg-aura-crimson-soft text-aura-crimson text-xs font-mono font-bold">
            Human review recommended
          </span>
        ) : (
          <span className="px-2 py-1 rounded bg-aura-emerald-soft text-aura-emerald text-xs font-mono font-bold">
            High confidence
          </span>
        )}
      </div>
      <ConfidenceMeter value={result.confidence} label="Overall" />
      {result.factors.map((f) => (
        <ConfidenceMeter key={f.name} value={f.score} label={f.name} />
      ))}
      <p className="text-xs text-aura-text-muted font-mono leading-snug">{result.explanation}</p>
    </div>
  );
}
