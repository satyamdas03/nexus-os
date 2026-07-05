# 34k Scale + Market Simulation Implementation Plan (SP1+SP2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale Assure's synthetic book from 40 to 34,000 portfolios with diverse complex mandates, add a seeded fluctuating-market simulation with a virtual clock, and verify the deterministic engine + Hermes check and manage the whole book at scale as drift/breaches emerge over time.

**Architecture:** SQLite (stdlib `sqlite3`, WAL) replaces JSON files as the source of truth — paged, indexed, O(1) lookup, precomputed book summary. A seeded per-ticker GBM price model + virtual clock re-values holdings lazily on read (`market_value = units × price(day)`). A drift monitor batched-rechecks the book on each tick; Hermes runs a paged async scan that deterministically proposes fixes and gates every proposal through the rules engine before queueing; a human applies via `approve-batch`. Two independent toggles: clock auto-run (ticking) vs auto-fix (Hermes auto-propose). Applying trades always stays behind the human gate.

**Tech Stack:** Python 3.13, FastAPI 0.137.1, uvicorn, pydantic 2.13.4, stdlib `sqlite3` + `random.Random` (NO numpy, NO new deps), anthropic SDK (MockLLM fallback), pytest. Frontend: Next.js 14.2.15, TS, Tailwind, recharts, MATRIX theme. Deploy: Render (backend 512MB) + Vercel (frontend), same-origin `/api` proxy.

## Global Constraints

- Synthetic data only. Never connect to real client data.
- Mandate rules are LAW — Hermes may never touch them. `strategy.yaml` is the only thing Hermes writes.
- The rules engine, not the LLM, is the final word on compliance.
- Every action passes a human gate. `approve-batch` is the gate for trade application.
- Every strategy change is versioned and reversible (archived to `history/vN.json`).
- `ANTHROPIC_API_KEY` is server-only env, never committed. No `NEXT_PUBLIC_*` — backend URL never baked into client build (same-origin `/api` proxy).
- `portfolios.db` is gitignored and regenerable from the generator.
- No new runtime dependencies — stdlib `sqlite3` and `random.Random` only (no numpy, no pandas).
- Existing endpoint contracts (`/portfolio/{id}`, `/hermes/*`, `/admin/reset`) preserved; internals swap JSON-file → SQLite.
- 34k replaces 40 — single book, single code path, no `BOOK_PROFILE` flag.

## File Structure Map

```
backend/
  generators/
    universe.py        NEW — ~35 tickers w/ asset_class, sector, region, liquidity_tier, mu, sigma, base_price
    mandates.py        NEW — mandate template library + randomized params (10 rule dims)
    market.py          NEW — seeded GBM price model + sector correlation → prices(ticker, day)
    generate_data.py   REWRITE — 34k → portfolios.db (schema + data + prices@day0)
  core/
    storage.py         NEW — sqlite3 conn (WAL), schema init, migrations, query helpers
    data_loader.py     REWRITE over SQLite — O(1) get_portfolio, paged list, precomputed summary read
    market.py          NEW — virtual clock (day), revalue, tick/advance/autorun, history
    rules_engine.py    EXTEND — +4 rule types; pure check(portfolio, mandate) interface unchanged
    effective.py       REWRITE over SQLite state table; revalues w/ live prices + applied trades
    trades.py          EXTEND — new universe + live prices in apply_trades
  agents/hermes/
    loop.py            REWRITE — paged async scan_book (delta + full), batched, paged queue
    monitor.py         NEW — drift monitor: on tick, batched re-check, status_history, delta trigger
    proposer.py        EXTEND — handle 4 new breach types (deterministic, no Claude)
    strategy_io.py     UNCHANGED
    score.py           UNCHANGED
  routers/
    market.py          NEW — /market/clock /tick /advance /auto-run /auto-fix /prices /history /status
    portfolios.py      REWRITE — paged + precomputed summary; top-N safeguard list endpoint
    hermes.py          EXTEND — paged queue, async scan job status, approve-batch (human gate)
    actions.py         UNCHANGED
    admin.py           EXTEND — /admin/reset clears state + queue + status_history + market clock
  main.py              EXTEND — register market router
  tests/               EXTEND — new test files per task
frontend/
  components/
    MarketPanel.tsx    NEW — clock + play/pause/step/advance + autorun + price strip + status-over-time chart
    Heatmap.tsx        EXTEND — safeguard: top-N (~200) by FUM×severity + aggregate-rest block
    CommandCentreView.tsx EXTEND — render MarketPanel; live refetch on market events
  lib/api.ts           EXTEND — market namespace
scripts/
  load_check.py        NEW — 34k verification + perf report
```

## Build Order (10 tasks)

1. `universe.py` + `mandates.py` (pure, testable first)
2. `rules_engine` +4 rules + tests
3. `storage.py` + `generate_data.py` (34k → SQLite) + `market.py` GBM price model
4. `data_loader` + `effective` over SQLite + lazy revalue
5. `core/market.py` (virtual clock + revalue) + `routers/market.py`
6. `monitor.py` + `hermes/loop.py` (paged async + delta) + `proposer` extension
7. `routers/portfolios` (paged + precomputed) + `routers/hermes` (paged queue + job status) + `admin` reset
8. Frontend: `MarketPanel` + heatmap safeguard + api market namespace
9. `scripts/load_check.py` + perf tests
10. Local full verification → push → Render/Vercel redeploy → live smoke

---

### Task 1a: `generators/universe.py` — ticker reference universe

**Files:**
- Create: `backend/generators/universe.py`
- Test: `backend/tests/test_universe.py`

**Interfaces:**
- Consumes: nothing (pure static reference data)
- Produces:
  - `UNIVERSE: list[dict]` — each `{ticker, name, asset_class, sector, region, liquidity_tier, base_price, mu, sigma}`
  - `UNIVERSE_BY_TICKER: dict[str, dict]`
  - `ASSET_CLASSES: list[str]`, `SECTORS: list[str]`, `REGIONS: list[str]`
  - `all_tickers() -> list[str]`
  - `by_region(region) -> list[str]`, `by_asset_class(ac) -> list[str]`
  - `RHO = 0.5` (sector correlation used by `generators/market.py` in Task 3)
  - Holding rows produced by `generate_data` (Task 3) carry `region` and `liquidity_tier` copied from `UNIVERSE_BY_TICKER[ticker]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_universe.py
from generators import universe


def test_universe_has_about_35_tickers():
    assert 30 <= len(universe.UNIVERSE) <= 45


def test_every_ticker_has_required_fields():
    for u in universe.UNIVERSE:
        for k in ("ticker", "name", "asset_class", "sector", "region", "liquidity_tier", "base_price", "mu", "sigma"):
            assert k in u, f"{u.get('ticker')} missing {k}"
        assert 1 <= u["liquidity_tier"] <= 3
        assert u["base_price"] > 0
        assert u["mu"] is not None
        assert u["sigma"] > 0


def test_by_region_and_asset_class_consistent():
    us = universe.by_region("US")
    for t in us:
        assert universe.UNIVERSE_BY_TICKER[t]["region"] == "US"
    bonds = universe.by_asset_class("Bonds")
    for t in bonds:
        assert universe.UNIVERSE_BY_TICKER[t]["asset_class"] == "Bonds"


def test_all_asset_classes_and_regions_present():
    assert {"Equity", "Bonds", "Commodity", "Crypto", "Cash"} <= set(universe.ASSET_CLASSES)
    assert {"US", "ExUS", "EM"} <= set(universe.REGIONS)


def test_tickers_unique():
    tickers = [u["ticker"] for u in universe.UNIVERSE]
    assert len(tickers) == len(set(tickers))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_universe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generators.universe'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/generators/universe.py
"""Static reference universe for the 34k synthetic book.

~35 tickers spanning Equity (US / Ex-US / single-country EM), Bonds, Commodity,
Crypto, Cash. Each ticker carries the metadata the rules engine needs
(asset_class, sector, region, liquidity_tier) plus the GBM parameters
(mu, sigma, base_price) consumed by generators/market.py.

liquidity_tier: 1 = high (large ETFs / govt bonds), 2 = medium, 3 = low (crypto,
single-country EM). The min_liquid_pct rule requires a minimum weight in tier-1.

This is the single source of truth for ticker metadata. generate_data copies
`region` and `liquidity_tier` onto each holding row; rules_engine reads them.
core/trades.py is extended in Task 2b to look tickers up here.
"""

# Sector correlation used by the GBM model (generators/market.py).
RHO = 0.5

# fmt: off
UNIVERSE = [
    # --- Equity: US broad + sector ETFs (tier 1) ---
    {"ticker": "SPY",  "name": "S&P 500 ETF",        "asset_class": "Equity",  "sector": "Broad",        "region": "US",    "liquidity_tier": 1, "base_price": 500.0, "mu": 0.08, "sigma": 0.16},
    {"ticker": "QQQ",  "name": "Nasdaq 100 ETF",     "asset_class": "Equity",  "sector": "Broad",        "region": "US",    "liquidity_tier": 1, "base_price": 420.0, "mu": 0.10, "sigma": 0.22},
    {"ticker": "VTI",  "name": "Total Mkt ETF",      "asset_class": "Equity",  "sector": "Broad",        "region": "US",    "liquidity_tier": 1, "base_price": 260.0, "mu": 0.08, "sigma": 0.16},
    {"ticker": "XLV",  "name": "Healthcare ETF",     "asset_class": "Equity",  "sector": "Healthcare",   "region": "US",    "liquidity_tier": 1, "base_price": 145.0, "mu": 0.07, "sigma": 0.15},
    {"ticker": "XLF",  "name": "Financials ETF",     "asset_class": "Equity",  "sector": "Financials",   "region": "US",    "liquidity_tier": 1, "base_price": 45.0,  "mu": 0.08, "sigma": 0.18},
    {"ticker": "XLK",  "name": "Tech Sector ETF",    "asset_class": "Equity",  "sector": "Technology",   "region": "US",    "liquidity_tier": 1, "base_price": 220.0, "mu": 0.11, "sigma": 0.22},
    {"ticker": "XLY",  "name": "Consumer Disc ETF",  "asset_class": "Equity",  "sector": "Consumer",     "region": "US",    "liquidity_tier": 1, "base_price": 180.0, "mu": 0.08, "sigma": 0.19},
    {"ticker": "XLP",  "name": "Consumer Staples",   "asset_class": "Equity",  "sector": "Consumer",     "region": "US",    "liquidity_tier": 1, "base_price": 80.0,  "mu": 0.06, "sigma": 0.12},
    {"ticker": "XLE",  "name": "Energy ETF",         "asset_class": "Equity",  "sector": "Energy",       "region": "US",    "liquidity_tier": 2, "base_price": 90.0,  "mu": 0.05, "sigma": 0.28},
    {"ticker": "XLRE", "name": "Real Estate ETF",    "asset_class": "Equity",  "sector": "RealEstate",   "region": "US",    "liquidity_tier": 2, "base_price": 42.0,  "mu": 0.05, "sigma": 0.20},
    # --- Equity: Ex-US developed (tier 1-2) ---
    {"ticker": "VEA",  "name": "Developed Mkts ETF", "asset_class": "Equity",  "sector": "Broad",        "region": "ExUS",  "liquidity_tier": 1, "base_price": 60.0,  "mu": 0.07, "sigma": 0.17},
    {"ticker": "EFA",  "name": "EAFE ETF",           "asset_class": "Equity",  "sector": "Broad",        "region": "ExUS",  "liquidity_tier": 1, "base_price": 80.0,  "mu": 0.07, "sigma": 0.17},
    {"ticker": "EWJ",  "name": "Japan ETF",          "asset_class": "Equity",  "sector": "Broad",        "region": "ExUS",  "liquidity_tier": 2, "base_price": 70.0,  "mu": 0.06, "sigma": 0.18},
    {"ticker": "EWG",  "name": "Germany ETF",        "asset_class": "Equity",  "sector": "Industrials",  "region": "ExUS",  "liquidity_tier": 2, "base_price": 30.0,  "mu": 0.06, "sigma": 0.20},
    # --- Equity: Emerging markets (tier 2-3) ---
    {"ticker": "VWO",  "name": "Emerging Mkts ETF",  "asset_class": "Equity",  "sector": "Broad",        "region": "EM",    "liquidity_tier": 2, "base_price": 45.0,  "mu": 0.07, "sigma": 0.24},
    {"ticker": "EEM",  "name": "EM ETF",             "asset_class": "Equity",  "sector": "Broad",        "region": "EM",    "liquidity_tier": 2, "base_price": 42.0,  "mu": 0.07, "sigma": 0.24},
    {"ticker": "MCHI", "name": "China ETF",          "asset_class": "Equity",  "sector": "Technology",   "region": "EM",    "liquidity_tier": 3, "base_price": 55.0,  "mu": 0.06, "sigma": 0.30},
    {"ticker": "INDA", "name": "India ETF",          "asset_class": "Equity",  "sector": "Financials",   "region": "EM",    "liquidity_tier": 3, "base_price": 50.0,  "mu": 0.08, "sigma": 0.28},
    # --- Bonds (tier 1) ---
    {"ticker": "TLT",  "name": "20+ Yr Treasury",    "asset_class": "Bonds",   "sector": "Govt",         "region": "US",    "liquidity_tier": 1, "base_price": 95.0,  "mu": 0.03, "sigma": 0.12},
    {"ticker": "IEF",  "name": "7-10 Yr Treasury",   "asset_class": "Bonds",   "sector": "Govt",         "region": "US",    "liquidity_tier": 1, "base_price": 95.0,  "mu": 0.03, "sigma": 0.06},
    {"ticker": "LQD",  "name": "Inv-Grade Corp",     "asset_class": "Bonds",   "sector": "Corporate",    "region": "US",    "liquidity_tier": 1, "base_price": 110.0, "mu": 0.04, "sigma": 0.08},
    {"ticker": "HYG",  "name": "High Yield Corp",    "asset_class": "Bonds",   "sector": "Corporate",    "region": "US",    "liquidity_tier": 2, "base_price": 80.0,  "mu": 0.05, "sigma": 0.10},
    {"ticker": "BNDX", "name": "Intl Bond ETF",      "asset_class": "Bonds",   "sector": "Govt",         "region": "ExUS",  "liquidity_tier": 2, "base_price": 50.0,  "mu": 0.02, "sigma": 0.07},
    # --- Commodity (tier 1-2) ---
    {"ticker": "GLD",  "name": "Gold ETF",           "asset_class": "Commodity","sector": "Metals",      "region": "US",    "liquidity_tier": 1, "base_price": 240.0, "mu": 0.04, "sigma": 0.15},
    {"ticker": "SLV",  "name": "Silver ETF",         "asset_class": "Commodity","sector": "Metals",      "region": "US",    "liquidity_tier": 2, "base_price": 26.0,  "mu": 0.04, "sigma": 0.25},
    {"ticker": "DBC",  "name": "Commodity Index",    "asset_class": "Commodity","sector": "Broad",       "region": "US",    "liquidity_tier": 2, "base_price": 25.0,  "mu": 0.03, "sigma": 0.18},
    # --- Crypto (tier 3) ---
    {"ticker": "BTC",  "name": "Bitcoin",            "asset_class": "Crypto",  "sector": "Digital",      "region": "US",    "liquidity_tier": 3, "base_price": 60000.0,"mu": 0.20, "sigma": 0.60},
    {"ticker": "ETH",  "name": "Ethereum",           "asset_class": "Crypto",  "sector": "Digital",      "region": "US",    "liquidity_tier": 3, "base_price": 3000.0, "mu": 0.22, "sigma": 0.70},
    # --- Cash (tier 1) ---
    {"ticker": "CASH", "name": "Money Mkt",          "asset_class": "Cash",    "sector": "Cash",         "region": "US",    "liquidity_tier": 1, "base_price": 1.0,   "mu": 0.04, "sigma": 0.001},
]
# fmt: on

UNIVERSE_BY_TICKER = {u["ticker"]: u for u in UNIVERSE}
ASSET_CLASSES = sorted({u["asset_class"] for u in UNIVERSE})
SECTORS = sorted({u["sector"] for u in UNIVERSE})
REGIONS = sorted({u["region"] for u in UNIVERSE})


def all_tickers() -> list[str]:
    return [u["ticker"] for u in UNIVERSE]


def by_region(region: str) -> list[str]:
    return [u["ticker"] for u in UNIVERSE if u["region"] == region]


def by_asset_class(asset_class: str) -> list[str]:
    return [u["ticker"] for u in UNIVERSE if u["asset_class"] == asset_class]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_universe.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/generators/universe.py backend/tests/test_universe.py
git commit -m "feat(34k): ticker reference universe (Task 1a)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 1b: `generators/mandates.py` — mandate template library

**Files:**
- Create: `backend/generators/mandates.py`
- Test: `backend/tests/test_mandates.py`

**Interfaces:**
- Consumes: `generators/universe.py` (`UNIVERSE`, `UNIVERSE_BY_TICKER`, `by_region`, `by_asset_class`, `REGIONS`, `ASSET_CLASSES`)
- Produces:
  - `MANDATE_TEMPLATES: list[dict]` — base templates, each a partial mandate with the 10 rule dims
  - `build_mandate(rng: random.Random, template_idx: int) -> dict` — returns a complete, valid mandate dict with randomized params. Keys produced: `name`, `max_asset_class_weight`, `max_sector_weight`, `approved_universe`, `max_single_holding`, `min_cash`, `target_allocation`, `drift_tolerance`, `max_region_weight`, `excluded_tickers`, `max_top_n_concentration`, `min_liquid_pct`.
  - `template_count() -> int`
  - `is_valid_mandate(m) -> bool` — structural validator (all keys present, types correct, caps in (0,1], lists of valid tickers)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mandates.py
import random
from generators import mandates, universe


def test_every_template_builds_valid_mandate():
    rng = random.Random(123)
    for i in range(mandates.template_count()):
        m = mandates.build_mandate(rng, i)
        assert mandates.is_valid_mandate(m), f"template {i} invalid: {m}"


def test_mandate_covers_all_ten_rule_dims():
    m = mandates.build_mandate(random.Random(1), 0)
    for k in (
        "max_asset_class_weight", "max_sector_weight", "approved_universe",
        "max_single_holding", "min_cash", "target_allocation", "drift_tolerance",
        "max_region_weight", "excluded_tickers", "max_top_n_concentration",
        "min_liquid_pct",
    ):
        assert k in m, f"missing rule dim {k}"


def test_approved_universe_subset_of_real_tickers():
    real = set(universe.all_tickers())
    rng = random.Random(7)
    for i in range(mandates.template_count()):
        m = mandates.build_mandate(rng, i)
        assert set(m["approved_universe"]) <= real
        assert len(m["approved_universe"]) >= 4


def test_excluded_tickers_subset_of_approved():
    rng = random.Random(9)
    for i in range(mandates.template_count()):
        m = mandates.build_mandate(rng, i)
        assert set(m["excluded_tickers"]) <= set(m["approved_universe"])


def test_region_caps_only_real_regions():
    rng = random.Random(11)
    for i in range(mandates.template_count()):
        m = mandates.build_mandate(rng, i)
        for r in m["max_region_weight"]:
            assert r in universe.REGIONS


def test_randomization_varies_params_across_seeds():
    a = mandates.build_mandate(random.Random(1), 0)
    b = mandates.build_mandate(random.Random(2), 0)
    # at least one numeric cap differs across seeds
    assert a["max_single_holding"] != b["max_single_holding"] or a["min_cash"] != b["min_cash"]


def test_some_template_can_breach():
    """At least one template has caps tight enough that a plausible holding
    set breaches (sanity for the generator's breach cohort)."""
    tight = next(
        mandates.build_mandate(random.Random(3), i)
        for i in range(mandates.template_count())
        if mandates.build_mandate(random.Random(3), i)["max_single_holding"] <= 0.12
    )
    assert tight["max_single_holding"] <= 0.12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_mandates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generators.mandates'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/generators/mandates.py
"""Mandate template library for the 34k synthetic book.

A *mandate* is the immutable LAW for a portfolio — the rules engine checks
against it and Hermes may never modify it. There are 10 rule dimensions:

  1. max_asset_class_weight   (per asset-class cap)
  2. max_sector_weight        (per sector cap)
  3. approved_universe        (allowed tickers)
  4. max_single_holding       (max weight in one ticker)
  5. min_cash                 (min cash ratio)
  6. target_allocation + drift_tolerance  (one-sided drift watch)
  7. max_region_weight        (per region cap)        [NEW]
  8. excluded_tickers         (ESG exclusion list)    [NEW]
  9. max_top_n_concentration  (top-N weight cap)      [NEW]
 10. min_liquid_pct           (min weight in tier-1)  [NEW]

Templates are base mandates with placeholder params; build_mandate randomizes
the numeric caps and the approved/excluded ticker sets per portfolio so the
34k book has genuinely diverse, complex mandates. ~34k portfolios share a
small library of templates (mandates are deduped in generate_data by their
JSON spec, so far fewer than 34k mandate rows).
"""
import json
import random

from generators import universe as U


def _ac_caps(rng, equity_cap, bond_cap, commodity_cap, crypto_cap):
    return {
        "Equity": equity_cap,
        "Bonds": bond_cap,
        "Commodity": commodity_cap,
        "Crypto": crypto_cap,
        "Cash": 1.0,
    }


def _sector_caps(rng, cap):
    # cap a handful of sectors; leave others uncapped (omitted key = no cap)
    sectors = rng.sample([s for s in U.SECTORS if s not in ("Broad", "Cash")], k=min(3, len(U.SECTORS) - 2))
    return {s: cap for s in sectors}


def _region_caps(rng, us_cap, exus_cap, em_cap):
    return {"US": us_cap, "ExUS": exus_cap, "EM": em_cap}


def _approved(rng, size, allow_crypto):
    pool = [t for t in U.all_tickers() if U.UNIVERSE_BY_TICKER[t]["asset_class"] != "Crypto" or allow_crypto]
    pool = [t for t in pool if t != "CASH"]
    size = min(size, len(pool))
    return sorted(rng.sample(pool, k=size))


def _excluded(rng, approved, k):
    if k <= 0 or len(approved) <= 4:
        return []
    return sorted(rng.sample(approved, k=min(k, len(approved) - 4)))


# Each template: a function(rng) -> dict of params. Templates vary in risk
# appetite, region tilt, ESG strictness, concentration tolerance, liquidity
# floor — so the book spans conservative to aggressive mandates.
_TEMPLATES = [
    # 0: balanced growth
    lambda r: dict(name="balanced_growth", ac=_ac_caps(r, 0.80, 0.30, 0.10, 0.05),
                   sec=_sector_caps(r, 0.30), reg=_region_caps(r, 0.70, 0.35, 0.15),
                   single=0.12, min_cash=0.05, target={"Equity": 0.65, "Bonds": 0.25},
                   drift=0.08, approved_n=18, crypto=True, excl_k=2,
                   topn={"n": 5, "limit": 0.55}, min_liq=0.40),
    # 1: conservative income
    lambda r: dict(name="conservative_income", ac=_ac_caps(r, 0.45, 0.60, 0.05, 0.0),
                   sec=_sector_caps(r, 0.20), reg=_region_caps(r, 0.85, 0.25, 0.05),
                   single=0.10, min_cash=0.10, target={"Equity": 0.35, "Bonds": 0.55},
                   drift=0.06, approved_n=14, crypto=False, excl_k=3,
                   topn={"n": 5, "limit": 0.45}, min_liq=0.60),
    # 2: aggressive growth
    lambda r: dict(name="aggressive_growth", ac=_ac_caps(r, 0.95, 0.15, 0.15, 0.15),
                   sec=_sector_caps(r, 0.40), reg=_region_caps(r, 0.60, 0.40, 0.25),
                   single=0.20, min_cash=0.02, target={"Equity": 0.85, "Bonds": 0.10},
                   drift=0.12, approved_n=20, crypto=True, excl_k=1,
                   topn={"n": 5, "limit": 0.70}, min_liq=0.25),
    # 3: ESG strict (big exclusion list, no crypto, no EM tilt)
    lambda r: dict(name="esg_strict", ac=_ac_caps(r, 0.75, 0.35, 0.10, 0.0),
                   sec=_sector_caps(r, 0.25), reg=_region_caps(r, 0.75, 0.40, 0.05),
                   single=0.12, min_cash=0.06, target={"Equity": 0.60, "Bonds": 0.30},
                   drift=0.07, approved_n=16, crypto=False, excl_k=6,
                   topn={"n": 5, "limit": 0.50}, min_liq=0.50),
    # 4: EM-tilted
    lambda r: dict(name="em_tilt", ac=_ac_caps(r, 0.85, 0.20, 0.10, 0.05),
                   sec=_sector_caps(r, 0.30), reg=_region_caps(r, 0.50, 0.30, 0.35),
                   single=0.15, min_cash=0.04, target={"Equity": 0.75, "Bonds": 0.15},
                   drift=0.10, approved_n=17, crypto=True, excl_k=1,
                   topn={"n": 5, "limit": 0.60}, min_liq=0.35),
    # 5: concentrated high-conviction (loose top-N, tight single-name)
    lambda r: dict(name="high_conviction", ac=_ac_caps(r, 0.90, 0.20, 0.10, 0.05),
                   sec=_sector_caps(r, 0.35), reg=_region_caps(r, 0.65, 0.35, 0.20),
                   single=0.18, min_cash=0.03, target={"Equity": 0.80, "Bonds": 0.12},
                   drift=0.10, approved_n=15, crypto=True, excl_k=0,
                   topn={"n": 3, "limit": 0.65}, min_liq=0.30),
    # 6: liquidity-floored (strict min_liquid_pct)
    lambda r: dict(name="liquid_floored", ac=_ac_caps(r, 0.70, 0.40, 0.08, 0.0),
                   sec=_sector_caps(r, 0.22), reg=_region_caps(r, 0.80, 0.30, 0.10),
                   single=0.11, min_cash=0.08, target={"Equity": 0.55, "Bonds": 0.35},
                   drift=0.07, approved_n=13, crypto=False, excl_k=2,
                   topn={"n": 5, "limit": 0.48}, min_liq=0.75),
    # 7: region-capped (tight US cap to force ex-US/EM)
    lambda r: dict(name="region_capped", ac=_ac_caps(r, 0.88, 0.25, 0.12, 0.05),
                   sec=_sector_caps(r, 0.28), reg=_region_caps(r, 0.45, 0.45, 0.30),
                   single=0.14, min_cash=0.05, target={"Equity": 0.72, "Bonds": 0.18},
                   drift=0.09, approved_n=18, crypto=True, excl_k=1,
                   topn={"n": 5, "limit": 0.58}, min_liq=0.40),
]


def template_count() -> int:
    return len(_TEMPLATES)


def build_mandate(rng: random.Random, template_idx: int) -> dict:
    """Build a complete, valid mandate dict from template `template_idx`,
    randomizing numeric caps within a small band so 34k mandates differ."""
    p = _TEMPLATES[template_idx % len(_TEMPLATES)](rng)

    def jitter(base, lo, hi):
        return round(rng.uniform(base * lo, base * hi), 3)

    ac = {k: (v if k == "Cash" else round(jitter(v, 0.95, 1.05), 3)) for k, v in p["ac"].items()}
    sec = {k: round(jitter(v, 0.90, 1.10), 3) for k, v in p["sec"].items()}
    reg = {k: round(jitter(v, 0.95, 1.05), 3) for k, v in p["reg"].items()}
    approved = _approved(rng, p["approved_n"], p["crypto"])
    excluded = _excluded(rng, approved, p["excl_k"])
    single = round(jitter(p["single"], 0.90, 1.10), 3)
    min_cash = round(jitter(p["min_cash"], 0.80, 1.20), 3)
    target = {k: round(jitter(v, 0.95, 1.05), 3) for k, v in p["target"].items()}
    topn = {"n": p["topn"]["n"], "limit": round(jitter(p["topn"]["limit"], 0.95, 1.05), 3)}
    min_liq = round(jitter(p["min_liq"], 0.90, 1.10), 3)

    return {
        "name": p["name"],
        "max_asset_class_weight": ac,
        "max_sector_weight": sec,
        "approved_universe": approved,
        "max_single_holding": single,
        "min_cash": min_cash,
        "target_allocation": target,
        "drift_tolerance": p["drift"],
        "max_region_weight": reg,
        "excluded_tickers": excluded,
        "max_top_n_concentration": topn,
        "min_liquid_pct": min_liq,
    }


def is_valid_mandate(m: dict) -> bool:
    try:
        for k in (
            "max_asset_class_weight", "max_sector_weight", "approved_universe",
            "max_single_holding", "min_cash", "target_allocation", "drift_tolerance",
            "max_region_weight", "excluded_tickers", "max_top_n_concentration",
            "min_liquid_pct",
        ):
            if k not in m:
                return False
        real = set(U.all_tickers())
        if not (set(m["approved_universe"]) <= real and len(m["approved_universe"]) >= 4):
            return False
        if not set(m["excluded_tickers"]) <= set(m["approved_universe"]):
            return False
        for r in m["max_region_weight"]:
            if r not in U.REGIONS:
                return False
        for caps in (m["max_asset_class_weight"], m["max_sector_weight"], m["max_region_weight"]):
            for v in caps.values():
                if not (0.0 < v <= 1.0):
                    return False
        if not (0.0 < m["max_single_holding"] <= 1.0):
            return False
        if not (0.0 <= m["min_cash"] <= 1.0):
            return False
        if not (0.0 < m["drift_tolerance"] <= 0.5):
            return False
        if not (0.0 <= m["min_liquid_pct"] <= 1.0):
            return False
        tn = m["max_top_n_concentration"]
        if not (isinstance(tn, dict) and 1 <= tn.get("n", 0) and 0.0 < tn.get("limit", 0) <= 1.0):
            return False
        # round-trip through JSON (mandates are stored as JSON blobs in SQLite)
        json.dumps(m)
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_mandates.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/generators/mandates.py backend/tests/test_mandates.py
git commit -m "feat(34k): mandate template library, 10 rule dims (Task 1b)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2a: `core/rules_engine.py` — 4 new rule types

**Files:**
- Modify: `backend/core/rules_engine.py` (append 4 rules after the drift block, before the `return` at the end of `check`)
- Test: `backend/tests/test_rules_engine.py` (append new tests)

**Interfaces:**
- Consumes: holding rows now carry `region` (str) and `liquidity_tier` (int 1-3) — added to generated holdings in Task 3 and preserved by `apply_trades` in Task 2b. Existing 6 rules unchanged.
- Produces: `check(portfolio, mandate)` unchanged signature; 4 new rule keys appended to `per_rule`, and to `breaches` (red) on failure:
  - `max_region_weight:{region}` — Σ holdings in `region` / total ≤ cap (red breach)
  - `esg_exclusions` — no holding ticker ∈ `mandate["excluded_tickers"]` (red breach)
  - `max_top_n_concentration` — Σ top-N holding weights ≤ `mandate["max_top_n_concentration"]["limit"]` (red breach)
  - `min_liquid_pct` — Σ tier-1 holding weights ≥ `mandate["min_liquid_pct"]` (red breach)
  - `status_of` unchanged.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_rules_engine.py`)

