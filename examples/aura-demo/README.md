# ASSURE — AI-Assured Portfolio Compliance

**Tagline:** *AI recommends, assurance verifies; human approves.*

ASSURE is an AI-assurance layer on top of portfolio management. It turns mandate compliance from a slow, spreadsheet-bound, per-portfolio task into a live, book-wide, explainable workflow where a deterministic rules engine is always the final authority, Claude agents translate and propose, and a human approves every material action.

All data is **synthetic**. No real client data is used anywhere.

---

## What problem it solves

Typical portfolio-assurance workflows today are:

- **Fragmented** — data lives across spreadsheets, custody screens, and compliance tools.
- **Slow** — a breach is a row of numbers that a human must decode.
- **Risky** — remediation is done by hand, with no simulated “does this fix it?” step.
- **Opaque** — little to no audit trail tying a decision to the data that justified it.
- **Narrow** — the team sees one portfolio at a time and misses book-wide patterns.

ASSURE’s answer:

- One live book view for **34,000 portfolios**.
- Deterministic rule engine is the single source of truth; AI only narrates and proposes.
- A **shadow / effective state** lets the system simulate fixes before any real change.
- **Hermes** runs the same propose-verify-approve loop at book scale and self-improves its remediation *strategy* without ever touching the mandate.
- Every action is human-gated, timestamped, explainable, and exportable.
- One-click **Evidence Pack** per portfolio generates a regulator-ready, print-to-PDF compliance proof artifact.

---

## Philosophy

1. **Determinism is the source of truth.** The LLM never decides compliance.
2. **Human-in-the-loop everywhere.** Nothing auto-executes.
3. **Everything explainable + audited.** Every proposal, approval, strategy change and evidence pack is logged.
4. **All data is synthetic.** The 34,000 portfolios, mandates, and prices are generated deterministically; no real client data.

---

## The two-tier safety cage

| Layer | What it is | Where it lives | Changeable? | Example |
|---|---|---|---|---|
| **Mandate rules = LAW** | Hard compliance limits per portfolio | `backend/core/rules_engine.py` + seeded mandate specs | No. Immutable. | Max single holding ≤ 10% |
| **Remediation strategy = JUDGMENT** | How Hermes chooses to fix breaches | `backend/agents/hermes/strategy.yaml` | Yes, via human-gated adopt | “Trim the largest offender first” vs “trim proportionally” |

The rules engine enforces **10 rule categories**:

- `max_asset_class_weight`
- `max_sector_weight`
- `approved_universe`
- `max_single_holding`
- `min_cash`
- `drift` watches (target allocation ± tolerance)
- `max_region_weight`
- `esg_exclusions`
- `max_top_n_concentration`
- `min_liquid_pct`

A portfolio is **green** (no breaches), **orange** (watches/drift only), or **red** (one or more breaches).

The AI — whether narrative generation, Explain targeting, or Hermes reflection — is structurally blocked from editing mandate rules. `strategy_io._guard()` refuses to write outside `strategy.yaml` / `history/`. The rules engine is never written by AI.

---

## Architecture

Next.js 14 (App Router) frontend + FastAPI backend, monorepo.

```
[Next.js: Command Centre, Diagnosis, Workbench, /hermes Mission Control]
            │                                    ↑
            └──────────────HTTP─────────────────┘
                                                │
                                          [FastAPI routers]
                                                │
            ┌───────────────────────────────────┼───────────────────────────────────┐
            │                                   │                                   │
   agents/ (explain, remediate, summarize, evidence)  agents/hermes/ (proposer, loop, score, reflect)  core/ (rules engine, effective state, market model)
            │                                   │                                   │
            └───────────────────────────────────┴───────────────────────────────────┘
                                                │
                                        [SQLite WAL + seeded GBM market model]
                                                │
                                     [34,000 synthetic portfolios + ~8 mandates]
                                                │
                                        [audit.jsonl — append-only]
```

Key backend modules:

- `backend/core/rules_engine.py` — deterministic source of truth; `check(portfolio, mandate) -> RulesResult`.
- `backend/core/effective.py` — shadow/effective state: seed holdings + approved trades.
- `backend/agents/evidence.py` — read-only assembler for per-portfolio Evidence Packs.
- `backend/agents/hermes/loop.py` — paged book-wide scan; gate-green proposals only.
- `backend/agents/hermes/proposer.py` — deterministic, strategy-driven trade generator.
- `backend/agents/hermes/reflect.py` — proposes one strategy-variable change; never writes.
- `backend/agents/hermes/strategy_io.py` — the only writer for `strategy.yaml`; guarded.
- `backend/core/market.py` + `generators/market.py` — seeded GBM price model.
- `backend/core/hermes_store.py` — pluggable runtime state (SQLite / Postgres) for scan jobs, heartbeat, queue.

---

## Data model: seed + approved = effective

1. **Seed portfolio** — immutable baseline holdings loaded from the seeded SQLite database.
2. **Effective portfolio** — seed holdings **plus every human-approved trade** (`core/effective.py`).

