"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Portfolio, RemediationResult, Trade, RulesResult } from "@/lib/types";
import { WorkbenchTable } from "@/components/WorkbenchTable";
import { VerifyPanel } from "@/components/VerifyPanel";
import { AuditTrail } from "@/components/AuditTrail";
import { SuggestionChip } from "@/components/SuggestionChip";
import { StatusBadge } from "@/components/StatusBadge";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { AboutPopover } from "@/components/guide/AboutPopover";
import { LoadingOverlay } from "@/components/ui/LoadingOverlay";
import { useMutationGuard } from "@/components/auth/useMutationGuard";
import { useAuth } from "@/components/auth/AuthContext";

export default function Workbench({ params }: { params: { id: string } }) {
  const guard = useMutationGuard();
  const { isAdmin } = useAuth();
  const { id } = params;
  const [p, setP] = useState<Portfolio | null>(null);
  const [res, setRes] = useState<RemediationResult | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [liveVerify, setLiveVerify] = useState<RulesResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [approved, setApproved] = useState(false);
  const [approving, setApproving] = useState(false);
  const [newStatus, setNewStatus] = useState<string | null>(null);
  const [err, setErr] = useState(false);
  const [approveErr, setApproveErr] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [approvedRulesResult, setApprovedRulesResult] = useState<RulesResult | null>(null);

  useEffect(() => {
    setApprovedRulesResult(null);
    api.getPortfolio(id).then(setP).catch(() => setErr(true));
  }, [id]);

  if (err) return <div className="p-8 font-mono text-aura-crimson">Backend unreachable. Check backend and retry.</div>;
  if (!p) {
    return (
      <LoadingOverlay
        label="Loading remediation workbench…"
        subLabel={`Fetching ${id} holdings and current mandate status for the assurance cage.`}
      />
    );
  }

  const propose = () => {
    setBusy(true);
    api.remediate(id).then((r) => { setRes(r); setTrades(r.trades); setLiveVerify(null); }).finally(() => setBusy(false));
  };

  const onTradesChange = (next: Trade[]) => {
    setTrades(next);
    api.verify(id, next).then(setLiveVerify).catch(() => setLiveVerify(null));
  };

  const approve = async () => {
    if (approving) return;
    setApproving(true);
    setApproveErr(null);
    try {
      const r = await api.approve(id, {
        trades,
        rationale: res?.resolved && !liveVerify ? "approved AI proposal" : "approved with manual edits",
        breach_type: p.rules_result!.breaches[0]?.rule,
        choice: trades[0] ? `${trades[0].action} ${trades[0].ticker}` : "manual",
      });
      setApproved(true);
      setNewStatus(r?.new_status ?? null);
      if (r?.rules_result) {
        setApprovedRulesResult(r.rules_result);
        setP((prev) => (prev ? { ...prev, rules_result: r.rules_result } : prev));
      }
    } catch (e) {
      setApproveErr(String((e as Error).message ?? e ?? "Approve failed. Check backend and retry."));
    } finally {
      setApproving(false);
    }
  };

  const aumImpact = trades.reduce((s, t) => s + Math.abs(t.value), 0) || 0;
  const verifyResult = liveVerify ?? approvedRulesResult ?? res?.verification ?? null;
  const resolved = verifyResult ? verifyResult.status === "green" : res?.resolved ?? false;

  const perRule = verifyResult?.per_rule ?? res?.verification?.per_rule ?? [];
  const rulesPass = perRule.filter((r) => r.pass).length;
  const rulesTotal = perRule.length;
  const confidenceLabel = verifyResult
    ? rulesTotal ? `Rules: ${rulesPass}/${rulesTotal} pass${res?.retried ? " - retried" : ""}` : `Verified by rules engine${res?.retried ? " - retried" : ""}`
    : null;

  const resetDemo = () => {
    if (!window.confirm("Reset demo state? This clears all applied trades across the book and resets the Hermes runtime. This cannot be undone.")) return;
    setResetting(true);
    api.reset().then(() => window.location.reload()).catch(() => { setResetting(false); window.alert("Reset failed. Check backend and retry."); });
  };

  return (
    <div className="relative p-4 lg:p-6 max-w-[1440px] mx-auto pb-32">
      <div className="absolute top-4 right-4 lg:top-6 lg:right-6 z-10">
        <AboutPopover title="About Workbench">
          <p>The AI proposes minimal compliant trades; the Assurance Check panel re-runs the deterministic rules engine on the post-trade portfolio.</p>
          <p>Edits to units or value are re-verified live.</p>
          <p>Nothing executes automatically. Approve & Log records the intent and appends the audit trail.</p>
        </AboutPopover>
      </div>
      <Link href={`/portfolio/${id}`} className="inline-flex items-center gap-1.5 text-aura-text-muted hover:text-aura-navy font-mono text-xs mb-4">
        <span className="material-symbols-outlined text-[16px]">arrow_back</span>
        <span className="uppercase tracking-wide">Back to Diagnosis</span>
      </Link>

      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-6">
        <div className="w-full">
          <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">Portfolio Delta Sync // {id}</p>
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <h1 className="font-mono text-2xl font-bold text-aura-text">Remediation Workbench</h1>
            <StatusBadge status={p.rules_result!.status} />
          </div>
          <p className="font-mono text-xs text-aura-text-muted">Entity: {p.client_name}</p>
        </div>
        <div className="text-right w-full md:w-auto flex flex-col items-end gap-3">
          <div>
            <p className="font-mono text-[10px] uppercase text-aura-text-subtle mb-1">AUM Impact</p>
            <p className="font-mono text-base font-bold tabular-nums text-aura-navy">${(aumImpact / 1e3).toFixed(0)}k ({((aumImpact / p.fum) * 100).toFixed(1)}%)</p>
          </div>
          <SecondaryButton
            onClick={resetDemo}
            disabled={resetting || !isAdmin}
            title={!isAdmin ? "Admin only" : undefined}
            loading={resetting}
            className="flex items-center gap-2 text-aura-crimson border-aura-crimson hover:bg-aura-crimson-soft"
          >
            <span className="material-symbols-outlined text-[16px]">restart_alt</span>
            {resetting ? "Resetting..." : "Reset demo state"}
          </SecondaryButton>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-8 flex flex-col gap-4">
          <div className="bg-aura-surface-low border border-aura-border rounded p-4 relative overflow-hidden" data-tour="strategy">
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-aura-navy" />
            <div className="pl-4">
              <div className="flex items-center gap-2 text-aura-navy mb-2">
                <span className="material-symbols-outlined material-symbols-filled">auto_awesome</span>
                <h3 className="font-mono text-base font-semibold">AI Remediation Strategy</h3>
                {confidenceLabel && <span className="ml-2 font-mono text-[10px] uppercase px-2 py-0.5 rounded border border-aura-emerald text-aura-emerald bg-aura-emerald-soft">{confidenceLabel}</span>}
              </div>
              <p className="font-mono text-sm text-aura-text-muted">
                {trades.length
                  ? `Proposed: ${trades.map((t) => `${t.action.toUpperCase()} ${t.ticker}`).join(", ")} to resolve mandate breaches and restore compliance. Edit units to test alternatives — re-verified live by the rules engine.`
                  : "Click 'Propose a fix' to generate an AI-assisted remediation strategy grounded in the deterministic rules engine."}
              </p>
            </div>
          </div>

          <WorkbenchTable trades={trades} portfolio={p} editable={!!res && !guard.disabled} onTradesChange={onTradesChange} />
          <SuggestionChip clientId={id} />
        </div>

        <div className="xl:col-span-4">
          <div className="xl:sticky xl:top-6 space-y-4">
            {verifyResult ? (
              <VerifyPanel verification={verifyResult} resolved={resolved} retried={res?.retried ?? false} priorStatus={p.rules_result?.status ?? "unknown"} />
            ) : (
              <div className="bg-aura-surface-low border border-aura-border rounded p-4">
                <p className="font-mono text-sm text-aura-text-muted">Click "Propose a fix" to generate compliant trades.</p>
              </div>
            )}
            {liveVerify && (
              <div className="bg-aura-ochre-soft border border-aura-ochre rounded p-3 font-mono text-xs text-aura-ochre">
                Live re-verify: trader edit rechecked by rules engine.
              </div>
            )}
          </div>
        </div>
      </div>

      {approveErr && (
        <div className="my-6 bg-aura-crimson-soft border border-aura-crimson rounded p-4 flex items-center gap-3">
          <span className="material-symbols-outlined text-aura-crimson">error</span>
          <div className="font-mono text-xs text-aura-crimson"><span className="font-medium">Approve failed.</span> {approveErr}</div>
        </div>
      )}

      {approved && (
        <div className="my-6 bg-aura-emerald-soft border border-aura-emerald rounded p-4 flex items-center gap-3">
          <span className="material-symbols-outlined text-aura-emerald material-symbols-filled">check_circle</span>
          <div className="font-mono text-xs">
            <span className="text-aura-text">Approved and logged.</span>{" "}
            <span className="text-aura-text-muted">Rules engine re-checked the effective portfolio: status <span className={newStatus === "green" ? "text-aura-emerald" : "text-aura-ochre"}>{newStatus?.toUpperCase() ?? "GREEN"}</span>. Audit trail appended.</span>
          </div>
        </div>
      )}

      <AuditTrail clientId={id} />

      <div className="hidden lg:flex fixed bottom-0 right-0 w-[calc(100%-220px)] bg-aura-surface/95 backdrop-blur border-t border-aura-border p-4 px-6 justify-between items-center z-40">
        <div className="flex items-center gap-2 text-aura-text-muted max-w-xl">
          <span className="material-symbols-outlined text-[20px]">info</span>
          <span className="font-mono text-xs">Nothing executes automatically. Approving logs the intent and queues orders for manual trader review.</span>
        </div>
        <div className="flex items-center gap-3">
          <SecondaryButton onClick={propose} disabled={busy || approving || guard.disabled} title={guard.title} loading={busy}>{busy ? "Proposing..." : "Propose a fix"}</SecondaryButton>
          <PrimaryButton onClick={approve} disabled={!res || approved || approving || guard.disabled} title={guard.title} loading={approving} className="flex items-center gap-2" data-tour="approve">
            <span className="material-symbols-outlined text-[18px]">gavel</span>
            {approved ? "Approved" : approving ? "Approving..." : "Approve & Log"}
          </PrimaryButton>
        </div>
      </div>

      <div className="lg:hidden mt-8 flex flex-col gap-3">
        <p className="font-mono text-xs text-aura-text-muted flex items-start gap-2">
          <span className="material-symbols-outlined text-[18px]">info</span>
          Nothing executes automatically. Approving logs the intent and queues orders for manual review.
        </p>
        <div className="flex gap-3">
          <SecondaryButton onClick={propose} disabled={busy || approving || guard.disabled} title={guard.title} loading={busy} className="flex-1">{busy ? "Proposing..." : "Propose a fix"}</SecondaryButton>
          <PrimaryButton onClick={approve} disabled={!res || approved || approving || guard.disabled} title={guard.title} loading={approving} className="flex-1 flex items-center justify-center gap-2">
            <span className="material-symbols-outlined text-[18px]">gavel</span>
            {approved ? "Approved" : approving ? "Approving..." : "Approve & Log"}
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}
