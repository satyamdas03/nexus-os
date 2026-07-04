export type Status = "green" | "orange" | "red";

export interface Holding {
  ticker: string; name: string; asset_class: string; sector: string;
  region?: string; liquidity_tier?: number;
  units: number; price: number; market_value: number;
}

export interface Mandate {
  max_asset_class_weight: Record<string, number>;
  max_sector_weight: Record<string, number>;
  approved_universe: string[];
  max_single_holding: number;
  min_cash: number;
  target_allocation: Record<string, number>;
  drift_tolerance: number;
}

export interface Breach {
  rule: string;
  current: number | string[];
  limit: number | string[];
  offending_holdings: string[];
  severity: "red" | "orange";
  plain: string;
}

export interface RuleResult {
  rule: string;
  pass: boolean;
  current: number | string[];
  limit: number | string[];
  offending_holdings: string[];
  severity: "red" | "orange" | "green";
}

export interface RulesResult {
  status: Status;
  breaches: Breach[];
  watches: Breach[];
  per_rule: RuleResult[];
}

export interface RuleDoc {
  type: string;
  title: string;
  summary: string;
  description: string;
  parameters: Record<string, any>;
  enabled: boolean;
  severity?: "hard breach" | "soft breach" | "watch" | null;
  message?: string | null;
}

export interface MandateDetail {
  client_id: string;
  mandate_id: string;
  version: string;
  source_path: string;
  created_ts: string;
  spec_hash: string;
  dsl: string;
  docs: {
    id?: string;
    name?: string;
    version: string;
    rule_count: number;
    enabled_rule_count: number;
    rules: RuleDoc[];
  };
}

export interface Portfolio {
  client_id: string; client_name: string; adviser: string; fum: number;
  mandate_id?: number;
  holdings: Holding[]; cash: number; mandate: Mandate;
  rules_result?: RulesResult;
}

export interface PortfolioSummary {
  client_id: string; client_name: string; adviser: string; fum: number;
  status: Status; top_reason: string | null; top_asset_class?: string;
}

export interface Trade {
  ticker: string; action: "buy" | "sell"; units: number; value: number; rationale: string;
}

export interface RemediationResult {
  trades: Trade[];
  verification: RulesResult;
  resulting_portfolio: Portfolio;
  retried: boolean;
  resolved: boolean;
}

export interface AuditEntry {
  timestamp: string; client_id: string; action_type: string; actor: string;
  tier: string; payload: any; rationale: string; rules_check_result: any; version: string;
}

export interface ApproveResult {
  ok: boolean; client_id: string;
  prior_status: Status; new_status: Status; rules_result: RulesResult;
}

export interface ExplainResult {
  narrative: string;
  breach_summaries?: string[];
  watch_summaries?: string[];
  metric?: string;
}

export interface SummaryAiResult {
  narrative: string;
  aggregate: {
    total_portfolios: number; green: number; orange: number; red: number;
    total_breaches: number;
    top_systemic_patterns: { rule: string; count: number }[];
  };
}

// ---- Hermes: self-improving remediation engine ----

export interface HermesScore {
  alignment_rate: number;
  avg_trades_per_fix: number;
  acceptance_rate: number;
  breaches_remaining: number;
  composite: number;
}

export interface HermesHeartbeat {
  counts: {
    scanned: number; green: number; remediated: number; missed: number; skipped: number;
  };
  queue_size: number;
  miss_count: number;
  score: HermesScore;
  top_misses: {
    client_id: string; client_name: string; prior_status: Status;
    remaining_breaches: number; rationale: string;
  }[];
  stale?: boolean;
  message?: string;
}

export interface HermesQueueItem {
  client_id: string; client_name?: string; fum: number;
  prior_status: Status; post_status: Status;
  severity_weight?: number; confidence?: number;
  trades: Trade[]; rationale: string;
  rank_score: number;
  day?: number; created_ts?: string;
}