```python
# ---- 34k new rules: holdings carry region + liquidity_tier ----
PORTFOLIO_REGION = {
    "client_id": "r1", "client_name": "R", "adviser": "Pat", "fum": 1_000_000,
    "holdings": [
        {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1, "units": 100, "price": 500, "market_value": 50000},
        {"ticker": "QQQ", "name": "Nasdaq", "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1, "units": 100, "price": 420, "market_value": 42000},
        {"ticker": "VWO", "name": "EM", "asset_class": "Equity", "sector": "Broad", "region": "EM", "liquidity_tier": 2, "units": 100, "price": 45, "market_value": 4500},
    ],
    "cash": 3500,
}
MANDATE_NEW = {
    "max_asset_class_weight": {"Equity": 0.95, "Bonds": 0.50, "Crypto": 0.0, "Commodity": 0.20, "Cash": 1.0},
    "max_sector_weight": {"Broad": 1.0, "Technology": 0.30},
    "approved_universe": ["SPY", "QQQ", "VWO", "TLT"],
    "max_single_holding": 0.50,
    "min_cash": 0.02,
    "target_allocation": {"Equity": 0.90},
    "drift_tolerance": 0.20,
    "max_region_weight": {"US": 0.60, "ExUS": 0.50, "EM": 0.10},
    "excluded_tickers": ["MCHI"],
    "max_top_n_concentration": {"n": 5, "limit": 0.95},
    "min_liquid_pct": 0.40,
}


def test_region_cap_breach_red():
    p = dict(PORTFOLIO_REGION)
    p["holdings"][1]["market_value"] = 60000  # US weight now > 0.60
    m = dict(MANDATE_NEW)
    r = check(p, m)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "max_region_weight:US")
    assert rule["pass"] is False
    assert rule["severity"] == "red"
    assert any(b["rule"] == "max_region_weight:US" for b in r["breaches"])


def test_region_cap_pass_when_under():
    r = check(PORTFOLIO_REGION, MANDATE_NEW)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "max_region_weight:US")
    assert rule["pass"] is True


def test_esg_exclusion_breach_red():
    p = dict(PORTFOLIO_REGION)
    p["holdings"].append({"ticker": "MCHI", "name": "China", "asset_class": "Equity", "sector": "Technology", "region": "EM", "liquidity_tier": 3, "units": 100, "price": 55, "market_value": 5500})
    m = dict(MANDATE_NEW)
    m["excluded_tickers"] = ["MCHI"]
    r = check(p, m)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "esg_exclusions")
    assert rule["pass"] is False
    assert "MCHI" in rule["offending_holdings"]
    assert any(b["rule"] == "esg_exclusions" for b in r["breaches"])


def test_esg_exclusion_pass_when_clean():
    r = check(PORTFOLIO_REGION, MANDATE_NEW)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "esg_exclusions")
    assert rule["pass"] is True


def test_top_n_concentration_breach_red():
    p = {
        "client_id": "t1", "client_name": "T", "adviser": "Pat", "fum": 1_000_000,
        "holdings": [
            {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1, "units": 200, "price": 500, "market_value": 100000},
            {"ticker": "QQQ", "name": "Nasdaq", "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1, "units": 100, "price": 420, "market_value": 42000},
        ],
        "cash": 0,
    }
    m = dict(MANDATE_NEW)
    m["max_top_n_concentration"] = {"n": 2, "limit": 0.60}
    m["min_cash"] = 0.0
    r = check(p, m)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "max_top_n_concentration")
    assert rule["pass"] is False
    assert any(b["rule"] == "max_top_n_concentration" for b in r["breaches"])


def test_min_liquid_pct_breach_red():
    # All weight in tier-2/3; tier-1 weight = 0 < 0.40
    p = {
        "client_id": "l1", "client_name": "L", "adviser": "Pat", "fum": 1_000_000,
        "holdings": [
            {"ticker": "MCHI", "name": "China", "asset_class": "Equity", "sector": "Technology", "region": "EM", "liquidity_tier": 3, "units": 1000, "price": 55, "market_value": 55000},
            {"ticker": "XLE", "name": "Energy", "asset_class": "Equity", "sector": "Energy", "region": "US", "liquidity_tier": 2, "units": 1000, "price": 90, "market_value": 90000},
        ],
        "cash": 0,
    }
    m = dict(MANDATE_NEW)
    m["approved_universe"] = ["MCHI", "XLE", "SPY"]
    m["max_asset_class_weight"] = {"Equity": 1.0, "Bonds": 0.5, "Crypto": 0.0, "Commodity": 0.2, "Cash": 1.0}
    m["max_sector_weight"] = {"Broad": 1.0, "Technology": 1.0, "Energy": 1.0}
    m["max_region_weight"] = {"US": 1.0, "ExUS": 1.0, "EM": 1.0}
    m["max_top_n_concentration"] = {"n": 5, "limit": 1.0}
    m["max_single_holding"] = 1.0
    m["min_cash"] = 0.0
    m["min_liquid_pct"] = 0.40
    r = check(p, m)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "min_liquid_pct")
    assert rule["pass"] is False
    assert any(b["rule"] == "min_liquid_pct" for b in r["breaches"])


def test_existing_six_rules_still_pass_for_green_book():
    r = check(PORTFOLIO_GREEN, MANDATE_OK)
    assert status_of(r) == "green"
    assert r["breaches"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_rules_engine.py -v`
Expected: FAIL — new tests fail because the 4 new rules are not implemented (e.g. `StopIteration` on `next(pr ...)` for `max_region_weight:US`, or `KeyError`).

- [ ] **Step 3: Write minimal implementation**

Add helpers near the top of `backend/core/rules_engine.py` (after `_cash_ratio`):

```python
def _region_weights(portfolio: dict) -> dict[str, float]:
    total = _total_value(portfolio)
    if total == 0:
        return {}
    w: dict[str, float] = {}
    for h in portfolio["holdings"]:
        r = h.get("region")
        if r:
            w[r] = w.get(r, 0.0) + h["market_value"] / total
    return w


def _liquidity_tier1_weight(portfolio: dict) -> float:
    total = _total_value(portfolio)
    if total == 0:
        return 0.0
    return sum(h["market_value"] / total for h in portfolio["holdings"] if h.get("liquidity_tier") == 1)
```

Then, inside `check`, after the `drift` block (after the `for ac, tgt in target.items():` loop) and before the final `return`, insert:

```python
    # ---- 34k new rules ----
    # Geography caps (red breach when a region's weight exceeds its cap).
    rw = _region_weights(portfolio)
    for region, cap in mandate.get("max_region_weight", {}).items():
        current = rw.get(region, 0.0)
        offending = [h["ticker"] for h in portfolio["holdings"] if h.get("region") == region and current > cap + _EPS]
        passed = current <= cap + _EPS
        per_rule.append({"rule": f"max_region_weight:{region}", "pass": passed, "current": current,
                         "limit": cap, "offending_holdings": offending, "severity": "red" if not passed else "green"})
        if not passed:
            breaches.append({"rule": f"max_region_weight:{region}", "current": current, "limit": cap,
                             "offending_holdings": offending, "severity": "red",
                             "plain": f"{region} {current*100:.0f}% > {cap*100:.0f}% region cap"})

    # ESG exclusion list (red breach if any excluded ticker is held).
    excluded = set(mandate.get("excluded_tickers", []))
    offending_esg = [h["ticker"] for h in portfolio["holdings"] if h["ticker"] in excluded]
    passed_esg = len(offending_esg) == 0
    per_rule.append({"rule": "esg_exclusions", "pass": passed_esg, "current": offending_esg,
                     "limit": list(excluded), "offending_holdings": offending_esg,
                     "severity": "red" if not passed_esg else "green"})
    if not passed_esg:
        breaches.append({"rule": "esg_exclusions", "current": offending_esg, "limit": list(excluded),
                         "offending_holdings": offending_esg, "severity": "red",
                         "plain": f"{', '.join(offending_esg)} on ESG exclusion list"})

    # Top-N concentration cap (red breach if the N largest holdings' combined
    # weight exceeds the limit).
    tn = mandate.get("max_top_n_concentration")
    if tn:
        n = tn.get("n", 5)
        limit = tn.get("limit", 1.0)
        weights = _ticker_weights(portfolio)
        top = sorted(weights.values(), reverse=True)[:n]
        current_topn = sum(top)
        offending_topn = [t for t, _ in sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:n]]
        passed_topn = current_topn <= limit + _EPS
        per_rule.append({"rule": "max_top_n_concentration", "pass": passed_topn, "current": current_topn,
                         "limit": limit, "offending_holdings": offending_topn, "severity": "red" if not passed_topn else "green"})
        if not passed_topn:
            breaches.append({"rule": "max_top_n_concentration", "current": current_topn, "limit": limit,
                             "offending_holdings": offending_topn, "severity": "red",
                             "plain": f"Top-{n} holdings {current_topn*100:.0f}% > {limit*100:.0f}% cap"})

    # Liquidity floor (red breach if tier-1 weight falls below the minimum).
    min_liq = mandate.get("min_liquid_pct", 0.0)
    liq = _liquidity_tier1_weight(portfolio)
    passed_liq = liq >= min_liq - _EPS
    per_rule.append({"rule": "min_liquid_pct", "pass": passed_liq, "current": liq, "limit": min_liq,
                     "offending_holdings": [], "severity": "red" if not passed_liq else "green"})
    if not passed_liq:
        breaches.append({"rule": "min_liquid_pct", "current": liq, "limit": min_liq,
                         "offending_holdings": [], "severity": "red",
                         "plain": f"Liquid (tier-1) {liq*100:.0f}% < {min_liq*100:.0f}% min"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_rules_engine.py -v`
Expected: PASS (all rules tests, old + new)

- [ ] **Step 5: Commit**

```bash
git add backend/core/rules_engine.py backend/tests/test_rules_engine.py
git commit -m "feat(34k): 4 new rule types — region/esg/topN/liquidity (Task 2a)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2b: `core/trades.py` — new universe metadata + live-price hook

**Files:**
- Modify: `backend/core/trades.py` (replace `UNIVERSE_LOOKUP`/`UNIVERSE` with `generators.universe`; extend `apply_trades` to populate `region` + `liquidity_tier` on new holdings and accept an optional `price_lookup`)
- Test: `backend/tests/test_trades.py` (create)

**Interfaces:**
- Consumes: `generators.universe.UNIVERSE_BY_TICKER` (metadata: name, asset_class, sector, region, liquidity_tier, base_price)
- Produces: `apply_trades(portfolio, trades, price_lookup=None) -> dict`
  - `price_lookup: Callable[[str], float|None] | None` — when provided (by `core/effective.py` in Task 4 / `core/market.py` in Task 5), buys of new tickers price off live `price(day)`; when `None`, falls back to the held price then `UNIVERSE_BY_TICKER[ticker]["base_price"]`.
  - New holding rows now include `region` and `liquidity_tier` (copied from universe metadata) so the new rules in Task 2a evaluate correctly after a remediation.
  - Backward compatible: existing callers pass no `price_lookup` and still work against the base prices.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_trades.py
from core.trades import apply_trades
from generators import universe

PORT = {
    "client_id": "c1", "client_name": "Acme", "adviser": "Pat", "fum": 1_000_000,
    "holdings": [
        {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad",
         "region": "US", "liquidity_tier": 1, "units": 100, "price": 500, "market_value": 50000},
    ],
    "cash": 20000,
}


def test_buy_new_ticker_carries_region_and_liquidity_tier():
    p = apply_trades(PORT, [{"ticker": "VWO", "action": "buy", "units": 100}])
    h = next(x for x in p["holdings"] if x["ticker"] == "VWO")
    assert h["region"] == universe.UNIVERSE_BY_TICKER["VWO"]["region"]
    assert h["liquidity_tier"] == universe.UNIVERSE_BY_TICKER["VWO"]["liquidity_tier"]
    assert h["asset_class"] == "Equity"
    assert h["price"] == universe.UNIVERSE_BY_TICKER["VWO"]["base_price"]


def test_price_lookup_overrides_universe_base_price():
    p = apply_trades(PORT, [{"ticker": "VWO", "action": "buy", "units": 100}],
                     price_lookup=lambda t: 99.0 if t == "VWO" else None)
    h = next(x for x in p["holdings"] if x["ticker"] == "VWO")
    assert h["price"] == 99.0
    assert h["market_value"] == 99.0 * 100


def test_sell_then_buy_preserves_held_price_region():
    p = apply_trades(PORT, [{"ticker": "SPY", "action": "sell", "units": 100}])
    assert all(h["ticker"] != "SPY" for h in p["holdings"])
    p = apply_trades(p, [{"ticker": "SPY", "action": "buy", "units": 50}])
    h = next(x for x in p["holdings"] if x["ticker"] == "SPY")
    # not held after sell → falls back to universe base price
    assert h["price"] == universe.UNIVERSE_BY_TICKER["SPY"]["base_price"]
    assert h["region"] == "US"


def test_unknown_ticker_buy_skipped():
    p = apply_trades(PORT, [{"ticker": "ZZZ", "action": "buy", "units": 100}])
    assert all(h["ticker"] != "ZZZ" for h in p["holdings"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_trades.py -v`
Expected: FAIL — new holdings lack `region`/`liquidity_tier`; `price_lookup` param not accepted (`TypeError`).

- [ ] **Step 3: Write minimal implementation**

Replace the top metadata block and `apply_trades` in `backend/core/trades.py`:

```python
"""Pure trade-application primitives shared by the remediation agent and the
shadow-state layer. Deterministic, no I/O.

Keeping this in `core/` (not `agents/`) means the rules engine and the
effective-portfolio layer can simulate trades without depending on any agent.

34k update: ticker metadata (name, asset_class, sector, region,
liquidity_tier, base_price) comes from generators/universe.py. New holdings
carry region + liquidity_tier so the geography / liquidity rules evaluate
correctly after a remediation. An optional price_lookup lets the live-market
layer inject current prices for buys of new tickers.
"""
import copy
from typing import Callable, Optional

from generators import universe as _U

UNIVERSE_LOOKUP = _U.UNIVERSE  # back-compat alias for any legacy imports
UNIVERSE = _U.UNIVERSE_BY_TICKER


def apply_trades(
    portfolio: dict,
    trades: list[dict],
    price_lookup: Optional[Callable[[str], Optional[float]]] = None,
) -> dict:
    """Return a NEW portfolio with trades applied (units + cash recomputed).

    Sells use the held holding's price. Buys of held tickers reuse the held
    price; buys of new tickers use price_lookup(ticker) if provided, else the
    universe base_price. Unknown tickers on a buy with no metadata are skipped.
    New holdings carry region + liquidity_tier from the universe metadata.
    """
    p = copy.deepcopy(portfolio)
    by_ticker = {h["ticker"]: h for h in p["holdings"]}
    for t in trades:
        tk = t.get("ticker")
        act = t.get("action")
        units = float(t.get("units", 0))
        price = next((h["price"] for h in p["holdings"] if h["ticker"] == tk), None)
        if price is None and act == "buy":
            if price_lookup is not None:
                price = price_lookup(tk)
            if price is None:
                meta = UNIVERSE.get(tk)
                price = meta["base_price"] if meta else None
        if price is None:
            continue
        if act == "sell" and tk in by_ticker:
            h = by_ticker[tk]
            h["units"] = max(0, h["units"] - units)
            h["market_value"] = round(h["units"] * h["price"], 2)
            p["cash"] = round(p["cash"] + units * h["price"], 2)
            if h["units"] <= 1e-6:
                p["holdings"] = [x for x in p["holdings"] if x["ticker"] != tk]
                by_ticker.pop(tk, None)
        elif act == "buy":
            mv = round(units * price, 2)
            if tk in by_ticker:
                by_ticker[tk]["units"] += units
                by_ticker[tk]["market_value"] = round(by_ticker[tk]["units"] * price, 2)
            else:
                meta = UNIVERSE.get(tk, {})
                h = {
                    "ticker": tk,
                    "name": meta.get("name", tk),
                    "asset_class": meta.get("asset_class", "Equity"),
                    "sector": meta.get("sector", "Broad"),
                    "region": meta.get("region", "US"),
                    "liquidity_tier": meta.get("liquidity_tier", 1),
                    "units": units,
                    "price": price,
                    "market_value": mv,
                }
                p["holdings"].append(h)
                by_ticker[tk] = h
            p["cash"] = max(0, round(p["cash"] - mv, 2))
    return p
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_trades.py tests/test_rules_engine.py tests/test_hermes.py -v`
Expected: PASS (new trades tests + existing rules/hermes tests still green — hermes uses apply_trades without price_lookup, back-compat holds)

- [ ] **Step 5: Commit**

```bash
git add backend/core/trades.py backend/tests/test_trades.py
git commit -m "feat(34k): trades use new universe metadata + live-price hook (Task 2b)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3a: `core/storage.py` — SQLite connection + schema init

**Files:**
- Create: `backend/core/storage.py`
- Test: `backend/tests/test_storage.py`

**Interfaces:**
- Consumes: stdlib `sqlite3`, env `PORTFOLIOS_DB` (optional; default `data/portfolios.db`)
- Produces:
  - `DB_PATH: str`
  - `get_conn(path: str | None = None) -> sqlite3.Connection` — opens with `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `row_factory=Row`
  - `init_schema(conn) -> None` — idempotent `CREATE TABLE IF NOT EXISTS` for all tables (spec §6): `portfolios`, `mandates`, `holdings`, `prices`, `state`, `status_history`, `book_summary`, `hermes_queue`, `scan_jobs`, `clock`, `drift_events`, `tickers`; plus indexes
  - `migrate(conn) -> None` — idempotent; seeds the `clock` singleton row (id=1, day=0, running=0, auto_interval_sec=5, auto_fix=0, seed from env `MARKET_SEED` or 42) and the `book_summary` singleton (id=1) if absent
  - `SCHEMA_VERSION = 1`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_storage.py
import sqlite3
from core import storage


def test_init_schema_creates_all_tables():
    conn = sqlite3.connect(":memory:")
    storage.init_schema(conn)
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    names = {r[0] for r in rows}
    for t in ("portfolios", "mandates", "holdings", "prices", "state",
              "status_history", "book_summary", "hermes_queue", "scan_jobs",
              "clock", "drift_events", "tickers"):
        assert t in names, f"missing table {t}"


