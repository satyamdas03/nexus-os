"use client";

import { useEffect, useState } from "react";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import type {
  PortfolioSummary,
  ScenarioMeta,
  ScenarioSweepJob,
} from "@/lib/types";
import { Panel } from "@/components/ui/Panel";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { useMutationGuard } from "@/components/auth/useMutationGuard";

const POLL_MS = 1500;
const MAX_POLL = 120;

const severityTone: Record<string, string> = {
  mild: "text-aura-emerald bg-aura-emerald-soft border-aura-emerald",
  moderate: "text-aura-ochre bg-aura-ochre-soft border-aura-ochre",
  severe: "text-aura-crimson bg-aura-crimson-soft border-aura-crimson",
  extreme: "text-aura-crimson bg-aura-crimson-soft border-aura-crimson",
};

export default function SyntheticPage() {
  const [portfolios, setPortfolios] = useState<PortfolioSummary[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [clientId, setClientId] = useState<string>("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [n, setN] = useState<number>(200);
  const [job, setJob] = useState<ScenarioSweepJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const guard = useMutationGuard();

  useEffect(() => {
    api.listPortfolios(200, 0).then((ps) => {
      setPortfolios(ps);
      if (ps.length && !clientId) setClientId(ps[0].client_id);
    });
    api.scenarios.list().then((res) => {
      setScenarios(res.scenarios);
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
            setBusy(false);
          }
        })
        .catch(() => {
          window.clearInterval(id);
          setBusy(false);
        });
      if (ticks >= MAX_POLL) {
        window.clearInterval(id);
        setErr("Sweep job timed out");
        setBusy(false);
      }
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [job?.job_id, job?.status]);

  const toggleScenario = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const selectAll = () => setSelected(new Set(scenarios.map((s) => s.id)));
  const clearAll = () => setSelected(new Set());

  const runSweep = async () => {
    if (!clientId) return;
    setBusy(true);
    setErr(null);
    setJob(null);
    try {
      const { job_id } = await api.scenarios.sweep({
        client_id: clientId,
        scenario_ids: selected.size ? Array.from(selected) : undefined,
        n,
        seed: 42,
        record_limit: 100,
      });
      const initial = await api.scenarios.sweepJob(job_id);
      setJob(initial);
    } catch (e: any) {
      setErr(e.message || "Sweep failed");
      setBusy(false);
    }
  };

  return (
    <div className="relative p-4 lg:p-gutter max-w-container-max mx-auto pb-32">
      <div className="mb-6">
        <h1 className="font-mono text-2xl font-bold text-aura-text">Synthetic Reality Engine</h1>
        <p className="font-mono text-xs text-aura-text-muted max-w-3xl leading-relaxed">
          Deterministic, infinite synthetic portfolios and stress scenarios. No LLM participates in the verdicts.
          Use adversarial sweeps to measure mandate fragility and generate regulator-ready reports.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-7 flex flex-col gap-6">
          <Panel
            header="Built-in Stress Scenarios"
            subheader="Immutable shock regimes from the ASSURE kernel"
            right={<span className="material-symbols-outlined text-aura-navy text-[20px]">science</span>}
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {scenarios.map((s) => {
                const active = selected.has(s.id);
                return (
                  <button
                    key={s.id}
                    onClick={() => toggleScenario(s.id)}
                    className={clsx(
                      "text-left border rounded p-3 transition-colors",
                      active
                        ? "border-aura-navy bg-aura-navy/5"
                        : "border-aura-border bg-aura-surface-low hover:bg-aura-surface"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-mono text-sm font-medium text-aura-text">{s.name}</span>
                      <span
                        className={clsx(
                          "text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded border",
                          severityTone[s.severity]
                        )}
                      >
                        {s.severity}
                      </span>
                    </div>
                    <p className="font-mono text-xs text-aura-text-muted leading-snug">{s.description}</p>
                  </button>
                );
              })}
            </div>
            <div className="flex gap-2 mt-3">
              <SecondaryButton onClick={selectAll}>Select all</SecondaryButton>
              <SecondaryButton onClick={clearAll}>Clear</SecondaryButton>
            </div>
          </Panel>
        </div>

        <div className="xl:col-span-5 flex flex-col gap-6">
          <Panel
            header="Adversarial Sweep"
            subheader="Generate synthetic portfolios, stress them, and count breaches"
            right={<span className="material-symbols-outlined text-aura-crimson text-[20px]">monitoring</span>}
          >
            <div className="space-y-3 mb-4">
              <div>
                <label className="block font-mono text-[10px] uppercase text-aura-text-subtle mb-1">
                  Portfolio / mandate
                </label>
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
                <label className="block font-mono text-[10px] uppercase text-aura-text-subtle mb-1">
                  Portfolios per scenario: {n}
                </label>
                <input
                  type="range"
                  min={50}
                  max={2000}
                  step={50}
                  value={n}
                  onChange={(e) => setN(Number(e.target.value))}
                  className="w-full accent-aura-navy"
                />
                <p className="font-mono text-[10px] text-aura-text-muted">
                  Total tests ≈ {n} × {selected.size || scenarios.length} scenarios
                </p>
              </div>
            </div>

            <PrimaryButton
              onClick={runSweep}
              disabled={!clientId || busy || guard.disabled}
              title={guard.title}
              loading={busy}
              className="w-full"
            >
              Run adversarial sweep
            </PrimaryButton>

            {err && <p className="font-mono text-xs text-aura-crimson mt-3">ERR: {err}</p>}

            {job?.status === "running" && (
              <p className="font-mono text-xs text-aura-text-muted mt-3 flex items-center gap-2">
                <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
                Running sweep…
              </p>
            )}

            {job?.status === "done" && job.result && (
              <div className="border border-aura-border rounded bg-aura-surface-low p-3 mt-3 space-y-3">
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <Metric label="Portfolios" value={job.result.total} />
                  <Metric label="Breach rate" value={`${(job.result.breach_rate * 100).toFixed(1)}%`} tone="red" />
                  <Metric label="Watch rate" value={`${(job.result.watch_rate * 100).toFixed(1)}%`} tone="ochre" />
                  <Metric label="Top rule" value={topRule(job.result.rule_breach_counts)} />
                </div>
                <a
                  href={api.scenarios.sweepReportHtmlUrl(job.job_id)}
                  target="_blank"
                  rel="noreferrer"
                  className="block w-full text-center px-4 py-2 rounded border border-aura-border text-aura-navy font-mono text-sm font-medium hover:bg-aura-surface"
                >
                  Open deterministic HTML report
                </a>
              </div>
            )}

            {job?.status === "failed" && (
              <p className="font-mono text-xs text-aura-crimson mt-3">Sweep failed: {job.error}</p>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: "red" | "ochre";
}) {
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

function topRule(counts: Record<string, number> | undefined): string {
  if (!counts) return "—";
  const entries = Object.entries(counts);
  if (!entries.length) return "—";
  entries.sort((a, b) => b[1] - a[1]);
  return entries[0][0];
}