`record_trades()` is called only by approve gates. This means ASSURE can simulate fixes, preview post-trade compliance, and roll back the demo state without touching seed data. `POST /admin/reset` clears only runtime state; the 34,000 seed portfolios stay intact.

---

## Cover-to-cover feature walkthrough

### 1. Command Centre

- Summary bar in plain English: *“34,000 portfolios. 27,200 aligned. 1,700 breached, 5,100 drifting.”*
- Heatmap of portfolio tiles sized by FUM and colored by status; largest portfolios top-left.
- Triage sidebar and search.

### 2. Market Simulation panel

- Seeded geometric Brownian motion (GBM) drives synthetic, sector-correlated prices.
- Controls: **Tick**, **Advance N**, **Auto-run**, **Auto-fix**.
- Line chart tracks green / orange / red counts per day.
- Drift monitor re-checks all 34,000 portfolios in batches of 1,000 per tick.

All prices are synthetic; e.g. SPY at ~$539 is a GBM output, not live market data.

### 3. Portfolio Diagnosis

- **Narrative panel** translates the deterministic `rules_engine.check()` result into plain English.
- **Holdings table** with breach chips that highlight offending holdings.
- **Explain targeting** — clicking “?” on a row calls the AI to explain the exact rule for that holding or asset class, not a generic story.
- **Allocation bar chart** with per-asset-class Explain.
- **Confidence line**: *“Rule check: deterministic (100%). Narrative: advisory.”*
- **Generate Evidence Pack** button opens a print-ready, timestamped compliance proof in a new tab.

### 4. Assurance Workbench

1. Click **“Open Remediation.”**
2. Deterministic proposer emits structured trades.
3. **Verify panel** applies trades to the effective portfolio and re-runs the rules engine.
4. If post-trade green → ✅✅✅; if still red → one retry.
5. Click **Approve** → `record_trades()` updates shadow state → status flips green → audit trail.
6. Export the remediation plan as an RFC-4180 CSV.

### 5. Hermes Mission Control (`/hermes`)

The book-wide autonomous loop, still inside the cage.

- **Scan Book** — pages through all 34,000 portfolios in batches of 500; gate-green proposals enter the queue.
- **Queue** — ranked by `FUM × severity`; only post-trade green/orange rows survive.
- **Book Score** — composite of alignment rate, acceptance rate, avg trades per fix, breaches remaining.
- **Remediation Strategy** — six tunable judgment variables in `strategy.yaml`.
- **Reflect** — proposes ONE strategy change from latest heartbeat + score.
- **Adopt** — human-gated writer; bumps version; archives prior snapshot to `history/vN.json`; writes audit entry.
- **Approve Batch** — applies queued rows through the same human gate as Workbench.
- **Rollback** — restore any archived strategy version; current version archived first.

Latest verified full-book scan (local):

```
34,000 scanned in 3.2 s
27,201 green
937 remediated
762 missed
5,100 skipped
avg_trades_per_fix: 2.66
```

### 6. Evidence Pack

A per-portfolio, one-click compliance proof artifact.

- Open from any portfolio detail page with **Generate Evidence Pack**.
- Backend endpoint `GET /api/evidence/portfolio/{client_id}` returns structured JSON.
- Backend endpoint `GET /api/evidence/portfolio/{client_id}/html` returns a complete, standalone, print-ready HTML page.
- The pack is **100% read-only** for this first cut: no state mutation, no audit-log write.
- Includes:
  - header with client ID, adviser, FUM, report day, generated timestamp and reference ID;
  - current compliance attestation with per-rule pass/fail table;
  - deterministic plain-English summary derived only from `rules_engine.check()`;
  - alignment history timeline and day-by-day status table;
  - remediation evidence from the immutable audit log;
  - determinism & control statement explaining that the rules engine is the final authority;
  - synthetic-data banner and footer with reference ID.
- `@media print` CSS keeps the banner visible, hides the print button, sets page margins and avoids internal page breaks in tables.
- Tested exports: A4 PDF with print backgrounds enabled.

---

## Where AI is (and is not)

### AI is used for

- **Translation / narrative** — turning deterministic rule output into plain English.
- **Hermes reflection** — proposing a single strategy-variable tweak.
- **Explain targeting** — grounded explanation of the rule that applies to a specific holding or metric.
- **Learning preference** — captured as versioned strategy history.

### AI is NOT used for

- Deciding compliance.
- Writing or editing mandate rules.
- Auto-executing trades or strategy changes.
- Generating the factual compliance attestation (Evidence Pack summary is deterministic).

---

## Run locally

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe generators/generate_data.py   # seeds data/aura.db with 34,000 portfolios
.venv/Scripts/uvicorn main:app --reload --port 8000

# frontend (other terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

With no `ANTHROPIC_API_KEY` the backend uses `MockLLM` (deterministic, offline). Set the key for real Claude narratives.

### Export the synthetic book to Excel

```bash
cd backend
.venv/Scripts/python.exe scripts/export_spreadsheet.py
```

