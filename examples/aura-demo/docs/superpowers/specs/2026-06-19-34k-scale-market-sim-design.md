# 34k Scale + Market Simulation — Design Spec (SP1+SP2 combined)

**Date:** 2026-06-19
**Status:** Approved
**Supersedes scope of:** prior 40-portfolio synthetic book (replaced)
**Related:** `2026-06-18-aura-*` specs (Phase 1 + Phase 2 Hermes)

## 1. Goal

Scale Assure's synthetic book from 40 to **34,000 portfolios** with **diverse, complex per-portfolio mandates**, add a **fluctuating-market simulation** that re-values holdings as prices move, and demonstrate the deterministic engine + Hermes **checking and managing the book at scale as drift/breaches emerge over time**.

Headline challenge (user): "with the fluctuating market how it is getting checked and managed is the main challenge."

## 2. Non-goals (deferred to later specs)

- **SP3** — full serving layer: aggregated/paginated list endpoints, precompute hardening, drift-over-time analytics endpoints.
- **SP4** — full 34k frontend: aggregated heatmap with drill-down, virtualized triage lists.
- **SP5** — Hermes perf hardening beyond the minimum async/paged scan in this spec.
- **SP6** — full load-test report + sustained-run analysis.

The minimum architecture the loop needs (SQLite, O(1) index, paged scan, precomputed summary) is inline in this spec. SP3 extends the serving layer on top of it.

## 3. Locked decisions (from brainstorm)

| Decision | Choice |
|---|---|
| Storage + compute | **SQLite** (stdlib `sqlite3`, no new deps), paged + indexed + precomputed |
| Market model | Seeded per-ticker **GBM + sector correlation**, deterministic given `(seed, day)` |
| Time | **Virtual clock** — `/market/tick`, `/market/advance?days=N`, optional `/market/auto-run`; deterministic |
| New rule types | Geography caps, ESG exclusion list, top-N concentration cap, liquidity-tier min (4 new → 10 total) |
| Seed distribution | Calm **5% red / 15% orange / 80% green**; FUM **power-law/lognormal** (few huge, many small) |
| SP2 deliverable | Full loop: sim + drift monitor + Hermes auto-propose at scale + scan-on-demand |
| Human gate | **Auto-propose, human applies** — Hermes autonomously scans/proposes/gates/queues; applying trades stays behind human `approve-batch`. The "every action passes a human gate" law holds. |
| Book profile | **Replace** 40 with 34k (single book, single code path; no profile flag) |
| Determinism | Seeded throughout; same seed → identical logical `portfolios.db` |

## 4. Scope (in)

- 34k generator + mandate-template library (10 rule types) + SQLite store
- Seeded market sim (GBM + sector correlation) + virtual-clock API
- Drift monitor (batched re-check on tick, status-over-time history)
- Hermes-at-scale: paged async scan + autonomous propose/gate/queue loop + scan-on-demand
- Precomputed book summary (invalidate on tick/trade)
- Minimal frontend: market panel + heatmap safeguard (top-N + aggregate-rest)
- Load/perf tests + 34k verification script
- Determinism throughout

## 5. Architecture

### 5.1 Component map

