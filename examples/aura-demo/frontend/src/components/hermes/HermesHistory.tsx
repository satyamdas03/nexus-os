"use client";

import { useState } from "react";
import { clsx } from "clsx";
import { Panel } from "@/components/ui/Panel";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { api } from "@/lib/api";
import type { HermesHistoryEntry, HermesStrategy } from "@/lib/types";

function fmtVal(v: unknown): string {
  if (Array.isArray(v)) return `${v.length} items`;
  if (typeof v === "number") return String(v);
  return String(v);
}

export function HermesHistory({
  history,
  onRollback,
}: {
  history: HermesHistoryEntry[];
  onRollback: (result: { strategy: HermesStrategy; history?: HermesHistoryEntry[] }) => void;
}) {
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const ordered = [...history].sort((a, b) => b.snapshot.version - a.snapshot.version);

  const restore = async (entry: HermesHistoryEntry) => {
    const ok = window.confirm(
      `Roll back strategy to v${entry.snapshot.version} (${entry.file})?\nThis reverts the live strategy.yaml and appends a new version.`
    );
    if (!ok) return;
    setBusy(entry.snapshot.version);
    setErr(null);
    try {
      const r = await api.hermes.rollback(entry.snapshot.version);
      onRollback({ strategy: r.strategy, history: r.history });
    } catch (e) {
      setErr(String((e as Error).message ?? e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Panel
      header="Strategy History"
      right={<span className="font-mono text-xs text-aura-text-subtle">{history.length} archived</span>}
    >
      {err && <p className="font-mono text-xs text-aura-crimson mb-3">ROLLBACK_ERR: {err}</p>}

      {history.length === 0 ? (
        <p className="font-mono text-sm text-aura-text-muted">
          NO ARCHIVES — adopt a change to snapshot the prior strategy.
        </p>
      ) : (
        <ol className="relative border-l border-aura-border pl-5 space-y-4">
          {ordered.map((h, idx) => {
            const isLatest = idx === 0;
            return (
              <li key={h.file} className="relative">
                <span
                  className={clsx(
                    "absolute -left-[26px] top-1 w-3 h-3 rounded border",
                    isLatest
                      ? "bg-aura-emerald border-aura-emerald"
                      : "bg-aura-surface-low border-aura-border-strong"
                  )}
                />
                <div className="border border-aura-border rounded bg-aura-surface-low p-3">
                  <div className="flex items-baseline justify-between gap-3 mb-1 flex-wrap">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-sm font-medium text-aura-emerald">
                        v{h.snapshot.version}
                      </span>
                      {isLatest && (
                        <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-aura-emerald border border-aura-emerald bg-aura-emerald-soft/50 px-1.5 py-0.5 rounded">
                          LATEST
                        </span>
                      )}
                      <span className="font-mono text-xs text-aura-text-subtle">{h.file}</span>
                    </div>
                    {h.timestamp && (
                      <span className="font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle">
                        {h.timestamp}
                      </span>
                    )}
                  </div>

                  {(h.actor || h.variable || h.rationale) && (
                    <div className="font-mono text-xs text-aura-text-muted mb-2 leading-snug">
                      {h.actor && (
                        <span>
                          <span className="text-aura-text font-medium">actor:</span> {h.actor}{" "}
                        </span>
                      )}
                      {h.variable && (
                        <span>
                          <span className="text-aura-text font-medium">{h.variable}</span>:{" "}
                          {h.from != null ? fmtVal(h.from) : "?"}{" "}
                          <span className="text-aura-ochre">→</span>{" "}
                          {h.to != null ? fmtVal(h.to) : "?"}
                        </span>
                      )}
                      {h.rationale && <span className="block">{h.rationale}</span>}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {Object.entries(h.snapshot.variables).map(([name, v]) => (
                      <span
                        key={name}
                        className="font-mono text-xs text-aura-text-muted bg-aura-surface border border-aura-border px-2 py-0.5 rounded"
                      >
                        {name}={fmtVal(v.value)}
                      </span>
                    ))}
                  </div>

                  <SecondaryButton
                    onClick={() => restore(h)}
                    disabled={busy !== null || isLatest}
                    loading={busy === h.snapshot.version}
                    className="flex items-center gap-2 text-aura-ochre border-aura-ochre hover:bg-aura-ochre-soft/40 disabled:opacity-40"
                  >
                    <span className="material-symbols-outlined text-[14px]">restore</span>
                    {busy === h.snapshot.version
                      ? "Rolling back..."
                      : isLatest
                      ? "Current"
                      : "Roll back to v" + h.snapshot.version}
                  </SecondaryButton>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <p className="font-mono text-xs text-aura-text-muted mt-4 leading-snug">
        Every strategy mutation is versioned + reversible. Roll back restores a prior snapshot and appends a new
        version.
      </p>
    </Panel>
  );
}
