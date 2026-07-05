"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function GeneratedTestView({ source }: { source: string }) {
  const [result, setResult] = useState<{ ok: boolean; stderr: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      const r = await api.hermes.runTest(source);
      setResult(r);
    } catch (e: any) {
      setResult({ ok: false, stderr: e.message || "Run failed" });
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
