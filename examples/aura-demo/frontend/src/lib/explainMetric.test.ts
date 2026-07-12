import { describe, it, expect } from "vitest";
import type { Holding, RulesResult } from "./types";
import {
  explainRule,
  explainMetric,
  explainHolding,
  metricForHolding,
  metricForAssetClass,
  formatPercent,
} from "./explainMetric";

const baseRulesResult: RulesResult = {
  status: "green",
  breaches: [],
  watches: [],
  per_rule: [
    {
      rule: "max_asset_class_weight:Equity",
      pass: true,
      current: 0.55,
      limit: 0.7,
      offending_holdings: [],
      severity: "green",
    },
    {
      rule: "max_asset_class_weight:Bonds",
      pass: true,
      current: 0.3,
      limit: 0.4,
      offending_holdings: [],
      severity: "green",
    },
    {
      rule: "min_cash",
      pass: true,
      current: 0.15,
      limit: 0.05,
      offending_holdings: [],
      severity: "green",
    },
  ],
};

const breachedRulesResult: RulesResult = {
  status: "red",
  breaches: [
    {
      rule: "max_single_holding",
      current: 0.3,
      limit: 0.2,
      offending_holdings: ["AAPL"],
      severity: "red",
      plain: "Single holding 30% > 20% cap",
    },
    {
      rule: "max_region_weight:US",
      current: 0.75,
      limit: 0.6,
      offending_holdings: ["AAPL", "VTI"],
      severity: "red",
      plain: "US 75% > 60% region cap",
    },
  ],
  watches: [],
  per_rule: [
    {
      rule: "max_single_holding",
      pass: false,
      current: 0.3,
      limit: 0.2,
      offending_holdings: ["AAPL"],
      severity: "red",
    },
    {
      rule: "max_region_weight:US",
      pass: false,
      current: 0.75,
      limit: 0.6,
      offending_holdings: ["AAPL", "VTI"],
      severity: "red",
    },
    {
      rule: "max_asset_class_weight:Equity",
      pass: true,
      current: 0.55,
      limit: 0.7,
      offending_holdings: [],
      severity: "green",
    },
  ],
};

const watchRulesResult: RulesResult = {
  status: "orange",
  breaches: [],
  watches: [
    {
      rule: "drift:Equity",
      current: 0.3,
      limit: 0.2,
      offending_holdings: ["AAPL", "VTI"],
      severity: "orange",
      plain: "Equity 30% exceeds 20% target by 10% (tol 5%)",
    },
  ],
  per_rule: [
    {
      rule: "drift:Equity",
      pass: false,
      current: 0.3,
      limit: 0.2,
      offending_holdings: ["AAPL", "VTI"],
      severity: "orange",
    },
  ],
};

describe("formatPercent", () => {
  it("formats decimals as percentages", () => {
    expect(formatPercent(0.1234)).toBe("12.3%");
    expect(formatPercent(0.0)).toBe("0.0%");
  });
});

describe("explainRule", () => {
  it("explains a passing asset-class weight", () => {
    const r = explainRule(baseRulesResult.per_rule[0]);
    expect(r).toContain("Equity allocation");
    expect(r).toContain("55.0%");
    expect(r).toContain("70.0%");
    expect(r).toContain("within");
  });

  it("explains a breached single-holding cap", () => {
    const r = explainRule(breachedRulesResult.per_rule[0]);
    expect(r).toContain("Single holding concentration breaches");
    expect(r).toContain("30.0%");
    expect(r).toContain("20.0%");
  });

  it("explains a breached region weight", () => {
    const r = explainRule(breachedRulesResult.per_rule[1]);
    expect(r).toContain("US allocation breaches");
    expect(r).toContain("75.0%");
    expect(r).toContain("60.0%");
  });

  it("explains a watch drift rule", () => {
    const r = explainRule(watchRulesResult.per_rule[0]);
    expect(r).toContain("Equity allocation");
    expect(r).toContain("30.0%");
    expect(r).toContain("20.0%");
    expect(r).toContain("drift watch");
  });

  it("explains approved-universe breach", () => {
    const rule = {
      rule: "approved_universe",
      pass: false,
      current: ["XYZ"],
      limit: ["AAPL", "VTI"],
      offending_holdings: ["XYZ"],
      severity: "red" as const,
    };
    expect(explainRule(rule)).toBe("XYZ is not in the approved universe.");
  });

  it("explains ESG exclusion breach", () => {
    const rule = {
      rule: "esg_exclusions",
      pass: false,
      current: ["WEAP", "COAL"],
      limit: ["WEAP", "COAL"],
      offending_holdings: ["WEAP", "COAL"],
      severity: "red" as const,
    };
    expect(explainRule(rule)).toBe("WEAP, COAL are on the ESG exclusion list.");
  });

  it("explains top-n concentration", () => {
    const rule = {
      rule: "max_top_n_concentration",
      pass: true,
      current: 0.5,
      limit: 0.6,
      offending_holdings: [],
      severity: "green" as const,
      n: 5,
    };
    expect(explainRule(rule as any)).toContain("Top-5 holdings concentration");
    expect(explainRule(rule as any)).toContain("50.0%");
    expect(explainRule(rule as any)).toContain("60.0%");
  });

  it("explains minimum liquidity", () => {
    const rule = {
      rule: "min_liquid_pct",
      pass: false,
      current: 0.2,
      limit: 0.3,
      offending_holdings: [],
      severity: "red" as const,
    };
    const r = explainRule(rule);
    expect(r).toContain("Liquid (tier-1)");
    expect(r).toContain("20.0%");
    expect(r).toContain("30.0%");
  });

  it("falls back gracefully for unknown rule shapes", () => {
    const rule = {
      rule: "custom:foo",
      pass: false,
      current: 0.42,
      limit: 0.1,
      offending_holdings: [],
      severity: "red" as const,
    };
    const r = explainRule(rule);
    expect(r).toContain("foo custom");
    expect(r).toContain("42.0%");
    expect(r).toContain("10.0%");
  });
});

