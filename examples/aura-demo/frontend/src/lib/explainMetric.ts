import type { Holding, RulesResult } from "./types";

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