```
backend/
  generators/
    universe.py        NEW: ~35 tickers w/ asset_class, sector, region, liquidity_tier, mu, sigma, price
    mandates.py        NEW: mandate template library + randomized params (10 rule dims)
    market.py          NEW: seeded GBM price model + sector correlation → prices(ticker, day)
    generate_data.py   REWRITE: 34k → portfolios.db (schema + data + prices seed at day 0)
  core/
    storage.py         NEW: sqlite3 conn (WAL), schema init, migrations, query helpers
    data_loader.py     REWRITE over SQLite: O(1) get_portfolio, paged list, precomputed summary read
    market.py          NEW: virtual clock (day), revalue (units × price(day)), tick/advance/autorun, history
    rules_engine.py    EXTEND: +4 rule types; pure, unchanged check(portfolio, mandate) interface
    effective.py       REWRITE over SQLite state table; revalues w/ live prices + applied trades
  agents/hermes/
    loop.py            REWRITE: paged async scan_book (delta + full), batched, paged queue
    monitor.py         NEW: drift monitor — on tick, batched re-check, status_history, delta-scan trigger
    proposer.py        EXTEND: handle 4 new breach types (deterministic, no Claude)
    strategy_io.py     UNCHANGED (judgment layer; strategy.yaml + history/)
    score.py           UNCHANGED (composite); operates on aggregate counts
  routers/
    market.py          NEW: /market/clock /tick /advance /auto-run /auto-fix /prices /history /status
    portfolios.py      REWRITE: paged + precomputed summary; top-N safeguard list endpoint
    hermes.py          EXTEND: paged queue, async scan job status, approve-batch (human gate)
    actions.py         UNCHANGED (single-portfolio explain/verify/remediate/approve)
    admin.py           EXTEND: /admin/reset clears state + queue + status_history + market clock
frontend/
  components/
    MarketPanel.tsx    NEW: clock + play/pause/step/advance + autorun + price strip + status-over-time chart
    Heatmap.tsx        EXTEND: safeguard — top-N (~200) by FUM×severity + aggregate-rest block
    CommandCentreView.tsx  EXTEND: render MarketPanel; live refetch on market events
  lib/api.ts           EXTEND: market namespace (clock, tick, advance, autorun, prices, history, status)
scripts/
  load_check.py        NEW: 34k verification + perf report
```

### 5.2 Data flow

```
generate_data → portfolios.db (portfolios, holdings, mandates, prices@day0)
                          │
                  virtual clock advances
                          ↓
market.tick(day+1) → recompute prices(ticker, day) → lazy revalue (units × price(day))
                          ↓
monitor.batched_recheck (500/batch) → status_history(day, client, status, breaches)
                                    → book_summary refresh
                                    → drift-event log (status transitions)
                          │  if auto_fix_on AND new breaches appeared
                          ↓
hermes.delta_scan(newly-non-green) → deterministic propose → check() GATE
                          │  gate drops still-red → misses
                          ↓
                  paged hermes_queue(day, client, trades, rationale, post_status)
                          ↓
                  HUMAN approve-batch → record_trades → effective revalue → green persists
```

## 6. SQLite schema

```sql
-- portfolios.db (WAL mode)
CREATE TABLE portfolios (
  client_id TEXT PRIMARY KEY,
  client_name TEXT, adviser TEXT, fum REAL, mandate_id INTEGER
);
CREATE TABLE mandates (
  mandate_id INTEGER PRIMARY KEY,
  spec TEXT            -- JSON blob: full mandate dict (the LAW; never written by Hermes)
);
CREATE TABLE holdings (
  client_id TEXT, ticker TEXT, units REAL,
  FOREIGN KEY(client_id) REFERENCES portfolios(client_id)
);
CREATE INDEX idx_holdings_client ON holdings(client_id);
CREATE TABLE prices (
  ticker TEXT, day INTEGER, price REAL,
  PRIMARY KEY(ticker, day)
);
CREATE TABLE state (
  client_id TEXT, ts TEXT, ticker TEXT, action TEXT, units REAL, value REAL, rationale TEXT
);
CREATE INDEX idx_state_client ON state(client_id);
CREATE TABLE status_history (
  day INTEGER, client_id TEXT, status TEXT, breach_count INTEGER, watch_count INTEGER,
  PRIMARY KEY(day, client_id)
);
CREATE INDEX idx_status_day ON status_history(day);
CREATE TABLE book_summary (
  id INTEGER PRIMARY KEY CHECK(id=1),
  day INTEGER, total INTEGER, green INTEGER, orange INTEGER, red INTEGER,
  breach_count INTEGER, updated_ts TEXT
);
CREATE TABLE hermes_queue (
  day INTEGER, client_id TEXT, prior_status TEXT, post_status TEXT,
  fum REAL, trades TEXT, rationale TEXT, rank_score REAL, created_ts TEXT
);
CREATE INDEX idx_queue_day ON hermes_queue(day);
CREATE TABLE scan_jobs (
  job_id TEXT PRIMARY KEY, kind TEXT, status TEXT, started_ts TEXT, done_ts TEXT,
  scanned INTEGER, remediated INTEGER, missed INTEGER, error TEXT
);
CREATE TABLE clock (
  id INTEGER PRIMARY KEY CHECK(id=1),
  day INTEGER, running INTEGER, auto_interval_sec INTEGER, auto_fix INTEGER, seed INTEGER
);
CREATE TABLE drift_events (
  day INTEGER, client_id TEXT, from_status TEXT, to_status TEXT, ts TEXT,
  PRIMARY KEY(day, client_id)
);
CREATE INDEX idx_drift_day ON drift_events(day);
CREATE TABLE tickers (
  ticker TEXT PRIMARY KEY, name TEXT, asset_class TEXT, sector TEXT,
  region TEXT, liquidity_tier INTEGER, base_price REAL, mu REAL, sigma REAL
);
```

