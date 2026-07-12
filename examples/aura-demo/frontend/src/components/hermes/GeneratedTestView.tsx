"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { RunTestResult } from "@/lib/types";

export function GeneratedTestView({
  source,
  result: controlledResult,
  onResult,
}: {
  source: string;
  result?: RunTestResult | null;
  onResult?: (result: RunTestResult) => void;
}) {
  const [internalResult, setInternalResult] = useState<RunTestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const result = controlledResult !== undefined ? controlledResult : internalResult;

  const run = async () => {
    setBusy(true);
    try {
      const r = await api.hermes.runTest(source);
      if (controlledResult === undefined) setInternalResult(r);
      onResult?.(r);
    } catch (e: any) {
      const r: RunTestResult = { ok: false, stdout: "", stderr: e.message || "Run failed", returncode: -1 };
      if (controlledResult === undefined) setInternalResult(r);
      onResult?.(r);
    }
    setBusy(false);
  };

  const copy = () => navigator.clipboard.writeText(source);

  return (
    <div className="bg-aura-surface-low border border-aura-border rounded p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-aura-text-subtle">Generated regression test</span>
        <div className="flex gap-2">
          <button
            onClick={copy}
            className="text-xs font-mono text-aura-navy hover:underline"
          >
            Copy
          </button>
          <button
            onClick={run}
            disabled={busy}
            className="text-xs font-mono text-aura-navy hover:underline disabled:opacity-50"
          >
            {busy ? "Running..." : "Run test"}
          </button>
        </div>
      </div>
      <pre className="text-[10px] font-mono bg-aura-background p-2 rounded overflow-x-auto">{source}</pre>
      {result && (
        <div
          className={`text-xs font-mono ${result.ok ? "text-aura-emerald" : "text-aura-crimson"}`}
        >
          {result.ok ? "Test passed" : `Test failed: ${result.stderr.slice(0, 200)}`}
        </div>
      )}
    </div>
  );
}
