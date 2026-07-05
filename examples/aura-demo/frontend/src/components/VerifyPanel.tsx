"use client";

import { clsx } from "clsx";
import type { RulesResult } from "@/lib/types";
import { Panel } from "@/components/ui/Panel";
import { StatusDot } from "@/components/ui/StatusDot";

export function VerifyPanel({ verification, resolved, retried, priorStatus }: {
  verification: RulesResult;
  resolved: boolean;
  retried: boolean;
  priorStatus?: string;
}) {
  const priorLabel = priorStatus === "green" ? "Aligned" : priorStatus === "orange" ? "Attention" : "Breach";
  const priorTone = priorStatus === "green" ? "green" : priorStatus === "orange" ? "orange" : "red";
  const postTone = resolved ? "green" : "red";

  return (
    <Panel header="Assurance Check" subheader="AI recommended. Assurance verifies." data-tour="verify">
      <p className="mb-4 font-mono text-xs text-aura-navy bg-aura-navy/5 border border-aura-navy/20 rounded p-3 flex items-start gap-2">
        <span className="material-symbols-outlined text-[18px]">tips_and_updates</span>
        <span>This is the assurance cage: AI proposes a trade, then the deterministic rules engine verifies the post-trade portfolio before any human approval.</span>
      </p>

      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded bg-aura-emerald-soft border border-aura-emerald flex items-center justify-center">
          <span className="material-symbols-outlined material-symbols-filled text-aura-emerald">verified_user</span>
        </div>
        <div>
          <h2 className="font-mono text-base font-semibold text-aura-text">Verification Result</h2>
          <p className="font-mono text-xs text-aura-text-muted">Deterministic rules engine review</p>
        </div>
      </div>

      <div className="bg-aura-surface rounded p-4 mb-6 border border-aura-border flex items-center justify-between relative overflow-hidden">
        <div className="flex flex-col items-center z-10 w-[40%]">
          <span className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-2">Current State</span>
          <div className={clsx(
            "px-3 py-1.5 rounded flex items-center gap-2 border font-mono",
            priorTone === "green"
              ? "bg-aura-emerald-soft text-aura-emerald border-aura-emerald"
              : priorTone === "orange"
              ? "bg-aura-ochre-soft text-aura-ochre border-aura-ochre"
              : "bg-aura-crimson-soft text-aura-crimson border-aura-crimson"
          )}>
            <StatusDot status={priorTone as any} />
            <span className="font-medium">{priorLabel.toUpperCase()}</span>
          </div>
        </div>
        <div className="z-10 flex-shrink-0 text-aura-text-muted">
          <span className="material-symbols-outlined">arrow_forward</span>
        </div>
        <div className="flex flex-col items-center z-10 w-[40%]">
          <span className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-2">Post-Trade</span>
          <div className={clsx(
            "px-3 py-1.5 rounded flex items-center gap-2 border font-mono",
            resolved
              ? "bg-aura-emerald-soft text-aura-emerald border-aura-emerald"
              : "bg-aura-crimson-soft text-aura-crimson border-aura-crimson"
          )}>
            <StatusDot status={postTone} />
            <span className="font-medium">{resolved ? "COMPLIANT" : "BREACH"}</span>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider">Mandate Verification</h3>
        {verification.per_rule.map((r) => {
          const currentNum = Array.isArray(r.current) ? `${r.current.length} items` : `${(Number(r.current) * 100).toFixed(1)}%`;
          const limitNum = Array.isArray(r.limit) ? "list" : `${(Number(r.limit) * 100).toFixed(1)}%`;
          return (
            <div key={r.rule} className="flex items-start gap-3">
              <span className={`material-symbols-outlined text-[18px] mt-0.5 ${r.pass ? "text-aura-emerald material-symbols-filled" : "text-aura-crimson"}`}>
                {r.pass ? "check_circle" : "cancel"}
              </span>
              <div className="flex-1">
                <div className="font-mono text-sm text-aura-text flex justify-between">
                  <span>{r.rule}</span>
                  <span className="text-xs text-aura-text-muted tabular-nums">{currentNum} / {limitNum}</span>
                </div>
                <div className="font-mono text-xs text-aura-text-muted mt-0.5">
                  {r.pass ? "Passes mandate check" : "Breach threshold exceeded"}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {retried && (
        <p className="mt-4 font-mono text-xs text-aura-text-muted">Agent retried once to find a compliant path.</p>
      )}
      <p className="mt-4 font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider flex items-center gap-2">
        <span className="material-symbols-outlined text-[14px]">lock</span>
        Approval is blocked until the rules engine reports COMPLIANT.
      </p>
    </Panel>
  );
}