A `clock` singleton row (id=1) holds the virtual-clock state: `day`, `running` (auto-tick on/off), `auto_interval_sec`, `auto_fix` (Hermes auto-propose on/off), `seed`. Two **independent** toggles — see §8.2 / §9.1.

Universe/metadata lookups (ticker → asset_class, sector, region, liquidity_tier, base price, mu, sigma) live in `generators/universe.py` as a static dict (small, in-memory is fine) and are also written to a `tickers` reference table for completeness.

Mandate is stored once per distinct mandate (deduped) in `mandates.spec` as JSON. ~34k portfolios share a library of mandate templates → far fewer than 34k rows.

## 7. New rule types (rules_engine extension)

All pure, deterministic, added to `check(portfolio, mandate)`. Each appends to `per_rule`; failures append to `breaches` (severity red) or `watches` (severity orange) per existing convention. Status logic unchanged.

| Rule key | Holding field added | Mandate field | Check |
|---|---|---|---|
| `max_region_weight:{region}` | `region` | `max_region_weight: {region: cap}` | Σ holdings in region / total ≤ cap |
| `esg_exclusions` | — | `excluded_tickers: [ticker…]` | no holding ticker ∈ excluded list (red breach) |
| `max_top_n_concentration` | — | `max_top_n_concentration: {n: 5, limit: 0.60}` | Σ top-N holding weights ≤ limit (red breach) |
| `min_liquid_pct` | `liquidity_tier` (1=high,2=med,3=low) | `min_liquid_pct: 0.40` | Σ tier-1 weights ≥ min (red breach) |

Universe expansion: ~35 tickers spanning Equity (US/ex-US/single-country), Bonds, Commodity, Crypto, Cash — each tagged with `region` (US, ex-US, EM, etc.) and `liquidity_tier`. This exercises all 10 rule types.

Existing 6 rules unchanged: `max_asset_class_weight`, `max_sector_weight`, `approved_universe`, `max_single_holding`, `min_cash`, `drift` (one-sided, over-target only).

## 8. Market simulation

### 8.1 Price model

Per-ticker geometric Brownian motion:
```
P(t) = P(t-1) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
Z = sector_factor * rho + idiosyncratic * sqrt(1 - rho^2)
```
- `dt = 1/252` (one trading day)
- `mu`, `sigma` per ticker (from `universe.py`)
- `sector_factor` shared across same-sector tickers (correlation `rho ≈ 0.5`)
- `Z` drawn from a seeded stdlib `random.Random` keyed by `(seed, ticker, day)` → deterministic, replayable, **no new dependency** (consistent with the SQLite choice). Correlated normals via Box-Muller + the linear combination above.

Prices written to `prices(ticker, day)` lazily on first request for that day and cached; `tick` precomputes the next day's prices for all tickers.

### 8.2 Virtual clock

- `day` stored in a `clock` singleton table (`{id:1, day, running, auto_interval_sec, seed}`).
- `/market/tick` → `day += 1`, compute prices for all tickers at new day, trigger `monitor.run(day)`.
- `/market/advance?days=N` → loop tick N times (batched; one monitor pass at end).
- `/market/auto-run` `{on: bool, interval_sec: int}` → FastAPI `BackgroundTasks` loop ticking every `interval_sec`; cancellable via `on:false`. Idempotent — concurrent tick calls safe under WAL. This toggles **clock auto-ticking only**.
- `/market/auto-fix` `{on: bool}` → toggles **Hermes auto-propose** (delta-scan on newly-non-green). Independent from auto-run. The human-applies gate always holds regardless.
- `/market/clock` → `{day, running, auto_interval_sec, auto_fix}`.
- `/market/prices` → `{ticker: price}` at current day (top N by FUM-relevance).
- `/market/history?from_day=&to_day=` → status-counts × day series from `status_history`.

