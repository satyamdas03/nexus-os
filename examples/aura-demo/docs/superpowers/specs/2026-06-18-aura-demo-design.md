# AURA — Assurance, Understanding, Remediation Agent
## Design Spec — 2026-06-18

**Status:** Approved. Build ready.
**Audience:** Kevin (COO) + technical/product team at Financial Simplicity Pty Ltd.
**Data:** Synthetic/public only. Never real FS data.

---

## 0. Purpose

AURA is an AI layer on top of a portfolio-assurance platform. It makes the platform intuitive, explainable, and semi-automated — **with a human in the loop for every consequential action.**

It tells one continuous story: a client portfolio goes **RED (breaching) → UNDERSTOOD (AI explains why, in plain English) → REMEDIATED (AI proposes compliant trades) → GREEN (aligned)**, with a human approving every step and a full audit trail recorded.

**Guiding philosophy:** *"AI Can Recommend. Assurance Verifies."* AI does comprehension + proposal; a deterministic rules engine + a human verify and approve; everything is logged and explainable.

This is the NeuralQuant pattern (import → multi-agent analysis → hallucination-guard → recommendation → human approval → audit) transplanted into the wealth-management-assurance domain. It is the literal embodiment of the "AI recommends, assurance verifies" thesis and of conformal-prediction thinking (knowing what is certain vs advisory).

---

## 1. Scope (V1)

Full spec, built in this order, all in V1:

1. Synthetic data generator + `rules_engine.py` (deterministic core).
2. Backend API (FastAPI routers).
3. Screen 1 — Heatmap.
4. Screen 2 — Diagnosis (the screen Kevin said is unreadable).
5. Screen 3 — Workbench.
6. Polish demo click-path.
7. Hermes-style learning loop (`reflect.py`) — in-scope, not deferred.
8. Deploy to Render + Vercel; one shareable URL.

Deferred / out of scope: multi-user auth, real data integration, production hardening beyond demo posture.

---

## 2. Tech Stack

- **Frontend:** Next.js (App Router) + React + TypeScript + Tailwind CSS + recharts.
- **Backend:** FastAPI (Python), modular routers, mirror NeuralQuant structure.
- **LLM:** Anthropic Claude Sonnet via API. Key in `ANTHROPIC_API_KEY` env var. Behind a provider interface so `MockLLM` can be substituted for tests/offline.
- **Data:** Synthetic. ~40 fake client portfolios. JSON/SQLite on backend; no external DB.
- **Audit:** Append-only JSONL (`audit.jsonl`), mirroring Hermes `hypotheses.jsonl` pattern.
- **Deploy:** Render (backend) + Vercel (frontend).
- **Repo:** monorepo with `/frontend` and `/backend`.

---

## 3. Architecture

```
[Next.js 3 screens] ←HTTP→ [FastAPI routers] → [agents/: explain, remediate, reflect]
                              ↓                    ↑ grounded against
                      [rules_engine.py]  ← source of truth (deterministic)
                              ↓
                      [synthetic data: 40 portfolios + mandates]
                              ↓
                      [audit.jsonl — append-only]
```

### The contract that locks the parallel build

`rules_engine.py` exposes:

```python
def check(portfolio: Portfolio, mandate: Mandate) -> RulesResult
```

where

```python
RulesResult = {
  status: "green" | "orange" | "red",
  breaches: [Breach],            # only red-level
  watches: [Breach],            # orange-level drift
  per_rule: [{
    rule: str,
    pass: bool,
    current: float | list,
    limit: float | list,
    offending_holdings: [str],   # tickers
    severity: "red" | "orange"
  }]
}
Breach = {
  rule: str,
  current: float | list,
  limit: float | list,
  offending_holdings: [str],
  severity: "red" | "orange",
  plain: str                     # one-line reason, e.g. "Tech 34% > 25% cap"
}
```

Every agent and every screen consumes `RulesResult`. Nothing else defines compliance. This is the stable interface the workflow agents build against.

---

## 4. Deterministic Core (source of truth)

### `generate_data.py` → `portfolios.json`

40 clients. Each:

```python
Portfolio = {
  client_id: str,
  client_name: str,             # fake
  adviser: str,                 # one of ~5 names
  fum: float,                   # $200k–$15M, skewed for treemap variety
  holdings: [{ticker, name, asset_class, sector, units, price, market_value}],
  cash: float,
  mandate: Mandate
}
Mandate = {
  max_asset_class_weight: {"Equity": 0.80, "Crypto": 0.0, "Bonds": 0.40, "Cash": 0.20, ...},
  max_sector_weight: {"Technology": 0.25, "Healthcare": 0.30, ...},
  approved_universe: [str],      # allowed tickers; some ban crypto, some ban single stocks
  max_single_holding: float,    # e.g. 0.10
  min_cash: float,               # e.g. 0.02
  target_allocation: {...},     # for drift detection
  drift_tolerance: float        # e.g. 0.05
}
```

**Universe:** SPY, QQQ, AAPL, MSFT, NVDA, AMZN, XLK, XLV, XLF, TLT, GLD, BTC, ETH, AVAX. Hardcoded price snapshot — no live data.

**Distribution (deliberate):** ~10% red (breach), ~15% orange (drift), rest green. Injected by perturbing generated weights: NVDA run-up pushing tech over cap, crypto holdings in no-crypto mandates, single-stock concentration, sub-min cash.

### `rules_engine.py` — pure functions, no I/O

Rules:
- `max_asset_class_weight` — weight per asset class ≤ limit.
- `max_sector_weight` — weight per sector ≤ limit.
- `approved_universe` — every holding ticker ∈ allow-list.
- `max_single_holding` — any single holding weight ≤ limit.
- `min_cash` — cash / total ≥ limit.
- `drift` — |weight − target| ≤ tolerance → orange (watch, not breach).

Each rule returns a `per_rule` entry with `pass`, `current`, `limit`, `offending_holdings`, `severity`. `status` = worst severity across rules. **This module is the only thing that colours a block or verifies a remediation. The LLM never overrides it.**

---

## 5. AI Agents (`backend/agents/`)

All agents receive `RulesResult` as grounding context + instruction: *only describe/act on breaches the engine flagged; never invent.* This is the NeuralQuant hallucination-guard pattern.

### `explain.py` — Explainer Agent
- **Input:** portfolio + mandate + RulesResult.
- **Output:** plain-English assurance narrative (2–4 sentences, the "breaching in 2 ways" style) + structured breach summaries.
- **Constraint:** may only reference `RulesResult.breaches` and `RulesResult.watches`. Must not invent rules or numbers.

### `remediate.py` — Remediation Agent
- **Input:** portfolio + mandate + RulesResult.
- **Output:** proposed trades, structured JSON:
  ```json
  [{"ticker": "...", "action": "buy|sell", "units": 0, "value": 0, "rationale": "..."}]
  ```
- **Constraint:** trades must be within `approved_universe` and respect `max_single_holding`, `min_cash`, etc.
- **Closed verify loop:** backend simulates the resulting portfolio → re-runs `rules_engine.check` → if any red/orange remains, **one retry** asking the agent to adjust → final `VerificationResult` shown to user. Max 1 retry. If still non-compliant after retry, show partial + "manual adjust required."

### `reflect.py` — Hermes Learning Loop (V1, in-scope)
See §7.

---

## 6. Three Screens