// retained for reference (scan now returns {job_id})
export interface HermesScanResult {
  heartbeat: HermesHeartbeat;
  queue: HermesQueueItem[];
  score: HermesScore;
}

export interface HermesStrategyVariable {
  value: any;
  rationale: string;
}

export interface HermesStrategy {
  version: number;
  variables: Record<string, HermesStrategyVariable>;
}

export interface HermesProposal {
  variable: string;
  current: any;
  to: any;
  rationale: string;
  mode: "fallback" | "hermes" | "fallback-fell-through";
}

export interface HermesAdoptResult {
  version: number;
  variable: string;
  from: any;
  to: any;
  rationale: string;
}

export interface HermesHistoryEntry {
  file: string;
  snapshot: HermesStrategy;
  timestamp?: string;
  actor?: string;
  variable?: string;
  from?: any;
  to?: any;
  rationale?: string;
}

export interface HermesApproveBatchItem {
  client_id: string;
  trades: Trade[];
  rationale: string;
}

export interface HermesApproveBatchResult {
  results: {
    client_id: string;
    prior_status?: Status;
    new_status?: Status;
    rules_result?: RulesResult;
    error?: string;
  }[];
  applied: number;
  failed: number;
}

// ---- Evidence Pack: read-only compliance proof artifact ----

export interface EvidencePackRuleRow {
  rule: string;
  current: number | string | string[];
  limit: number | string | string[];
  pass: boolean;
  severity: "green" | "orange" | "red";
}

export interface EvidencePackHeader {
  client_name: string;
  client_id: string;
  adviser: string;
  fum: number;
  day: number;
  generated_at: string;
  reference_id: string;
  synthetic_data: boolean;
  synthetic_disclaimer: string;
}

export interface EvidencePackHistoryRow {
  day: number;
  status: Status;
  breach_count: number;
  watch_count: number;
}

export interface EvidencePackRemediationRow {
  timestamp: string;
  action_type: string;
  actor: string;
  tier: string;
  rationale: string;
  payload_summary: string;
  rules_status?: string;
}

export interface EvidencePack {
  version: string;
  header: EvidencePackHeader;
  current_attestation: {
    status: Status;
    per_rule: EvidencePackRuleRow[];
  };
  deterministic_summary: string;
  alignment_history: EvidencePackHistoryRow[];
  remediation_evidence: EvidencePackRemediationRow[];
  control_statement: string;
  footer: {
    generated_at: string;
    reference_id: string;
    synthetic_disclaimer: string;
  };
}

export interface HermesRollbackResult {
  ok: boolean;
  version: number;
  strategy: HermesStrategy;
  history?: HermesHistoryEntry[];
}

// ---- Market simulation (virtual clock + seeded GBM) ----

export interface MarketClock {
  day: number;
  running: boolean;
  auto_interval_sec: number;
  auto_fix: boolean;
  seed: number;
}

export interface MarketHistoryPoint {
  day: number;
  green: number;
  orange: number;
  red: number;
}

// Backend `/market/prices` returns a flat `{ticker: price}` map (no wrapper).
export type MarketPrices = Record<string, number>;

// Backend `core/market.py` `status()` returns `{clock, summary}` (nested).
export interface MarketStatus {
  clock: MarketClock;
  summary: {
    total: number; green: number; orange: number; red: number; breach_count: number;
  };
}

export interface TopSafeguardRow extends PortfolioSummary {}

export interface TopSafeguard {
  top: TopSafeguardRow[];
  rest: { count: number; fum: number; dominant_status: Status };
}

export interface HermesQueuePage {
  day: number;
  rows: HermesQueueItem[];
  next_cursor: number;
}

export interface HermesScanJob {
  job_id: string;
  kind: string;
  status: string;
  started_ts: string | null;
  done_ts: string | null;
  scanned: number;
  remediated: number;
  missed: number;
  error: string | null;
}
