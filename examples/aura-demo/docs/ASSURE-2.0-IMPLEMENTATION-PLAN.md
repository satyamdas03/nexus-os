# ASSURE 2.0 — 90-Day Implementation Plan
## From aura-demo hardening to the first external-ready assurance kernel

**Branch:** `feat/aura-demo-improvements` in `satyamdas03/nexus-os`  
**Goal:** Turn the hardened aura-demo into the foundation of the ASSURE Graph.

---

## Sprint 0 — Stabilize (Week 1)

### Deliverables
1. All aura-demo CI checks pass on the branch.
2. Security review items closed (CORS, admin secret, headers, audit script).
3. Memory architecture for Bull/NEXUS OS updated if needed.

### Files to verify
- `.github/workflows/ci.yml`
- `.github/workflows/keep-warm.yml`
- `frontend/next.config.js`
- `backend/main.py`
- `backend/routers/admin.py`
- `scripts/e2e_audit.py`
- `README.md`, `backend/.env.example`, `frontend/.env.local.example`

---

## Sprint 1 — Extract the Kernel (Weeks 2–3)

### Goal
Move `core/rules_engine.py` from an aura-demo internal module into a reusable, versioned package.

### New structure
```
examples/aura-demo/
  packages/
    assure-kernel/
      pyproject.toml
      assure_kernel/
        __init__.py
        schema.py        # Mandate, Portfolio, RulesResult pydantic models
        engine.py        # pure check() ported from rules_engine.py
        grammar.py       # rule type registry
        version.py       # semantic version
      tests/
        test_engine.py   # property-based + adversarial tests
```

### Tasks
1. Define Pydantic models for `Portfolio`, `Mandate`, `RulesResult`.
2. Port `check()` with zero behavioral change.
3. Add rule-type registry so new rules can be registered declaratively.
4. Property-based tests with Hypothesis: random portfolios, random mandates, assert invariants.
5. Backward-compatibility shim in `backend/core/rules_engine.py` re-exporting from the kernel.

### Acceptance Criteria
- `python -m pytest packages/assure-kernel/tests` passes.
- aura-demo backend tests still pass using the shim.
- Kernel can be installed independently: `pip install ./packages/assure-kernel`.

---

## Sprint 2 — Declarative Mandate DSL (Weeks 3–4)

### Goal
Replace hardcoded JSON/Python mandates with a versioned, regulator-reviewable rule language.

### Schema sketch (YAML/JSON)
```yaml
version: "1.0"
identity:
  client_id: "C-001"
  adviser: "Jane Doe"
rules:
  - type: max_asset_class_weight
    asset_class: Equity
    limit: 0.60
  - type: max_sector_weight
    sector: Technology
    limit: 0.25
  - type: max_single_holding
    limit: 0.10
  - type: min_cash
    limit: 0.05
  - type: approved_universe
    tickers: [AAPL, MSFT, BHP, CBA, ...]
  - type: esg_exclusions
    tickers: [WEAP, COAL, ...]
  - type: max_region_weight
    region: Emerging Markets
    limit: 0.15
  - type: min_liquid_pct
    limit: 0.80
```

### Tasks
1. Implement `Mandate.from_yaml(path)` and `.to_yaml()`.
2. Migrate demo data to DSL.
3. Add rule documentation renderer (human-readable explanation per rule).
4. Version mandates in the SQLite schema.

### Acceptance Criteria
- All demo portfolios load from DSL files.
- Rule documentation page in frontend.
- Invalid DSL fails fast with clear errors.

---

## Sprint 3 — Kernel API (Weeks 4–6)

### Goal
Expose the kernel as a standalone service with `/check`, `/verify`, `/evidence`, `/explain`.

### New module
```
packages/assure-kernel/
  assure_kernel/
    api.py          # FastAPI router
    service.py      # business logic layer
    explain.py      # grounded explainer (no LLM required; deterministic templates)
    evidence.py     # JSON/PDF evidence pack builder
```

### Endpoints
- `POST /v1/check` — full rules check.
- `POST /v1/verify` — what-if trade verification.
- `POST /v1/evidence` — evidence pack (JSON + HTML).
- `POST /v1/explain` — deterministic, grounded explanation.

