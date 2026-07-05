"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";
import { Panel } from "@/components/ui/Panel";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";

export function AuditTrail({ clientId }: { clientId: string }) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    api.audit()
      .then((e) => setEntries(e.filter((x) => x.client_id === clientId).reverse()))
      .finally(() => setLoading(false));
  }, [clientId]);

  return (
    <Panel header="Audit Trail" className="mt-6">
      {loading ? (
        <LoadingSpinner label="Loading audit trail…" />
      ) : entries.length === 0 ? (
        <p className="font-mono text-sm text-aura-text-muted">No actions yet for this client.</p>
      ) : (
        <ul className="space-y-3">
          {entries.map((e, i) =>(
            <li key={i} className="border-b border-aura-border last:border-0 pb-3 last:pb-0">
              <div className="flex items-center gap-2 font-mono text-sm text-aura-text flex-wrap">
                <span className="text-aura-text-muted">{new Date(e.timestamp).toLocaleString()}</span>
                <span className="font-medium">{e.action_type}</span>
                <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider border ${
                  e.tier === "deterministic"
                    ? "bg-aura-emerald-soft border-aura-emerald text-aura-emerald"
                    : "bg-aura-ochre-soft border-aura-ochre text-aura-ochre"
                }`}>
                  {e.tier}
                </span>
              </div>
              {e.rationale && (
                <p className="font-mono text-sm text-aura-text-muted mt-1">{e.rationale}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
