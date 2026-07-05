"use client";

import { useState } from "react";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import { Panel } from "@/components/ui/Panel";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import type { HermesSimulationResult, HermesScanJob } from "@/lib/types";
import { useMutationGuard } from "@/components/auth/useMutationGuard";

const pollJob = (jobId: string): Promise<HermesScanJob> =>
  new Promise((resolve, reject) => {
    let attempts = 0;
    const tick = () => {
      attempts += 1;
      api.hermes
        .scanJob(jobId)
        .then((job) => {
          if (job.status === "done" || job.status === "failed") resolve(job);
          else if (attempts >= 200) reject(new Error("scan timeout"));
          else window.setTimeout(tick, 300);
        })
        .catch((e) => reject(e));
    };
    tick();
  });

export function HermesPreventPanel({
  onPreventDone,
}: {
  onPreventDone?: () => void;
}) {
  const [scanning, setScanning] = useState(false);
  const [simBusy, setSimBusy] = useState(false);
  const [simResult, setSimResult] = useState<HermesSimulationResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const guard = useMutationGuard();

  const preventScan = () => {
    if (scanning) return;
    setScanning(true);
    setErr(null);
    api.hermes
      .preventScan()
      .then(({ job_id }) => pollJob(job_id))
      .then(() => onPreventDone?.())
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setScanning(false));
  };

  const runSim = (mode: "reactive" | "prevent") => {
    setSimBusy(true);
    setErr(null);
    api.hermes
      .simulate({ days: 100, mode, seed: 42 })
      .then(setSimResult)
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setSimBusy(false));
  };

  const reduction =
    simResult?.reactive_incidence != null &&
    simResult?.prevent_incidence != null &&
    simResult.reactive_incidence > 0
      ? ((simResult.reactive_incidence - simResult.prevent_incidence) / simResult.reactive_incidence) * 100
      : null;

  return (
    <Panel
      header="Hermes 2.0 · Proactive Drift Prevention"
      right={<span className="material-symbols-outlined text-aura-navy text-[20px]">shield</span>}
    >
      <p className="font-mono text-xs text-aura-text-muted leading-snug mb-4">
        Looks 14 days ahead at currently-green portfolios, predicts breach risk via a deterministic GBM model,
        and queues small preventive trades that keep the book green while reducing projected risk. Still gated
        by the rules engine; human approval required unless a low-risk policy band auto-approves.
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        <PrimaryButton onClick={preventScan} disabled={scanning || guard.disabled} title={guard.title} loading={scanning} className="flex items-center gap-2">
          <span className={clsx("material-symbols-outlined text-[18px]", scanning && "animate-spin")}>
            radar
          </span>
          {scanning ? "Prevent scan…" : "Prevent Scan"}
        </PrimaryButton>
        <SecondaryButton onClick={() => runSim("reactive")} disabled={simBusy || guard.disabled} title={guard.title} loading={simBusy}>
          Simulate 100d reactive
        </SecondaryButton>
        <SecondaryButton onClick={() => runSim("prevent")} disabled={simBusy || guard.disabled} title={guard.title} loading={simBusy}>
          Simulate 100d prevent
        </SecondaryButton>
      </div>

      {err && <p className="font-mono text-xs text-aura-crimson mb-3">ERR: {err}</p>}

      {simResult && (
        <div className="border border-aura-border rounded bg-aura-surface-low p-3 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="font-mono text-sm font-medium text-aura-text">
              Simulation · {simResult.mode} · {simResult.days} days
            </span>
            {reduction != null && (
              <span className={clsx(
                "font-mono text-xs font-semibold px-2 py-0.5 rounded",
                reduction >= 50
                  ? "bg-aura-emerald-soft text-aura-emerald border border-aura-emerald"
                  : "bg-aura-ochre-soft text-aura-ochre border border-aura-ochre"
              )}>
                {reduction >= 0 ? "↓" : "↑"} {Math.abs(reduction).toFixed(1)}% breach incidence
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-xs font-mono">
            <div className="border border-aura-border rounded p-2">
              <span className="block text-aura-text-subtle">mode</span>
              <span className="text-aura-text font-medium">{simResult.mode}</span>
            </div>
            <div className="border border-aura-border rounded p-2">
              <span className="block text-aura-text-subtle">seed</span>
              <span className="text-aura-text font-medium">{simResult.seed ?? "default"}</span>
            </div>
            <div className="border border-aura-border rounded p-2">
              <span className="block text-aura-text-subtle">prevent trades</span>
              <span className="text-aura-text font-medium">{simResult.approved_prevent_trades}</span>
            </div>
            <div className="border border-aura-border rounded p-2">
              <span className="block text-aura-text-subtle">prevented days</span>
              <span className="text-aura-text font-medium">{simResult.prevented_breaches}</span>
            </div>
            {simResult.reactive_incidence != null && (
              <div className="border border-aura-border rounded p-2">
                <span className="block text-aura-text-subtle">reactive incidence</span>
                <span className="text-aura-text font-medium">{simResult.reactive_incidence}</span>
              </div>
            )}
            {simResult.prevent_incidence != null && (
              <div className="border border-aura-border rounded p-2">
                <span className="block text-aura-text-subtle">prevent incidence</span>
                <span className="text-aura-text font-medium">{simResult.prevent_incidence}</span>
              </div>
            )}
          </div>

          <div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle mb-1">
              Daily breach counts (red + orange)
            </div>
            <div className="flex items-end gap-1 h-16">
              {simResult.series.map((pt) => {
                const h = Math.min(100, (pt.counts.red + pt.counts.orange) / 5);
                return (
                  <div
                    key={pt.day}
                    className={clsx(
                      "flex-1 rounded-sm",
                      pt.counts.red > 0 ? "bg-aura-crimson" : "bg-aura-ochre"
                    )}
                    style={{ height: `${Math.max(4, h * 0.64)}px` }}
                    title={`day ${pt.day}: ${pt.counts.red + pt.counts.orange}`}
                  />
                );
              })}
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
