import type { Holding, RuleResult, RulesResult } from "./types";

const PERCENT = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export function formatPercent(n: number): string {
  return PERCENT.format(n);
}

export function formatUsd(n: number): string {
  return USD.format(n);
}

function ruleName(rule: string): string {
  const [prefix, tail] = rule.split(":");
  if (!tail) return prefix.replace(/_/g, " ");
  if (prefix === "max_asset_class_weight") return `${tail} asset-class weight`;
  if (prefix === "max_sector_weight") return `${tail} sector weight`;
  if (prefix === "max_region_weight") return `${tail} region weight`;
  if (prefix === "drift") return `${tail} target allocation drift`;
  return `${tail} ${prefix.replace(/_/g, " ")}`;
}

function isArrayCurrent(current: number | string[]): current is string[] {
  return Array.isArray(current);
}

function isArrayLimit(limit: number | string[]): limit is string[] {
  return Array.isArray(limit);
}

/**
 * Build a deterministic, plain-English explanation for a single rule result row.
 */
export function explainRule(r: RuleResult): string {
  const name = ruleName(r.rule);
  const [prefix, tail] = r.rule.split(":");

  if (prefix === "approved_universe") {
    if (r.pass) return "All holdings are in the approved universe.";
    const offenders = isArrayCurrent(r.current) ? r.current : [];
    const list = offenders.join(", ");
    return offenders.length === 1
      ? `${list} is not in the approved universe.`
      : `${list} are not in the approved universe.`;
  }

  if (prefix === "esg_exclusions") {
    if (r.pass) return "No holdings violate the ESG exclusion list.";
    const offenders = isArrayCurrent(r.current) ? r.current : [];
    const list = offenders.join(", ");
    return offenders.length === 1
      ? `${list} is on the ESG exclusion list.`
      : `${list} are on the ESG exclusion list.`;
  }

  if (prefix === "max_top_n_concentration") {
    const current = typeof r.current === "number" ? r.current : 0;
    const limit = typeof r.limit === "number" ? r.limit : 1;
    const n = (r as any).n ?? 5;
    if (r.pass) return `Top-${n} holdings concentration is ${formatPercent(current)}, within the ${formatPercent(limit)} cap.`;
    return `Top-${n} holdings concentration breaches the mandate cap: ${formatPercent(current)} vs ${formatPercent(limit)}.`;
  }

  if (prefix === "min_liquid_pct") {
    const current = typeof r.current === "number" ? r.current : 0;
    const limit = typeof r.limit === "number" ? r.limit : 0;
    if (r.pass) return `Liquid (tier-1) allocation is ${formatPercent(current)}, meeting the ${formatPercent(limit)} minimum.`;
    return `Liquid (tier-1) allocation breaches the mandate minimum: ${formatPercent(current)} vs ${formatPercent(limit)}.`;
  }

  if (prefix === "min_cash") {
    const current = typeof r.current === "number" ? r.current : 0;
    const limit = typeof r.limit === "number" ? r.limit : 0;
    if (r.pass) return `Cash reserve is ${formatPercent(current)}, meeting the ${formatPercent(limit)} minimum.`;
    return `Cash reserve breaches the mandate minimum: ${formatPercent(current)} vs ${formatPercent(limit)}.`;
  }

  if (prefix === "max_single_holding") {
    const current = typeof r.current === "number" ? r.current : 0;
    const limit = typeof r.limit === "number" ? r.limit : 1;
    if (r.pass) return `Largest single holding is ${formatPercent(current)}, within the ${formatPercent(limit)} cap.`;
    return `Single holding concentration breaches the mandate cap: ${formatPercent(current)} vs ${formatPercent(limit)}.`;
  }

  if (prefix === "drift") {
    const current = typeof r.current === "number" ? r.current : 0;
    const limit = typeof r.limit === "number" ? r.limit : 0;
    const over = current - limit;
    return `${tail} allocation is ${formatPercent(current)}, exceeding the ${formatPercent(limit)} target by ${formatPercent(over)} (drift watch).`;
  }

  // max_asset_class_weight, max_sector_weight, max_region_weight, and any other max:* rule
  if (prefix.startsWith("max_") && tail) {
    const current = typeof r.current === "number" ? r.current : 0;
    const limit = typeof r.limit === "number" ? r.limit : 1;
    if (r.pass) return `${tail} allocation is ${formatPercent(current)}, within the ${formatPercent(limit)} mandate cap.`;
    return `${tail} allocation breaches the mandate cap: ${formatPercent(current)} vs ${formatPercent(limit)}.`;
  }

  // Generic fallback for unknown rule shapes.
  if (r.pass) return `${name} passes.`;
  const current = typeof r.current === "number" ? formatPercent(r.current) : isArrayCurrent(r.current) ? r.current.join(", ") : String(r.current);
  const limit = typeof r.limit === "number" ? formatPercent(r.limit) : isArrayLimit(r.limit) ? r.limit.join(", ") : String(r.limit);
  return `${name} breaches: ${current} vs limit ${limit}.`;
}