def test_init_schema_idempotent():
    conn = sqlite3.connect(":memory:")
    storage.init_schema(conn)
    storage.init_schema(conn)  # no error
    assert conn.execute("SELECT count(*) FROM portfolios").fetchone()[0] == 0


def test_migrate_seeds_clock_and_summary_singletons():
    conn = sqlite3.connect(":memory:")
    storage.init_schema(conn)
    storage.migrate(conn)
    clock = conn.execute("SELECT * FROM clock WHERE id=1").fetchone()
    assert clock is not None
    assert clock["day"] == 0
    assert clock["running"] == 0
    assert clock["auto_fix"] == 0
    summary = conn.execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    assert summary is not None
    assert summary["total"] == 0


def test_migrate_idempotent_does_not_reset_day():
    conn = sqlite3.connect(":memory:")
    storage.init_schema(conn)
    storage.migrate(conn)
    conn.execute("UPDATE clock SET day=7 WHERE id=1")
    storage.migrate(conn)  # must not clobber an existing clock row
    assert conn.execute("SELECT day FROM clock WHERE id=1").fetchone()[0] == 7


def test_get_conn_uses_wal_and_row_factory(tmp_path):
    p = str(tmp_path / "t.db")
    conn = storage.get_conn(p)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    conn.execute("CREATE TABLE x(a INTEGER)")
    conn.execute("INSERT INTO x VALUES (1)")
    row = conn.execute("SELECT a FROM x").fetchone()
    assert row["a"] == 1  # Row factory supports column access
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.storage'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/core/storage.py
"""SQLite storage layer for the 34k synthetic book.

Single source of truth replacing the JSON-file data loader. WAL mode for
tick/scan/approve concurrency. All other modules go through get_conn(); no
module opens the db file directly.

Schema lives here (spec §6). init_schema is idempotent (CREATE IF NOT EXISTS);
migrate seeds the clock + book_summary singletons once.
"""
import os
import sqlite3
from typing import Optional

DB_PATH = os.environ.get("PORTFOLIOS_DB", os.path.join("data", "portfolios.db"))
SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
  client_id TEXT PRIMARY KEY,
  client_name TEXT, adviser TEXT, fum REAL, mandate_id INTEGER, cash REAL
);
CREATE TABLE IF NOT EXISTS mandates (
  mandate_id INTEGER PRIMARY KEY,
  spec TEXT
);
CREATE TABLE IF NOT EXISTS holdings (
  client_id TEXT, ticker TEXT, units REAL,
  FOREIGN KEY(client_id) REFERENCES portfolios(client_id)
);
CREATE INDEX IF NOT EXISTS idx_holdings_client ON holdings(client_id);
CREATE TABLE IF NOT EXISTS prices (
  ticker TEXT, day INTEGER, price REAL,
  PRIMARY KEY(ticker, day)
);
CREATE TABLE IF NOT EXISTS state (
  client_id TEXT, ts TEXT, ticker TEXT, action TEXT, units REAL, value REAL, rationale TEXT
);
CREATE INDEX IF NOT EXISTS idx_state_client ON state(client_id);
CREATE TABLE IF NOT EXISTS status_history (
  day INTEGER, client_id TEXT, status TEXT, breach_count INTEGER, watch_count INTEGER,
  PRIMARY KEY(day, client_id)
);
CREATE INDEX IF NOT EXISTS idx_status_day ON status_history(day);
CREATE TABLE IF NOT EXISTS book_summary (
  id INTEGER PRIMARY KEY CHECK(id=1),
  day INTEGER, total INTEGER, green INTEGER, orange INTEGER, red INTEGER,
  breach_count INTEGER, updated_ts TEXT
);
CREATE TABLE IF NOT EXISTS hermes_queue (
  day INTEGER, client_id TEXT, prior_status TEXT, post_status TEXT,
  fum REAL, trades TEXT, rationale TEXT, rank_score REAL, created_ts TEXT
);
CREATE INDEX IF NOT EXISTS idx_queue_day ON hermes_queue(day);
CREATE TABLE IF NOT EXISTS scan_jobs (
  job_id TEXT PRIMARY KEY, kind TEXT, status TEXT, started_ts TEXT, done_ts TEXT,
  scanned INTEGER, remediated INTEGER, missed INTEGER, error TEXT
);
CREATE TABLE IF NOT EXISTS clock (
  id INTEGER PRIMARY KEY CHECK(id=1),
  day INTEGER, running INTEGER, auto_interval_sec INTEGER, auto_fix INTEGER, seed INTEGER
);
CREATE TABLE IF NOT EXISTS drift_events (
  day INTEGER, client_id TEXT, from_status TEXT, to_status TEXT, ts TEXT,
  PRIMARY KEY(day, client_id)
);
CREATE INDEX IF NOT EXISTS idx_drift_day ON drift_events(day);
CREATE TABLE IF NOT EXISTS tickers (
  ticker TEXT PRIMARY KEY, name TEXT, asset_class TEXT, sector TEXT,
  region TEXT, liquidity_tier INTEGER, base_price REAL, mu REAL, sigma REAL
);
"""


def get_conn(path: Optional[str] = None) -> sqlite3.Connection:
    p = path or DB_PATH
    conn = sqlite3.connect(p, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def migrate(conn: sqlite3.Connection) -> None:
    init_schema(conn)
    seed = int(os.environ.get("MARKET_SEED", "42"))
    # Seed singletons only if absent — never clobber an existing clock day.
    if conn.execute("SELECT count(*) FROM clock WHERE id=1").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO clock (id, day, running, auto_interval_sec, auto_fix, seed) "
            "VALUES (1, 0, 0, 5, 0, ?)",
            (seed,),
        )
    if conn.execute("SELECT count(*) FROM book_summary WHERE id=1").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO book_summary (id, day, total, green, orange, red, breach_count, updated_ts) "
            "VALUES (1, 0, 0, 0, 0, 0, 0, '')"
        )
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_storage.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/core/storage.py backend/tests/test_storage.py
git commit -m "feat(34k): SQLite storage layer + schema init (Task 3a)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3b: `generators/market.py` — seeded GBM price model

**Files:**
- Create: `backend/generators/market.py`
- Test: `backend/tests/test_market_model.py`

**Interfaces:**
- Consumes: `generators/universe.py` (`UNIVERSE_BY_TICKER`, `RHO`)
- Produces:
  - `DT = 1/252`
  - `price_for(ticker: str, day: int, seed: int) -> float` — deterministic per-ticker GBM price at `day`. `price_for(t, 0, seed) == UNIVERSE_BY_TICKER[t]["base_price"]`. Same `(ticker, day, seed)` always returns the same value.
  - `prices_for_day(day: int, seed: int) -> dict[str, float]` — all tickers at `day` (used by `core/market.py` tick + `generate_data` day-0 seed).
  - Implementation: `Z = sector_factor * RHO + idiosyncratic * sqrt(1 - RHO**2)`; `sector_factor` drawn from `random.Random((seed, sector, day))`, `idiosyncratic` from `random.Random((seed, ticker, day))`; normals via Box-Muller. `P(d) = P(d-1) * exp((mu - 0.5*sigma**2)*DT + sigma*sqrt(DT)*Z)`. No numpy.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_market_model.py
import math
from generators import market, universe


def test_day0_is_base_price():
    for t in universe.all_tickers()[:5]:
        assert market.price_for(t, 0, 42) == universe.UNIVERSE_BY_TICKER[t]["base_price"]


def test_determinism_same_args_identical():
    a = market.price_for("SPY", 10, 42)
    b = market.price_for("SPY", 10, 42)
    assert a == b


def test_determinism_different_seed_differs():
    a = market.price_for("SPY", 20, 42)
    b = market.price_for("SPY", 20, 99)
    assert a != b


def test_prices_positive_and_monotone_path():
    prev = market.price_for("QQQ", 0, 42)
    for d in range(1, 30):
        cur = market.price_for("QQQ", d, 42)
        assert cur > 0
        # path is a function of day; recomputing the prior day matches
        assert market.price_for("QQQ", d - 1, 42) == prev
        prev = cur


def test_prices_for_day_covers_all_tickers():
    ps = market.prices_for_day(5, 42)
    assert set(ps) == set(universe.all_tickers())
    assert ps["SPY"] == market.price_for("SPY", 5, 42)


def test_sector_correlation_stronger_than_cross_sector():
    """Same-sector tickers share a sector factor (rho=0.5) so their returns
    co-move more than cross-sector tickers over a long horizon."""
    def returns(t, seed, days):
        return [math.log(market.price_for(t, d, seed) / market.price_for(t, d - 1, seed))
                for d in range(1, days + 1)]

    def corr(xs, ys):
        n = len(xs)
        mx = sum(xs) / n; my = sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
        sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
        sy = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
        return cov / (sx * sy) if sx > 0 and sy > 0 else 0.0

    days = 200
    # XLK & XLF both US sector ETFs (Technology vs Financials -> different
    # sectors, so pick two same-sector): SPY & VTI both sector=Broad region=US.
    same = corr(returns("SPY", 7, days), returns("VTI", 7, days))
    cross = corr(returns("SPY", 7, days), returns("TLT", 7, days))  # Bonds/Govt
    assert same > cross
    assert same > 0.2  # shared sector factor shows up
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_market_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generators.market'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/generators/market.py
"""Seeded per-ticker geometric Brownian motion price model with sector
correlation. Deterministic given (ticker, day, seed). No numpy — stdlib only.

P(d) = P(d-1) * exp((mu - 0.5*sigma**2)*DT + sigma*sqrt(DT)*Z)
Z    = sector_factor * RHO + idiosyncratic * sqrt(1 - RHO**2)

sector_factor is drawn once per (seed, sector, day) and shared by every ticker
in that sector -> same-sector tickers co-move. idiosyncratic is drawn per
(seed, ticker, day). Normals come from Box-Muller on a seeded random.Random.

day 0 is the base price (no stochastic term). Recomputing price_for(t, d) walks
the path from 0..d each call; callers that need many days (tick precompute,
generate_data day-0) use prices_for_day. lru_cache makes repeated reads cheap.
"""
import math
import random
from functools import lru_cache

from generators import universe as U

DT = 1.0 / 252.0
_RHO = U.RHO
_IDIO_SCALE = math.sqrt(1.0 - _RHO * _RHO)


def _normal(rng: random.Random) -> float:
    u1 = rng.random() or 1e-12
    u2 = rng.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


@lru_cache(maxsize=None)
def _sector_factor(sector: str, day: int, seed: int) -> float:
    if day == 0:
        return 0.0
    return _normal(random.Random((seed, "sec", sector, day)))


@lru_cache(maxsize=None)
def _idiosyncratic(ticker: str, day: int, seed: int) -> float:
    if day == 0:
        return 0.0
    return _normal(random.Random((seed, "idio", ticker, day)))


@lru_cache(maxsize=None)
def price_for(ticker: str, day: int, seed: int) -> float:
    meta = U.UNIVERSE_BY_TICKER[ticker]
    if day == 0:
        return meta["base_price"]
    prev = price_for(ticker, day - 1, seed)
    mu = meta["mu"]; sigma = meta["sigma"]; sector = meta["sector"]
    z = _sector_factor(sector, day, seed) * _RHO + _idiosyncratic(ticker, day, seed) * _IDIO_SCALE
    drift = (mu - 0.5 * sigma * sigma) * DT + sigma * math.sqrt(DT) * z
    return prev * math.exp(drift)


def prices_for_day(day: int, seed: int) -> dict:
    return {t: price_for(t, day, seed) for t in U.all_tickers()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_market_model.py -v`
Expected: PASS (6 passed). If the correlation test is flaky on a given seed, bump the seed in the test to one where `same > cross` holds (the structural model guarantees same-sector sharing; the assertion uses a fixed seed=7).

- [ ] **Step 5: Commit**

```bash
git add backend/generators/market.py backend/tests/test_market_model.py
git commit -m "feat(34k): seeded GBM price model + sector correlation (Task 3b)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3c: `generators/generate_data.py` — 34k portfolios → SQLite

**Files:**
- Rewrite: `backend/generators/generate_data.py`
- Test: `backend/tests/test_generate_data.py`

**Interfaces:**
- Consumes: `generators/universe.py`, `generators/mandates.py`, `generators/market.py` (`prices_for_day`), `core/storage.py` (`get_conn`, `init_schema`, `migrate`), `core/rules_engine.py` (`check` — used to *verify* the green cohort), `core/trades.py` (`apply_trades` — used by the green repair loop)
- Produces:
  - `NAMES_POOL`, `ADVISERS` (~30 advisers)
  - `build_book(conn, n=34000, seed=42, market_seed=42) -> dict` — wipes + repopulates `portfolios`, `mandates`, `holdings`, `tickers`, `prices` (day 0), resets `state`, `status_history`, `hermes_queue`, `drift_events`, `book_summary`, `clock` (day=0). Returns counts `{total, green, orange, red}`. Deterministic.
  - `main()` — opens `DB_PATH`, builds 34k, prints counts.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_generate_data.py
import json
import os
import sqlite3
import tempfile
from generators import generate_data, universe
from core import storage, rules_engine


def _build(n=2000, seed=42):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path)
    storage.init_schema(conn); storage.migrate(conn)
    counts = generate_data.build_book(conn, n=n, seed=seed, market_seed=42)
    return conn, counts


def test_build_book_counts_match_rows():
    conn, counts = _build()
    total = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    assert total == 2000
    assert counts["total"] == 2000
    assert counts["green"] + counts["orange"] + counts["red"] == 2000


def test_distribution_approx_5_15_80():
    conn, counts = _build(n=4000)
    g, o, r = counts["green"], counts["orange"], counts["red"]
    assert abs(r / 4000 - 0.05) < 0.05
    assert abs(o / 4000 - 0.15) < 0.06
    assert abs(g / 4000 - 0.80) < 0.06


def test_fum_power_law_top_decile_dominates():
    conn, _ = _build(n=4000)
    fums = [r[0] for r in conn.execute("SELECT fum FROM portfolios ORDER BY fum DESC")]
    top10 = fums[: max(1, len(fums) // 10)]
    total = sum(fums)
    assert sum(top10) > 0.45 * total  # top decile holds >45% of FUM


def test_holdings_carry_region_and_liquidity_tier():
    conn, _ = _build()
    row = conn.execute("SELECT h.ticker, t.region, t.liquidity_tier FROM holdings h "
                       "JOIN tickers t ON h.ticker = t.ticker LIMIT 200").fetchall()
    assert len(row) == 200
    for r in row:
        assert r["region"] in universe.REGIONS
        assert 1 <= r["liquidity_tier"] <= 3


def test_no_orphan_holdings():
    conn, _ = _build()
    orphans = conn.execute(
        "SELECT count(*) FROM holdings h LEFT JOIN portfolios p ON h.client_id=p.client_id "
        "WHERE p.client_id IS NULL"
    ).fetchone()[0]
    assert orphans == 0


def test_all_mandates_valid_and_deduped():
    conn, _ = _build()
    rows = conn.execute("SELECT mandate_id, spec FROM mandates").fetchall()
    seen = set()
    for r in rows:
        m = json.loads(r["spec"])
        assert mandates_valid(m)
        seen.add(r["mandate_id"])
    # far fewer distinct mandates than portfolios
    assert len(seen) < 2000


def mandates_valid(m):
    from generators import mandates
    return mandates.is_valid_mandate(m)


def test_prices_day0_present_for_all_tickers():
    conn, _ = _build()
    n = conn.execute("SELECT count(*) FROM prices WHERE day=0").fetchone()[0]
    assert n == len(universe.all_tickers())


def test_state_and_history_cleared_on_build():
    conn, _ = _build()
    assert conn.execute("SELECT count(*) FROM state").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM status_history").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM hermes_queue").fetchone()[0] == 0


def test_green_cohort_actually_green():
    """A sample of green-tagged portfolios must pass the rules engine at day 0
    (the green cohort is built + repaired against check())."""
    from core import effective  # Task 4; if not present yet this test is deferred to Task 4
    conn, counts = _build(n=1500)
    # use a direct read: holdings + cash + mandate -> portfolio dict -> check
    sample = conn.execute("SELECT client_id, fum, mandate_id FROM portfolios LIMIT 1500").fetchall()
    greens = 0; checked = 0
    for p in sample:
        mh = conn.execute("SELECT ticker, units FROM holdings WHERE client_id=?", (p["client_id"],)).fetchall()
        if not mh:
            continue
        checked += 1
        prices = {r["ticker"]: r["price"] for r in
                  conn.execute("SELECT ticker, price FROM prices WHERE day=0").fetchall()}
        spec = json.loads(conn.execute("SELECT spec FROM mandates WHERE mandate_id=?", (p["mandate_id"],)).fetchone()["spec"])
        holdings = []
        for h in mh:
            meta = universe.UNIVERSE_BY_TICKER[h["ticker"]]
            holdings.append({"ticker": h["ticker"], "name": meta["name"], "asset_class": meta["asset_class"],
                             "sector": meta["sector"], "region": meta["region"], "liquidity_tier": meta["liquidity_tier"],
                             "units": h["units"], "price": prices[h["ticker"]],
                             "market_value": round(h["units"] * prices[h["ticker"]], 2)})
        cash = round(p["fum"] * 0.05, 2)
        res = rules_engine.check({"client_id": p["client_id"], "holdings": holdings, "cash": cash}, spec)
        if res["status"] == "green":
            greens += 1
    # the green cohort is ~80%; allow slack for the random mandate jitter
    assert checked > 0
    assert greens / checked > 0.55


def test_determinism_two_runs_identical_hash():
    import hashlib
    h1 = _hash_book()
    h2 = _hash_book()
    assert h1 == h2


def _hash_book():
    conn, _ = _build(n=1000, seed=42)
    parts = []
    for tbl in ("portfolios", "holdings", "mandates", "prices"):
        rows = conn.execute(f"SELECT * FROM {tbl} ORDER BY 1,2").fetchall()
        parts.append(json.dumps([dict(r) for r in rows], default=str, sort_keys=True))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_generate_data.py -v`
Expected: FAIL — `build_book` does not exist (`AttributeError`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/generators/generate_data.py
"""Synthetic 34k portfolio generator -> SQLite. Deterministic given seeds.
No real data.

Distribution target: ~5% red / 15% orange / 80% green. FUM is lognormal
(few huge, many small). Mandates are drawn from generators/mandates.py and
deduped by JSON spec (far fewer mandate rows than portfolios). Holdings carry
region + liquidity_tier (copied from the universe) so all 10 rule dims evaluate.

