"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HermesGenerateResult, HermesGenerateJob, RunTestResult } from "@/lib/types";
import { StrategyDiff } from "./StrategyDiff";
import { GeneratedTestView } from "./GeneratedTestView";
import { PrimaryButton } from "@/components/ui/PrimaryButton";

const POLL_MS = 1500;
const MAX_POLL = 120;

export function HermesGeneratePanel({ onAdopted }: { onAdopted?: () => void }) {
  const [result, setResult] = useState<HermesGenerateResult | null>(null);
  const [job, setJob] = useState<HermesGenerateJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [adopting, setAdopting] = useState(false);
  const [adoptErr, setAdoptErr] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ status: "passed" | "failed"; result: RunTestResult } | null>(null);

  const handleJobUpdate = (j: HermesGenerateJob) => {
    setJob(j);
    if (j.status === "done") {
      if (j.result) setResult(j.result);
      setBusy(false);
    }
    if (j.status === "failed") {
      setAdoptErr(j.error || "Generate job failed");
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed") return;
    let ticks = 0;
    const id = setInterval(() => {
      ticks += 1;
      api.hermes.generateJob(job.job_id).then(handleJobUpdate);
      if (ticks >= MAX_POLL) {
        clearInterval(id);
        setAdoptErr("Generate job timed out");
        setBusy(false);
      }
    }, POLL_MS);
    return () => clearInterval(id);
  }, [job]);

  // Auto-run the generated regression test once per result so the Adopt gate
  // has a deterministic pass/fail status before the user can commit.
  useEffect(() => {
    if (!result?.test) return;
    let cancelled = false;
    api.hermes
      .runTest(result.test.source)
      .then((r) => {
        if (cancelled) return;
        setTestResult({ status: r.ok ? "passed" : "failed", result: r });
      })
      .catch((e) => {
        if (cancelled) return;
        setTestResult({
          status: "failed",
          result: { ok: false, stdout: "", stderr: String(e.message ?? e), returncode: -1 },
        });
      });
    return () => {
      cancelled = true;
    };
  }, [result?.test]);

  const generate = async () => {
    setBusy(true);
    setAdoptErr(null);
    setResult(null);
    setJob(null);
    setTestResult(null);
    try {
      const { job_id } = await api.hermes.generate({ days: 7, seed: 42 });
      const initial = await api.hermes.generateJob(job_id);
      handleJobUpdate(initial);
    } catch (e: any) {
      setAdoptErr(e.message || "Generate failed");
      setBusy(false);
    }
  };

  const adopt = async () => {
    if (!result?.diff) return;
    setAdopting(true);
    setAdoptErr(null);
    try {
      await api.hermes.adopt({
        variable: result.diff.variable,
        to: result.diff.to,
        rationale: result.diff.rationale,
      });
      onAdopted?.();
    } catch (e: any) {
      setAdoptErr(e.message || "Adopt failed");
    }
    setAdopting(false);
  };

  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="font-mono text-sm font-bold text-aura-text">Synthetic Reality → Code</h3>
          <p className="font-mono text-xs text-aura-text-muted">
            Generate a strategy diff backed by a generated regression test.
          </p>
        </div>
        <PrimaryButton onClick={generate} disabled={busy} loading={busy}>
          Generate strategy diff
        </PrimaryButton>
      </div>

      {adoptErr && <p className="font-mono text-xs text-aura-crimson">{adoptErr}</p>}

      {job?.status === "running" && (
        <p className="font-mono text-xs text-aura-text-muted flex items-center gap-2">
          <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
          Running synthetic prevent-mode simulation…
        </p>
      )}

      {result && (
        <div className="space-y-3">
          {result.diff ? (
            <>
              <StrategyDiff diff={result.diff} />
              {result.test && (
                <GeneratedTestView
                  source={result.test.source}
                  result={testResult?.result ?? null}
                  onResult={(r) => setTestResult({ status: r.ok ? "passed" : "failed", result: r })}
                />
              )}
              <PrimaryButton
                onClick={adopt}
                disabled={testResult?.status !== "passed" || adopting}
                loading={adopting}
                title={
                  testResult?.status !== "passed"
                    ? "Generated regression test must pass before adopting"
                    : undefined
                }
              >
                Adopt as next version
              </PrimaryButton>
              {result.test && testResult?.status !== "passed" && (
                <p className="font-mono text-xs text-aura-text-muted">
                  Adopt is disabled until the generated regression test passes. Run the test above.
                </p>
              )}
            </>
          ) : (
            <p className="font-mono text-xs text-aura-text-muted">
              No statistically significant improvement found for the current strategy.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
