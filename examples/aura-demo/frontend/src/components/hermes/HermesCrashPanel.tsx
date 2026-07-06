"use client";

import { useEffect, useState } from "react";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import type {
  PortfolioSummary,
  ScenarioMeta,
  ScenarioApplyResult,
  ScenarioStressPortfolioResult,
  ScenarioSweepJob,
  Status,
} from "@/lib/types";
import { Panel } from "@/components/ui/Panel";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { StatusBadge } from "@/components/StatusBadge";
import { useMutationGuard } from "@/components/auth/useMutationGuard";

const POLL_MS = 1500;
const MAX_POLL = 120;

const severityTone: Record<string, string> = {
  mild: "text-aura-emerald bg-aura-emerald-soft border-aura-emerald",
  moderate: "text-aura-ochre bg-aura-ochre-soft border-aura-ochre",
  severe: "text-aura-crimson bg-aura-crimson-soft border-aura-crimson",
  extreme: "text-aura-crimson bg-aura-crimson-soft border-aura-crimson",
};

export function HermesCrashPanel() {
  const [portfolios, setPortfolios] = useState<PortfolioSummary[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [clientId, setClientId] = useState<string>("");
  const [scenarioId, setScenarioId] = useState<string>("");
  const [applyResult, setApplyResult] = useState<ScenarioApplyResult | null>(null);
  const [stressResult, setStressResult] = useState<ScenarioStressPortfolioResult | null>(null);
  const [job, setJob] = useState<ScenarioSweepJob | null>(null);
  const [busyApply, setBusyApply] = useState(false);
  const [busyStress, setBusyStress] = useState(false);
  const [busySweep, setBusySweep] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const guard = useMutationGuard();

  useEffect(() => {
    api.listPortfolios(200, 0).then((ps) => {
      setPortfolios(ps);
      if (ps.length && !clientId) setClientId(ps[0].client_id);
    });
    api.scenarios.list().then((res) => {
      setScenarios(res.scenarios);
      if (res.scenarios.length && !scenarioId) setScenarioId(res.scenarios[0].id);
    });
  }, []);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed") return;
    let ticks = 0;
    const id = window.setInterval(() => {
      ticks += 1;
      api.scenarios
        .sweepJob(job.job_id)
        .then((j) => {
          setJob(j);
          if (j.status === "done" || j.status === "failed") {
            window.clearInterval(id);
            setBusySweep(false);
          }
        })
        .catch(() => {
          window.clearInterval(id);
          setBusySweep(false);
        });
      if (ticks >= MAX_POLL) {
        window.clearInterval(id);
        setErr("Sweep job timed out");
        setBusySweep(false);
      }
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [job?.job_id, job?.status]);

  const apply = async () => {
    if (!clientId || !scenarioId) return;
    setBusyApply(true);
    setErr(null);
    setApplyResult(null);
    try {
      const res = await api.scenarios.apply({ client_id: clientId, scenario_id: scenarioId });
      setApplyResult(res);
    } catch (e: any) {
      setErr(e.message || "Apply failed");
    }
    setBusyApply(false);
  };

  const stressAll = async () => {
    if (!clientId) return;
    setBusyStress(true);
    setErr(null);
    setStressResult(null);
    try {
      const res = await api.scenarios.stressPortfolio({ client_id: clientId });
      setStressResult(res);
    } catch (e: any) {
      setErr(e.message || "Stress portfolio failed");
    }
    setBusyStress(false);
  };

  const sweep = async () => {
    if (!clientId) return;
    setBusySweep(true);
    setErr(null);
    setJob(null);
    try {
      const { job_id } = await api.scenarios.sweep({
        client_id: clientId,
        scenario_ids: scenarioId ? [scenarioId] : undefined,
        n: 200,
        seed: 42,
        record_limit: 100,
      });
      const initial = await api.scenarios.sweepJob(job_id);
      setJob(initial);
    } catch (e: any) {
      setErr(e.message || "Sweep failed");
      setBusySweep(false);
    }
  };

  return (
    <Panel
      header="Crash Scenario Testing"
      subheader="Deterministic stress scenarios from the ASSURE Synthetic Reality Engine"
      right={<span className="material-symbols-outlined text-aura-crimson text-[20px]">monitoring</span>}
    >
      <p className="font-mono text-xs text-aura-text-muted leading-snug mb-4">
        Test how a portfolio behaves under 2008-style equity crashes, rapid rate hikes, crypto winters,
        and more. Every shock is deterministic and read-only — the live book is never touched.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div>
          <label className="block font-mono text-[10px] uppercase text-aura-text-subtle mb-1">Portfolio</label>
          <select
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="w-full px-3 py-2 rounded border border-aura-border bg-aura-background text-sm"
          >
            <option value="">Select portfolio</option>
            {portfolios.map((p) => (
              <option key={p.client_id} value={p.client_id}>
                {p.client_name} ({p.client_id})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block font-mono text-[10px] uppercase text-aura-text-subtle mb-1">Scenario</label>
          <select
            value={scenarioId}
            onChange={(e) => setScenarioId(e.target.value)}
            className="w-full px-3 py-2 rounded border border-aura-border bg-aura-background text-sm"
          >
            <option value="">All / adversarial</option>
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end gap-2">
          <PrimaryButton
            onClick={apply}
            disabled={!clientId || !scenarioId || busyApply || guard.disabled}
            title={guard.title}
            loading={busyApply}
            className="flex-1"
          >
            Apply scenario
          </PrimaryButton>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <SecondaryButton
          onClick={stressAll}
          disabled={!clientId || busyStress || guard.disabled}
          title={guard.title}
          loading={busyStress}
        >
          Stress all scenarios
        </SecondaryButton>
        <SecondaryButton
          onClick={sweep}
          disabled={!clientId || busySweep || guard.disabled}
          title={guard.title}
          loading={busySweep}
        >
          Adversarial sweep
        </SecondaryButton>
        {job?.status === "done" && job.result && (
          <a
            href={api.scenarios.sweepReportHtmlUrl(job.job_id)}
            target="_blank"
            rel="noreferrer"
            className="px-4 py-2 rounded border border-aura-border text-aura-navy font-mono text-sm font-medium hover:bg-aura-surface inline-flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-[18px]">open_in_new</span>
            Open HTML report
          </a>
        )}
      </div>

      {err && <p className="font-mono text-xs text-aura-crimson mb-3">ERR: {err}</p>}

      {applyResult && (
        <div className="border border-aura-border rounded bg-aura-surface-low p-3 space-y-3 mb-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="font-mono text-sm font-medium text-aura-text">
              {scenarios.find((s) => s.id === applyResult.scenario_id)?.name ?? applyResult.scenario_id}
            </span>
            <span
              className={clsx(
                "font-mono text-xs px-2 py-0.5 rounded border",
                applyResult.value_change_pct >= 0
                  ? "text-aura-emerald bg-aura-emerald-soft border-aura-emerald"
                  : "text-aura-crimson bg-aura-crimson-soft border-aura-crimson"
              )}
            >
              {applyResult.value_change_pct >= 0 ? "+" : ""}
              {(applyResult.value_change_pct * 100).toFixed(2)}%
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <StatusCard label="Baseline" status={applyResult.baseline_status} value={applyResult.baseline_value} />
            <StatusCard label="Stressed" status={applyResult.stressed_status} value={applyResult.stressed_value} />
            <div className="border border-aura-border rounded p-2">
              <span className="block text-[10px] text-aura-text-subtle uppercase">baseline breaches</span>
              <span className="font-mono text-sm font-medium text-aura-text">
                {applyResult.baseline_rules_result.breaches.length}
              </span>
            </div>
            <div className="border border-aura-border rounded p-2">
              <span className="block text-[10px] text-aura-text-subtle uppercase">stressed breaches</span>
              <span className="font-mono text-sm font-medium text-aura-text">
                {applyResult.stressed_rules_result.breaches.length}
              </span>
            </div>
          </div>
        </div>
      )}

      {stressResult && (
        <div className="border border-aura-border rounded bg-aura-surface-low p-3 mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-sm font-medium text-aura-text">Scenario map</span>
            <StatusBadge status={stressResult.baseline_status} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-left text-aura-text-subtle border-b border-aura-border">
                  <th className="py-1">Scenario</th>
                  <th className="py-1">Status</th>
                  <th className="py-1">Δ value</th>
                  <th className="py-1">Breaches</th>
                  <th className="py-1">Watches</th>
                </tr>
              </thead>
              <tbody>
                {stressResult.scenarios.map((row) => (
                  <tr key={row.scenario_id} className="border-b border-aura-border/50">
                    <td className="py-1">
                      {scenarios.find((s) => s.id === row.scenario_id)?.name ?? row.scenario_id}
                    </td>
                    <td className="py-1">
                      <StatusBadge status={row.stressed_status} />
                    </td>
                    <td className={clsx("py-1", row.value_change_pct >= 0 ? "text-aura-emerald" : "text-aura-crimson")}>
                      {row.value_change_pct >= 0 ? "+" : ""}
                      {(row.value_change_pct * 100).toFixed(2)}%
                    </td>
                    <td className="py-1 text-aura-crimson">{row.breach_count}</td>
                    <td className="py-1 text-aura-ochre">{row.watch_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {job?.status === "running" && (
        <p className="font-mono text-xs text-aura-text-muted flex items-center gap-2">
          <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
          Running adversarial sweep…
        </p>
      )}

      {job?.status === "done" && job.result && (
        <div className="border border-aura-border rounded bg-aura-surface-low p-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono">
            <Metric label="Portfolios" value={job.result.total} />
            <Metric label="Breach rate" value={`${(job.result.breach_rate * 100).toFixed(1)}%`} tone="red" />
            <Metric label="Watch rate" value={`${(job.result.watch_rate * 100).toFixed(1)}%`} tone="ochre" />
            <Metric label="Scenarios" value={Object.keys(job.result.scenario_status_counts ?? {}).length} />
          </div>
        </div>
      )}

      {job?.status === "failed" && <p className="font-mono text-xs text-aura-crimson">Sweep failed: {job.error}</p>}
    </Panel>
  );
}

function StatusCard({ label, status, value }: { label: string; status: Status; value: number }) {
  return (
    <div className="border border-aura-border rounded p-2">
      <span className="block text-[10px] text-aura-text-subtle uppercase">{label}</span>
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-medium text-aura-text">${value.toLocaleString()}</span>
        <StatusBadge status={status} />
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string | number; tone?: "red" | "ochre" }) {
  return (
    <div className="border border-aura-border rounded p-2">
      <span className="block text-[10px] text-aura-text-subtle uppercase">{label}</span>
      <span
        className={clsx(
          "font-mono text-sm font-medium",
          tone === "red" ? "text-aura-crimson" : tone === "ochre" ? "text-aura-ochre" : "text-aura-text"
        )}
      >
        {value}
      </span>
    </div>
  );
}
