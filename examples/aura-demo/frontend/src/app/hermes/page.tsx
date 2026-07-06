"use client";

import { useEffect, useState } from "react";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import type {
  HermesHeartbeat,
  HermesStrategy,
  HermesQueueItem,
  HermesHistoryEntry,
  HermesAdoptResult,
  HermesApproveBatchItem,
} from "@/lib/types";
import { HermesScorePanel } from "@/components/hermes/HermesScorePanel";
import { HermesStrategyPanel } from "@/components/hermes/HermesStrategyPanel";
import { HermesQueue } from "@/components/hermes/HermesQueue";
import { HermesHistory } from "@/components/hermes/HermesHistory";
import { HermesPreventPanel } from "@/components/hermes/HermesPreventPanel";
import { HermesGeneratePanel } from "@/components/hermes/HermesGeneratePanel";
import { HermesCrashPanel } from "@/components/hermes/HermesCrashPanel";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { Panel } from "@/components/ui/Panel";
import { AboutPopover } from "@/components/guide/AboutPopover";
import { LoadingOverlay } from "@/components/ui/LoadingOverlay";
import { useMutationGuard } from "@/components/auth/useMutationGuard";

const CAGE_STAGES: { label: string; sub: string; icon: string; tone: string }[] = [
  { label: "Hermes proposes", sub: "strategy.yaml · judgment", icon: "auto_awesome", tone: "text-aura-ochre" },
  { label: "Rules engine verifies", sub: "rules_engine.py · LAW", icon: "verified_user", tone: "text-aura-emerald" },
  { label: "Human approves", sub: "final authority", icon: "gavel", tone: "text-aura-navy" },
  { label: "Feeds back to Hermes", sub: "reflection · learn", icon: "loop", tone: "text-aura-ochre" },
];

