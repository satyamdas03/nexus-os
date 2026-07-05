# AURA Phase 2 — "The Self-Improving Assurance Engine" Design

**Date:** 2026-06-18
**Status:** Approved
**Base:** live Phase 1 at https://aura-demo-rho.vercel.app (do NOT rebuild).
**Goal:** Turn AURA from a one-portfolio assistant into a self-improving, book-wide remediation engine (Hermes) caged by deterministic assurance + a human approver.

## Decisions (locked)
1. **Hermes proposer = deterministic + strategy-driven.** `proposer.py` reads `strategy.yaml` and produces trades with no Claude call. Strategy mutations genuinely change output (unit test asserts). Claude only writes the one-line rationale + the "wants to evolve" reflection proposal. Rationale: makes self-improvement legible + instant + free; real-Claude-per-portfolio would be ~2min/scan and make strategy.yaml theater.
2. **All 5 steps, one session.**
3. **Ephemeral Render disk OK.** `state.json`, `hermes/history/`, `heartbeat.json` reset on redeploy. `strategy.yaml` seed committed to git; runtime files gitignored. Hit Reset before each live run.

## Safety cage (two-tier, enforced in code)
```
HERMES proposes (strategy.yaml) → RULES ENGINE verifies (mandate = law) → HUMAN approves → feeds HERMES reflection
```
- Mandate rules (per-portfolio `mandate` in portfolios.json) = law. Hermes never writes here.
- Remediation strategy (`agents/hermes/strategy.yaml`) = judgment. Reflection writes ONLY here.
- `reflect.py` single write fn refuses paths outside `strategy.yaml`/`history/`. Unit test asserts it cannot touch mandates.
- Every Hermes proposal gated by `rules_engine.check` before a human sees it. Non-compliant → discarded + logged as strategy "miss".

## Step 1 — Foundation: shadow state + green-persist + drift fix
- `backend/core/effective.py`: `effective_portfolio(p)` = seed holdings + applied trades (recompute units/cash). All reads (heatmap, diagnosis, triage, rules engine) use effective.
- `backend/data/state.json` (runtime, gitignored): `{applied_trades: {client_id: [{ticker, action, units, value, ts}]}}`.
- `approve` endpoint: apply proposed trades to state.json → recompute → real status flip (red→green because holdings changed). Heatmap/diagnosis read effective → persists on reload.
- `POST /admin/reset`: clears state.json (+ optional hermes history/heartbeat).
- Drift bug fix in `rules_engine.py` (POST-TRADE showed `drift: Equity 51.3% / 60.0% Breach` though 51.3<60) + unit test `51.3 < 60 ⇒ pass`.

## Step 2 — Phase-1 gaps
- `GET /portfolios/summary_ai`: Claude prose grounded in aggregate engine output (counts + top systemic pattern). Replaces static banner text; counts as sub-line. Grounding: only state engine-produced facts.
- "Explain this" per metric: `POST /portfolio/{id}/explain` with `metric` param → one-sentence popover on holdings rows.
- `POST /portfolio/{id}/verify`: verify arbitrary trades (enables manual edit + live re-check + Hermes row expand).
- WorkbenchTable: editable units/value inputs → live VerifyPanel re-check.
- Before/after red→green mini-blocks beside VerifyPanel.
- AllocationDonut: hatch/outline offending (over-cap) slices.
- Heatmap: wire adviser + asset-class `onChange`; add "Needs action today" (red+orange).