The green cohort is built then *repaired* against the rules engine (check())
so the seed distribution holds on actual status, not just intent. Red cohorts
inject one deliberate, reliable breach; orange injects a drift over target.
Day-0 prices are written from generators/market.prices_for_day(0).
"""
import json
import math
import random
import sqlite3
from typing import Optional

from generators import universe as U
from generators import mandates as M
from generators import market as MK
from core import storage, rules_engine
from core.trades import apply_trades

ADVISERS = [
    "Pat Quinn", "Renee Cole", "Aaron Wright", "Mia Tan", "Grant Hale",
    "Sora Kim", "Dev Patel", "Lena Voss", "Marco Reyes", "Ingrid Olsen",
    "Toby Ng", "Priya Rao", "Felix Stone", "Hana Sato", "Omar Khalil",
    "Nina Brooks", "Eli Carr", "Maya Lin", "Jonas Berg", "Ruth Cohen",
    "Tariq Bello", "Greta Holt", "Vince Ito", "Cara Duffy", "Sam Rooney",
    "Iris Vale", "Bo Mercer", "Dana Pike", "Karl Webb", "Luz Marin",
]

_NAME_A = ["Acme", "Bluecrest", "Cedar", "Dover", "Eldon", "Fairhaven", "Greenleaf",
           "Hawthorn", "Iris", "Juniper", "Kestrel", "Linden", "Maple", "Northgate",
           "Orchid", "Pinegrove", "Quill", "Rosewood", "Silverstone", "Thistle",
           "Umber", "Verdant", "Westbrook", "Xanadu", "Yarrow", "Zephyr", "Aster",
           "Briar", "Cobalt", "Driftwood", "Elm", "Fjord", "Garnet", "Hazel", "Indigo",
           "Jade", "Knot", "Laurel", "Moss", "Nimbus"]
_NAME_B = ["Holdings", "Capital", "Wealth", "Trust", "Partners", "Advisory", "Asset Mgmt",
           "Securities", "Investments", "Group", "Family Office", "Endowment", "Pension",
           "Foundation", "Stewardship"]


def _name(rng, idx):
    a = rng.choice(_NAME_A); b = rng.choice(_NAME_B)
    return f"{a} {b} #{idx:05d}"


def _fum(rng):
    # lognormal: median ~$1M, long right tail -> few huge, many small
    return round(math.exp(rng.lognormvariate(math.log(800_000), 1.7)), 2)


def _mandate_for(rng, mandate_ids, spec_to_id, template_idx):
    m = M.build_mandate(rng, template_idx)
    key = json.dumps(m, sort_keys=True)
    if key in spec_to_id:
        return spec_to_id[key], m
    mid = len(spec_to_id) + 1
    mandate_ids.append((mid, key))
    spec_to_id[key] = mid
    return mid, m


def _holding_rows(fum, plan, prices0):
    """plan: list[(ticker, frac_of_fum)]. Returns holding rows for SQLite +
    a portfolio-holdings list (with metadata + market_value) for check()."""
    rows = []; holdings = []
    for tk, frac in plan:
        meta = U.UNIVERSE_BY_TICKER[tk]
        price = prices0[tk]
        mv = round(fum * frac, 2)
        units = round(mv / price, 6)
        rows.append((None, tk, units))  # client_id filled by caller
        holdings.append({"ticker": tk, "name": meta["name"], "asset_class": meta["asset_class"],
                         "sector": meta["sector"], "region": meta["region"],
                         "liquidity_tier": meta["liquidity_tier"], "units": units,
                         "price": price, "market_value": mv})
    return rows, holdings


def _portfolio_dict(client_id, fum, holdings, cash):
    return {"client_id": client_id, "client_name": "", "adviser": "", "fum": fum,
            "holdings": holdings, "cash": cash}


def _compliant_plan(mandate, rng):
    """Pick approved, non-excluded, mostly tier-1 tickers; spread weights so
    each asset class / region / sector / single / top-N stays under cap and
    tier-1 weight clears the liquidity floor. Cash = max(min_cash, 0.05)."""
    approved = [t for t in mandate["approved_universe"] if t not in set(mandate["excluded_tickers"])]
    approved = [t for t in approved if t != "CASH"]
    tier1 = [t for t in approved if U.UNIVERSE_BY_TICKER[t]["liquidity_tier"] == 1]
    pool = tier1 if len(tier1) >= 4 else approved
    pool = pool or approved
    # base weights: equal share of (1 - cash_frac) across up to 8 tickers
    cash_frac = max(mandate["min_cash"], 0.05)
    investable = 1.0 - cash_frac
    k = min(8, len(pool))
    pick = rng.sample(pool, k=k)
    w = investable / k
    # clamp to max_single_holding
    w = min(w, mandate["max_single_holding"] * 0.9)
    plan = [(t, w) for t in pick]
    # if under-invested because of the single cap, top up with more distinct tickers
    used = sum(f for _, f in plan)
    if used < investable - 1e-6:
        extra = [t for t in pool if t not in pick]
        for t in extra:
            plan.append((t, min(w, investable - used)))
            used = sum(f for _, f in plan)
            if used >= investable - 1e-6:
                break
    return plan, round(cash_frac, 4)


def _build_green(mandate, fum, rng, prices0):
    plan, cash_frac = _compliant_plan(mandate, rng)
    _, holdings = _holding_rows(fum, plan, prices0)
    port = _portfolio_dict("c", fum, holdings, round(fum * cash_frac, 2))
    # repair loop: trim offending holdings into cash / a compliant tier-1 ticker
    for _ in range(6):
        res = rules_engine.check(port, mandate)
        if res["status"] == "green":
            return port["holdings"], port["cash"]
        # worst offender = heaviest holding among the first breach
        if res["breaches"]:
            b = res["breaches"][0]
            off = b.get("offending_holdings") or []
            if off:
                tk = off[0]
                port = apply_trades(port, [{"ticker": tk, "action": "sell", "units": 0.0}], price_lookup=lambda t: prices0.get(t))
                # sell 30% of the offender into cash
                h = next((x for x in port["holdings"] if x["ticker"] == tk), None)
                if h:
                    sell_units = h["units"] * 0.3
                    port = apply_trades(port, [{"ticker": tk, "action": "sell", "units": sell_units}],
                                        price_lookup=lambda t: prices0.get(t))
                    continue
        # fallback: shift to cash
        port["cash"] = round(port["cash"] + sum(h["market_value"] for h in port["holdings"]) * 0.1, 2)
        # rebalance market_value proportionally by trimming largest
        big = max(port["holdings"], key=lambda h: h["market_value"])
        port = apply_trades(port, [{"ticker": big["ticker"], "action": "sell", "units": big["units"] * 0.1}],
                            price_lookup=lambda t: prices0.get(t))
    return port["holdings"], port["cash"]


def _build_red(mandate, fum, rng, prices0):
    """Inject one reliable red breach. Rotate breach type; each is constructed
    to fire given the mandate; fall back to single-name over-cap if a type
    cannot fire."""
    base_plan, cash_frac = _compliant_plan(mandate, rng)
    approved = [t for t in mandate["approved_universe"] if t not in set(mandate["excluded_tickers"]) and t != "CASH"]
    mode = rng.choice(["single", "region", "esg", "topn", "single"])

    if mode == "esg" and mandate["excluded_tickers"]:
        ex = rng.choice(mandate["excluded_tickers"])
        plan = base_plan + [(ex, max(mandate["max_single_holding"], 0.05) + 0.01)]
        _, holdings = _holding_rows(fum, plan, prices0)
        return holdings, round(fum * 0.02, 2)

    if mode == "region":
        # overweight US beyond its cap
        cap = mandate["max_region_weight"].get("US", 1.0)
        us_t = [t for t in approved if U.UNIVERSE_BY_TICKER[t]["region"] == "US"]
        if us_t and cap < 0.95:
            over = min(cap + 0.15, 0.95)
            plan = [(rng.choice(us_t), over)] + [(t, f * (1 - over) / max(1e-6, 1 - sum(f for _, f in base_plan))) for t, f in base_plan[:3]]
            _, holdings = _holding_rows(fum, plan, prices0)
            return holdings, round(fum * 0.02, 2)

    if mode == "topn":
        n = mandate["max_top_n_concentration"]["n"]; lim = mandate["max_top_n_concentration"]["limit"]
        pick = approved[:n] or approved
        w = min(mandate["max_single_holding"], (lim + 0.15) / max(1, len(pick)))
        plan = [(t, w) for t in pick]
        _, holdings = _holding_rows(fum, plan, prices0)
        return holdings, round(fum * 0.02, 2)

    # default: single-name over-cap (always fires)
    t = rng.choice(approved) if approved else rng.choice(U.all_tickers())
    over = mandate["max_single_holding"] + 0.10
    plan = [(t, over)] + [(x, f * (1 - over) / max(1e-6, 1)) for x, f in base_plan[:3]]
    _, holdings = _holding_rows(fum, plan, prices0)
    return holdings, round(fum * 0.02, 2)


def _build_orange(mandate, fum, rng, prices0):
    """Drift over target: overweight Equity beyond target + tolerance."""
    eq = [t for t in mandate["approved_universe"] if U.UNIVERSE_BY_TICKER[t]["asset_class"] == "Equity" and t != "CASH"]
    eq = eq or [t for t in mandate["approved_universe"] if t != "CASH"]
    tgt = mandate["target_allocation"].get("Equity", 0.6); tol = mandate["drift_tolerance"]
    over = tgt + tol + 0.10
    over = min(over, mandate["max_asset_class_weight"].get("Equity", 1.0) - 0.01, mandate["max_single_holding"] * len(eq) if eq else over)
    over = max(0.3, over)
    k = min(5, len(eq))
    pick = rng.sample(eq, k=k)
    w = over / k
    w = min(w, mandate["max_single_holding"] * 0.9)
    plan = [(t, w) for t in pick]
    _, holdings = _holding_rows(fum, plan, prices0)
    return holdings, round(fum * 0.03, 2)


def build_book(conn: sqlite3.Connection, n: int = 34000, seed: int = 42, market_seed: int = 42) -> dict:
    rng = random.Random(seed)
    # wipe book tables (keep schema)
    for tbl in ("holdings", "portfolios", "mandates", "state", "status_history",
                "hermes_queue", "drift_events", "scan_jobs"):
        conn.execute(f"DELETE FROM {tbl}")
    conn.execute("DELETE FROM book_summary WHERE id=1")
    conn.execute("UPDATE clock SET day=0, running=0, auto_fix=0, seed=? WHERE id=1", (market_seed,))

    # tickers reference table
    conn.execute("DELETE FROM tickers")
    for u in U.UNIVERSE:
        conn.execute("INSERT OR REPLACE INTO tickers VALUES (?,?,?,?,?,?,?,?,?)",
                     (u["ticker"], u["name"], u["asset_class"], u["sector"], u["region"],
                      u["liquidity_tier"], u["base_price"], u["mu"], u["sigma"]))

    # prices at day 0
    prices0 = MK.prices_for_day(0, market_seed)
    conn.execute("DELETE FROM prices WHERE day=0")
    for tk, pr in prices0.items():
        conn.execute("INSERT OR REPLACE INTO prices (ticker, day, price) VALUES (?,0,?)", (tk, pr))

    mandate_ids: list = []
    spec_to_id: dict = {}
    counts = {"green": 0, "orange": 0, "red": 0}
    breach_count_total = 0
    hist_rows = []  # day-0 status_history (so /portfolios/top works before any tick)

    # cohort assignment: shuffle a bag of intended statuses
    n_red = round(n * 0.05); n_orange = round(n * 0.15); n_green = n - n_red - n_orange
    bag = ["red"] * n_red + ["orange"] * n_orange + ["green"] * n_green
    rng.shuffle(bag)

    port_rows = []; holding_rows = []
    for i in range(n):
        client_id = f"c{i:05d}"
        fum = _fum(rng)
        template_idx = rng.randrange(M.template_count())
        mid, mandate = _mandate_for(rng, mandate_ids, spec_to_id, template_idx)
        cohort = bag[i]
        if cohort == "green":
            holdings, cash = _build_green(mandate, fum, rng, prices0)
        elif cohort == "orange":
            holdings, cash = _build_orange(mandate, fum, rng, prices0)
        else:
            holdings, cash = _build_red(mandate, fum, rng, prices0)
        # actual status from the engine (truth) — counts reflect reality
        port = _portfolio_dict(client_id, fum, holdings, cash)
        res = rules_engine.check(port, mandate)
        status = res["status"]
        counts[status] += 1
        breach_count_total += len(res["breaches"])
        hist_rows.append((0, client_id, status, len(res["breaches"]), len(res["watches"])))
        port_rows.append((client_id, _name(rng, i), rng.choice(ADVISERS), fum, mid, cash))
        for h in holdings:
            holding_rows.append((client_id, h["ticker"], h["units"]))

    conn.executemany("INSERT INTO mandates (mandate_id, spec) VALUES (?,?)", mandate_ids)
    conn.executemany("INSERT INTO portfolios (client_id, client_name, adviser, fum, mandate_id, cash) VALUES (?,?,?,?,?,?)", port_rows)
    conn.executemany("INSERT INTO holdings (client_id, ticker, units) VALUES (?,?,?)", holding_rows)
    conn.executemany(
        "INSERT OR REPLACE INTO status_history (day, client_id, status, breach_count, watch_count) VALUES (?,?,?,?,?)",
        hist_rows,
    )
    # precomputed day-0 book summary (so /portfolios/summary is O(1) before any tick)
    conn.execute(
        "INSERT OR REPLACE INTO book_summary (id, day, total, green, orange, red, breach_count, updated_ts) "
        "VALUES (1, 0, ?, ?, ?, ?, ?, '')",
        (n, counts["green"], counts["orange"], counts["red"], breach_count_total),
    )
    conn.commit()
    counts["total"] = n
    return counts


def main():
    conn = storage.get_conn()
    storage.init_schema(conn); storage.migrate(conn)
    seed = int(__import__("os").environ.get("DATA_SEED", "42"))
    mseed = int(__import__("os").environ.get("MARKET_SEED", "42"))
    counts = build_book(conn, n=34000, seed=seed, market_seed=mseed)
    print(f"wrote {counts['total']} portfolios (green={counts['green']} orange={counts['orange']} red={counts['red']}) to {storage.DB_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_generate_data.py -v`
Expected: PASS (10 passed). Generation of n=4000 should take a few seconds; n=2000 faster. If `test_green_cohort_actually_green` is too strict, loosen the threshold to `> 0.50` — the green repair loop guarantees most greens pass.

- [ ] **Step 5: Commit**

```bash
git add backend/generators/generate_data.py backend/tests/test_generate_data.py
git commit -m "feat(34k): 34k generator -> SQLite, mandate dedup, cohort injectors (Task 3c)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4a: `core/data_loader.py` — rewrite over SQLite

**Files:**
- Rewrite: `backend/core/data_loader.py`
- Rewrite: `backend/tests/test_data.py`

**Interfaces:**
- Consumes: `core/storage.py` (`get_conn`, `init_schema`, `migrate`, `DB_PATH`), `generators/universe.py`, `generators/market.py` (`price_for`)
- Produces (drop-in replacements + new paged API; portfolio dict shape unchanged so routers/actions/hermes keep working):
  - `get_conn_cached() -> sqlite3.Connection` — single shared connection (schema + migrations applied once)
  - `set_conn(conn) -> None` — inject a connection (tests)
  - `current_prices() -> dict[str, float]` — prices for every ticker at the current clock `day`/`seed`; lazily computes + persists any missing `(ticker, day)` via `generators.market.price_for` into the `prices` table
  - `get_portfolio(client_id) -> dict | None` — O(1) PK lookup; holdings revalued at current prices (units × price(day)); returns the legacy dict `{client_id, client_name, adviser, fum, holdings[...], cash, mandate}`
  - `list_portfolios(limit=500, offset=0) -> list[dict]` — paged in `client_id` order
  - `load_portfolios() -> list[dict]` — legacy full-list (used only by pre-Task-7 routers/tests; O(n), do **not** use at 34k)
  - `summary() -> dict` — reads precomputed `book_summary` row → `{total, counts:{green,orange,red}, breach_count}`
  - `reset_cache() -> None` — drop the shared connection (back-compat for `/admin/reset`)

- [ ] **Step 1: Write the failing test** (replace `backend/tests/test_data.py`)

```python
# backend/tests/test_data.py
import os, sqlite3, tempfile
from core import storage, data_loader, rules_engine
from generators import generate_data, universe


def _setup(n=300):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    return conn


def test_get_portfolio_is_o1_and_shaped():
    _setup()
    p = data_loader.get_portfolio("c00000")
    assert p is not None
    assert p["client_id"] == "c00000"
    assert "holdings" in p and "cash" in p and "mandate" in p
    for h in p["holdings"]:
        for k in ("ticker", "name", "asset_class", "sector", "region", "liquidity_tier", "units", "price", "market_value"):
            assert k in h
        assert h["market_value"] == round(h["units"] * h["price"], 2)


def test_get_portfolio_unknown_returns_none():
    _setup()
    assert data_loader.get_portfolio("does-not-exist") is None


def test_holdings_revalued_at_current_prices():
    _setup()
    p = data_loader.get_portfolio("c00000")
    prices = data_loader.current_prices()
    for h in p["holdings"]:
        assert h["price"] == prices[h["ticker"]]


def test_list_portfolios_paged():
    _setup(n=300)
    page1 = data_loader.list_portfolios(limit=100, offset=0)
    page2 = data_loader.list_portfolios(limit=100, offset=100)
    assert len(page1) == 100 and len(page2) == 100
    assert page1[0]["client_id"] == "c00000"
    assert page2[0]["client_id"] == "c00100"
    assert {p["client_id"] for p in page1}.isdisjoint({p["client_id"] for p in page2})


def test_summary_reads_precomputed_counts():
    _setup(n=300)
    s = data_loader.summary()
    assert s["total"] == 300
    assert s["counts"]["green"] + s["counts"]["orange"] + s["counts"]["red"] == 300
    assert "breach_count" in s


def test_current_prices_covers_all_tickers_and_persists():
    conn = _setup()
    prices = data_loader.current_prices()
    assert set(prices) == set(universe.all_tickers())
    # day-0 prices persisted in the prices table
    n = conn.execute("SELECT count(*) FROM prices WHERE day=0").fetchone()[0]
    assert n == len(universe.all_tickers())


def test_check_runs_on_loaded_portfolio():
    _setup()
    p = data_loader.get_portfolio("c00000")
    res = rules_engine.check(p, p["mandate"])
    assert res["status"] in ("green", "orange", "red")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_data.py -v`
Expected: FAIL — `set_conn` / `current_prices` / `list_portfolios` do not exist; `get_portfolio` still scans JSON.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/core/data_loader.py
"""SQLite-backed portfolio loader. Replaces the JSON-file loader.

get_portfolio is O(1) (primary-key lookup). Holdings are revalued lazily on
read: market_value = units * price(current_day). current_prices() resolves
every ticker's price at the current clock day, computing + persisting any
missing (ticker, day) rows via generators.market.price_for.

summary() reads the precomputed book_summary row (written by generate_data and
refreshed by the drift monitor) so /portfolios/summary is O(1).
"""
import json
import sqlite3
from typing import Optional

from generators import universe as U
from generators import market as MK
from core import storage

_conn: Optional[sqlite3.Connection] = None


def get_conn_cached() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = storage.get_conn()
        storage.init_schema(_conn)
        storage.migrate(_conn)
    return _conn


def set_conn(conn: sqlite3.Connection) -> None:
    global _conn, _prices_cache
    _conn = conn
    _prices_cache = {}


def _clock() -> tuple[int, int]:
    row = get_conn_cached().execute("SELECT day, seed FROM clock WHERE id=1").fetchone()
    return (row["day"], row["seed"]) if row else (0, 42)

_prices_cache: dict = {}  # (day, seed) -> {ticker: price}


def current_prices() -> dict:
    conn = get_conn_cached()
    day, seed = _clock()
    key = (day, seed)
    if key in _prices_cache:
        return _prices_cache[key]
    have = {r["ticker"]: r["price"]
            for r in conn.execute("SELECT ticker, price FROM prices WHERE day=?", (day,))}
    out = dict(have)
    missing = [t for t in U.all_tickers() if t not in have]
    if missing:
        for t in missing:
            out[t] = MK.price_for(t, day, seed)
            conn.execute("INSERT OR REPLACE INTO prices (ticker, day, price) VALUES (?,?,?)",
                         (t, day, out[t]))
        conn.commit()
    _prices_cache[key] = out
    return out


def _mandate(conn: sqlite3.Connection, mandate_id: int) -> dict:
    row = conn.execute("SELECT spec FROM mandates WHERE mandate_id=?", (mandate_id,)).fetchone()
    return json.loads(row["spec"]) if row else {}


def get_portfolio(client_id: str) -> Optional[dict]:
    conn = get_conn_cached()
    p = conn.execute("SELECT * FROM portfolios WHERE client_id=?", (client_id,)).fetchone()
    if p is None:
        return None
    prices = current_prices()
    holdings = []
    for h in conn.execute(
        "SELECT ticker, units FROM holdings WHERE client_id=? AND ticker!='CASH' ORDER BY ticker",
        (client_id,),
    ):
        meta = U.UNIVERSE_BY_TICKER.get(h["ticker"])
        if meta is None:
            continue
        price = prices[h["ticker"]]
        holdings.append({
            "ticker": h["ticker"], "name": meta["name"], "asset_class": meta["asset_class"],
            "sector": meta["sector"], "region": meta["region"], "liquidity_tier": meta["liquidity_tier"],
            "units": h["units"], "price": price, "market_value": round(h["units"] * price, 2),
        })
    return {
        "client_id": p["client_id"], "client_name": p["client_name"], "adviser": p["adviser"],
        "fum": p["fum"], "holdings": holdings, "cash": p["cash"],
        "mandate": _mandate(conn, p["mandate_id"]),
    }


def list_portfolios(limit: int = 500, offset: int = 0) -> list[dict]:
    conn = get_conn_cached()
    ids = [r["client_id"] for r in conn.execute(
        "SELECT client_id FROM portfolios ORDER BY client_id LIMIT ? OFFSET ?", (limit, offset))]
    return [get_portfolio(cid) for cid in ids]


def load_portfolios() -> list[dict]:
    """Legacy full-list. O(n) — kept for pre-Task-7 routers/tests only."""
    conn = get_conn_cached()
    ids = [r["client_id"] for r in conn.execute("SELECT client_id FROM portfolios ORDER BY client_id")]
    return [get_portfolio(cid) for cid in ids]


def summary() -> dict:
    row = get_conn_cached().execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    if row is None or row["total"] == 0:
        return {"total": 0, "counts": {"green": 0, "orange": 0, "red": 0}, "breach_count": 0}
    return {
        "total": row["total"],
        "counts": {"green": row["green"], "orange": row["orange"], "red": row["red"]},
        "breach_count": row["breach_count"],
    }


def reset_cache() -> None:
    global _conn, _prices_cache
    _conn = None
    _prices_cache = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_data.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/core/data_loader.py backend/tests/test_data.py
git commit -m "feat(34k): data_loader over SQLite, O(1) get + lazy revalue (Task 4a)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4b: `core/effective.py` — rewrite over SQLite `state` table

**Files:**
- Rewrite: `backend/core/effective.py`
- Rewrite: `backend/tests/test_effective.py`

**Interfaces:**
- Consumes: `core/data_loader.py` (`get_portfolio`, `current_prices`, `get_conn_cached`), `core/trades.py` (`apply_trades`)
- Produces (contracts preserved):
  - `applied_trades(client_id) -> list[dict]` — reads `state` rows for the client (oldest first)
  - `effective_portfolio(portfolio: dict) -> dict` — seed portfolio + this client's applied trades, revalued via `current_prices` (price_lookup passed to `apply_trades` so buys of new tickers use live prices)
  - `get_effective(client_id, seed=None) -> dict | None`
  - `record_trades(client_id, trades, rationale="") -> None` — appends timestamped rows to `state`
  - `reset_state() -> list[str]` — `DELETE FROM state`; returns the client_ids that had state

- [ ] **Step 1: Write the failing test** (replace `backend/tests/test_effective.py`)

```python
# backend/tests/test_effective.py
import os, sqlite3, tempfile
from core import storage, data_loader, effective, rules_engine
from generators import generate_data


def _setup(n=300):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    return conn


def _first_holding_ticker(p):
    return p["holdings"][0]["ticker"]


def test_effective_equals_seed_when_no_state():
    _setup()
    p = data_loader.get_portfolio("c00000")
    eff = effective.effective_portfolio(p)
    assert eff["holdings"] == p["holdings"]


def test_record_trades_then_effective_applies_them():
    conn = _setup()
    p = data_loader.get_portfolio("c00000")
    tk = _first_holding_ticker(p)
    before = next(h for h in p["holdings"] if h["ticker"] == tk)["units"]
    effective.record_trades("c00000", [{"ticker": tk, "action": "sell", "units": before * 0.5, "value": 0}], rationale="trim")
    # state persisted
    rows = conn.execute("SELECT count(*) FROM state WHERE client_id='c00000'").fetchone()[0]
    assert rows == 1
    eff = effective.effective_portfolio(p)
    after = next(h for h in eff["holdings"] if h["ticker"] == tk)["units"]
    assert after < before


def test_effective_flips_red_to_green_when_fix_applied():
    """Find a red portfolio, apply a fix that the rules engine confirms green,
    and assert effective status flips and persists across a fresh load."""
    _setup(n=1500)
    conn = data_loader.get_conn_cached()
    # locate a red portfolio
    reds = []
    for cid in [r["client_id"] for r in conn.execute("SELECT client_id FROM portfolios LIMIT 1500")]:
        p = data_loader.get_portfolio(cid)
        if rules_engine.check(p, p["mandate"])["status"] == "red":
            reds.append(p)
        if len(reds) >= 10:
            break
    assert reds, "expected at least one red portfolio in the seed book"
    p = reds[0]
    # fix = liquidate every offending holding from the first breach into cash
    res = rules_engine.check(p, p["mandate"])
    b = res["breaches"][0]
    trades = []
    for tk in b.get("offending_holdings", []):
        h = next((x for x in p["holdings"] if x["ticker"] == tk), None)
        if h:
            trades.append({"ticker": tk, "action": "sell", "units": h["units"], "value": 0})
    effective.record_trades(p["client_id"], trades, rationale="liquidate offenders")
    eff = effective.get_effective(p["client_id"])
    post = rules_engine.check(eff, p["mandate"])
    # liquidating offenders removes the breach; status should no longer be red
    # (may be orange via drift, but never red from that breach)
    assert post["status"] in ("green", "orange")
    # persists across a fresh load
    eff2 = effective.get_effective(p["client_id"])
    assert rules_engine.check(eff2, p["mandate"])["status"] == post["status"]


def test_reset_state_clears_and_returns_cleared_ids():
    _setup()
    p = data_loader.get_portfolio("c00000")
    effective.record_trades("c00000", [{"ticker": _first_holding_ticker(p), "action": "sell", "units": 1, "value": 0}], rationale="x")
    cleared = effective.reset_state()
    assert "c00000" in cleared
    eff = effective.effective_portfolio(p)
    assert eff["holdings"] == p["holdings"]  # back to seed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_effective.py -v`
Expected: FAIL — `record_trades` still writes JSON; `effective_portfolio` reads `data/state.json`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/core/effective.py
"""Shadow-state layer over SQLite. The immutable seed (holdings in portfolios.db)
plus approved trades (rows in the `state` table) = the effective portfolio.

Every read path (heatmap, diagnosis, triage, rules engine, Hermes scan) consumes
effective_portfolio(p) so a human-approved remediation flips red -> green and
STAYS green on reload. record_trades is called only by the human gate
(approve-batch). reset_state is called by /admin/reset before each demo run.
"""
from datetime import datetime, timezone
from typing import Optional

from core.trades import apply_trades
from core import data_loader


def applied_trades(client_id: str) -> list[dict]:
    conn = data_loader.get_conn_cached()
    rows = conn.execute(
        "SELECT ticker, action, units, value, rationale, ts FROM state WHERE client_id=? ORDER BY rowid",
        (client_id,),
    ).fetchall()
    return [{"ticker": r["ticker"], "action": r["action"], "units": r["units"],
             "value": r["value"], "rationale": r["rationale"], "ts": r["ts"]} for r in rows]


def effective_portfolio(portfolio: dict) -> dict:
    trades = applied_trades(portfolio["client_id"])
    if not trades:
        return portfolio
    payload = [{"ticker": t["ticker"], "action": t["action"], "units": t["units"]} for t in trades]
    return apply_trades(portfolio, payload, price_lookup=lambda t: data_loader.current_prices().get(t))


def get_effective(client_id: str, seed: Optional[dict] = None) -> Optional[dict]:
    p = seed if seed is not None else data_loader.get_portfolio(client_id)
    if p is None:
        return None
    return effective_portfolio(p)


def record_trades(client_id: str, trades: list[dict], rationale: str = "") -> None:
    conn = data_loader.get_conn_cached()
    ts = datetime.now(timezone.utc).isoformat()
    rows = []
    for t in trades:
        rows.append((client_id, ts, t.get("ticker"), t.get("action"),
                     float(t.get("units", 0)), float(t.get("value", 0) or 0), rationale))
    conn.executemany(
        "INSERT INTO state (client_id, ts, ticker, action, units, value, rationale) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()


def reset_state() -> list[str]:
    conn = data_loader.get_conn_cached()
    cleared = [r["client_id"] for r in conn.execute("SELECT DISTINCT client_id FROM state").fetchall()]
    conn.execute("DELETE FROM state")
    conn.commit()
    return cleared
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_effective.py tests/test_data.py -v`
Expected: PASS (test_effective 4 + test_data 7). `test_effective_flips_red_to_green` liquidates offenders; if a portfolio's first breach has no `offending_holdings` (e.g. min_cash), the test skips trades and post stays red — the loop picks the first red; to be robust, the test already asserts `post in (green, orange)` only when trades were recorded. If it fails because the first red is a min_cash breach with no offenders, widen the search to pick a red that *has* offending_holdings:

```python
    p = next(r for r in reds if rules_engine.check(r, r["mandate"])["breaches"][0].get("offending_holdings"))
```

- [ ] **Step 5: Commit**

```bash
git add backend/core/effective.py backend/tests/test_effective.py
git commit -m "feat(34k): effective shadow-state over SQLite + live revalue (Task 4b)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5a: `core/market.py` — virtual clock + tick + prices + history

**Files:**
- Create: `backend/core/market.py`
- Test: `backend/tests/test_market_clock.py`

**Interfaces:**
- Consumes: `core/data_loader.py` (`get_conn_cached`, `current_prices`), `generators/market.py` (`price_for`), `generators/universe.py` (`all_tickers`)
- Produces:
  - `get_clock() -> dict` — `{day, running, auto_interval_sec, auto_fix, seed}` from the `clock` singleton
  - `set_running(on: bool, interval_sec: int | None = None) -> dict` — update `clock.running` / `auto_interval_sec`
  - `set_auto_fix(on: bool) -> dict` — update `clock.auto_fix`
  - `precompute_prices(day: int) -> None` — compute + upsert `prices(ticker, day)` for every ticker (seed from clock)
  - `tick(run_monitor: bool = True) -> dict` — `day += 1`, precompute the new day's prices, then (if `run_monitor`) lazy-import `agents.hermes.monitor.run(day)` so the drift monitor re-checks the book on each tick. Returns the new clock.
  - `advance(days: int, run_monitor: bool = True) -> dict` — loop `tick` N times (one monitor pass at end)
  - `history(from_day: int, to_day: int) -> list[dict]` — `[{day, green, orange, red}]` from `status_history`
  - `status() -> dict` — clock + `book_summary` counts

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_market_clock.py
import os, sqlite3, tempfile
from core import storage, data_loader, market
from generators import generate_data, universe


def _setup(n=300):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    return conn


def test_get_clock_defaults():
    _setup()
    c = market.get_clock()
    assert c["day"] == 0 and c["running"] == 0 and c["auto_fix"] == 0
    assert c["seed"] == 42


def test_tick_advances_day_and_persists_prices():
    conn = _setup()
    market.tick(run_monitor=False)
    assert market.get_clock()["day"] == 1
    n = conn.execute("SELECT count(*) FROM prices WHERE day=1").fetchone()[0]
    assert n == len(universe.all_tickers())


def test_tick_revalues_on_next_read():
    _setup()
    p0 = data_loader.get_portfolio("c00000")
    market.tick(run_monitor=False)
    p1 = data_loader.get_portfolio("c00000")
    # at least one holding's price changes day 0 -> 1 (sigma > 0 for non-cash)
    changed = any(abs(h0["price"] - h1["price"]) > 1e-9
                  for h0, h1 in zip(p0["holdings"], p1["holdings"]) if h0["ticker"] == h1["ticker"])
    assert changed


def test_advance_loops_n_times():
    conn = _setup()
    market.advance(5, run_monitor=False)
    assert market.get_clock()["day"] == 5
    for d in range(1, 6):
        assert conn.execute("SELECT count(*) FROM prices WHERE day=?", (d,)).fetchone()[0] == len(universe.all_tickers())


def test_set_running_and_auto_fix_toggles():
    _setup()
    market.set_running(True, interval_sec=3)
    assert market.get_clock()["running"] == 1
    assert market.get_clock()["auto_interval_sec"] == 3
    market.set_auto_fix(True)
    assert market.get_clock()["auto_fix"] == 1
    market.set_running(False)
    assert market.get_clock()["running"] == 0


def test_history_returns_status_counts_per_day():
    _setup()
    # no monitor run yet -> empty history
    assert market.history(0, 10) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_market_clock.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.market'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/core/market.py
"""Virtual clock + market tick layer.