Produces `ASSURE_Synthetic_34k_Book.xlsx` in the project root: 34,000 portfolios, all holdings, 8 mandate templates, price master, breach register, and day-0 book summary. All synthetic.

---

## Security & deployment notes

- **Admin endpoints** (`POST /admin/reset`) are open by default for local demos. In production, set `ADMIN_SECRET` on the backend and `NEXT_PUBLIC_ADMIN_SECRET_HINT` on the frontend; the reset button will then send `X-Admin-Secret` automatically.
- **CORS** defaults to permissive (`*`) for local development. Restrict it in production with `CORS_ALLOWED_ORIGINS=https://your-frontend.example.com`.
- **Frontend security headers** (CSP, X-Frame-Options, HSTS-style referrer policy, nosniff) are emitted from `next.config.js` on every route.
- **Explain-fetch races** in `BreachChips` and `HoldingsTable` are cancelled via `AbortController`, preventing stale results from appearing under the wrong rule or ticker.
- **CI** runs backend `pytest` and frontend typecheck/tests on every push via `.github/workflows/ci.yml`.

---

## Demo (60-second click-path)

See `docs/WALKTHROUGH.md` for the full script. In brief:

1. **Command Centre heatmap** — FUM-sized tiles with live status; summary bar reads the book.
2. **Market Panel** — tick/advance the virtual clock to watch market drift create breaches.
3. **Diagnosis** — AI narrative + breach chips + confidence line separating rule maths from advisory text.
4. **Explain targeting** — “?” on a holding sends the exact rule for that ticker/asset class/region.
5. **Workbench** — Open Remediation → Propose → Verify (rules engine re-checks shadow state) → Approve (human gate) → audit trail.
6. **Workbench CSV export** — RFC-4180 quoted fields for safe downstream use.
7. **/hermes Mission Control** — Scan Book → rules-engine-gated queue + Book Score → Reflect (one proposal) → Adopt (human gate, version bump, archive) → Approve Batch.
8. **Evidence Pack** — from any portfolio detail page, click **Generate Evidence Pack** to open a print-ready, regulator-ready compliance proof.

---

## Test

```bash
# backend
cd backend && .venv/Scripts/python.exe -m pytest -q
# 152 passed, 1 skipped

# frontend type check
cd frontend && npx tsc --noEmit

# frontend build
cd frontend && npx next build
# 5 app routes: /, /hermes, /portfolio/[id], /portfolio/[id]/workbench

# frontend unit tests
cd frontend && npx vitest run
# 3 passed

# E2E deep (from repo root)
cd /c/Users/point/projects/financialSimplicity/prototyping
python scripts/e2e_deep.py
# PASS: 23, FAIL: 0

# Evidence Pack regression (local)
python scripts/verify_evidence_regression.py
# 0 errors across Command Centre, Portfolio, Workbench, Hermes + red/orange/green evidence packs

# Evidence Pack regression (production)
FRONT_URL=https://aura-demo-rho.vercel.app \
API_URL=https://aura-demo-rho.vercel.app/api \
python scripts/verify_evidence_regression.py
# 0 errors

# Production tour regression
URL=https://aura-demo-rho.vercel.app python scripts/verify_tour_prod.py
# 0 errors, 6/6 tour steps reached
```

---

## Deploy

- **Frontend** → Vercel (`vercel.json` / `frontend/vercel.json`)
- **Backend** → Vercel serverless functions (`backend/Procfile`, `backend/requirements.txt`)

Set `ANTHROPIC_API_KEY` on Vercel as an env var only (never committed). The frontend proxies same-origin `/api/:path*` to the backend via `next.config` rewrites using a **server-only** `API_URL` env, so the backend URL is never baked into the client build.

Live URLs:

- Frontend: `https://aura-demo-rho.vercel.app`
- Health: `https://aura-demo-rho.vercel.app/api/health`
- Summary: `https://aura-demo-rho.vercel.app/api/portfolios/summary`
- Evidence Pack (red example): `https://aura-demo-rho.vercel.app/api/evidence/portfolio/c00011/html`
- Evidence Pack JSON (red example): `https://aura-demo-rho.vercel.app/api/evidence/portfolio/c00011`

If the demo state drifts to unrealistic levels, use `POST /api/admin/reset`; seed data is untouched.

---

## Verification state

- Backend tests: **152 passed, 1 skipped**
- Frontend tests: **3 passed**
- Frontend build routes: **5**
- Deep E2E: **23/23 PASS**
- Local Evidence Pack regression: **0 errors**
- Live Evidence Pack regression: **0 errors**
- Live tour regression: **0 errors, 6/6 steps**
- Latest Hermes full-book scan: **34,000 scanned in ~3.2 s, 27,201 green, 937 remediated, 762 missed, 5,100 skipped, 2.66 avg trades/fix**

---

## Why

> *“AI recommends. Assurance verifies.”*

ASSURE is the literal embodiment of that thesis: AI handles comprehension and proposal; a deterministic rules engine and a human verify and approve; everything is logged, explainable, reversible, and now exportable as a regulator-ready Evidence Pack.