### 8.3 Re-valuation

Lazy: `market_value(ticker) = units × price(ticker, day)`. Computed on read in `effective_portfolio` / `data_loader`. No eager writes to holdings on tick. Precomputed `book_summary` invalidated + recomputed by `monitor.run(day)`.

## 9. Drift monitor + Hermes at scale

### 9.1 monitor.run(day)

1. Batched full-book re-check (500 portfolios/batch): for each, `effective_portfolio` (revalue with live prices + applied trades) → `check` → status + breach/watch counts.
2. Upsert `status_history(day, client_id, status, breach_count, watch_count)`.
3. Recompute + upsert `book_summary(id=1)`.
4. Detect transitions vs `status_history(day-1)` → write drift-events log (in-memory + optional table) for observability.
5. If `clock.auto_fix` is on and any portfolio went green→orange or orange→red (newly non-green): trigger `hermes.delta_scan(newly_non_green_set, day)`.

### 9.2 Hermes scan (paged + async)

- `scan_book_paged(cursor, batch=500, full=False, subset=None)`:
  - Iterate portfolios in `client_id` order from cursor (or `subset`).
  - For each non-green: deterministic `propose` (no Claude) → `apply_trades` → `check` GATE.
  - Gate-pass (post-trade green/orange, no breaches) → `hermes_queue` row.
  - Gate-fail → `misses` (logged, not silently dropped).
  - Rank survivors by `fum × severity_weight`.
  - Return `{queue_page, next_cursor, counts}`.
- Async wrapper: `POST /hermes/scan` creates a `scan_jobs` row, runs via `BackgroundTasks`, returns `job_id`; `GET /hermes/scan/{job_id}` → status + counts + first queue page.
- Delta scan: same path with `subset` = newly-non-green ids; fast (few hundred).
- Queue pagination: `GET /hermes/queue?day=&cursor=&limit=50`.
- **Human gate:** `POST /hermes/approve-batch` (existing) applies chosen queue items → `record_trades` → effective revalue → green persists. Unchanged contract.

### 9.3 Proposer extension

`proposer.propose` extended to handle the 4 new breach types deterministically (trim-to-cap for geography/sector/asset, liquidate for ESG exclusions, trim largest for top-N concentration, rotate into liquid tier-1 for min_liquid_pct). No Claude. Strategy vars (`strategy.yaml`) still drive priority/trim-method/replacement/min-size/max-trades/cash-buffer. Strategy changes still versioned + reversible via `strategy_io`.

## 10. Frontend (minimal, this spec)

- **MarketPanel** (rendered in `CommandCentreView`, above heatmap):
  - Clock day display, Play/Pause (auto-run = clock auto-tick), Auto-fix toggle (Hermes auto-propose), Step (tick), Advance N days input.
  - Live price strip: top ~12 tickers, current price + day-over-day Δ (green/red).
  - Book-status-over-time mini-chart (recharts line/area): green/orange/red counts × day from `/market/history`.
- **Heatmap safeguard:** when `portfolios.length` large (> ~500), render top-N (~200) blocks by `FUM × severity_weight` + one **aggregate block** labeled "N remaining" sized by remaining FUM, colored by dominant status. Prevents 34k-cell browser crash. Full aggregated/drill-down heatmap = SP4.
- **Diagnosis/Workbench:** unchanged; operate on a single portfolio (now O(1) lookup).
- **Hermes Mission Control:** queue paged (first 50 + "Load more"), Scan Book button (async job + status), monitor status (last drift event), approve-batch unchanged. Reflects `day` in queue rows.
- `CommandCentreView` live refetch: on market tick (poll `/market/clock` while running) + on focus/visibility (existing).

## 11. Perf / scale targets

| Operation | Target |
|---|---|
| Generation (34k + prices@day0) | < 60 s |
| Single tick + full-book re-check (`monitor.run`) | < 10 s |
| Hermes delta scan (few hundred newly-non-green) | < 5 s |
| `/portfolio/{id}` (O(1) index + lazy revalue) | < 100 ms |
| `/portfolios/summary` (precomputed) | < 50 ms |
| Paged `/portfolios` (500/page) | < 200 ms |
| Peak memory (Render 512 MB tier) | < 400 MB |