### Tasks
1. Build FastAPI service with OpenAPI docs.
2. Add request/response logging.
3. Add API key auth middleware (pluggable).
4. Dockerize the kernel.
5. Add load tests (≥1,000 RPS check throughput).

### Acceptance Criteria
- `curl` examples work against Docker container.
- Response latency P95 < 50ms for a 50-holding portfolio.
- 100% test coverage on API contracts.

---

## Sprint 4 — Synthetic Reality Engine v0.1 (Weeks 6–8)

### Goal
Generate infinite synthetic portfolios/markets to stress-test the kernel and AI agents.

### New module
```
packages/assure-kernel/
  assure_kernel/
    synthetic/
      generator.py   # portfolio + market generators
      scenarios.py   # regime definitions
      adversary.py   # auto-find breaches and AI failures
      report.py      # HTML/JSON stress report
```

### Capabilities
1. Generate 10,000 portfolios matching real-world distributions.
2. Apply historical and synthetic stress regimes.
3. Run AI remediation agent against every breach; record resolution rate.
4. Detect divergence between engine verdicts and agent claims.

### Acceptance Criteria
- CI runs synthetic suite on every PR.
- Report shows breach type distribution and agent resolution rate.
- Any regression in engine/agent agreement blocks merge.

---

## Sprint 5 — Conversational Assurance v0.1 (Weeks 8–10)

### Goal
Add a grounded, voice/text-capable explainer to aura-demo.

### Components
1. **Backend:** `agents/conversational.py` — takes natural-language query + rules result, returns grounded answer.
2. **Frontend:** Chat/voice drawer on portfolio detail page.
3. **Safety:** Every answer cites the exact `per_rule` row it is grounded in.

### Example queries
- "Why is this portfolio red?" → cites breach rows.
- "What happens if I sell 100 AAPL?" → calls `/verify` and explains result.
- "Can I increase tech exposure?" → checks mandate and explains constraint.

### Acceptance Criteria
- Voice input works in supported browsers.
- LLM cannot hallucinate rules; all claims linked to engine output.
- Eval set of 50 questions with expected grounded answers.

---

## Sprint 6 — Hermes 2.0 + Proactive Drift Prevention (Weeks 10–12)

### Goal
Upgrade Hermes from reactive breach scanner to proactive drift prevention engine.

### New behaviors
1. Predict likely breaches 5–30 days ahead using price trajectory + drift tolerance.
2. Propose trades that keep portfolios green *before* they breach.
3. Policy-driven auto-approval for low-risk actions inside a tolerance band.
4. Preference learning persists per client/adviser.

### Tasks
1. Add drift prediction module in `core/market.py`.
2. Extend Hermes loop with "prevent" mode.
3. Add policy config UI in frontend.
4. Simulation mode: run Hermes for 100 virtual days, measure breach prevention rate.

### Acceptance Criteria
- Simulation shows ≥50% reduction in breach incidence vs. reactive mode.
- All auto-approved actions are still logged and reversible.

---

## Sprint 7 — Packaging and Pilot Prep (Weeks 12–13)

### Deliverables
1. Docker Compose stack: kernel + aura-demo backend + frontend + nginx.
2. Deployment guide for AWS/GCP/Azure.
3. SOC 2 readiness checklist.
4. Pilot onboarding template.
5. Whitepaper draft in `docs/whitepaper/`.

---

## Cross-Cutting Concerns

### Security
- No AI endpoint can mutate portfolio state without human approval.
- Admin endpoints require `ADMIN_SECRET`.
- All evidence packs are signed with a deterministic reference ID.

### Observability
- Prometheus metrics on check latency, breach counts, agent resolution rate.
- Structured logs for every assurance decision.

### Compliance
- Every rule change is versioned.
- Every remediation is audited.
- Synthetic test reports are retained for regulator review.

---

## How to Start Today

1. Review and merge the current `feat/aura-demo-improvements` improvements.
2. Create `packages/assure-kernel/` and port `rules_engine.py`.
3. Run the existing test suite to establish the baseline.
4. Open a tracking issue for each sprint above.
5. Recruit pilot adviser/platform for Sprint 1 feedback.