## Step 3 — Hermes core (`backend/agents/hermes/`)
- `strategy.yaml` (committed seed) — vars each with value + rationale: `breach_priority_order`, `preferred_trim_method`, `replacement_preference`, `min_trade_size`, `max_trades_per_portfolio`, `cash_buffer_target`.
- `proposer.py` — deterministic, strategy-driven. Input: effective portfolio + rules_result + strategy. Output: proposed trades (structured). Strategy-var change ⇒ different output (tested).
- `loop.py` `scan_book()`: effective state all 40 → for each red/orange: proposer → gate via rules engine → keep compliant, log misses → ranked queue (FUM×severity) → `heartbeat.json`. `POST /hermes/scan`.
- `score.py`: book goals (≥95% aligned, ≤N breaches, minimal trades) + composite (alignment rate, avg trades/fix, acceptance rate).
- `reflect.py`: `--fallback` (deterministic rule-based) + `--hermes` (Claude proposes one strategy-var change w/ reasoning). Writes ONLY strategy.yaml. Surfaced as "Hermes wants to evolve" → human Adopt/Dismiss → bump version → archive `history/vN.json` → audit. Never self-adopts.
- `history/` + `heartbeat.json`: runtime, gitignored.
- `routers/hermes.py`: `POST /hermes/scan`, `GET /hermes/strategy`, `POST /hermes/reflect` (returns suggestion), `POST /hermes/adopt` (apply mutation, version, archive, audit), `GET /hermes/heartbeat`, `GET /hermes/history`.

## Step 4 — Hermes UI (new Screen 4 `/hermes`)
- Status header: heartbeat (last scan, scanned, compliant, discarded), strategy version, alignment score + trend.
- "HERMES: Scan the Book" primary button → scanning animation → populate queue.
- Remediation Queue table: client, FUM, status, #trades, Assurance ✅, Hermes confidence, rationale. Row expandable → exact trades + per-rule VerifyPanel.
- Per-row Approve/Modify/Reject + "Approve all verified" (confirm). Approve → apply shadow state → flip green → audit.
- "Hermes is learning" panel: strategy vars+rationales, live evolve suggestion Adopt/Dismiss, version-history timeline (v1→v2→v3, what/when/why/who, reversible).
- Assurance-cage diagram legend.

## Step 5 — polish + docs + deploy
- Reset control reachable (admin/header).
- Safety microcopy throughout.
- Update `docs/WALKTHROUGH.md` (6-min Phase 2 script) + `README.md` (Hermes arch + cage diagram + synthetic note).
- Redeploy Render + Vercel; browser smoke: reset → scan → verify → approve → green persists → reflect → adopt → version bump.

## API contracts (so frontend + backend agents agree)
- `POST /hermes/scan` → `{heartbeat: {scanned_at, portfolios_scanned, compliant_proposals, discarded}, queue: [{client_id, client_name, fum, status, trades: [...], verify: <RulesResult>, confidence, rationale}], score: {...}}`
- `GET /hermes/strategy` → `{version, variables: {name: {value, rationale}}, last_scan_score}`
- `POST /hermes/reflect` → `{suggestion: {variable, from, to, reason} | null, mode}`
- `POST /hermes/adopt` `{variable, to, reason}` → `{ok, version, archived_to}`
- `POST /portfolio/{id}/verify` `{trades: [...]}` → `<RulesResult>`
- `POST /portfolio/{id}/explain` `{metric?}` → `{narrative, ...}`
- `POST /admin/reset` → `{ok, cleared: [...]}`

## Testing
- Drift fix test; effective_portfolio apply→flip test; proposer strategy-sensitivity test; reflect mandate-guard test; Hermes scan integration test.

## File map
```
backend/core/effective.py (NEW)            backend/core/rules_engine.py (drift fix)
backend/data/state.json (NEW, gitignored)  backend/agents/hermes/{__init__,proposer,loop,score,reflect}.py + strategy.yaml (NEW)
backend/agents/hermes/{history/,heartbeat.json} (NEW, gitignored)
backend/routers/hermes.py (NEW)            backend/routers/admin.py (NEW)
backend/routers/{portfolios,actions}.py (summary_ai, verify, apply-trades, explain-metric)
frontend/src/app/hermes/page.tsx (NEW)     frontend/src/components/hermes/* (NEW)
frontend/src/components/{WorkbenchTable,AllocationDonut,Heatmap}.tsx (edits)
frontend/src/lib/{api,types}.ts (hermes endpoints/types)
docs/WALKTHROUGH.md, README.md (updates)   backend/tests/* (new tests)
```

## Execution
Hybrid: drive interdependent core edits inline (foundation + wiring touch shared files — parallel subagents would conflict); fan out parallel agents on disjoint new-file chunks (hermes backend module, hermes frontend screen+components, docs, tests) against the fixed API contracts above; integrate + build + deploy + browser-smoke inline; final adversarial review via workflow.