export default function HermesPage() {
  const [heartbeat, setHeartbeat] = useState<HermesHeartbeat | null>(null);
  const [queue, setQueue] = useState<HermesQueueItem[]>([]);
  const [strategy, setStrategy] = useState<HermesStrategy | null>(null);
  const [history, setHistory] = useState<HermesHistoryEntry[]>([]);
  const [scanning, setScanning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [scanPhase, setScanPhase] = useState(0);
  const [initializing, setInitializing] = useState(true);
  const [queueMode, setQueueMode] = useState<"remediate" | "prevent" | undefined>(undefined);
  const guard = useMutationGuard();

  const refreshAll = async () => {
    const [hb, strat, hist] = await Promise.all([
      api.hermes.heartbeat().catch(() => null),
      api.hermes.strategy(),
      api.hermes.history().catch(() => []),
    ]);
    setHeartbeat(hb);
    setStrategy(strat);
    setHistory(hist);
  };

  // The /hermes/queue SELECT returns `trades` as a JSON STRING (not Trade[])
  // and omits `client_name`. Coerce both at load time so the queue renders and
  // downstream approve/verify calls send arrays, not strings.
  const loadQueue = async () => {
    try {
      const page = await api.hermes.queue(undefined, 0, 50, queueMode);
      setQueue(
        page.rows.map((r) => ({
          ...r,
          trades:
            typeof r.trades === "string"
              ? JSON.parse(r.trades as unknown as string)
              : (r.trades ?? []),
          client_name: r.client_name ?? r.client_id,
        }))
      );
    } catch {
      /* keep last */
    }
  };

  useEffect(() => {
    Promise.all([refreshAll(), loadQueue()])
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setInitializing(false));
  }, []);

  useEffect(() => {
    if (!initializing) loadQueue().catch(() => {});
  }, [queueMode]);

  // Progress animation while scanning.
  useEffect(() => {
    if (!scanning) {
      setScanPhase(0);
      return;
    }
    const id = window.setInterval(() => setScanPhase((p) => (p + 1) % 100), 40);
    return () => window.clearInterval(id);
  }, [scanning]);

  // Async scan job: backend POST /hermes/scan returns {job_id}; we poll the
  // job status until done/failed, then refresh queue + heartbeat + history.
  // A full 34k-portfolio scan can take 15-30s on a dev machine, so we allow up
  // to 60s before giving up (300ms interval x 200 attempts).
  const pollJob = (jobId: string) =>
    new Promise<void>((resolve, reject) => {
      let attempts = 0;
      const tick = () => {
        attempts += 1;
        api.hermes
          .scanJob(jobId)
          .then((job) => {
            if (job.status === "done") resolve();
            else if (job.status === "failed") reject(new Error(job.error || "scan failed"));
            else if (attempts >= 200) reject(new Error("scan timeout"));
            else window.setTimeout(tick, 300);
          })
          .catch((e) => reject(e));
      };
      tick();
    });

  const scan = () => {
    if (scanning) return;
    setScanning(true);
    setErr(null);
    api.hermes
      .scan()
      .then(({ job_id }) => pollJob(job_id))
      .then(() => Promise.all([loadQueue(), refreshAll()]))
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setScanning(false));
  };

  const onAdopted = (_r: HermesAdoptResult) => {
    refreshAll().catch(() => {});
  };

  const refreshHeartbeat = () => api.hermes.heartbeat().then(setHeartbeat).catch(() => {});

  const handleApprove = async (q: HermesQueueItem) => {
    await api.approve(q.client_id, { trades: q.trades, rationale: q.rationale });
    await Promise.all([loadQueue(), refreshHeartbeat(), refreshAll()]);
  };

  const handleApproveBatch = async (items: HermesQueueItem[]) => {
    const payload: HermesApproveBatchItem[] = items.map((q) => ({
      client_id: q.client_id,
      trades: q.trades,
      rationale: q.rationale,
      mode: q.mode ?? "remediate",
    }));
    await api.hermes.approveBatch(payload);
    await Promise.all([loadQueue(), refreshAll()]);
  };

  const handleRollback = (r: { strategy: HermesStrategy; history?: HermesHistoryEntry[] }) => {
    setStrategy(r.strategy);
    if (r.history) setHistory(r.history);
    else refreshAll().catch(() => {});
    refreshHeartbeat();
  };

  if (initializing) {
    return (
      <LoadingOverlay
        label="Booting Hermes Mission Control…"
        subLabel="Loading book score, strategy, and remediation queue from the assurance engine."
      />
    );
  }

  return (
    <div className="relative p-4 lg:p-gutter max-w-container-max mx-auto pb-32">
      <div className="absolute top-4 right-4 lg:top-6 lg:right-6 z-10">
        <AboutPopover title="About Hermes">
          <p>Hermes is the book-wide self-improving remediation engine.</p>
          <p>The Assurance Cage separates LAW (mandate rules, enforced by rules_engine.py) from JUDGMENT (strategy.yaml, Hermes-tunable).</p>
          <p>Scan Book proposes trades for every non-green portfolio and gates each proposal through the rules engine before a human sees it. Prevent Scan looks ahead 14 days for currently-green portfolios and queues small preventive trades. Hermes never self-adopts and cannot touch mandate rules.</p>
        </AboutPopover>
      </div>
      {/* Scanning progress bar */}
      {scanning && (
        <div className="fixed top-0 left-0 lg:left-[220px] right-0 h-1 z-50 bg-aura-border overflow-hidden">
          <div
            className="h-full bg-aura-navy"
            style={{ width: `${scanPhase}%`, transition: "width 40ms linear" }}
          />
        </div>
      )}

      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-6">
        <div>
          <SectionHeader
            label="HERMES · Self-Improving Assurance Engine"
            title="Mission Control"
          />
          <p className="font-mono text-xs text-aura-text-muted max-w-3xl leading-relaxed">
            Autonomous book-wide remediation. Hermes proposes from strategy.yaml, the deterministic rules engine
            verifies, a human approves. Reflection learns from misses and tunes the strategy — never the mandate.
          </p>
        </div>
        <PrimaryButton onClick={scan} disabled={scanning || guard.disabled} title={guard.title} loading={scanning} className="flex items-center gap-2">
          <span className={clsx("material-symbols-outlined text-[18px]", scanning && "animate-spin")}>
            radar
          </span>
          {scanning ? "Scanning book…" : "Scan Book"}
        </PrimaryButton>
      </div>

      {/* Assurance cage diagram */}
      <p className="mb-3 font-mono text-xs text-aura-navy bg-aura-navy/5 border border-aura-navy/20 rounded p-3 flex items-start gap-2">
        <span className="material-symbols-outlined text-[18px]">tips_and_updates</span>
        <span>
          <strong>Money shot:</strong> Hermes scales the same propose → verify → approve flow across the entire book.
          Every queued trade is rules-engine green before a human ever sees it.
        </span>
      </p>
      <Panel
        data-tour="hermes"
        header="Assurance Cage · 4-Stage Gate"
        right={<span className="material-symbols-outlined text-aura-navy text-[20px]">shield</span>}
        className="mb-6"
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 items-stretch">
          {CAGE_STAGES.map((s, i) => (
            <div key={s.label} className="flex items-stretch gap-2">
              <div className="flex-1 border border-aura-border rounded bg-aura-surface-low p-3 flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className={clsx("material-symbols-outlined text-[18px]", s.tone)}>{s.icon}</span>
                  <span className="font-mono text-sm font-medium text-aura-text">{s.label}</span>
                </div>
                <span className="font-mono text-xs text-aura-text-subtle leading-snug">{s.sub}</span>
              </div>
              {i < CAGE_STAGES.length - 1 && (
                <div className="hidden md:flex items-center text-aura-border-strong font-mono text-sm">→</div>
              )}
            </div>
          ))}
        </div>
        <div className="md:hidden flex flex-col items-center gap-1 my-2 text-aura-border-strong font-mono text-xs">
          <span>↓</span>
          <span>↓</span>
          <span>↓</span>
        </div>
        <p className="font-mono text-xs text-aura-text-muted mt-4 leading-relaxed">
          <span className="text-aura-text font-medium">TWO-TIER CAGE.</span> Mandate rules = LAW (set by client,
          enforced only by deterministic{" "}
          <span className="text-aura-emerald font-medium">rules_engine.py</span>). Remediation strategy = JUDGMENT
          (<span className="text-aura-emerald font-medium">strategy.yaml</span>, Hermes-tunable). Hermes reflection
          writes ONLY strategy.yaml. Nothing auto-executes; nothing self-adopts; every change is versioned + reversible.
        </p>
      </Panel>

      {err && (
        <div className="mb-6 bg-aura-crimson-soft border border-aura-crimson rounded p-3 font-mono text-xs text-aura-crimson">
          BACKEND_UNREACHABLE — {err}. Check backend + retry.
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-7 flex flex-col gap-6">
          <HermesScorePanel heartbeat={heartbeat} />
          <HermesGeneratePanel onAdopted={refreshAll} />
          <HermesPreventPanel onPreventDone={loadQueue} />
          <HermesCrashPanel />
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <span className="font-mono text-xs text-aura-text-muted">Queue filter</span>
            <div className="flex gap-2">
              <SecondaryButton onClick={() => setQueueMode(undefined)} disabled={queueMode === undefined}>All</SecondaryButton>
              <SecondaryButton onClick={() => setQueueMode("remediate")} disabled={queueMode === "remediate"}>Remediate</SecondaryButton>
              <SecondaryButton onClick={() => setQueueMode("prevent")} disabled={queueMode === "prevent"}>Prevent</SecondaryButton>
            </div>
          </div>
          <HermesQueue
            queue={queue}
            heartbeat={heartbeat}
            onApprove={handleApprove}
            onApproveBatch={handleApproveBatch}
            onRefreshQueue={loadQueue}
          />
        </div>
        <div className="xl:col-span-5 flex flex-col gap-6">
          <HermesStrategyPanel strategy={strategy} onAdopted={onAdopted} />
          <HermesHistory history={history} onRollback={handleRollback} />
        </div>
      </div>
    </div>
  );
}