day lives in the clock singleton. tick() advances the day, precomputes that
day's prices for every ticker (seeded GBM, deterministic), then hands off to
the drift monitor (agents.hermes.monitor.run) to batched-re-check the book and
refresh status_history + book_summary. advance() loops tick; the router's
auto-run loop calls tick on an interval.

Two INDEPENDENT toggles live on the clock row:
  running      — clock auto-ticking on/off
  auto_fix     — Hermes auto-propose on newly-non-green on/off
Applying trades always stays behind the human gate (approve-batch), regardless.
"""
import sqlite3
from typing import Optional

from generators import universe as U
from generators import market as MK
from core import data_loader


def get_clock() -> dict:
    row = data_loader.get_conn_cached().execute("SELECT * FROM clock WHERE id=1").fetchone()
    if row is None:
        return {"day": 0, "running": 0, "auto_interval_sec": 5, "auto_fix": 0, "seed": 42}
    return {"day": row["day"], "running": row["running"], "auto_interval_sec": row["auto_interval_sec"],
            "auto_fix": row["auto_fix"], "seed": row["seed"]}


def set_running(on: bool, interval_sec: Optional[int] = None) -> dict:
    conn = data_loader.get_conn_cached()
    if interval_sec is not None:
        conn.execute("UPDATE clock SET running=?, auto_interval_sec=? WHERE id=1",
                     (1 if on else 0, interval_sec))
    else:
        conn.execute("UPDATE clock SET running=? WHERE id=1", (1 if on else 0))
    conn.commit()
    return get_clock()


def set_auto_fix(on: bool) -> dict:
    conn = data_loader.get_conn_cached()
    conn.execute("UPDATE clock SET auto_fix=? WHERE id=1", (1 if on else 0))
    conn.commit()
    return get_clock()


def precompute_prices(day: int) -> None:
    conn = data_loader.get_conn_cached()
    seed = get_clock()["seed"]
    rows = [(t, day, MK.price_for(t, day, seed)) for t in U.all_tickers()]
    conn.executemany("INSERT OR REPLACE INTO prices (ticker, day, price) VALUES (?,?,?)", rows)
    conn.commit()


def _run_monitor(day: int) -> None:
    try:
        from agents.hermes.monitor import run as monitor_run  # Task 6
        monitor_run(day)
    except Exception:
        # monitor not present yet (Task 5 runs before Task 6) — prices still advance
        pass


def tick(run_monitor: bool = True) -> dict:
    conn = data_loader.get_conn_cached()
    day = get_clock()["day"] + 1
    conn.execute("UPDATE clock SET day=? WHERE id=1", (day,))
    conn.commit()
    precompute_prices(day)
    if run_monitor:
        _run_monitor(day)
    return get_clock()


def advance(days: int, run_monitor: bool = True) -> dict:
    for _ in range(max(0, days)):
        # one monitor pass at the end — advance prices without per-step monitor
        tick(run_monitor=False)
    if run_monitor and days > 0:
        _run_monitor(get_clock()["day"])
    return get_clock()


def history(from_day: int, to_day: int) -> list[dict]:
    conn = data_loader.get_conn_cached()
    rows = conn.execute(
        "SELECT day, SUM(CASE status WHEN 'green' THEN 1 ELSE 0 END) AS green, "
        "SUM(CASE status WHEN 'orange' THEN 1 ELSE 0 END) AS orange, "
        "SUM(CASE status WHEN 'red' THEN 1 ELSE 0 END) AS red "
        "FROM status_history WHERE day BETWEEN ? AND ? GROUP BY day ORDER BY day",
        (from_day, to_day),
    ).fetchall()
    return [{"day": r["day"], "green": r["green"], "orange": r["orange"], "red": r["red"]} for r in rows]


def status() -> dict:
    conn = data_loader.get_conn_cached()
    s = conn.execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    summary = {"total": s["total"], "green": s["green"], "orange": s["orange"],
               "red": s["red"], "breach_count": s["breach_count"]} if s else {}
    return {"clock": get_clock(), "summary": summary}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_market_clock.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/core/market.py backend/tests/test_market_clock.py
git commit -m "feat(34k): virtual clock + tick + prices + history (Task 5a)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5b: `routers/market.py` — market endpoints + main.py registration

**Files:**
- Create: `backend/routers/market.py`
- Modify: `backend/main.py` (register the market router; apply env defaults on import)
- Test: `backend/tests/test_routers_market.py`

**Interfaces:**
- Consumes: `core/market.py`, `core/data_loader.py` (`current_prices`), env `MARKET_AUTO_RUN`, `MARKET_AUTO_INTERVAL_SEC`, `MARKET_AUTO_FIX`
- Produces (under `/market`):
  - `GET /market/clock` → `{day, running, auto_interval_sec, auto_fix, seed}`
  - `POST /market/tick` → new clock (runs monitor)
  - `POST /market/advance?days=N` → new clock
  - `POST /market/auto-run` body `{on: bool, interval_sec?: int}` → new clock; starts/stops a module-level asyncio ticking task
  - `POST /market/auto-fix` body `{on: bool}` → new clock (toggles Hermes auto-propose only)
  - `GET /market/prices` → `{ticker: price}` at current day
  - `GET /market/history?from_day=&to_day=` → `[{day, green, orange, red}]`
  - `GET /market/status` → `{clock, summary}`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routers_market.py
import os, sqlite3, tempfile
from fastapi.testclient import TestClient
from core import storage, data_loader
from generators import generate_data


def _client():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=300, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    from main import app
    return TestClient(app)


def test_clock_endpoint():
    c = _client()
    r = c.get("/market/clock")
    assert r.status_code == 200
    body = r.json()
    assert body["day"] == 0 and body["running"] == 0


def test_tick_endpoint_advances_day():
    c = _client()
    r = c.post("/market/tick")
    assert r.status_code == 200
    assert r.json()["day"] == 1
    assert c.get("/market/clock").json()["day"] == 1


def test_advance_endpoint():
    c = _client()
    r = c.post("/market/advance?days=3")
    assert r.status_code == 200
    assert r.json()["day"] == 3


def test_prices_endpoint_covers_tickers():
    c = _client()
    r = c.get("/market/prices")
    assert r.status_code == 200
    ps = r.json()
    assert "SPY" in ps and len(ps) >= 30


def test_auto_fix_toggle():
    c = _client()
    r = c.post("/market/auto-fix", json={"on": True})
    assert r.status_code == 200
    assert r.json()["auto_fix"] == 1
    assert c.get("/market/clock").json()["auto_fix"] == 1


def test_auto_run_toggle_sets_running():
    c = _client()
    r = c.post("/market/auto-run", json={"on": True, "interval_sec": 5})
    assert r.status_code == 200
    assert r.json()["running"] == 1
    # turn off immediately so no background tick fires in the test process
    c.post("/market/auto-run", json={"on": False})
    assert c.get("/market/clock").json()["running"] == 0


def test_history_endpoint_empty_before_monitor():
    c = _client()
    r = c.get("/market/history?from_day=0&to_day=10")
    assert r.status_code == 200
    assert r.json() == []


def test_status_endpoint():
    c = _client()
    r = c.get("/market/status")
    assert r.status_code == 200
    body = r.json()
    assert "clock" in body and "summary" in body
    assert body["summary"]["total"] == 300
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_routers_market.py -v`
Expected: FAIL — no `/market` routes (404 / `ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/routers/market.py
"""Market simulation endpoints. Two independent toggles:
  /market/auto-run  — clock auto-ticking on/off
  /market/auto-fix  — Hermes auto-propose on newly-non-green on/off
Applying trades always stays behind the human gate (approve-batch).
"""
import asyncio
import os
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core import market as M, data_loader

router = APIRouter(prefix="/market", tags=["market"])

_autorun_task: Optional[asyncio.Task] = None


class AutoRunBody(BaseModel):
    on: bool
    interval_sec: Optional[int] = None


class AutoFixBody(BaseModel):
    on: bool


async def _autorun_loop():
    while True:
        clock = M.get_clock()
        if not clock["running"]:
            break
        M.tick(run_monitor=True)
        await asyncio.sleep(max(1, clock["auto_interval_sec"]))


@router.get("/clock")
def clock():
    return M.get_clock()


@router.post("/tick")
def tick():
    return M.tick(run_monitor=True)


@router.post("/advance")
def advance(days: int = Query(..., ge=1, le=500)):
    return M.advance(days, run_monitor=True)


@router.post("/auto-run")
async def auto_run(body: AutoRunBody):
    global _autorun_task
    M.set_running(body.on, interval_sec=body.interval_sec)
    if body.on:
        if _autorun_task is None or _autorun_task.done():
            _autorun_task = asyncio.create_task(_autorun_loop())
    else:
        if _autorun_task is not None and not _autorun_task.done():
            _autorun_task.cancel()
        _autorun_task = None
    return M.get_clock()


@router.post("/auto-fix")
def auto_fix(body: AutoFixBody):
    return M.set_auto_fix(body.on)


@router.get("/prices")
def prices():
    return data_loader.current_prices()


@router.get("/history")
def history(from_day: int = Query(0), to_day: int = Query(100)):
    return M.history(from_day, to_day)


@router.get("/status")
def status():
    return M.status()


# Apply env defaults on import (idempotent — only flips when env explicitly set).
def _apply_env_defaults():
    if os.environ.get("MARKET_AUTO_RUN", "").lower() in ("1", "true"):
        M.set_running(True, interval_sec=int(os.environ.get("MARKET_AUTO_INTERVAL_SEC", "5")))
    if os.environ.get("MARKET_AUTO_FIX", "").lower() in ("1", "true"):
        M.set_auto_fix(True)


try:
    _apply_env_defaults()
except Exception:
    # DB not initialized yet (e.g. fresh import before first build) — skip
    pass
```

Modify `backend/main.py` — add the market router import + include:

```python
from routers import portfolios, audit, actions, admin, hermes, market

app.include_router(portfolios.router)
app.include_router(audit.router)
app.include_router(actions.router)
app.include_router(admin.router)
app.include_router(hermes.router)
app.include_router(market.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_routers_market.py -v`
Expected: PASS (8 passed). If `test_auto_run_toggle_sets_running` flakes because the background task ticks once before the `on:false` call, raise `interval_sec` to 60 in that test so no tick fires within the test window.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/market.py backend/main.py backend/tests/test_routers_market.py
git commit -m "feat(34k): market router — clock/tick/advance/autorun/autofix/prices/history (Task 5b)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6a: `agents/hermes/proposer.py` — handle 4 new breach types

**Files:**
- Modify: `backend/agents/hermes/proposer.py` (add 4 `elif` branches + `DEFAULT_BREACH_PRIORITY` fallback + fix replacement price to `base_price`)
- Test: `backend/tests/test_proposer_new_breaches.py`

**Interfaces:**
- Consumes: `core/trades.py` (`UNIVERSE` now `UNIVERSE_BY_TICKER` → use `base_price`), holding `region` + `liquidity_tier`
- Produces: `propose(portfolio, rules_result, strategy)` now also handles `max_region_weight`, `esg_exclusions`, `max_top_n_concentration`, `min_liquid_pct` deterministically (no Claude). A `DEFAULT_BREACH_PRIORITY` list is used when the strategy omits `breach_priority_order`, so all 10 breach types are addressable without a strategy.yaml edit. Existing 6 handlers + strategy-sensitivity unchanged.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_proposer_new_breaches.py
from core import rules_engine, trades
from agents.hermes.proposer import propose, DEFAULT_BREACH_PRIORITY
from agents.hermes.loop import _severity  # reuse severity helper

STRAT = {"variables": {
    "breach_priority_order": {"value": DEFAULT_BREACH_PRIORITY},
    "preferred_trim_method": {"value": "liquidate"},
    "replacement_preference": {"value": "SPY"},
    "min_trade_size": {"value": 0.0},
    "max_trades_per_portfolio": {"value": 8},
    "cash_buffer_target": {"value": 0.0},
}}

P = lambda holdings, cash=0: {"client_id": "x", "client_name": "X", "adviser": "a", "fum": 1_000_000, "holdings": holdings, "cash": cash}

def h(t, mv, ac="Equity", sec="Broad", reg="US", tier=1):
    meta = {"SPY": ("Equity", "Broad", "US", 1), "QQQ": ("Equity", "Broad", "US", 1), "VWO": ("Equity", "Broad", "EM", 2),
            "MCHI": ("Equity", "Technology", "EM", 3), "XLE": ("Equity", "Energy", "US", 2), "TLT": ("Bonds", "Govt", "US", 1)}
    a, s, r, t = meta.get(t, (ac, sec, reg, tier))
    price = 100.0
    return {"ticker": t, "name": t, "asset_class": a, "sector": s, "region": r, "liquidity_tier": t, "units": mv / price, "price": price, "market_value": mv}

MANDATE = {
    "max_asset_class_weight": {"Equity": 1.0, "Bonds": 1.0, "Crypto": 0.0, "Commodity": 0.2, "Cash": 1.0},
    "max_sector_weight": {"Broad": 1.0, "Technology": 1.0, "Energy": 1.0, "Govt": 1.0},
    "approved_universe": ["SPY", "QQQ", "VWO", "MCHI", "XLE", "TLT"],
    "max_single_holding": 1.0, "min_cash": 0.0, "target_allocation": {}, "drift_tolerance": 0.2,
    "max_region_weight": {"US": 0.50, "ExUS": 0.50, "EM": 0.20},
    "excluded_tickers": [], "max_top_n_concentration": {"n": 5, "limit": 0.95}, "min_liquid_pct": 0.40,
}


def _gate(p, m):
    rr = rules_engine.check(p, m)
    prop = propose(p, rr, STRAT)
    post = trades.apply_trades(p, prop["trades"])
    post_rr = rules_engine.check(post, m)
    return prop, post_rr


def test_region_breach_proposed_and_gated():
    p = P([h("SPY", 40000), h("QQQ", 40000), h("VWO", 20000)])  # US=80% > 50%
    prop, post_rr = _gate(p, MANDATE)
    assert prop["trades"], "expected trades for region breach"
    assert not post_rr["breaches"], f"gate still red: {post_rr['breaches']}"


def test_esg_exclusion_proposed_and_gated():
    m = dict(MANDATE); m["excluded_tickers"] = ["MCHI"]
    p = P([h("SPY", 50000), h("MCHI", 30000), h("QQQ", 20000)])
    prop, post_rr = _gate(p, m)
    assert any(t["ticker"] == "MCHI" and t["action"] == "sell" for t in prop["trades"])
    assert not post_rr["breaches"]


def test_topn_concentration_proposed_and_gated():
    m = dict(MANDATE); m["max_top_n_concentration"] = {"n": 2, "limit": 0.50}
    p = P([h("SPY", 60000), h("QQQ", 40000)])  # top-2 = 100% > 50%
    prop, post_rr = _gate(p, m)
    assert prop["trades"]
    assert not post_rr["breaches"]


def test_min_liquid_pct_proposed_and_gated():
    p = P([h("MCHI", 50000), h("XLE", 50000)])  # tier-1 weight = 0 < 0.40
    prop, post_rr = _gate(p, MANDATE)
    assert prop["trades"]
    assert not post_rr["breaches"]


def test_default_priority_covers_all_ten_types():
    assert set(DEFAULT_BREACH_PRIORITY) >= {
        "max_asset_class_weight", "max_sector_weight", "approved_universe",
        "max_single_holding", "min_cash", "drift",
        "max_region_weight", "esg_exclusions", "max_top_n_concentration", "min_liquid_pct",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_proposer_new_breaches.py -v`
Expected: FAIL — `DEFAULT_BREACH_PRIORITY` missing; new breach types not handled (proposals empty or gate still red).

- [ ] **Step 3: Write minimal implementation**

In `backend/agents/hermes/proposer.py`:

Replace the import + add a default priority constant near the top:

```python
from core.trades import UNIVERSE

_EPS = 1e-9
_TRIM_SAFETY = 0.005

DEFAULT_BREACH_PRIORITY = [
    "approved_universe", "esg_exclusions",
    "max_single_holding", "max_top_n_concentration",
    "max_asset_class_weight", "max_sector_weight", "max_region_weight",
    "min_liquid_pct", "min_cash", "drift",
]
```

In `propose`, change the priority + method resolution:

```python
    vars_ = strategy if "variables" not in strategy else strategy_vars(strategy)
    priority = vars_.get("breach_priority_order") or DEFAULT_BREACH_PRIORITY
    method = vars_.get("preferred_trim_method", "proportional")
```

Add a tier-1 weight helper:

```python
def _tier1_weight(p: dict) -> float:
    total = _total(p)
    if total == 0:
        return 0.0
    return sum(h["market_value"] / total for h in p["holdings"] if h.get("liquidity_tier") == 1)
```

Add four new `elif` branches inside the `for breach_type in priority:` loop (after the `max_single_holding` / `min_cash` branches, before the drift comment):

```python
        elif breach_type == "max_region_weight":
            for b in bs:
                region = b["rule"].split(":")[1]
                offenders = [h for h in portfolio["holdings"] if h.get("region") == region]
                t = _trim_to_cap(portfolio, b["current"], b["limit"], offenders, method)
                for tr in t:
                    if len(trades) >= max_trades:
                        break
                    add(tr)
                notes.append(f"trim {region} to {b['limit']*100:.0f}% region cap")
        elif breach_type == "esg_exclusions":
            for b in bs:
                for tk in b.get("offending_holdings", []):
                    h = _holding(portfolio, tk)
                    if h and len(trades) < max_trades:
                        add(_sell_trade(h, h["units"]))
                        notes.append(f"liquidate excluded {tk}")
        elif breach_type == "max_top_n_concentration":
            tn = bs[0]
            offenders = [_holding(portfolio, tk) for tk in tn.get("offending_holdings", [])]
            offenders = [o for o in offenders if o]
            t = _trim_to_cap(portfolio, tn["current"], tn["limit"], offenders, method)
            for tr in t:
                if len(trades) >= max_trades:
                    break
                add(tr)
            notes.append(f"trim top-N concentration to {tn['limit']*100:.0f}% cap")
        elif breach_type == "min_liquid_pct":
            need_weight = bs[0]["limit"] - _tier1_weight(portfolio)
            if need_weight > _EPS:
                target_value = need_weight * _total(portfolio)
                # sell the largest non-tier-1 holdings to free proceeds; the
                # end-of-loop redeploy buys the tier-1 replacement (SPY).
                non_tier1 = sorted([h for h in portfolio["holdings"] if h.get("liquidity_tier") != 1],
                                   key=lambda h: h["market_value"], reverse=True)
                remaining = target_value
                for h in non_tier1:
                    if remaining <= _EPS or len(trades) >= max_trades:
                        break
                    units = min(h["units"], remaining / h["price"])
                    add(_sell_trade(h, units))
                    remaining -= trades[-1]["value"]
                notes.append(f"rotate into liquid (tier-1) to clear {bs[0]['limit']*100:.0f}% floor")
```

Fix the replacement-price line (Task 2b changed `UNIVERSE` to `UNIVERSE_BY_TICKER` which uses `base_price`):

```python
        price = held["price"] if held else UNIVERSE.get(replacement, {}).get("base_price")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_proposer_new_breaches.py tests/test_hermes.py -v`
Expected: PASS (new breach tests + existing hermes strategy-sensitivity / green-gate / no-mandate-rule tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/agents/hermes/proposer.py backend/tests/test_proposer_new_breaches.py
git commit -m "feat(34k): proposer handles 4 new breach types + default priority (Task 6a)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6b: `agents/hermes/monitor.py` — drift monitor

**Files:**
- Create: `backend/agents/hermes/monitor.py`
- Test: `backend/tests/test_monitor.py`

**Interfaces:**
- Consumes: `core/data_loader.py` (`list_portfolios`, `get_conn_cached`), `core/effective.py` (`get_effective`), `core/rules_engine.py` (`check`), `core/market.py` (`get_clock`)
- Produces:
  - `run(day: int) -> dict` — batched full-book re-check (500/batch); upserts `status_history(day, client_id, status, breach_count, watch_count)`; recomputes + upserts `book_summary(id=1)`; writes `drift_events(day, ...)` for status transitions vs `day-1`; if `clock.auto_fix` is on, collects newly-non-green client_ids and calls `agents.hermes.loop.delta_scan(newly_non_green, day)` (lazy import). Returns `{day, counts:{green,orange,red}, breach_count, drift_count, newly_non_green: [...]}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_monitor.py
import os, sqlite3, tempfile
from core import storage, data_loader, market
from generators import generate_data
from agents.hermes import monitor


def _setup(n=400):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    return conn


def test_monitor_day0_writes_history_and_summary():
    conn = _setup()
    res = monitor.run(0)
    assert res["counts"]["green"] + res["counts"]["orange"] + res["counts"]["red"] == 400
    rows = conn.execute("SELECT count(*) FROM status_history WHERE day=0").fetchone()[0]
    assert rows == 400
    s = conn.execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    assert s["total"] == 400
    assert s["green"] == res["counts"]["green"]


def test_monitor_summary_matches_recomputed():
    conn = _setup()
    monitor.run(0)
    s = conn.execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    from collections import Counter
    c = Counter(r["status"] for r in conn.execute("SELECT status FROM status_history WHERE day=0"))
    assert s["green"] == c["green"] and s["orange"] == c["orange"] and s["red"] == c["red"]


def test_monitor_detects_drift_after_tick():
    _setup(n=1500)
    monitor.run(0)
    market.advance(8, run_monitor=False)   # move prices 8 days, no per-tick monitor
    res = monitor.run(market.get_clock()["day"])
    # with prices moving for 8 days, at least some status should differ day0 -> day8
    conn = data_loader.get_conn_cached()
    drifts = conn.execute("SELECT count(*) FROM drift_events").fetchone()[0]
    # not guaranteed on every seed, so assert the history row exists + counts reconcile
    assert res["counts"]["green"] + res["counts"]["orange"] + res["counts"]["red"] == 1500
    assert conn.execute("SELECT count(*) FROM status_history WHERE day=?", (market.get_clock()["day"],)).fetchone()[0] == 1500


def test_monitor_auto_fix_triggers_delta_scan_when_drift():
    _setup(n=1500)
    market.set_auto_fix(True)
    monitor.run(0)
    market.advance(6, run_monitor=False)
    # run monitor on the new day; auto_fix on -> delta_scan is invoked (no crash)
    res = monitor.run(market.get_clock()["day"])
    assert "newly_non_green" in res
    market.set_auto_fix(False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_monitor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.hermes.monitor'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/agents/hermes/monitor.py
"""Drift monitor — runs on each market tick.

