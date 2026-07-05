import type { PortfolioSummary, Portfolio, RulesResult, RemediationResult, AuditEntry, ApproveResult, ExplainResult, SummaryAiResult, EvidencePack, HermesStrategy, HermesProposal, HermesAdoptResult, HermesHeartbeat, HermesHistoryEntry, HermesApproveBatchItem, HermesApproveBatchResult, HermesRollbackResult, MarketClock, MarketHistoryPoint, MarketPrices, MarketStatus, TopSafeguard, HermesQueuePage, HermesScanJob, MandateDetail } from "./types";

function base() {
  // Client (browser): same-origin /api, proxied to backend via next.config rewrites.
  // Server (RSC on Vercel): absolute API_URL (server-only env); localhost in dev.
  // No NEXT_PUBLIC_* — client never knows the backend URL, so no build-time baking.
  if (typeof window === "undefined") return process.env.API_URL || "http://127.0.0.1:8000";
  return "/api";
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${base()}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json() as Promise<T>;
}

// Backend `get_clock()` returns SQLite ints (0/1) for `running`/`auto_fix`;
// coerce to real booleans so the UI gets honest bools.
const _clock = (r: any): MarketClock => ({
  day: r.day, running: !!r.running, auto_interval_sec: r.auto_interval_sec,
  auto_fix: !!r.auto_fix, seed: r.seed,
});

export const api = {
  listPortfolios: (limit = 500, offset = 0) =>
    j<PortfolioSummary[]>(`/portfolios?limit=${limit}&offset=${offset}`),
  portfoliosTop: (limit = 200) =>
    j<TopSafeguard>(`/portfolios/top?limit=${limit}`),
  getPortfolio: (id: string) => j<Portfolio>(`/portfolio/${id}`),
  getMandate: (id: string) => j<MandateDetail>(`/portfolio/${id}/mandate`),
  check: (id: string) => j<RulesResult>(`/portfolio/${id}/check`),
  explain: (id: string, metric?: string, signal?: AbortSignal) =>
    j<ExplainResult>(`/portfolio/${id}/explain`, {
      method: "POST", body: JSON.stringify(metric ? { metric } : {}), signal,
    }),
  verify: (id: string, trades: any[]) =>
    j<RulesResult>(`/portfolio/${id}/verify`, { method: "POST", body: JSON.stringify({ trades }) }),
  remediate: (id: string) =>
    j<RemediationResult>(`/portfolio/${id}/remediate`, { method: "POST" }),
  approve: (id: string, body: { trades: any[]; rationale: string; breach_type?: string | null; choice?: string | null }) =>
    j<ApproveResult>(`/portfolio/${id}/approve`, {
      method: "POST", body: JSON.stringify(body),
    }),
  audit: () => j<AuditEntry[]>("/audit"),
  summary: () => j<{ total: number; counts: Record<string, number>; breach_count: number }>("/portfolios/summary"),
  summaryAi: () => j<SummaryAiResult>("/portfolios/summary_ai"),
  reset: () => {
    const headers: Record<string, string> = {};
    if (typeof window !== "undefined") {
      const secret = window.sessionStorage.getItem("admin_secret");
      if (secret) headers["X-Admin-Secret"] = secret;
    }
    return j<{ ok: boolean; cleared: string[]; extra: string[] }>("/admin/reset", { method: "POST", headers });
  },
  market: {
    clock: () => j<any>("/market/clock").then(_clock),
    tick: () => j<any>("/market/tick", { method: "POST" }).then(_clock),
    advance: (days: number) =>
      j<any>(`/market/advance?days=${days}`, { method: "POST" }).then(_clock),
    autorun: (on: boolean, interval_sec = 5) =>
      j<any>("/market/auto-run", { method: "POST", body: JSON.stringify({ on, interval_sec }) }).then(_clock),
    autofix: (on: boolean) =>
      j<any>("/market/auto-fix", { method: "POST", body: JSON.stringify({ on }) }).then(_clock),
    prices: () => j<MarketPrices>("/market/prices"),
    history: (fromDay?: number, toDay?: number) => {
      const params = new URLSearchParams();
      if (fromDay != null) params.set("from_day", String(fromDay));
      if (toDay != null) params.set("to_day", String(toDay));
      const qs = params.toString();
      return j<MarketHistoryPoint[]>(`/market/history${qs ? `?${qs}` : ""}`);
    },
    status: () => j<MarketStatus>("/market/status"),
  },
  reflect: (id: string) => j<{ suggestion: any | null }>(`/portfolio/${id}/reflect`, { method: "POST" }),
  adopt: (body: { breach_type: string; preference: string; rationale: string }) =>
    j<{ ok: boolean; version: number }>("/preferences/adopt", { method: "POST", body: JSON.stringify(body) }),

  // Hermes — book-wide self-improving remediation engine.
  hermes: {
    scan: () => j<{ job_id: string }>("/hermes/scan", { method: "POST" }),
    queue: (day?: number, cursor = 0, limit = 50) =>
      j<HermesQueuePage>(`/hermes/queue?cursor=${cursor}&limit=${limit}${day != null ? `&day=${day}` : ""}`),
    scanJob: (jobId: string) => j<HermesScanJob>(`/hermes/scan/${jobId}`),
    strategy: () => j<HermesStrategy>("/hermes/strategy"),
    reflect: (mode: "fallback" | "hermes") =>
      j<HermesProposal>("/hermes/reflect", { method: "POST", body: JSON.stringify({ mode }) }),
    adopt: (body: { variable: string; to: any; rationale: string }) =>
      j<HermesAdoptResult>("/hermes/adopt", { method: "POST", body: JSON.stringify(body) }),
    heartbeat: () => j<HermesHeartbeat>("/hermes/heartbeat"),
    history: () => j<HermesHistoryEntry[]>("/hermes/history"),
    approveBatch: (items: HermesApproveBatchItem[]) =>
      j<HermesApproveBatchResult>("/hermes/approve-batch", { method: "POST", body: JSON.stringify({ items }) }),
    rollback: (version: number) =>
      j<HermesRollbackResult>("/hermes/rollback", { method: "POST", body: JSON.stringify({ version }) }),
  },

  // Evidence Pack — read-only compliance proof artifact for a single portfolio.
  evidence: {
    portfolio: (clientId: string) => j<EvidencePack>(`/evidence/portfolio/${clientId}`),
    portfolioHtmlUrl: (clientId: string) => `${base()}/evidence/portfolio/${clientId}/html`,
  },

  // Conversational Assurance — grounded chat + optional LiveKit voice transport.
  chat: (clientId: string, query: string, signal?: AbortSignal) =>
    j<import("./types").ChatResponse>(`/portfolio/${clientId}/chat`, {
      method: "POST",
      body: JSON.stringify({ query }),
      signal,
    }),
  voiceStatus: () => j<import("./types").VoiceStatus>("/voice/status"),
  voiceToken: (clientId: string) =>
    j<import("./types").VoiceToken>(`/voice/token/${clientId}`, { method: "POST" }),
};