/**
 * Build a deterministic, sentence-style explanation for a specific metric,
 * or for the whole portfolio when no metric is supplied.
 */
export function explainMetric(
  rulesResult: RulesResult | undefined,
  metric?: string | null,
): string {
  if (!rulesResult) return "No mandate check data available.";

  if (metric) {
    const rule = rulesResult.per_rule.find((r) => r.rule === metric);
    if (rule) return explainRule(rule);
  }

  const statusText =
    rulesResult.status === "red"
      ? "breached"
      : rulesResult.status === "orange"
        ? "on watch"
        : "compliant";

  const parts: string[] = [];
  parts.push(`Portfolio status is ${statusText}.`);

  if (rulesResult.breaches.length > 0) {
    parts.push(
      `Mandate breaches: ${rulesResult.breaches
        .map((b) => b.plain)
        .join("; ")}.`
    );
  }

  if (rulesResult.watches.length > 0) {
    parts.push(
      `Drift watches: ${rulesResult.watches
        .map((w) => w.plain)
        .join("; ")}.`
    );
  }

  const passing = rulesResult.per_rule.filter((r) => r.pass).slice(0, 3);
  if (passing.length > 0 && rulesResult.status !== "red") {
    parts.push(
      `Key passing checks: ${passing
        .map((r) => explainRule(r).replace(/\.$/, ""))
        .join("; ")}.`
    );
  }

  if (parts.length === 1) {
    parts.push("All mandate checks pass.");
  }

  return parts.join(" ");
}

/**
 * Build a deterministic explanation for a single holding.
 */
export function explainHolding(
  rulesResult: RulesResult | undefined,
  h: Holding,
): string {
  if (!rulesResult) return "No mandate checks apply to this holding.";

  if (rulesResult.per_rule?.length > 0) {
    const metric = metricForHolding(rulesResult, h);
    if (metric) {
      const rule = rulesResult.per_rule.find((r) => r.rule === metric);
      if (rule) return explainRule(rule);
    }
  }

  // No specific rule mentions this holding; surface any breach or watch that includes it.
  const related = rulesResult.breaches.filter((b) =>
    b.offending_holdings.includes(h.ticker)
  );
  if (related.length > 0) {
    return `This holding contributes to ${related.length} mandate breach${related.length > 1 ? "es" : ""}: ${related
      .map((b) => b.plain)
      .join("; ")}.`;
  }

  const relatedWatches = rulesResult.watches.filter((w) =>
    w.offending_holdings.includes(h.ticker)
  );
  if (relatedWatches.length > 0) {
    return `This holding contributes to ${relatedWatches.length} drift watch${relatedWatches.length > 1 ? "es" : ""}: ${relatedWatches
      .map((w) => w.plain)
      .join("; ")}.`;
  }

  if (!rulesResult.per_rule?.length) {
    return "No mandate checks apply to this holding.";
  }

  return `${h.ticker} is compliant with all visible mandate checks.`;
}

/**
 * Pick the best per-rule metric to send to /explain for a single holding.
 *
 * Preference order:
 *   1. A failing rule that mentions this holding (by ticker, asset class, sector, or region).
 *   2. A passing rule that mentions this holding.
 *   3. null → ask for the whole-portfolio narrative instead of inventing a rule.
 *
 * This guarantees the /explain endpoint finds a matching `per_rule` row and
 * produces a grounded, holding-specific sentence instead of
 * "No mandate check named '...' applies".
 */
export function metricForHolding(
  rulesResult: RulesResult | undefined,
  h: Holding,
): string | null {
  if (!rulesResult?.per_rule?.length) return null;
  const matches = rulesResult.per_rule.filter((r) => ruleMentionsHolding(r, h));
  const failing = matches.find((r) => !r.pass);
  if (failing) return failing.rule;
  return matches[0]?.rule ?? null;
}

/**
 * Pick the best per-rule metric for an asset-class slice (AllocationDonut).
 */
export function metricForAssetClass(
  rulesResult: RulesResult | undefined,
  assetClass: string,
): string | null {
  if (!rulesResult?.per_rule?.length) return null;
  const matches = rulesResult.per_rule.filter((r) => {
    const [prefix, tail] = r.rule.split(":");
    if (tail && tail === assetClass) return true;
    return prefix === "max_asset_class_weight" && tail === assetClass;
  });
  const failing = matches.find((r) => !r.pass);
  if (failing) return failing.rule;
  return matches[0]?.rule ?? null;
}

function ruleMentionsHolding(row: { rule: string; offending_holdings?: string[] }, h: Holding): boolean {
  if (row.offending_holdings?.includes(h.ticker)) return true;
  const tail = row.rule.split(":")[1];
  if (!tail) return false;
  if (tail === h.asset_class || tail === h.sector || tail === h.region) return true;
  return false;
}