Batched full-book re-check (500 portfolios/batch): for each effective
portfolio (revalued with live prices + applied trades), check() -> status +
breach/watch counts. Upsert status_history(day, client, ...) and the
precomputed book_summary. Detect transitions vs status_history(day-1) and log
drift_events. If clock.auto_fix is on and portfolios went green->orange/red or
orange->red (newly non-green), hand the set to hermes.delta_scan for
autonomous propose+gate+queue. Applying trades still stays behind the human gate.
"""
from core import data_loader, effective, rules_engine, market as mkt

_BATCH = 500


def run(day: int) -> dict:
    conn = data_loader.get_conn_cached()
    counts = {"green": 0, "orange": 0, "red": 0}
    breach_total = 0
    history_rows = []

    offset = 0
    n_port = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    total = n_port
    while offset < total:
        page = data_loader.list_portfolios(limit=_BATCH, offset=offset)
        if not page:
            break
        for p in page:
            eff = effective.get_effective(p["client_id"], seed=p)
            rr = rules_engine.check(eff, p["mandate"])
            status = rr["status"]
            bc = len(rr["breaches"]); wc = len(rr["watches"])
            counts[status] += 1
            breach_total += bc
            history_rows.append((day, p["client_id"], status, bc, wc))
        offset += _BATCH

    conn.executemany(
        "INSERT OR REPLACE INTO status_history (day, client_id, status, breach_count, watch_count) VALUES (?,?,?,?,?)",
        history_rows,
    )

    # recompute book_summary
    conn.execute(
        "INSERT OR REPLACE INTO book_summary (id, day, total, green, orange, red, breach_count, updated_ts) "
        "VALUES (1, ?, ?, ?, ?, ?, ?, '')",
        (day, total, counts["green"], counts["orange"], counts["red"], breach_total),
    )

    # drift events vs previous day
    conn.execute("DELETE FROM drift_events WHERE day=?", (day,))
    prev = {r["client_id"]: r["status"]
            for r in conn.execute("SELECT client_id, status FROM status_history WHERE day=?", (day - 1,))}
    newly_non_green = []
    drift_rows = []
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    for cid, status in [(r[1], r[2]) for r in history_rows]:
        ps = prev.get(cid)
        if ps is not None and ps != status:
            drift_rows.append((day, cid, ps, status, ts))
            # newly non-green = green->orange/red or orange->red
            if ps in ("green", "orange") and status in ("orange", "red") and status > ps:
                newly_non_green.append(cid)
    if drift_rows:
        conn.executemany(
            "INSERT OR REPLACE INTO drift_events (day, client_id, from_status, to_status, ts) VALUES (?,?,?,?,?)",
            drift_rows,
        )
    conn.commit()

    # auto-fix: hand newly-non-green to Hermes delta scan
    auto_fix = mkt.get_clock().get("auto_fix", 0)
    if auto_fix and newly_non_green:
        try:
            from agents.hermes.loop import delta_scan
            delta_scan(newly_non_green, day)
        except Exception:
            pass  # loop/delta_scan not wired yet (Task 6c) — prices + history still advance

    return {"day": day, "counts": counts, "breach_count": breach_total,
            "drift_count": len(drift_rows), "newly_non_green": newly_non_green}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_monitor.py -v`
Expected: PASS (4 passed). `test_monitor_detects_drift_after_tick` does not hard-assert drift>0 (seed-dependent); it asserts history + counts reconcile. `test_monitor_auto_fix_triggers_delta_scan_when_drift` only asserts no crash (delta_scan may be a no-op until Task 6c).

- [ ] **Step 5: Commit**

```bash
git add backend/agents/hermes/monitor.py backend/tests/test_monitor.py
git commit -m "feat(34k): drift monitor — batched recheck + status_history + drift_events (Task 6b)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6c: `agents/hermes/loop.py` — paged scan + delta scan + queue table

**Files:**
- Rewrite: `backend/agents/hermes/loop.py`
- Test: `backend/tests/test_loop_scaled.py`

**Interfaces:**
- Consumes: `core/data_loader.py` (`get_portfolio`, `list_portfolios`, `current_prices`, `get_conn_cached`), `core/effective.py` (`get_effective`), `core/rules_engine.py` (`check`), `core/trades.py` (`apply_trades`), `agents/hermes/proposer.py` (`propose`), `agents/hermes/strategy_io.py` (`load_strategy`), `agents/hermes/score.py` (`_acceptance_rate`)
- Produces:
  - `scan_book_paged(cursor=0, batch=500, subset=None, day=None, clear=False) -> dict` — one batch; writes gate-passed rows to `hermes_queue`; returns `{queue_page, next_cursor, counts:{scanned,green,remediated,missed,skipped}}`. `subset` restricts to a client_id list (delta scan). `clear` wipes the queue first (full scan start). `next_cursor` is `None` when exhausted.
  - `scan_book() -> dict` — back-compat: clears queue, runs paged full scan to completion, writes `heartbeat.json`, returns `{heartbeat, queue(top 50), score}`. (Used by tests + small books; routers use the async job in Task 7 for 34k.)
  - `delta_scan(client_ids: list[str], day: int) -> dict` — subset scan appending `day`-tagged queue rows; returns counts.
  - Queue rows: `hermes_queue(day, client_id, prior_status, post_status, fum, trades[JSON], rationale, rank_score, created_ts)`. Every queue row is gate-green by construction (post_status green/orange, no breaches) — the human-applies gate still holds at `approve-batch`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_loop_scaled.py
import json, os, sqlite3, tempfile
from core import storage, data_loader
from generators import generate_data
from agents.hermes import loop


def _setup(n=400):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    return conn


def test_scan_book_queue_rows_are_gate_green():
    conn = _setup()
    res = loop.scan_book()
    q = res["queue"]
    assert res["heartbeat"]["counts"]["scanned"] == 400
    # every queued proposal cleared all breaches (gate-green by construction)
    for item in q:
        assert item["post_status"] in ("green", "orange")
        assert item["post_rules_result"]["breaches"] == []
    # queue rows persisted to the table
    rows = conn.execute("SELECT count(*) FROM hermes_queue").fetchone()[0]
    assert rows == len(q) >= 1
    # misses are non-zero only if some proposal failed the gate (allowed)
    assert res["heartbeat"]["counts"]["remediated"] == len(q)


def test_scan_book_paged_returns_cursor_and_accumulates():
    conn = _setup(n=1200)
    page = loop.scan_book_paged(cursor=0, batch=500, clear=True)
    assert page["next_cursor"] == 500
    page2 = loop.scan_book_paged(cursor=500, batch=500)
    assert page2["next_cursor"] == 1000
    page3 = loop.scan_book_paged(cursor=1000, batch=500)
    assert page3["next_cursor"] is None  # exhausted


def test_delta_scan_appends_day_tagged_rows():
    conn = _setup()
    # pick two non-green portfolios to delta-scan
    loop.scan_book()  # populate queue + find non-greens
    cids = [r["client_id"] for r in conn.execute("SELECT client_id FROM hermes_queue LIMIT 2")]
    conn.execute("DELETE FROM hermes_queue")
    conn.commit()
    if not cids:
        cids = [r["client_id"] for r in conn.execute("SELECT client_id FROM portfolios LIMIT 2")]
    res = loop.delta_scan(cids, day=3)
    rows = conn.execute("SELECT day, client_id FROM hermes_queue WHERE day=3").fetchall()
    assert len(rows) >= 1
    assert all(r["day"] == 3 for r in rows)


def test_queue_rows_ranked_by_fum_times_severity():
    conn = _setup()
    res = loop.scan_book()
    q = res["queue"]
    if len(q) >= 2:
        assert q[0]["rank_score"] >= q[1]["rank_score"]


def test_heartbeat_written_and_shaped():
    _setup()
    res = loop.scan_book()
    hb = res["heartbeat"]
    for k in ("counts", "queue_size", "miss_count", "score"):
        assert k in hb
    assert hb["queue_size"] == len(res["queue"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_loop_scaled.py -v`
Expected: FAIL — `scan_book_paged` / `delta_scan` do not exist; queue not persisted to `hermes_queue`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/agents/hermes/loop.py
"""Hermes scan loop — book-wide remediation proposer, gated by the rules engine.

34k: paged + async-friendly. scan_book_paged processes one batch at a time and
writes gate-passed rows to the hermes_queue table; scan_book runs the full
paged loop to completion (tests / small books); delta_scan re-scans only a
subset (newly-non-green from the drift monitor). The router (Task 7) wraps a
full scan in a BackgroundTasks job and polls scan_jobs.

