"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RulesResult } from "@/lib/types";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";

export function NarrativePanel({ clientId, rules_result }: { clientId: string; rules_result: RulesResult }) {
  const [narr, setNarr] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .explain(clientId)
      .then((r) => setNarr(r.narrative))
      .catch(() => {
        setNarr(
          "AI narrative unavailable - showing rule facts only. Breaches: " +
            rules_result.breaches.map((b) => b.plain).join("; ")
        );
      })
      .finally(() => setLoading(false));
  }, [clientId, rules_result]);

  return (
    <div className="bg-aura-surface-low border border-aura-border rounded p-4 mb-6 relative overflow-hidden" data-tour="narrative">
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-aura-navy" />
      <div className="pl-4">
        <div className="flex items-center gap-2 text-aura-navy mb-2">
          <span className="material-symbols-outlined material-symbols-filled">auto_awesome</span>
          <h3 className="font-mono text-base font-semibold">Assurance Narrative</h3>
        </div>
        {loading ? (
          <LoadingSpinner label="Reading portfolio and drafting assurance narrative…" />
        ) : (
          <div className="font-mono text-sm text-aura-text-muted leading-relaxed max-w-3xl space-y-2">
            {narr.split(/(?<=[.!?])\s+/).map((sentence, i) => (
              <p key={i}>{sentence}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