Enforced via `scripts/load_check.py` timed asserts + pytest-benchmark (or timed) tests.

## 12. Error handling

- SQLite WAL mode for tick/scan/approve concurrency; single-writer safe for demo.
- auto-run background task: cancellable, idempotent day advance (concurrent tick calls no-op if already at target day).
- Hermes async scan: `scan_jobs` status `running|done|failed`; partial failures → `misses` (no silent drop); `error` field on failure.
- Schema migration on startup; missing `portfolios.db` → regenerate from generator (or fail fast with clear message).
- LLM unchanged: `MockLLM` fallback when no `ANTHROPIC_API_KEY`; `summary_ai` uses precomputed `book_summary` aggregate (one Claude call, no per-portfolio LLM).
- Mandate validation on generation: every generated portfolio's mandate is structurally valid + at least the seed distribution holds; orphans/invalid → generator raises.

## 13. Testing

### 13.1 Unit
- `rules_engine`: 4 new rules, hermetic per-rule pass/fail + severity; existing 6 unchanged.
- `proposer`: handles each new breach type; strategy var change alters output (existing assertion extended).
- `market` GBM: same `(seed, ticker, day)` → identical price; sector correlation present (same-sector tickers co-move > cross-sector).
- `mandates` library: every template yields a valid mandate; randomization covers all 10 dims; some templates produce breaches.

### 13.2 Integration
- Generate 34k → assert counts ≈ 5/15/80 (±2% tol), FUM power-law shape (top 10% of portfolios > 50% of FUM), no orphan holdings, all mandates valid.
- Tick N=20 days → assert drift emergence: at least some green→orange transitions recorded in `status_history`.
- `monitor.run(day)` → `status_history` + `book_summary` written; `book_summary` counts match recomputed.
- Hermes delta scan over a synthetic newly-non-green set → queue rows are gate-green (post_status green/orange, no breaches); misses logged.
- Approve-batch a queue item → `record_trades` + effective revalue → status flips green + persists across reload.

### 13.3 Load / perf
- `scripts/load_check.py`: generate 34k, time generation; run 20 ticks timing `monitor.run`; run delta scan; time `/portfolio/{id}`, `/portfolios/summary`, paged `/portfolios`. Print report; exit non-zero if any target missed.
- pytest timed asserts for tick/scan/lookup targets.

### 13.4 Determinism
- Same seed → identical logical content (portfolios, mandates, prices@day0, price series) — verified by hashing key tables across two runs.

## 14. Determinism + deploy

- Seeded throughout: data-gen seed, market seed, GBM per `(seed, ticker, day)`.
- `portfolios.db` gitignored (regenerable from generator). Generated at build (Render build command runs generator) or on first boot if absent.
- 34k replaces 40 → single book, no `BOOK_PROFILE` flag.
- Env unchanged + optional `MARKET_AUTO_RUN` (bool, clock auto-tick) + `MARKET_AUTO_INTERVAL_SEC` + `MARKET_AUTO_FIX` (bool, Hermes auto-propose on drift) + `MARKET_SEED` + `DATA_SEED`.
- Render 512 MB tier viable (paged reads, <400 MB target); WAL for concurrency.
- Existing endpoints (`/portfolio/{id}`, `/hermes/*`, `/admin/reset`) keep contracts; internals swap JSON-file → SQLite.

## 15. Build / run order (for the plan)

1. `universe.py` + `mandates.py` (template library) — pure, testable first.
2. `rules_engine` +4 rules + tests.
3. `storage.py` (schema) + `generate_data.py` (34k → SQLite) + `market.py` (GBM price model).
4. `data_loader` + `effective` rewritten over SQLite + lazy revalue.
5. `core/market.py` (virtual clock + revalue) + `routers/market.py`.
6. `monitor.py` (drift monitor) + `hermes/loop.py` (paged async + delta) + `proposer` extension.
7. `routers/portfolios` (paged + precomputed) + `routers/hermes` (paged queue + job status) + `admin` reset.
8. Frontend: `MarketPanel` + heatmap safeguard + api market namespace.
9. `scripts/load_check.py` + perf tests.
10. Local full verification → push → Render/Vercel redeploy → live smoke (tick → drift → delta scan → approve-batch → green persists).