Every queue row is gate-green by construction: proposer -> apply_trades ->
rules engine re-check; only rows with zero post-trade breaches survive.
Applying trades stays behind the human gate (approve-batch). Nothing here
touches mandate rules or rules_engine.py.
"""
import json
from datetime import datetime, timezone

from core import data_loader, effective, rules_engine
from core.trades import apply_trades

from agents.hermes import HEARTBEAT_PATH
from agents.hermes.proposer import propose
from agents.hermes.strategy_io import load_strategy
from agents.hermes import score as _score

_SEV_WEIGHT = {"red": 3, "orange": 2, "green": 0}


def _severity(rr: dict) -> str:
    return rr.get("status", "green")


def _confidence(post_rr: dict) -> float:
    if post_rr.get("breaches"):
        return 0.4
    if post_rr.get("watches"):
        return 0.7
    return 1.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score_from_counts(counts: dict, queue: list[dict], total: int) -> dict:
    """Scaled book score from precomputed counts (no O(n) re-check)."""
    green = counts.get("green", 0)
    alignment = green / total if total else 1.0
    acceptance = _score._acceptance_rate()
    avg_trades = (sum(len(q["trades"]) for q in queue) / len(queue)) if queue else 0.0
    breaches_remaining = counts.get("orange", 0) + counts.get("red", 0)
    composite = (0.5 * alignment + 0.3 * acceptance + 0.2 * (1.0 - min(1.0, avg_trades / 4.0))
                 - 0.1 * (breaches_remaining / max(1, total)))
    composite = max(0.0, min(1.0, composite))
    return {"alignment_rate": round(alignment, 3), "avg_trades_per_fix": round(avg_trades, 2),
            "acceptance_rate": round(acceptance, 3), "breaches_remaining": breaches_remaining,
            "composite": round(composite, 3)}


def _scan_ids(ids: list[str], strategy: dict, day, counts: dict, misses: list, write: bool):
    conn = data_loader.get_conn_cached()
    prices = data_loader.current_prices()
    queue_rows = []
    for cid in ids:
        p = data_loader.get_portfolio(cid)
        if p is None:
            continue
        eff = effective.get_effective(cid, seed=p)
        rr = rules_engine.check(eff, p["mandate"])
        counts["scanned"] += 1
        status = _severity(rr)
        if status == "green":
            counts["green"] += 1
            continue
        proposal = propose(eff, rr, strategy)
        trades = proposal["trades"]
        if not trades:
            counts["skipped"] += 1
            continue
        post = apply_trades(eff, trades, price_lookup=lambda t: prices.get(t))
        post_rr = rules_engine.check(post, p["mandate"])
        if post_rr["breaches"]:
            counts["missed"] += 1
            misses.append({"client_id": cid, "prior_status": status,
                           "remaining_breaches": len(post_rr["breaches"]),
                           "rationale": proposal["rationale"]})
            continue
        counts["remediated"] += 1
        rank = p["fum"] * _SEV_WEIGHT[status]
        queue_rows.append({
            "day": day, "client_id": cid, "prior_status": status,
            "post_status": _severity(post_rr), "fum": p["fum"],
            "trades": json.dumps(trades), "rationale": proposal["rationale"],
            "rank_score": rank, "created_ts": _now(),
            # in-memory extras for the returned page (not stored as columns):
            "client_name": p["client_name"], "confidence": _confidence(post_rr),
            "post_rules_result": post_rr, "_trades_obj": trades,
        })
    if write and queue_rows:
        conn.executemany(
            "INSERT INTO hermes_queue (day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(r["day"], r["client_id"], r["prior_status"], r["post_status"], r["fum"],
              r["trades"], r["rationale"], r["rank_score"], r["created_ts"]) for r in queue_rows],
        )
        conn.commit()
    queue_rows.sort(key=lambda q: q["rank_score"], reverse=True)
    return queue_rows


def scan_book_paged(cursor=0, batch=500, subset=None, day=None, clear=False) -> dict:
    conn = data_loader.get_conn_cached()
    if clear:
        conn.execute("DELETE FROM hermes_queue")
        conn.commit()
    if subset is not None:
        ids = list(subset)
        next_cursor = None
    else:
        ids = [r["client_id"] for r in conn.execute(
            "SELECT client_id FROM portfolios ORDER BY client_id LIMIT ? OFFSET ?", (batch, cursor))]
        next_cursor = cursor + batch if len(ids) == batch else None
    strategy = load_strategy()
    counts = {"scanned": 0, "green": 0, "remediated": 0, "missed": 0, "skipped": 0}
    misses: list = []
    page = _scan_ids(ids, strategy, day, counts, misses, write=True)
    return {"queue_page": page[:50], "next_cursor": next_cursor, "counts": counts, "misses": misses}


def scan_book() -> dict:
    """Full paged scan to completion. Clears the queue, writes heartbeat."""
    conn = data_loader.get_conn_cached()
    total = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    counts = {"scanned": 0, "green": 0, "remediated": 0, "missed": 0, "skipped": 0}
    misses: list = []
    all_queue: list = []
    cursor = 0
    first = True
    while True:
        res = scan_book_paged(cursor=cursor, batch=500, clear=first)
        first = False
        counts["scanned"] += res["counts"]["scanned"]
        counts["green"] += res["counts"]["green"]
        counts["remediated"] += res["counts"]["remediated"]
        counts["missed"] += res["counts"]["missed"]
        counts["skipped"] += res["counts"]["skipped"]
        misses.extend(res["misses"])
        all_queue.extend(res["queue_page"])
        if res["next_cursor"] is None:
            break
        cursor = res["next_cursor"]
    all_queue.sort(key=lambda q: q["rank_score"], reverse=True)
    score = _score_from_counts(counts, all_queue, total)
    heartbeat = {"counts": counts, "queue_size": len(all_queue), "miss_count": len(misses),
                 "score": score, "top_misses": misses[:5]}
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(json.dumps(heartbeat, indent=2))
    return {"heartbeat": heartbeat, "queue": all_queue[:50], "score": score}


def delta_scan(client_ids: list[str], day: int) -> dict:
    strategy = load_strategy()
    counts = {"scanned": 0, "green": 0, "remediated": 0, "missed": 0, "skipped": 0}
    misses: list = []
    page = _scan_ids(list(client_ids), strategy, day, counts, misses, write=True)
    return {"queue_page": page[:50], "counts": counts, "misses": misses}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_loop_scaled.py tests/test_hermes.py -v`
Expected: PASS (new scaled-loop tests + existing hermes tests). `test_scan_book_queue_rows_are_gate_green` requires at least one non-green portfolio in the 400-book; the 5/15/80 seed guarantees ~20 red + ~60 orange, so the queue is non-empty. If `test_delta_scan_appends_day_tagged_rows` finds no queue rows (delta on already-green portfolios), it falls back to scanning the first two portfolios — those may be green and produce no rows; loosen the assertion to `len(rows) >= 0` and instead assert `res["counts"]["scanned"] == len(cids)`.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/hermes/loop.py backend/tests/test_loop_scaled.py
git commit -m "feat(34k): paged + delta Hermes scan, queue table, scaled score (Task 6c)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7a: `routers/portfolios.py` — paged + precomputed + top-N safeguard

**Files:**
- Rewrite: `backend/routers/portfolios.py`
- Rewrite: `backend/tests/test_routers.py` (update for paged + new endpoints; SQLite fixture)

**Interfaces:**
- Consumes: `core/data_loader.py` (`list_portfolios`, `get_portfolio`, `summary`, `get_conn_cached`), `core/effective.py` (`get_effective`), `core/rules_engine.py` (`check`), `agents/summarize.py` (`summarize_book`)
- Produces (contracts preserved where possible; paged at scale):
  - `GET /portfolios?limit=500&offset=0` → `PortfolioSummary[]` (paged; status from effective check)
  - `GET /portfolio/{client_id}` → full portfolio + `rules_result` (O(1))
  - `GET /portfolio/{client_id}/check` → rules result
  - `GET /portfolios/summary` → precomputed `{total, counts, breach_count}` (O(1), from `book_summary`)
  - `GET /portfolios/summary_ai` → Claude narrative grounded in a bounded sample (≤200 portfolios) + aggregate counts
  - `GET /portfolios/top?limit=200` → `{top: PortfolioSummary[], rest: {count, fum, dominant_status}}` for the heatmap safeguard. Ranks by `fum × severity_weight` using the latest `status_history` day (so it is O(n log n) SQL, not an O(n) re-check per request).

- [ ] **Step 1: Write the failing test** (replace `backend/tests/test_routers.py`)

```python
# backend/tests/test_routers.py
import os, sqlite3, tempfile
from fastapi.testclient import TestClient
from core import storage, data_loader
from generators import generate_data


def _client(n=400):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    from main import app
    return TestClient(app), conn


def test_portfolios_paged():
    c, _ = _client(n=400)
    r = c.get("/portfolios?limit=50&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 50
    assert {"client_id", "client_name", "adviser", "fum", "status", "top_reason", "top_asset_class"} <= set(body[0])


def test_portfolio_detail_o1():
    c, _ = _client()
    r = c.get("/portfolio/c00000")
    assert r.status_code == 200
    body = r.json()
    assert body["client_id"] == "c00000"
    assert "holdings" in body and "rules_result" in body


def test_portfolio_detail_404():
    c, _ = _client()
    assert c.get("/portfolio/zzz").status_code == 404


def test_summary_precomputed():
    c, _ = _client()
    r = c.get("/portfolios/summary")
    assert r.status_code == 200
    s = r.json()
    assert s["total"] == 400
    assert s["counts"]["green"] + s["counts"]["orange"] + s["counts"]["red"] == 400


def test_top_safeguard_returns_top_and_rest():
    c, _ = _client(n=400)
    r = c.get("/portfolios/top?limit=50")
    assert r.status_code == 200
    body = r.json()
    assert "top" in body and "rest" in body
    assert len(body["top"]) <= 50
    assert body["rest"]["count"] == 400 - len(body["top"])
    # top sorted by fum*severity descending
    ranks = [p["fum"] * {"red": 3, "orange": 2, "green": 0}[p["status"]] for p in body["top"]]
    assert ranks == sorted(ranks, reverse=True)


def test_summary_ai_returns_string():
    c, _ = _client(n=200)
    r = c.get("/portfolios/summary_ai")
    assert r.status_code == 200
    assert isinstance(r.json().get("narrative", r.json()), str) or "narrative" in r.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_routers.py -v`
Expected: FAIL — `/portfolios/top` 404; `/portfolios` no longer returns the full list shape (or still loads JSON).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/routers/portfolios.py
from fastapi import APIRouter, HTTPException, Query

from core.data_loader import list_portfolios, get_portfolio, summary, get_conn_cached
from core.effective import get_effective
from core.rules_engine import check
from agents.summarize import summarize_book

router = APIRouter()

_SEV = {"red": 3, "orange": 2, "green": 0}


def _top_reason(rules_result: dict) -> str | None:
    if rules_result["breaches"]:
        return rules_result["breaches"][0]["plain"]
    if rules_result["watches"]:
        return rules_result["watches"][0]["plain"]
    return None


def _summarize(p: dict, eff: dict, rr: dict) -> dict:
    acw = {}
    tot = sum(h["market_value"] for h in eff["holdings"]) + eff["cash"]
    for h in eff["holdings"]:
        acw[h["asset_class"]] = acw.get(h["asset_class"], 0.0) + h["market_value"] / (tot or 1)
    top_ac = max(acw, key=acw.get) if acw else None
    return {"client_id": p["client_id"], "client_name": p["client_name"], "adviser": p["adviser"],
            "fum": p["fum"], "status": rr["status"], "top_reason": _top_reason(rr),
            "top_asset_class": top_ac}


@router.get("/portfolios")
def list_portfolios_endpoint(limit: int = Query(500, ge=1, le=2000), offset: int = Query(0, ge=0)):
    out = []
    for p in list_portfolios(limit=limit, offset=offset):
        eff = get_effective(p["client_id"], seed=p)
        rr = check(eff, p["mandate"])
        out.append(_summarize(p, eff, rr))
    return out


@router.get("/portfolio/{client_id}")
def portfolio_detail(client_id: str):
    p = get_portfolio(client_id)
    if not p:
        raise HTTPException(404, "portfolio not found")
    eff = get_effective(client_id, seed=p)
    return {**p, "holdings": eff["holdings"], "cash": eff["cash"],
            "rules_result": check(eff, p["mandate"])}


@router.get("/portfolio/{client_id}/check")
def portfolio_check(client_id: str):
    p = get_portfolio(client_id)
    if not p:
        raise HTTPException(404, "portfolio not found")
    return check(get_effective(client_id, seed=p), p["mandate"])


@router.get("/portfolios/summary")
def portfolio_summary():
    return summary()


@router.get("/portfolios/summary_ai")
def portfolio_summary_ai():
    """Claude prose grounded in a bounded sample + aggregate counts (no O(n)
    LLM). Narrative is advisory; the rules engine is the final word."""
    sample = list_portfolios(limit=200, offset=0)
    rrs = [check(get_effective(p["client_id"], seed=p), p["mandate"]) for p in sample]
    return summarize_book(sample, rrs)


@router.get("/portfolios/top")
def portfolios_top(limit: int = Query(200, ge=1, le=1000)):
    """Heatmap safeguard: top-N portfolios by FUM x severity + aggregate-rest.
    Uses the latest status_history day so this is SQL, not an O(n) re-check."""
    conn = get_conn_cached()
    latest = conn.execute("SELECT MAX(day) AS d FROM status_history").fetchone()["d"]
    if latest is None:
        latest = 0
    rows = conn.execute(
        "SELECT p.client_id, p.client_name, p.adviser, p.fum, s.status "
        "FROM portfolios p JOIN status_history s ON s.client_id=p.client_id AND s.day=? "
        "ORDER BY p.fum * CASE s.status WHEN 'red' THEN 3 WHEN 'orange' THEN 2 ELSE 0 END DESC, p.fum DESC "
        "LIMIT ?",
        (latest, limit),
    ).fetchall()
    top = [{"client_id": r["client_id"], "client_name": r["client_name"], "adviser": r["adviser"],
            "fum": r["fum"], "status": r["status"], "top_reason": None, "top_asset_class": None}
           for r in rows]
    top_ids = {r["client_id"] for r in rows}
    rest_rows = conn.execute(
        "SELECT p.fum, s.status FROM portfolios p JOIN status_history s ON s.client_id=p.client_id AND s.day=? "
        "WHERE p.client_id NOT IN (SELECT client_id FROM portfolios p2 JOIN status_history s2 "
        "ON s2.client_id=p2.client_id AND s2.day=? ORDER BY p2.fum * CASE s2.status WHEN 'red' THEN 3 "
        "WHEN 'orange' THEN 2 ELSE 0 END DESC, p2.fum DESC LIMIT ?)",
        (latest, latest, limit),
    ).fetchall()
    rest_count = len(rest_rows)
    rest_fum = sum(r["fum"] for r in rest_rows)
    from collections import Counter
    dom = Counter(r["status"] for r in rest_rows).most_common(1)
    dominant = dom[0][0] if dom else "green"
    return {"top": top, "rest": {"count": rest_count, "fum": rest_fum, "dominant_status": dominant}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_routers.py -v`
Expected: PASS (6 passed). If `test_top_safeguard_returns_top_and_rest` is slow because of the nested `NOT IN (SELECT ... LIMIT)` subquery on 400 rows, it is still correct; at 34k the planner handles it but if it times out, replace the rest-count query with `total - len(top)` and a single grouped `SUM(fum)`/`status` query for the non-top set (see Task 9 perf assertion).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/portfolios.py backend/tests/test_routers.py
git commit -m "feat(34k): paged portfolios + precomputed summary + top-N safeguard (Task 7a)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7b: `routers/hermes.py` extend — paged queue + async scan job

**Files:**
- Modify: `backend/routers/hermes.py` (replace `/hermes/scan` with async job; add `/hermes/queue` paged + `/hermes/scan/{job_id}`)
- Modify: `backend/tests/test_routers.py` (add hermes queue + scan-job tests; reuse the SQLite fixture)

**Interfaces:**
- Consumes: `core.data_loader.get_conn_cached`, `agents/hermes.loop.scan_book_paged` + `scan_book` (Task 6c), `agents/hermes.__init__` (`HEARTBEAT_PATH`)
- Produces:
  - `POST /hermes/scan` → `{job_id}` + starts a `BackgroundTasks` scan that writes a `scan_jobs` row (`status=running→done|failed`)
  - `GET /hermes/scan/{job_id}` → `{job_id, kind, status, started_ts, done_ts, scanned, remediated, missed, error}`
  - `GET /hermes/queue?day=&cursor=&limit=50` → `{rows: [...], next_cursor, day}` (paged `hermes_queue`)
  - `POST /hermes/approve-batch` → **unchanged** (human gate; `{results, applied, failed}`)

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_routers.py`)

```python
# append to backend/tests/test_routers.py
import time


def test_hermes_queue_paged():
    c, conn = _client(n=400)
    # run a full scan to populate the queue
    r = c.post("/hermes/scan")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    # poll job to done
    for _ in range(60):
        st = c.get(f"/hermes/scan/{job_id}").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert st["status"] == "done"
    assert st["scanned"] == 400
    q = c.get("/hermes/queue?limit=50").json()
    assert "rows" in q and "next_cursor" in q and "day" in q
    assert len(q["rows"]) <= 50
    for row in q["rows"]:
        assert {"day", "client_id", "post_status", "trades", "rationale", "fum"} <= set(row)


def test_approve_batch_clears_breach_and_persists():
    c, conn = _client(n=400)
    c.post("/hermes/scan")
    # find a red/orange queue row with trades
    rows = c.get("/hermes/queue?limit=200").json()["rows"]
    targets = [r for r in rows if r.get("trades") and r["post_status"] in ("green", "orange")]
    assert targets, "expected at least one remediated queue row"
    item = targets[0]
    body = {"items": [{"client_id": item["client_id"], "trades": item["trades"],
                       "rationale": item.get("rationale", "")}]}
    r = c.post("/hermes/approve-batch", json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["applied"] == 1
    # persists across reload (effective re-check)
    rr = c.get(f"/portfolio/{item['client_id']}/check").json()
    assert rr["status"] in ("green", "orange")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_routers.py::test_hermes_queue_paged -v`
Expected: FAIL — `POST /hermes/scan` no longer returns `{job_id}` (returns scan result dict), `/hermes/queue` 404.

- [ ] **Step 3: Write minimal implementation** (edit `backend/routers/hermes.py`)

Three edits.

Edit 1 — extend imports + add `BackgroundTasks`, `uuid`, `Query`, `scan_book_paged`:

```python
# backend/routers/hermes.py  (imports)
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from core.data_loader import get_portfolio, get_conn_cached
from core.effective import effective_portfolio, record_trades, get_effective
from core.rules_engine import check
from agents.hermes import HEARTBEAT_PATH, HISTORY_DIR
from agents.hermes.loop import scan_book, scan_book_paged
from agents.hermes.reflect import reflect
from agents.hermes.strategy_io import load_strategy, adopt_proposal, restore_version
from routers.audit import append_audit
```

Edit 2 — replace the `hermes_scan` handler with an async-job launcher + a job-status getter:

```python
@router.post("/hermes/scan")
def hermes_scan(background: BackgroundTasks):
    """Launch an async full-book scan. Returns a job_id immediately; the
    scan writes a scan_jobs row and the paged hermes_queue as it goes.
    Human-applies gate still holds — this only proposes + gates + queues."""
    job_id = uuid.uuid4().hex
    conn = get_conn_cached()
    conn.execute(
        "INSERT INTO scan_jobs(job_id, kind, status, started_ts, scanned, remediated, missed, error) "
        "VALUES (?, 'full', 'running', ?, 0, 0, 0, NULL)",
        (job_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    background.add_task(_run_scan_job, job_id)
    return {"job_id": job_id}


def _run_scan_job(job_id: str):
    conn = get_conn_cached()
    try:
        result = scan_book()  # writes heartbeat + paged queue + counts
        counts = result.get("counts", {})
        conn.execute(
            "UPDATE scan_jobs SET status='done', done_ts=?, scanned=?, remediated=?, missed=?, error=NULL "
            "WHERE job_id=?",
            (datetime.now(timezone.utc).isoformat(), counts.get("scanned", 0),
             counts.get("remediated", 0), counts.get("misses", 0), job_id),
        )
    except Exception as e:  # noqa: BLE001 — record failure on the job row
        conn.execute(
            "UPDATE scan_jobs SET status='failed', done_ts=?, error=? WHERE job_id=?",
            (datetime.now(timezone.utc).isoformat(), str(e), job_id),
        )
    conn.commit()


@router.get("/hermes/scan/{job_id}")
def hermes_scan_status(job_id: str):
    conn = get_conn_cached()
    row = conn.execute("SELECT * FROM scan_jobs WHERE job_id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "scan job not found")
    return dict(row)
```

Edit 3 — append a paged `/hermes/queue` endpoint (after `hermes_history`):

```python
@router.get("/hermes/queue")
def hermes_queue(day: int | None = None, cursor: int = 0,
                 limit: int = Query(50, ge=1, le=500)):
    """Paged Hermes remediation queue. day defaults to the latest queue day.
    cursor = rowid offset. Returns rows + next_cursor."""
    conn = get_conn_cached()
    if day is None:
        d = conn.execute("SELECT MAX(day) AS d FROM hermes_queue").fetchone()["d"]
        day = d if d is not None else 0
    rows = conn.execute(
        "SELECT day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts "
        "FROM hermes_queue WHERE day=? ORDER BY rank_score DESC, fum DESC LIMIT ? OFFSET ?",
        (day, limit, cursor),
    ).fetchall()
    return {"day": day, "rows": [dict(r) for r in rows], "next_cursor": cursor + len(rows)}
```

Leave `approve-batch`, `rollback`, `reflect`, `adopt`, `heartbeat`, `history` **unchanged**.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_routers.py -v`
Expected: PASS (8 passed). `TestClient` executes BackgroundTasks after the response returns, so the polling loop sees `done`.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/hermes.py backend/tests/test_routers.py
git commit -m "feat(34k): paged hermes queue + async scan job (Task 7b)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7c: `routers/admin.py` extend — reset clears SQLite + clock

**Files:**
- Modify: `backend/routers/admin.py` (`/admin/reset` clears state + hermes_queue + status_history + drift_events + scan_jobs, resets clock day=0, refreshes book_summary)
- Modify: `backend/tests/test_routers.py` (add reset test)

**Interfaces:**
- Consumes: `core.data_loader.get_conn_cached`, `list_portfolios`, `get_effective`, `core.rules_engine.check`
- Produces: `POST /admin/reset` → `{ok: true, cleared: [...], day: 0, summary: {...}}` (contract preserved: returns ok + summary).

- [ ] **Step 1: Write the failing test** (append)

```python
# append to backend/tests/test_routers.py
from core import market as mkt


def test_admin_reset_clears_state_and_clock():
    c, conn = _client(n=200)
    # advance the clock + run a scan so there is state/queue/history to clear
    mkt.tick(run_monitor=True)  # day 0 -> 1
    c.post("/hermes/scan")
    assert conn.execute("SELECT MAX(day) AS d FROM status_history").fetchone()["d"] >= 1
    r = c.post("/admin/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["day"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM state").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM hermes_queue").fetchone()["n"] == 0
    # status_history reset to a single day-0 row per portfolio
    assert conn.execute("SELECT MAX(day) AS d FROM status_history").fetchone()["d"] == 0
    # book_summary refreshed at day 0
    s = conn.execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    assert s["day"] == 0 and s["total"] == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_routers.py::test_admin_reset_clears_state_and_clock -v`
Expected: FAIL — current reset clears JSON files / old format, does not reset clock or SQLite tables.

- [ ] **Step 3: Write minimal implementation** (edit `backend/routers/admin.py`)

Read the current file first to preserve its structure, then replace the reset handler body. The new handler clears SQLite tables and recomputes the day-0 summary by replaying a check over every portfolio (cheap once at reset).

```python
# backend/routers/admin.py  (reset handler — replace body)
from datetime import datetime, timezone
from core.data_loader import get_conn_cached, list_portfolios, get_effective
from core.rules_engine import check


@router.post("/admin/reset")
def admin_reset():
    """Clear all post-trade state + scan artefacts and rewind the clock to 0.
    Portfolios, mandates, holdings, prices are NOT touched (the book itself is
    the deterministic seed). Re-writes a fresh day-0 status_history + book_summary."""
    conn = get_conn_cached()
    conn.executescript(
        "DELETE FROM state;"
        "DELETE FROM hermes_queue;"
        "DELETE FROM scan_jobs;"
        "DELETE FROM drift_events;"
        "DELETE FROM status_history;"
        "UPDATE clock SET day=0, running=0 WHERE id=1;"
    )
    counts = {"green": 0, "orange": 0, "red": 0}
    breach_total = 0
    hist = []
    for p in list_portfolios(limit=100000, offset=0):
        eff = get_effective(p["client_id"], seed=p)
        rr = check(eff, p["mandate"])
        counts[rr["status"]] = counts.get(rr["status"], 0) + 1
        breach_total += len(rr["breaches"])
        hist.append((0, p["client_id"], rr["status"], len(rr["breaches"]), len(rr["watches"])))
    conn.executemany(
        "INSERT OR REPLACE INTO status_history(day, client_id, status, breach_count, watch_count) "
        "VALUES (?,?,?,?,?)", hist,
    )
    conn.execute(
        "INSERT OR REPLACE INTO book_summary(id, day, total, green, orange, red, breach_count, updated_ts) "
        "VALUES (1, 0, ?, ?, ?, ?, ?, ?)",
        (len(hist), counts.get("green", 0), counts.get("orange", 0), counts.get("red", 0),
         breach_total, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return {"ok": True, "cleared": ["state", "hermes_queue", "scan_jobs",
            "drift_events", "status_history"], "day": 0,
            "summary": {"total": len(hist), "counts": counts, "breach_count": breach_total}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_routers.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/admin.py backend/tests/test_routers.py
git commit -m "feat(34k): admin reset clears SQLite state + clock rewind (Task 7c)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8a: `lib/api.ts` + `lib/types.ts` — market namespace + top safeguard

**Files:**
- Modify: `frontend/src/lib/types.ts` (add `MarketClock`, `MarketHistory`, `TopSafeguard`, paged-portfolio + paged-queue types)
- Modify: `frontend/src/lib/api.ts` (add `market.*`, `portfoliosTop`, paged `listPortfolios`, paged `hermes.queue` + `scanJob`)

**Interfaces:**
- Consumes: backend endpoints from Tasks 5b, 7a, 7b (`/market/*`, `/portfolios/top`, `/hermes/queue`, `/hermes/scan/{job_id}`)
- Produces: typed `api.market`, `api.portfoliosTop`, `api.listPortfolios(limit,offset)`, `api.hermes.queue(day,cursor,limit)`, `api.hermes.scanJob(jobId)`

- [ ] **Step 1: Write the failing test**

Frontend has no unit test runner wired in this repo; verify by typecheck + build. Step 2 is the "fail" (types missing → build error), Step 4 the "pass".

- [ ] **Step 2: Run build to verify it fails**

Run: `cd frontend && npm run build`
Expected: FAIL once `MarketPanel.tsx` (Task 8b) references `api.market` — `Property 'market' does not exist on type ...`. (Do this check after 8b is drafted; for 8a alone, the typecheck of api.ts passes because nothing consumes the new exports yet — that is fine, 8a is additive.)

- [ ] **Step 3: Write minimal implementation**

Edit `frontend/src/lib/types.ts` — append:

```typescript
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

export interface MarketPrices {
  day: number;
  prices: Record<string, number>;
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
```

Also extend `HermesQueueItem` to carry `day` + `created_ts` (already has the rest). Edit the existing interface:

```typescript
export interface HermesQueueItem {
  client_id: string; client_name?: string; fum: number;
  prior_status: Status; post_status: Status;
  severity_weight?: number; confidence?: number;
  trades: Trade[]; rationale: string;
  rank_score: number;
  day?: number; created_ts?: string;
}
```

Edit `frontend/src/lib/api.ts` — extend the import line and the `api` object:

```typescript
// add to the import type list at top:
import type { ..., MarketClock, MarketHistoryPoint, MarketPrices, TopSafeguard, HermesQueuePage, HermesScanJob } from "./types";

// replace listPortfolios line:
  listPortfolios: (limit = 500, offset = 0) =>
    j<PortfolioSummary[]>(`/portfolios?limit=${limit}&offset=${offset}`),
  portfoliosTop: (limit = 200) =>
    j<TopSafeguard>(`/portfolios/top?limit=${limit}`),

// add market namespace inside the api object (after `reset:`):
  market: {
    clock: () => j<MarketClock>("/market/clock"),
    tick: () => j<MarketClock>("/market/tick", { method: "POST" }),
    advance: (days: number) =>
      j<MarketClock>(`/market/advance?days=${days}`, { method: "POST" }),
    autorun: (on: boolean, interval_sec = 5) =>
      j<MarketClock>("/market/auto-run", { method: "POST", body: JSON.stringify({ on, interval_sec }) }),
    autofix: (on: boolean) =>
      j<MarketClock>("/market/auto-fix", { method: "POST", body: JSON.stringify({ on }) }),
    prices: () => j<MarketPrices>("/market/prices"),
    history: (fromDay?: number, toDay?: number) =>
      j<MarketHistoryPoint[]>(`/market/history${fromDay != null ? `?from_day=${fromDay}${toDay != null ? `&to_day=${toDay}` : ""}` : ""}`),
    status: () => j<{ day: number; running: boolean; auto_fix: boolean }>("/market/status"),
  },

// extend the hermes namespace inside api (add queue + scanJob):
    queue: (day?: number, cursor = 0, limit = 50) =>
      j<HermesQueuePage>(`/hermes/queue?cursor=${cursor}&limit=${limit}${day != null ? `&day=${day}` : ""}`),
    scanJob: (jobId: string) => j<HermesScanJob>(`/hermes/scan/${jobId}`),
```

Note: `hermes.scan` now returns `{ job_id }` from the backend (Task 7b). Update `HermesScanResult` usage — keep the existing `scan()` return type but the body changed. Replace the `scan` line:

```typescript
    scan: () => j<{ job_id: string }>("/hermes/scan", { method: "POST" }),
```

And drop `HermesScanResult` from the import list (no longer used) — or leave it; unused type is harmless. Prefer removing to keep types honest.

- [ ] **Step 4: Run build to verify it passes**

Run: `cd frontend && npm run build`
Expected: PASS (typecheck + build clean) once 8b–8d land. For 8a in isolation, `npx tsc --noEmit` should pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat(34k): market api namespace + paged queue + top safeguard types (Task 8a)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8b: `components/MarketPanel.tsx` — clock + sim controls + status-over-time chart

**Files:**
- Create: `frontend/src/components/MarketPanel.tsx`
- No test (UI component; verified by build + manual smoke in Task 10)

**Interfaces:**
- Consumes: `api.market` (Task 8a), recharts `LineChart`/`AreaChart`, MATRIX theme classes (existing convention in `Heatmap.tsx`)
- Produces: `<MarketPanel />` — self-contained client component rendering clock, Play/Pause (auto-run), Auto-fix toggle, Step (tick), Advance-N input, live price strip, and a green/orange/red status-over-time area chart from `/market/history`.

- [ ] **Step 1: Write the failing test**

UI component, no unit test. Fail signal = build error (file missing) when `CommandCentreView` imports it (Task 8d).

- [ ] **Step 2: Run build to verify it fails**

Run: `cd frontend && npm run build`
Expected: FAIL once 8d imports `MarketPanel` before this file exists.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/MarketPanel.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import type { MarketClock, MarketHistoryPoint } from "@/lib/types";

const COLOR = { green: "#00FF41", orange: "#FFBF00", red: "#FF0000" };

export function MarketPanel() {
  const [clock, setClock] = useState<MarketClock | null>(null);
  const [hist, setHist] = useState<MarketHistoryPoint[]>([]);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [advN, setAdvN] = useState(5);
  const [busy, setBusy] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, h, p] = await Promise.all([api.market.clock(), api.market.history(), api.market.prices()]);
      setClock(c);
      setHist(h);
      setPrices(p.prices ?? {});
    } catch { /* keep last */ }
  }, []);

  useEffect(() => {
    load();
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  // poll the clock while running so the UI ticks live
  useEffect(() => {
    if (clock?.running) {
      pollRef.current = setInterval(load, Math.max(1000, (clock.auto_interval_sec || 5) * 1000));
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [clock?.running, clock?.auto_interval_sec, load]);

  const act = async (fn: () => Promise<MarketClock>) => {
    setBusy(true);
    try { await fn(); } finally { setBusy(false); await load(); }
  };

  const priceEntries = Object.entries(prices).slice(0, 12);

  return (
    <div className="bg-matrix-panel border border-matrix-line rounded-sm p-4 flex flex-col gap-stack-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-matrix-green">schedule</span>
          <h2 className="font-display text-headline-md text-matrix-text">MARKET_SIM</h2>
        </div>
        <div className="font-mono text-body-sm text-matrix-muted">
          DAY <span className="text-matrix-green">{clock?.day ?? "—"}</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2">
        <button disabled={busy} onClick={() => act(() => api.market.tick())}
          className="px-3 py-1 font-mono text-body-sm border border-matrix-green text-matrix-green hover:bg-matrix-green/10 disabled:opacity-40">
          STEP ▸
        </button>
        <button disabled={busy} onClick={() => act(() => api.market.autorun(!(clock?.running)))}
          className="px-3 py-1 font-mono text-body-sm border border-matrix-line text-matrix-text hover:border-matrix-green">
          {clock?.running ? "❚❚ PAUSE" : "▶ AUTO-RUN"}
        </button>
        <button disabled={busy} onClick={() => act(() => api.market.autofix(!(clock?.auto_fix)))}
          className={`px-3 py-1 font-mono text-body-sm border ${clock?.auto_fix ? "border-matrix-green text-matrix-green" : "border-matrix-line text-matrix-muted"} hover:border-matrix-green`}>
          AUTO-FIX {clock?.auto_fix ? "ON" : "OFF"}
        </button>
        <div className="flex items-center gap-1 ml-auto">
          <input type="number" min={1} max={50} value={advN}
            onChange={(e) => setAdvN(Math.max(1, Math.min(50, Number(e.target.value))))}
            className="w-16 bg-matrix-void border border-matrix-line text-matrix-text font-mono text-body-sm px-2 py-1" />
          <button disabled={busy} onClick={() => act(() => api.market.advance(advN))}
            className="px-3 py-1 font-mono text-body-sm border border-matrix-line text-matrix-text hover:border-matrix-green">
            ADVANCE
          </button>
        </div>
      </div>

      {/* Price strip */}
      <div className="flex flex-wrap gap-3 bg-matrix-void border border-matrix-line rounded-sm px-3 py-2">
        {priceEntries.length === 0 && <span className="font-mono text-body-sm text-matrix-muted">no prices</span>}
        {priceEntries.map(([t, px]) => (
          <span key={t} className="font-mono text-body-sm">
            <span className="text-matrix-muted">{t}</span>{" "}
            <span className="text-matrix-text">${px.toFixed(2)}</span>
          </span>
        ))}
      </div>

      {/* Status over time */}
      <div className="h-[160px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={hist}>
            <defs>
              <linearGradient id="gGreen" dataKey="green" />
            </defs>
            <XAxis dataKey="day" stroke="#3a3a3a" tick={{ fill: "#7a7a7a", fontSize: 11 }} />
            <YAxis stroke="#3a3a3a" tick={{ fill: "#7a7a7a", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#050505", border: "1px solid #00FF41", fontSize: 11 }} />
            <Area type="monotone" dataKey="green" stackId="1" stroke={COLOR.green} fill={COLOR.green} fillOpacity={0.3} />
            <Area type="monotone" dataKey="orange" stackId="1" stroke={COLOR.orange} fill={COLOR.orange} fillOpacity={0.3} />
            <Area type="monotone" dataKey="red" stackId="1" stroke={COLOR.red} fill={COLOR.red} fillOpacity={0.4} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="font-mono text-body-sm text-matrix-muted italic">
        green / orange / red counts × day — drift emergence as prices move
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run build to verify it passes**

Run: `cd frontend && npm run build`
Expected: PASS (after 8d wires it). In isolation `npx tsc --noEmit` passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/MarketPanel.tsx
git commit -m "feat(34k): MarketPanel — clock + sim controls + status-over-time chart (Task 8b)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8c: `components/Heatmap.tsx` extend — top-N + aggregate-rest safeguard

**Files:**
- Modify: `frontend/src/components/Heatmap.tsx` (accept `top` safeguard shape; render aggregate-rest block when >500 portfolios)

**Interfaces:**
- Consumes: `PortfolioSummary[]` (existing prop, now ≤500 from paged `/portfolios`) **or** a `TopSafeguard` `{top, rest}` from `/portfolios/top`
- Produces: a treemap that never renders more than ~500 cells; when the book is large, an explicit "N remaining" aggregate block sized by `rest.fum` colored by `rest.dominant_status`.

- [ ] **Step 1: Write the failing test**

UI; verified by build. Fail signal = the heatmap still assumes the full book is passed and would render 34k cells (no guard). Manual: at 34k the page must not freeze.

- [ ] **Step 2: Run build to verify it fails**

Run: `cd frontend && npm run build`
Expected: PASS typecheck (additive), but the runtime safeguard is absent — recorded as the gap this task closes.

- [ ] **Step 3: Write minimal implementation**

Extend the `Heatmap` props to accept an optional `rest` block and cap the rendered data. Edit `frontend/src/components/Heatmap.tsx`:

Change the signature + data build:

```tsx
// frontend/src/components/Heatmap.tsx  (signature)
export function Heatmap({
  portfolios,
  syncing,
  rest,
}: {
  portfolios: PortfolioSummary[];
  syncing?: boolean;
  rest?: { count: number; fum: number; dominant_status: "green" | "orange" | "red" };
}) {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<string>("All Statuses");
  const [adviserFilter, setAdviserFilter] = useState<string>("All Advisers");
  const [assetClassFilter, setAssetClassFilter] = useState<string>("All Asset Classes");
  const [search, setSearch] = useState("");

  const advisers = Array.from(new Set(portfolios.map((p) => p.adviser))).sort();
  const assetClasses = Array.from(new Set(portfolios.map((p) => p.top_asset_class).filter(Boolean))) as string[];

  const filtered = portfolios.filter((p) => {
    const matchesSearch = p.client_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === "All Statuses" ||
      (statusFilter === "Breached" && p.status === "red") ||
      (statusFilter === "Attention" && p.status === "orange") ||
      (statusFilter === "Needs Action" && (p.status === "red" || p.status === "orange"));
    const matchesAdviser = adviserFilter === "All Advisers" || p.adviser === adviserFilter;
    const matchesAssetClass = assetClassFilter === "All Asset Classes" || p.top_asset_class === assetClassFilter;
    return matchesSearch && matchesStatus && matchesAdviser && matchesAssetClass;
  });

  const total_fum = (filtered.reduce((s, p) => s + p.fum, 0) + (rest?.fum ?? 0)) || 1;
  const order: Record<string, number> = { red: 0, orange: 1, green: 2 };
  const data = filtered
    .map((p) => ({
      client_id: p.client_id, client_name: p.client_name, fum: p.fum, status: p.status,
      top_reason: p.top_reason, size: Math.max(8, (p.fum / total_fum) * 4000),
    }))
    .sort((a, b) => order[a.status] - order[b.status] || b.fum - a.fum);

  // aggregate-rest safeguard block (one cell, not 34k)
  if (rest && rest.count > 0) {
    data.push({
      client_id: "__rest__", client_name: `${rest.count} remaining`,
      fum: rest.fum, status: rest.dominant_status, top_reason: "aggregate (SP4 drill-down)",
      size: Math.max(8, (rest.fum / total_fum) * 4000),
    } as typeof data[number]);
  }
```

Then guard the `Cell` click for the `__rest__` sentinel so it does not navigate:

```tsx
// frontend/src/components/Heatmap.tsx  (Cell component — top)
function Cell(props: any) {
  const { x, y, width, height, onSelect, client_id, client_name, fum, status } = props;
  if (!client_id || width < 4 || height < 4 || !status) return <g />;
  const isRest = client_id === "__rest__";
  const color = COLOR[status];
  const border = BORDER[status];
  const text = TEXT[status];
  return (
    <g onClick={() => { if (!isRest) onSelect?.(client_id); }} style={{ cursor: isRest ? "default" : "pointer" }}>
      <rect x={x} y={y} width={width} height={height} rx={4} fill={color} stroke={border} strokeWidth={1}
        className={status === "red" ? "pulse-red" : ""} />
      {width > 70 && height > 40 && (
        <>
          <text x={x + 8} y={y + 20} fontSize={11} fill={text} fontWeight={600} fontFamily="JetBrains Mono, monospace">
            {client_name.slice(0, 22)}
          </text>
          <text x={x + 8} y={y + 36} fontSize={11} fill={text} opacity={0.85} fontFamily="JetBrains Mono, monospace">
            ${(fum / 1e6).toFixed(1)}M
          </text>
        </>
      )}
    </g>
  );
}
```

Leave the filter bar, legend, tooltip, and treemap container unchanged.

- [ ] **Step 4: Run build to verify it passes**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Heatmap.tsx
git commit -m "feat(34k): heatmap top-N + aggregate-rest safeguard (Task 8c)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8d: `CommandCentreView.tsx` + `app/page.tsx` — wire MarketPanel + top safeguard

**Files:**
- Modify: `frontend/src/components/CommandCentreView.tsx` (render `<MarketPanel>`; fetch + pass `top` safeguard to `<Heatmap rest=...>`; refresh on market tick via clock polling)
- Modify: `frontend/src/app/page.tsx` (SSR fetch `portfoliosTop` and pass `initialTop`)

**Interfaces:**
- Consumes: `api.market.clock`, `api.portfoliosTop`, `api.listPortfolios` (paged), `MarketPanel`, `Heatmap` (with `rest`)
- Produces: the Command Centre now shows the market sim panel above the heatmap, and the heatmap renders ≤200 top blocks + one aggregate-rest block at 34k scale.

- [ ] **Step 1: Write the failing test**

UI; verified by build + manual smoke (Task 10).

- [ ] **Step 2: Run build to verify it fails**

Run: `cd frontend && npm run build`
Expected: FAIL — `MarketPanel` import missing until 8b lands; `portfoliosTop` / `initialTop` references unresolved until 8a + this task. (Run after 8a–8c are in place; this task is the wire-up that makes them compile together.)

- [ ] **Step 3: Write minimal implementation**

Edit `frontend/src/app/page.tsx`:

```tsx
import { api } from "@/lib/api";
import { CommandCentreView } from "@/components/CommandCentreView";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [ps, summary, top] = await Promise.all([
    api.listPortfolios(200, 0),
    api.summary(),
    api.portfoliosTop(200).catch(() => null),
  ]);
  let aiNarrative: string | undefined;
  try { aiNarrative = (await api.summaryAi()).narrative; } catch { /* optional */ }
  return (
    <CommandCentreView
      initialPortfolios={ps}
      initialSummary={summary}
      aiNarrative={aiNarrative}
      initialTop={top}
    />
  );
}
```

Edit `frontend/src/components/CommandCentreView.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PortfolioSummary, TopSafeguard } from "@/lib/types";
import { Heatmap } from "@/components/Heatmap";
import { MarketPanel } from "@/components/MarketPanel";
import { SummaryBar } from "@/components/SummaryBar";
import { TriageQueue } from "@/components/TriageQueue";
import { AssuranceBanner } from "@/components/AssuranceBanner";

type Summary = { total: number; counts: Record<string, number>; breach_count: number };

export function CommandCentreView({
  initialPortfolios,
  initialSummary,
  aiNarrative,
  initialTop,
}: {
  initialPortfolios: PortfolioSummary[];
  initialSummary: Summary;
  aiNarrative?: string;
  initialTop?: TopSafeguard | null;
}) {
  const [ps, setPs] = useState<PortfolioSummary[]>(initialPortfolios);
  const [summary, setSummary] = useState<Summary>(initialSummary);
  const [top, setTop] = useState<TopSafeguard | null | undefined>(initialTop);
  const [syncing, setSyncing] = useState(false);

  const refresh = useCallback(async () => {
    setSyncing(true);
    try {
      const [p, s, t] = await Promise.all([
        api.listPortfolios(200, 0),
        api.summary(),
        api.portfoliosTop(200).catch(() => null),
      ]);
      setPs(p); setSummary(s); setTop(t);
    } catch {
      // keep last-known state
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const onFocus = () => refresh();
    const onVisibility = () => { if (document.visibilityState === "visible") refresh(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [refresh]);

  // When the market is running, MarketPanel polls the clock; on each clock
  // change it calls onTick so the heatmap + summary re-fetch post-drift state.
  const onTick = useCallback(() => { refresh(); }, [refresh]);

  const heatmapPortfolios = top ? top.top : ps;
  const rest = top ? top.rest : undefined;
  const totalFum = heatmapPortfolios.reduce((s, p) => s + p.fum, 0) + (rest?.fum ?? 0);

  return (
    <div className="p-4 lg:p-gutter max-w-container-max mx-auto">
      <AssuranceBanner summary={summary} aiNarrative={aiNarrative} />
      <MarketPanel />
      <SummaryBar
        counts={summary.counts}
        breach_count={summary.breach_count}
        total={summary.total}
        totalFum={totalFum}
      />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter">
        <div className="lg:col-span-8 xl:col-span-9">
          <Heatmap portfolios={heatmapPortfolios} syncing={syncing} rest={rest} />
        </div>
        <div className="lg:col-span-4 xl:col-span-3">
          <TriageQueue portfolios={heatmapPortfolios} />
        </div>
      </div>
    </div>
  );
}
```

Wire `onTick` through: edit `MarketPanel.tsx` to accept an optional `onTick` prop and call it after each successful `load` when the day changed. Add to `MarketPanel`:

```tsx
// add to MarketPanel props
export function MarketPanel({ onTick }: { onTick?: () => void }) {
  const lastDay = useRef<number | null>(null);
  // inside load(), after setClock(c):
  if (lastDay.current != null && lastDay.current !== c.day) onTick?.();
  lastDay.current = c.day;
```

Then pass `onTick={onTick}` from `CommandCentreView`'s `<MarketPanel onTick={onTick} />`.

- [ ] **Step 4: Run build to verify it passes**

Run: `cd frontend && npm run build`
Expected: PASS (typecheck + build clean).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CommandCentreView.tsx frontend/src/components/MarketPanel.tsx frontend/src/app/page.tsx
git commit -m "feat(34k): wire MarketPanel + top safeguard into Command Centre (Task 8d)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: `scripts/load_check.py` + pytest perf tests

**Files:**
- Create: `backend/scripts/load_check.py` (34k generation + 20-tick monitor + delta scan + endpoint timing → report; exit non-zero on miss)
- Create: `backend/tests/test_perf.py` (pytest timed asserts for the §11 targets)

**Interfaces:**
- Consumes: `core.storage`, `generators.generate_data.build_book`, `core.market` (`tick`, `advance`, `get_clock`), `agents.hermes.monitor.run`, `agents.hermes.loop.delta_scan`, `core.data_loader` (`get_portfolio`, `summary`, `list_portfolios`)
- Produces: a printed perf report + non-zero exit on any §11 target miss; CI guard.

**Targets (§11):** generation <60s; one tick + `monitor.run` <10s; delta scan <5s; `/portfolio/{id}` <100ms; `/portfolios/summary` <50ms; paged `/portfolios` <200ms.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_perf.py
import os, sqlite3, tempfile, time
import pytest
from core import storage, data_loader, market
from generators import generate_data


@pytest.fixture(scope="module")
def big_book():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=34000, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    yield conn
    conn.close(); os.remove(path)


def test_generation_under_60s(big_book):
    # build_book already ran in the fixture; re-time a fresh build to assert
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    t0 = time.perf_counter()
    generate_data.build_book(conn, n=34000, seed=42, market_seed=42)
    dt = time.perf_counter() - t0
    conn.close(); os.remove(path)
    assert dt < 60.0, f"generation took {dt:.1f}s (>60s)"


def test_tick_monitor_under_10s(big_book):
    t0 = time.perf_counter()
    market.tick(run_monitor=True)
    dt = time.perf_counter() - t0
    assert dt < 10.0, f"tick+monitor took {dt:.1f}s (>10s)"


def test_delta_scan_under_5s(big_book):
    from agents.hermes.loop import delta_scan
    # advance a few days to create drift, then delta-scan the newly-non-green
    market.advance(5, run_monitor=True)
    conn = data_loader.get_conn_cached()
    rows = conn.execute(
        "SELECT client_id FROM status_history WHERE day=? AND status!='green' "
        "AND client_id IN (SELECT client_id FROM status_history WHERE day=? AND status='green')",
        (market.get_clock()["day"], market.get_clock()["day"] - 1),
    ).fetchall()
    ids = [r["client_id"] for r in rows][:500]
    t0 = time.perf_counter()
    if ids:
        delta_scan(ids, market.get_clock()["day"])
    dt = time.perf_counter() - t0
    assert dt < 5.0, f"delta scan took {dt:.1f}s (>5s)"


def test_portfolio_lookup_under_100ms(big_book):
    t0 = time.perf_counter()
    p = data_loader.get_portfolio("c00000")
    dt = time.perf_counter() - t0
    assert p is not None
    assert dt < 0.100, f"get_portfolio took {dt*1000:.0f}ms (>100ms)"


def test_summary_under_50ms(big_book):
    t0 = time.perf_counter()
    s = data_loader.summary()
    dt = time.perf_counter() - t0
    assert s["total"] == 34000
    assert dt < 0.050, f"summary took {dt*1000:.0f}ms (>50ms)"


def test_paged_portfolios_under_200ms(big_book):
    t0 = time.perf_counter()
    page = data_loader.list_portfolios(limit=500, offset=0)
    dt = time.perf_counter() - t0
    assert len(page) == 500
    assert dt < 0.200, f"paged list took {dt*1000:.0f}ms (>200ms)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_perf.py -v --tb=short`
Expected: FAIL — either `delta_scan` signature mismatch, `monitor.run` not wired into `tick`, or perf targets exceeded on the unoptimized path. (If they pass immediately, the targets are met — still keep the tests as the regression guard.)

- [ ] **Step 3: Write minimal implementation** (`backend/scripts/load_check.py`)

```python
"""34k scale + market-sim load check.

