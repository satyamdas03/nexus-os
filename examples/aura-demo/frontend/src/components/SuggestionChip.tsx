"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";

export function SuggestionChip({ clientId }: { clientId: string }) {
  const [s, setS] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [adopted, setAdopted] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.reflect(clientId).then((r) => setS(r.suggestion)).finally(() => setLoading(false));
  }, [clientId]);

  if (loading || dismissed || adopted || !s) return null;

  return (
    <div className="rounded border border-aura-ochre bg-aura-ochre-soft/20 p-4 mt-4 relative overflow-hidden">
      <div className="flex items-start gap-3 relative">
        <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded bg-aura-ochre-soft border border-aura-ochre text-aura-ochre shrink-0">
          learning loop
        </span>
        <p className="font-mono text-sm text-aura-ochre flex-1">{s.suggestion}</p>
      </div>
      <div className="flex gap-2 mt-3">
        <PrimaryButton
          onClick={() =>
            api
              .adopt({
                breach_type: s.breach_type,
                preference: s.pattern.split(": ").slice(-1)[0],
                rationale: s.pattern,
              })
              .then(() => setAdopted(true))
          }
          className="px-3 py-1.5 text-xs"
        >
          Adopt
        </PrimaryButton>
        <SecondaryButton onClick={() => setDismissed(true)} className="px-3 py-1.5 text-xs">
          Dismiss
        </SecondaryButton>
      </div>
      <p className="font-mono text-xs text-aura-text-muted mt-2">
        Pattern from {s.count} prior approvals. Advisory only - never auto-applies.
      </p>
    </div>
  );
}