### Screen 1 — Portfolio Heatmap (`/`) — "Command Centre"
- Treemap (recharts), block size ∝ FUM, colour from `rules_engine` status (green/orange/red).
- Top AI summary bar: Claude over aggregate state — "38 of 45 aligned. 4 breached, 3 need attention. Largest exposure: tech concentration across 5 portfolios driven by NVDA run-up. Estimated remediation: 12 trades."
- Filters: adviser, breach severity, asset class, needs-action-today.
- Triage sort: order red/orange by FUM × severity.
- Hover tooltip: client name, FUM, status, one-line reason (engine's top breach `plain`).
- Click block → Screen 2.

### Screen 2 — Client Detail (`/portfolio/[id]`) — "Diagnosis"
- Holdings table: ticker, name, units, price, market value, weight %.
- Cash position + total portfolio value.
- Donut: allocation by asset class, aligned vs misaligned portions visually distinct.
- Performance line graph (synthetic series).
- **Narrative panel** at top (Explainer agent output).
- **Breach badges/chips:** each breach a clickable chip ("Tech 34% > 25% cap", "AVAX not in approved list"), severity-coloured. Click → highlights offending holdings in table.
- **"Explain this" button** on every metric → Claude one-liner (directly answers "I don't understand what I'm looking at").
- **Confidence/assurance line:** tags each check deterministic (rule maths, 100%) vs AI-inferred (advisory).
- Go to Workbench.

### Screen 3 — Remediation Workbench (`/portfolio/[id]/workbench`) — "Treatment"
- Editable trade table: holding, current weight, proposed trade (buy/sell/units), trade value, resulting weight, P/L.
- Manager can manually edit any number/trade.
- **"Propose a fix" button** → Remediation agent + closed verify loop → verification panel ✅/❌ per rule.
- **Before/after heatmap mini-state** for this portfolio (red → green).
- **Human-in-the-loop:** Approve / Modify buttons. No auto-execution.
- On Approve → append `audit.jsonl` + flip block green.
- Full audit trail visible: every AI suggestion, human decision, rule-check result, with timestamp + rationale.

---

## 7. The Verify Loop + Confidence Line (the thesis, made visible)

The single most important conceptual point. Two-tier trust, explicit in UI:

- **Deterministic checks** (rules engine): ✅/❌ + "100% — rule maths". These decide compliance.
- **AI outputs** (narrative, proposals): tagged "advisory — AI-inferred, verify before acting".

Remediation flow: **AI proposes → engine verifies → human approves.** LLM is never the final word on compliance. This is "AI recommends, assurance verifies" + the conformal certain-vs-advisory split rendered as UI.

---

## 8. Hermes Learning Loop (`reflect.py`)

Mirror Hermes: change **one rule-of-thumb at a time**, written rationale + version history, human-approved.

- **Logged:** every Approve/Modify decision → `audit.jsonl` entry with breach type + the manager's actual trade choices (e.g. tech-breach → trimmed NVDA not MSFT).
- **Breach type** = the `rule` field of the breach (e.g. `max_sector_weight:Technology`). Decisions are grouped by breach type for pattern detection.
- **Surfaced:** after N (default 5) decisions of a given breach type, detect a preference pattern. Output a *suggestion chip* on the Workbench: "In 5 of last 5 tech-breach cases you trimmed NVDA over MSFT — default to that?"
- **Adopt:** human clicks → becomes a soft default for future proposals, version bump + rationale written to `preferences.jsonl` (second append-only file, separate from `audit.jsonl`).
- **Dismiss:** human clicks → logged, no change.
- **Never auto-applies.** Suggests only.

Demo script line: *"And over time it learns your team's preferences — but only ever suggests, never overrides."*

---

## 9. Audit Log

Append-only JSONL `backend/data/audit.jsonl`. Schema:

```json
{
  "timestamp": "ISO-8601",
  "client_id": "...",
  "action_type": "explain | remediate_propose | verify | approve | modify | reflect_suggest | reflect_adopt | reflect_dismiss",
  "actor": "ai | human | engine",
  "tier": "deterministic | advisory",
  "payload": { ... },
  "rationale": "...",
  "rules_check_result": "RulesResult | null",
  "version": "0.1.0"
}
```

Mirror Hermes `hypotheses.jsonl`. Audit write failure blocks the Approve (never silently lose a record).

---

## 10. API Endpoints

```
GET  /portfolios                 → heatmap data (all portfolios + status)
GET  /portfolio/{id}              → detail (portfolio + holdings + RulesResult)
GET  /portfolio/{id}/check        → rules result only
POST /portfolio/{id}/explain      → Explainer agent narrative
POST /portfolio/{id}/remediate    → Remediation agent proposal + verify loop result
POST /portfolio/{id}/approve      → write audit log, flip status green
POST /portfolio/{id}/reflect      → surface learning suggestion (if pattern ready)
GET  /audit                       → audit log tail (for the trail panel)
```

---

## 11. Error Handling

- LLM call failure → fall back to deterministic-only render (engine result shows; narrative panel shows "AI unavailable — showing rule facts only"). Demo never breaks on a flaky API call.
- Remediation verify loop failure (still non-compliant after retry) → show partial result + "AI proposal did not fully resolve — manual adjust required." Honest, not hidden.
- Audit write failure → block Approve. Never silently lose an audit record.
- Frontend network failure → show last-known status with a "reconnecting" badge; rules-engine-derived data remains readable.

---

## 12. Testing

- `rules_engine` unit tests: green/orange/red cases per rule. Fully testable without LLM.
- Agent grounding tests: `MockLLM` + assert agent only references engine-flagged breaches (hallucination-guard test).
- Verify-loop test: feed a non-compliant proposal, assert retry fires; assert final result carries honest "manual adjust required" when still failing.
- Endpoint smoke tests (13/13 style like NeuralQuant).
- Audit log append + schema test.
- Reflect loop test: seed N decisions of one pattern → assert suggestion fires; assert Adopt writes `preferences.jsonl` with version bump.

---

## 13. Design Principles (non-negotiable)

1. **Trust-first aesthetic:** calm, professional, finance-grade. Muted palette, clear typography, generous spacing. Safe, not flashy — it's people's money.
2. **Determinism is the source of truth:** the LLM never decides compliance. The rules engine does. Always show the deterministic check alongside any AI output.
3. **Human-in-the-loop everywhere:** no action auto-executes. Every consequential step has explicit human Approve/Modify.
4. **Everything explainable + audited:** every AI claim traceable to a rule-engine fact; every decision logged with who/what/why/when.
5. **Plain English over jargon:** default to clear sentences a non-technical COO can read.
6. **Don't touch the legacy concept:** AURA is a layer on top, not a replacement. It reads their data and renders it better — it does not rebuild the core engine.

---

## 14. Demo Script (5-minute click-path)

1. Open on Heatmap. AI summary bar reads the book aloud. Point out red blocks. *"This is the command centre — and unlike today, it tells you what's wrong before you click anything."*
2. Click biggest red block → Diagnosis. Plain-English narrative explains breaches instantly. *"Kevin said he sometimes can't tell what he's looking at — this fixes exactly that."*
3. Click a breach chip → offending holdings highlight. Click "Explain this" on a metric → one-liner.
4. Go to Workbench. Click "Propose a fix." AI proposes minimal compliant trades. *"AI recommends..."*
5. Verification panel lights up — deterministic engine re-checks every rule: ✅✅✅. *"...assurance verifies. The AI doesn't get the final say — this rules engine does."*
6. Click Approve. Block flips green. Audit log entry appears with timestamp + rationale. *"Human in the loop, fully audited."*
7. Show learning panel: *"And over time it learns your team's preferences — but only ever suggests."*
8. Close: *"Today this is three slow, manual, spreadsheet-bound screens. Same data, same accuracy, same human control — made intuitive, explained, semi-automated. That's the V1-to-V2 jump."*

---

## 15. Build + Deploy Plan

1. This spec written + committed.
2. `/gstack` scaffolds Next.js+FastAPI monorepo + Render/Vercel deploy config.
3. `/workflows` fan-out per the `RulesResult` contract:
   - Agent A: data generator + `rules_engine.py` + unit tests.
   - Agent B: backend routers + 3 agents (explain, remediate, reflect) + audit log.
   - Agent C: Screen 1 Heatmap.
   - Agent D: Screen 2 Diagnosis.
   - Agent E: Screen 3 Workbench.
   - Agent F: Hermes `reflect.py` loop + suggestion chip UI.
   Each verifies against the `RulesResult` contract before completion.
4. Wire real Claude (`ANTHROPIC_API_KEY`), polish demo click-path.
5. Deploy → one shareable URL + README + 60-second walkthrough script.

---

## 16. Deliverables

- Working deployed demo at a single URL.
- 60-second loom-style written walkthrough script.
- README.md: philosophy ("AI recommends, assurance verifies"), architecture, synthetic-data note.
- Clean, commented code talkable-through in an interview.

---

## 17. Emphasis When Presenting (notes, not code)

- Not a toy — the exact NeuralQuant pattern transplanted into their domain. Already built and shipped this engine.
- Deterministic rules engine as source of truth + AI as comprehension/proposal layer = literal embodiment of "AI recommends, assurance verifies" + conformal-prediction research (certain vs advisory).
- Hermes learning loop = the self-improving idea pitched to Kevin, made concrete and kept human-approved.
- Directly fixes the pain Kevin named: "I sometimes don't understand what I'm looking at."
- Respects their reality: a layer on a great legacy foundation they don't want to disturb — not a rebuild.
- Frame humbly: rough proof-of-concept on public/synthetic data, expecting it's naive in places only their domain experts can see.