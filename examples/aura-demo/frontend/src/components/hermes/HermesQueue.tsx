"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { clsx } from "clsx";
import { Panel } from "@/components/ui/Panel";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { StatusBadge } from "@/components/StatusBadge";
import { VerifyPanel } from "@/components/VerifyPanel";
import { api } from "@/lib/api";
import type { HermesQueueItem, HermesHeartbeat, RulesResult } from "@/lib/types";

type RowState = "pending" | "applied" | "rejected";

function QueueRow({
  q,
  rank,
  onApprove,
  onReject,
}: {
  q: HermesQueueItem;
  rank: number;
  onApprove: (q: HermesQueueItem) => Promise<void>;
  onReject: (q: HermesQueueItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const [verification, setVerification] = useState<RulesResult | null>(null);
  const [loadingV, setLoadingV] = useState(false);
  const [state, setState] = useState<RowState>("pending");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // confidence is optional on HermesQueueItem (/hermes/queue SELECT omits it).
  // Fall back to 0 so the tone + % render without undefined arithmetic.
  const conf = q.confidence ?? 0;
  const confTone = conf >= 1.0 ? "text-aura-emerald" : conf >= 0.7 ? "text-aura-ochre" : "text-aura-crimson";

  const expand = async () => {
    const next = !open;
    setOpen(next);
    if (next && !verification && !loadingV) {
      setLoadingV(true);
      setErr(null);
      api.verify(q.client_id, q.trades)
        .then(setVerification)
        .catch((e) => setErr(String(e.message ?? e)))
        .finally(() => setLoadingV(false));
    }
  };

  const approve = async () => {
    setBusy(true);
    setErr(null);
    try {
      await onApprove(q);
      setState("applied");
    } catch (e) {
      setErr(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const reject = () => {
    onReject(q);
    setState("rejected");
  };

  const resolved = verification?.status === "green";

  if (state === "applied") {
    return (
      <div className="border border-aura-emerald rounded bg-aura-emerald-soft/40 p-3">
        <div className="flex items-center gap-2 font-mono text-xs text-aura-emerald">
          <span className="material-symbols-outlined text-[18px] material-symbols-filled">check_circle</span>
          APPLIED — {q.client_name} ({q.client_id}) — {q.trades.length} trade(s) sent to execution.
        </div>
      </div>
    );
  }
  if (state === "rejected") {
    return (
      <div className="border border-aura-ochre rounded bg-aura-ochre-soft/40 p-3">
        <div className="flex items-center gap-2 font-mono text-xs text-aura-ochre">
          <span className="material-symbols-outlined text-[18px]">block</span>
          REJECTED — {q.client_name} — removed from local queue (manager override).
        </div>
      </div>
    );
  }

  return (
    <div className="border border-aura-border rounded bg-aura-surface-low hover:border-aura-border-strong transition-colors">
      <button
        type="button"
        onClick={expand}
        className="w-full text-left p-3"
        aria-expanded={open}
      >
        <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-aura-text-subtle w-6">#{rank}</span>
            <span className="font-mono text-sm font-medium text-aura-emerald">{q.client_name}</span>
            <span className="font-mono text-xs text-aura-text-subtle">({q.client_id})</span>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={q.prior_status} />
            <span className="text-aura-text-subtle font-mono text-xs">→</span>
            <StatusBadge status={q.post_status} />
            {q.mode === "prevent" ? (
              <span className="ml-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-aura-navy bg-aura-navy/10 text-aura-navy font-mono text-[10px] uppercase tracking-wider">
                <span className="material-symbols-outlined text-[14px] material-symbols-filled">shield</span>
                PREVENT
              </span>
            ) : (
              <span className="ml-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-aura-emerald bg-aura-emerald-soft/50 text-aura-emerald font-mono text-[10px] uppercase tracking-wider">
                <span className="material-symbols-outlined text-[14px] material-symbols-filled">verified</span>
                ASSURANCE
              </span>
            )}
            <span
              className={clsx(
                "material-symbols-outlined text-[18px] text-aura-text-subtle transition-transform",
                open && "rotate-90"
              )}
            >
              chevron_right
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4 flex-wrap mb-2 font-mono text-xs">
          <span className="text-aura-text-subtle">
            FUM <span className="text-aura-text">${(q.fum / 1e6).toFixed(2)}M</span>
          </span>
          <span className="text-aura-text-subtle">
            confidence <span className={confTone}>{(conf * 100).toFixed(0)}%</span>
          </span>
          <span className="text-aura-text-subtle">
            trades <span className="text-aura-text">{q.trades.length}</span>
          </span>
        </div>
        <p className="font-mono text-xs text-aura-text-muted leading-snug">{q.rationale}</p>
        {q.mode === "prevent" && q.prevent_meta && (
          <p className="font-mono text-[10px] text-aura-navy mt-1 leading-snug">
            Proactive · {q.prevent_meta.horizon_days}d horizon · risk {q.prevent_meta.risk_before.toFixed(2)} →{" "}
            {q.prevent_meta.risk_after.toFixed(2)} · projected {q.prevent_meta.projected_status}
          </p>
        )}
      </button>

      {open && (
        <div className="border-t border-aura-border p-3 space-y-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle mb-2">
              Proposed Trades
            </div>
            <div className="overflow-x-auto">
              <table className="w-full font-mono text-xs">
                <thead>
                  <tr className="text-aura-text-subtle text-left">
                    <th className="py-1 pr-3 font-medium">ACT</th>
                    <th className="py-1 pr-3 font-medium">TICKER</th>
                    <th className="py-1 pr-3 font-medium text-right">UNITS</th>
                    <th className="py-1 font-medium text-right">VALUE</th>
                  </tr>
                </thead>
                <tbody>
                  {q.trades.map((t, i) => (
                    <tr key={i} className="border-t border-aura-border">
                      <td
                        className={clsx(
                          "py-1 pr-3",
                          t.action === "sell" ? "text-aura-crimson" : "text-aura-emerald"
                        )}
                      >
                        {t.action.toUpperCase()}
                      </td>
                      <td className="py-1 pr-3 text-aura-text">{t.ticker}</td>
                      <td className="py-1 pr-3 text-right text-aura-text tabular">
                        {t.units.toFixed(2)}
                      </td>
                      <td className="py-1 text-right text-aura-text tabular">
                        ${t.value.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle mb-2">
              Assurance Check {loadingV && "— verifying..."}
            </div>
            {loadingV && (
              <p className="font-mono text-xs text-aura-text-muted inline-flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
                Running rules_engine.py against post-trade book...
              </p>
            )}
            {!loadingV && verification && (
              <VerifyPanel verification={verification} resolved={resolved} retried={false} priorStatus={q.prior_status} />
            )}
            {!loadingV && !verification && err && (
              <p className="font-mono text-xs text-aura-crimson">VERIFY_ERR: {err}</p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <PrimaryButton onClick={approve} disabled={busy} loading={busy} className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">check</span>
              {busy ? "Approving..." : "Approve"}
            </PrimaryButton>
            <Link
              href={`/portfolio/${q.client_id}/workbench`}
              className="px-4 py-2 rounded border border-aura-border text-aura-navy font-mono text-sm font-medium flex items-center gap-2 hover:bg-aura-surface transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">edit</span>
              Modify
            </Link>
            <button
              onClick={reject}
              disabled={busy}
              className="px-4 py-2 rounded border border-aura-crimson text-aura-crimson font-mono text-sm font-medium flex items-center gap-2 hover:bg-aura-crimson-soft/40 transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
              Reject
            </button>
            {err && <span className="font-mono text-xs text-aura-crimson">ERR: {err}</span>}
          </div>
          <p className="font-mono text-xs text-aura-text-muted leading-snug">
            Every item was deterministically verified by the rules engine before it reached you. You are the final authority.
          </p>
        </div>
      )}
    </div>
  );
}

export function HermesQueue({
  queue,
  heartbeat,
  onApprove,
  onApproveBatch,
  onRefreshQueue,
}: {
  queue: HermesQueueItem[];
  heartbeat: HermesHeartbeat | null;
  onApprove: (q: HermesQueueItem) => Promise<void>;
  onApproveBatch: (items: HermesQueueItem[]) => Promise<void>;
  onRefreshQueue?: () => Promise<void>;
}) {
  const misses = heartbeat?.top_misses ?? [];
  const [items, setItems] = useState<HermesQueueItem[]>(queue);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchErr, setBatchErr] = useState<string | null>(null);

  // keep local items in sync when the prop changes (e.g. after a new scan)
  // but preserve user-driven removals until a new prop reference arrives.
  const [lastRef, setLastRef] = useState<HermesQueueItem[] | null>(null);
  useEffect(() => {
    if (queue !== lastRef) {
      setLastRef(queue);
      setItems(queue);
    }
  }, [queue, lastRef]);

  const removeItem = (clientId: string) => {
    setItems((prev) => prev.filter((it) => it.client_id !== clientId));
  };

  const handleApprove = async (q: HermesQueueItem) => {
    await onApprove(q);
    removeItem(q.client_id);
  };

  const handleReject = (q: HermesQueueItem) => {
    removeItem(q.client_id);
  };

  const approveAll = async () => {
    if (items.length === 0) return;
    const ok = window.confirm(
      `Approve all ${items.length} verified proposal(s)?\nEach was rules-engine gated green. This sends the trades to execution.`
    );
    if (!ok) return;
    setBatchBusy(true);
    setBatchErr(null);
    try {
      await onApproveBatch(items);
      if (onRefreshQueue) {
        await onRefreshQueue();
      } else {
        setItems([]);
      }
    } catch (e) {
      setBatchErr(String((e as Error).message ?? e));
    } finally {
      setBatchBusy(false);
    }
  };

  return (
    <Panel
      header="Remediation Queue"
      right={
        <span className="font-mono text-xs text-aura-text-subtle">
          {items.length} verified · {misses.length} missed
        </span>
      }
    >
      {items.length === 0 && (
        <p className="font-mono text-sm text-aura-text-muted mb-4">
          NO PROPOSALS — scan the book to populate the queue.
        </p>
      )}

      {items.length > 0 && (
        <div className="mb-4 border border-aura-emerald rounded bg-aura-surface p-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div className="font-mono text-sm font-medium text-aura-text">Bulk Action</div>
              <p className="font-mono text-xs text-aura-text-muted leading-snug">
                Approve all verified — every queued item is rules-engine green.
              </p>
            </div>
            <PrimaryButton onClick={approveAll} disabled={batchBusy} loading={batchBusy} className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">done_all</span>
              {batchBusy ? "Approving all..." : `Approve all verified (${items.length})`}
            </PrimaryButton>
          </div>
          {batchErr && <p className="font-mono text-xs text-aura-crimson mt-2">BATCH_ERR: {batchErr}</p>}
        </div>
      )}

      <div className="space-y-2 mb-5">
        {items.map((q, i) => (
          <QueueRow
            key={q.client_id}
            q={q}
            rank={i + 1}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        ))}
      </div>

      {misses.length > 0 && (
        <div className="border-t border-aura-border pt-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-symbols-outlined text-aura-crimson text-[18px]">error</span>
            <span className="font-mono text-sm font-medium text-aura-crimson uppercase tracking-wide">
              Misses — gate dropped still-red proposals
            </span>
          </div>
          <div className="space-y-1.5">
            {misses.map((m) => (
              <div key={m.client_id} className="font-mono text-xs text-aura-text-muted">
                <span className="text-aura-text font-medium">{m.client_name}</span>{" "}
                ({m.prior_status}) → {m.remaining_breaches} breach(es) remain.{" "}
                <span className="text-aura-text-subtle">{m.rationale}</span>
              </div>
            ))}
          </div>
          <p className="font-mono text-xs text-aura-text-muted mt-2">
            High miss rate feeds Hermes reflection — it proposes a strategy tweak (e.g. switch trim method).
          </p>
        </div>
      )}
    </Panel>
  );
}