describe("explainMetric", () => {
  it("returns a message when rulesResult is missing", () => {
    expect(explainMetric(undefined)).toBe("No mandate check data available.");
  });

  it("generates a compliant portfolio summary", () => {
    const r = explainMetric(baseRulesResult);
    expect(r).toContain("Portfolio status is compliant");
    expect(r).toContain("Key passing checks:");
    expect(r).toContain("Equity allocation is 55.0%, within the 70.0% mandate cap");
  });

  it("generates a breached portfolio summary", () => {
    const r = explainMetric(breachedRulesResult);
    expect(r).toContain("Portfolio status is breached");
    expect(r).toContain("Mandate breaches:");
    expect(r).toContain("Single holding 30% > 20% cap");
    expect(r).toContain("US 75% > 60% region cap");
  });

  it("generates a watch portfolio summary", () => {
    const r = explainMetric(watchRulesResult);
    expect(r).toContain("Portfolio status is on watch");
    expect(r).toContain("Drift watches:");
    expect(r).toContain("Equity 30% exceeds 20% target by 10% (tol 5%)");
  });

  it("explains a specific metric when provided", () => {
    const r = explainMetric(breachedRulesResult, "max_single_holding");
    expect(r).toContain("Single holding concentration breaches");
  });

  it("falls back to portfolio summary for unknown metric", () => {
    const r = explainMetric(baseRulesResult, "does_not_exist");
    expect(r).toContain("Portfolio status is compliant");
  });
});

describe("metricForHolding", () => {
  const h: Holding = {
    ticker: "AAPL",
    name: "Apple Inc",
    asset_class: "Equity",
    sector: "Technology",
    region: "US",
    units: 10,
    price: 150,
    market_value: 1500,
  };

  it("picks a failing rule mentioning the holding", () => {
    expect(metricForHolding(breachedRulesResult, h)).toBe("max_single_holding");
  });

  it("picks a passing rule by asset class when no failing match", () => {
    expect(metricForHolding(baseRulesResult, h)).toBe("max_asset_class_weight:Equity");
  });

  it("returns null when no rule matches", () => {
    const orphan: Holding = { ...h, asset_class: "Crypto", sector: "Unknown", region: "Mars" };
    expect(metricForHolding(baseRulesResult, orphan)).toBeNull();
  });
});

describe("metricForAssetClass", () => {
  it("selects the asset-class rule", () => {
    expect(metricForAssetClass(baseRulesResult, "Equity")).toBe("max_asset_class_weight:Equity");
    expect(metricForAssetClass(baseRulesResult, "Bonds")).toBe("max_asset_class_weight:Bonds");
  });

  it("prefers a failing match for the same asset class", () => {
    const result: RulesResult = {
      ...breachedRulesResult,
      per_rule: [
        {
          rule: "max_asset_class_weight:Equity",
          pass: false,
          current: 0.75,
          limit: 0.7,
          offending_holdings: ["AAPL"],
          severity: "red",
        },
        {
          rule: "max_asset_class_weight:Bonds",
          pass: true,
          current: 0.2,
          limit: 0.4,
          offending_holdings: [],
          severity: "green",
        },
      ],
    };
    expect(metricForAssetClass(result, "Equity")).toBe("max_asset_class_weight:Equity");
  });

  it("returns null for unmatched asset class", () => {
    expect(metricForAssetClass(baseRulesResult, "Crypto")).toBeNull();
  });
});

describe("explainHolding", () => {
  const h: Holding = {
    ticker: "AAPL",
    name: "Apple Inc",
    asset_class: "Equity",
    sector: "Technology",
    region: "US",
    units: 10,
    price: 150,
    market_value: 1500,
  };

  it("explains the matched rule for a holding", () => {
    const r = explainHolding(breachedRulesResult, h);
    expect(r).toContain("Single holding concentration breaches");
  });

  it("falls back to related breaches when no per_rule row matches", () => {
    const orphan: Holding = { ...h, ticker: "AAPL", asset_class: "Crypto", sector: "Unknown", region: "Mars" };
    const result: RulesResult = {
      ...breachedRulesResult,
      per_rule: [],
    };
    const r = explainHolding(result, orphan);
    expect(r).toContain("contributes to 2 mandate breaches");
    expect(r).toContain("Single holding 30% > 20% cap");
    expect(r).toContain("US 75% > 60% region cap");
  });

  it("reports compliant when no rule matches the holding", () => {
    const orphan: Holding = { ...h, ticker: "XRP", asset_class: "Crypto", sector: "Blockchain", region: "Global" };
    const r = explainHolding(baseRulesResult, orphan);
    expect(r).toContain("XRP is compliant");
  });
});