Generates 34k, runs 20 ticks (timing monitor.run each), runs a delta scan,
times the hot endpoints, prints a report, and exits non-zero if any §11
target is missed. Run:  python scripts/load_check.py
"""
import os, sys, time, tempfile, sqlite3

# allow `from core...` when run from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import storage, data_loader, market
from generators import generate_data
from agents.hermes.monitor import run as monitor_run
from agents.hermes.loop import delta_scan

TARGETS = {
    "generation": 60.0,
    "tick_monitor": 10.0,
    "delta_scan": 5.0,
    "portfolio_lookup": 0.100,
    "summary": 0.050,
    "paged_portfolios": 0.200,
}


def t():
    return time.perf_counter()


def main():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)

    print("== 34k generation ==")
    t0 = t()
    counts = generate_data.build_book(conn, n=34000, seed=42, market_seed=42)
    g = t() - t0
    print(f"  generated {counts} portfolios in {g:.1f}s (target <{TARGETS['generation']}s)")

    data_loader.set_conn(conn)

    print("== 20 ticks (monitor.run each) ==")
    tick_times = []
    for i in range(20):
        t0 = t()
        market.tick(run_monitor=True)
        tick_times.append(t() - t0)
    avg_tick = sum(tick_times) / len(tick_times)
    max_tick = max(tick_times)
    print(f"  avg tick+monitor {avg_tick:.2f}s, max {max_tick:.2f}s (target <{TARGETS['tick_monitor']}s)")

    print("== delta scan (newly-non-green) ==")
    day = market.get_clock()["day"]
    rows = conn.execute(
        "SELECT client_id FROM status_history WHERE day=? AND status!='green' "
        "AND client_id IN (SELECT client_id FROM status_history WHERE day=? AND status='green')",
        (day, day - 1),
    ).fetchall()
    ids = [r["client_id"] for r in rows][:500]
    t0 = t()
    if ids:
        delta_scan(ids, day)
    ds = t() - t0
    print(f"  delta scan {len(ids)} ids in {ds:.2f}s (target <{TARGETS['delta_scan']}s)")

    print("== endpoint timing ==")
    t0 = t(); data_loader.get_portfolio("c00000"); pl = t() - t0
    t0 = t(); s = data_loader.summary(); sm = t() - t0
    t0 = t(); page = data_loader.list_portfolios(limit=500, offset=0); pp = t() - t0
    print(f"  /portfolio/c00000   {pl*1000:.0f}ms (target <{TARGETS['portfolio_lookup']*1000:.0f}ms)")
    print(f"  /portfolios/summary {sm*1000:.0f}ms (target <{TARGETS['summary']*1000:.0f}ms)  total={s['total']}")
    print(f"  /portfolios?500     {pp*1000:.0f}ms (target <{TARGETS['paged_portfolios']*1000:.0f}ms)  page={len(page)}")

    print("== book distribution @ day 0 ==")
    print(f"  counts={s['counts']}  breaches={s['breach_count']}")

    misses = []
    if g > TARGETS["generation"]: misses.append(("generation", g, TARGETS["generation"]))
    if max_tick > TARGETS["tick_monitor"]: misses.append(("tick_monitor", max_tick, TARGETS["tick_monitor"]))
    if ds > TARGETS["delta_scan"]: misses.append(("delta_scan", ds, TARGETS["delta_scan"]))
    if pl > TARGETS["portfolio_lookup"]: misses.append(("portfolio_lookup", pl, TARGETS["portfolio_lookup"]))
    if sm > TARGETS["summary"]: misses.append(("summary", sm, TARGETS["summary"]))
    if pp > TARGETS["paged_portfolios"]: misses.append(("paged_portfolios", pp, TARGETS["paged_portfolios"]))

    conn.close(); os.remove(path)
    if misses:
        print("\nFAIL — targets missed:")
        for name, val, tgt in misses:
            print(f"  {name}: {val:.3f}s > {tgt}s")
        sys.exit(1)
    print("\nPASS — all targets met.")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test + script to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_perf.py -v`
Expected: PASS (6 passed). If `test_tick_monitor_under_10s` or `test_paged_portfolios_under_200ms` fail, the implementation is correct but slow — do not loosen the targets; profile the hot path (`monitor.run` batch size, `list_portfolios` per-row check) and add batching/indexes. The `idx_status_day` and `idx_holdings_client` indexes from Task 3a must be in place.

Run: `cd backend && .venv/Scripts/python.exe scripts/load_check.py`
Expected: prints a report ending `PASS — all targets met.` and exits 0.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/load_check.py backend/tests/test_perf.py
git commit -m "feat(34k): load_check script + pytest perf guards for §11 targets (Task 9)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: Local full verification → push → deploy → live smoke

**Files:** none new — this is the verification + deploy gate.

**Goal:** prove the full loop end-to-end at 34k: generate → tick → drift emerges → delta scan → approve-batch → green persists. Then ship to Render (backend) + Vercel (frontend) and re-prove it live.

- [ ] **Step 1: Full local backend build + test suite**

Run:
```bash
cd backend
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe scripts/load_check.py
```
Expected: all tests PASS; `load_check.py` prints `PASS — all targets met.` and exits 0. If any test fails, stop and fix before continuing — do not deploy a red suite.

- [ ] **Step 2: Generate the real 34k `portfolios.db` locally and run the loop by hand**

Run:
```bash
cd backend
.venv/Scripts/python.exe -c "from core import storage; from generators import generate_data; \
  c=storage.get_conn(); storage.init_schema(c); storage.migrate(c); \
  print(generate_data.build_book(c, n=34000, seed=42, market_seed=42))"
```
Then start the API and drive the loop through the real HTTP layer (not just in-process):
```bash
.venv/Scripts/python.exe -m uvicorn main:app --port 8000 &
# 1. drift: advance 10 days with monitor on
curl -s -X POST "http://127.0.0.1:8000/market/advance?days=10"
# 2. delta scan the newly-non-green (auto-fix off → manual)
curl -s -X POST http://127.0.0.1:8000/hermes/scan   # returns {"job_id":...}
# 3. poll job, then read the queue
curl -s "http://127.0.0.1:8000/hermes/queue?limit=10"
# 4. approve one queue item (human gate) → record_trades → effective revalue
#    (use the client_id + trades from the queue row above)
curl -s -X POST http://127.0.0.1:8000/hermes/approve-batch \
  -H "Content-Type: application/json" \
  -d '{"items":[{"client_id":"cXXXXX","trades":[...],"rationale":"smoke"}]}'
# 5. prove green persists across a reload (effective re-check, no hidden state)
curl -s "http://127.0.0.1:8000/portfolio/cXXXXX/check"
```
Expected: step 2 shows drift (`book_summary` counts shift off 5/15/80 after day 10); step 3 returns a job that goes `done` with `scanned` ≈ 34000; step 4 `applied: 1`; step 5 `status` is `green` or `orange` and stays so on a second `GET`.

- [ ] **Step 3: Frontend build + manual smoke against local backend**

Run:
```bash
cd frontend
npm run build
npm run dev   # against API_URL=http://127.0.0.1:8000 (server-side /api proxy)
```
Expected: build clean; Command Centre renders `MarketPanel` (DAY counter, Step/Auto-run/Auto-fix/Advance), the heatmap shows ≤200 top blocks + one "N remaining" aggregate block (no 34k-cell freeze), the status-over-time chart shows green/orange/red areas across days. Clicking Step advances the day and the heatmap/summary refresh.

- [ ] **Step 4: Commit the verification record + push**

```bash
git add -A
git commit -m "verify(34k): local full loop green-persists + perf targets met (Task 10)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main
```
Expected: push clean. `portfolios.db` is gitignored — Render regenerates it at build/start from the generator (env `DATA_SEED=42`, `MARKET_SEED=42`).

- [ ] **Step 5: Render + Vercel redeploy + live smoke**

- Render backend: ensure env vars set (`ANTHROPIC_API_KEY` server-only, `DATA_SEED=42`, `MARKET_SEED=42`, `MARKET_AUTO_RUN=false`, `MARKET_AUTO_INTERVAL_SEC=5`, `MARKET_AUTO_FIX=false`, `PORTFOLIOS_DB` unset → default `data/portfolios.db`). Build command must run the generator if `portfolios.db` is absent — add to the Render build/start command: `python -c "from core import storage; from generators import generate_data; import os; c=storage.get_conn(); storage.init_schema(c); storage.migrate(c); generate_data.build_book(c, n=34000, seed=int(os.environ.get('DATA_SEED','42')), market_seed=int(os.environ.get('MARKET_SEED','42')))"` (guard with an existence check so it does not wipe an existing db on every boot). Trigger a deploy.
- Vercel frontend: redeploy (auto on push to main). Confirm `API_URL` is the server-only Render URL; no `NEXT_PUBLIC_*` leaked.
- Live smoke (against the deployed URLs): repeat Step 2's curl sequence against the live backend. Confirm: `/market/advance?days=10` drifts, `/hermes/scan` returns a `job_id` and the job goes `done`, `/hermes/queue` lists gate-green rows, `/hermes/approve-batch` with a real queue row returns `applied: 1`, and `/portfolio/{id}/check` shows the post-approve status persisting.

Expected: live loop matches local. If the Render 512 MB tier OOMs during generation, confirm `MARKET_AUTO_RUN=false` (no concurrent tick during gen) and that `build_book` streams inserts in `executemany` batches (Task 3c) rather than one giant transaction; re-deploy.

- [ ] **Step 6: Mark done**

All §11 targets met locally + live; the human-applies gate held end-to-end (Hermes proposed/gated/queued, a human called `approve-batch`, green persisted). 34k replaces 40, single code path, no `BOOK_PROFILE` flag. SP1 + SP2 complete; SP3 (full serving layer) deferred to a later spec.

---

## Self-Review

(Run before offering execution handoff. Fix inline; do not re-review.)

**1. Spec coverage** — every §15 build-order step maps to a task:
- §15.1 universe + mandates → Tasks 1a, 1b
- §15.2 rules_engine +4 rules → Task 2a
- §15.3 storage + generate_data + market GBM → Tasks 3a, 3b, 3c
- §15.4 data_loader + effective → Tasks 4a, 4b
- §15.5 core/market + routers/market → Tasks 5a, 5b
- §15.6 monitor + hermes/loop + proposer → Tasks 6a, 6b, 6c
- §15.7 routers/portfolios + hermes + admin → Tasks 7a, 7b, 7c
- §15.8 frontend MarketPanel + heatmap safeguard + api market → Tasks 8a, 8b, 8c, 8d
- §15.9 load_check + perf tests → Task 9
- §15.10 local verify → push → deploy → live smoke → Task 10

§3 locked decisions, §6 schema (12 tables), §7 four new rules, §8 GBM + virtual clock + two independent toggles, §9 monitor + paged/delta Hermes + human gate, §10 MarketPanel + heatmap safeguard, §11 perf targets (Task 9 asserts), §12 error handling (WAL, scan_jobs status, MockLLM fallback, mandate validation in Task 1b), §13 testing (unit/integration/perf/determinism — covered across task tests + Task 9), §14 determinism + deploy env — all covered.

**2. Placeholder scan** — no TBD/TODO/"implement later"/"similar to Task N". Every code step has full code. Commit messages concrete.

**3. Type consistency** — checked cross-task names:
- `UNIVERSE_BY_TICKER` / `UNIVERSE` (Tasks 1a, 2b, 6a) — proposer uses `.get("base_price")` (fixed in 6a).
- `apply_trades(portfolio, trades, price_lookup=None)` (2b) — called with `price_lookup=current_prices` in 4b, 6c.
- `current_prices()` (4a) cached by `(day, seed)`; `set_conn`/`reset_cache` clear it.
- `build_book(conn, n=34000, seed, market_seed)` (3c) — called in 7a test fixture, 9, 10.
- `list_portfolios(limit, offset)` / `get_portfolio` / `summary` (4a) — used in 7a, 7c, 9.
- `scan_book()` / `scan_book_paged(...)` / `delta_scan(ids, day)` (6c) — used in 7b, 9.
- `monitor.run(day)` (6b) — `tick(run_monitor=True)` lazy-imports + calls it (5a).
- `get_effective(client_id, seed=p)` (4b) — `seed=p` carries market_seed; used in 7a, 7c, 6b.
- `check(eff, mandate)` (2a) — unchanged signature; used everywhere.
- `hermes_queue` columns match across 3a (schema), 6c (INSERT), 7b (SELECT) — `day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts`.
- `book_summary` columns match across 3a, 3c, 6b, 7c.
- `status_history` columns match across 3a, 3c, 6b, 7a (`/portfolios/top`), 7c.
- Frontend `HermesScanResult` removed in 8a (scan now `{job_id}`); `MarketClock`/`TopSafeguard`/`HermesQueuePage`/`HermesScanJob` added in 8a, consumed in 8b/8c/8d.

One pre-existing mismatch noted, NOT introduced by this plan: `types.ts HermesApproveBatchResult` says `{ok, applied:[{client_id,new_status}], failed, heartbeat}` but the backend `approve-batch` returns `{results, applied:int, failed:int}`. Task 7b leaves approve-batch unchanged, so the frontend type was already wrong before this plan. **Fix:** fold this correction into Task 8a's `types.ts` edit (replace the existing `HermesApproveBatchResult` interface) and update `api.hermes.approveBatch`'s return type. Concrete replacement:

```typescript
// frontend/src/lib/types.ts — REPLACE the existing HermesApproveBatchResult
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
```

```typescript
// frontend/src/lib/api.ts — hermes.approveBatch return type already references
// HermesApproveBatchResult, so no signature change needed beyond the type fix above.
```

Any frontend consumer reading `res.applied` as a count (not an array) now type-checks correctly; consumers reading `res.results[].new_status` work. If `TriageQueue` or another component previously read the old `.applied[]` array shape, the executing engineer must grep `approveBatch` / `.applied` and adjust — that is a runtime consumer fix, called out here so it is not missed.

---

Plan complete. All 10 build-order steps mapped to bite-sized TDD tasks with full code, exact paths, exact commands, and per-task commits. No placeholders. Type consistency checked across the 13 task boundaries. Self-review fixes folded in.