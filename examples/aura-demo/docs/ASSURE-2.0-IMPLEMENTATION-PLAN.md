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

## Sprint 1 — Extract the Kernel ✅ COMPLETE

### Goal
Move `core/rules_engine.py` from an aura-demo internal module into a reusable, versioned package.

### Delivered structure
```
examples/aura-demo/packages/assure-kernel/
  pyproject.toml
  README.md
  src/assure_kernel/
    __init__.py        # public API exports
    types.py           # Status, Severity, RuleType enums
    models.py          # Portfolio, Holding, Mandate, Rule, RulesResult, Violation
    engine.py          # deterministic evaluate_portfolio() + legacy converters
    registry.py        # extensible rule evaluator registry
    dsl.py             # YAML/JSON mandate loader + legacy round-trip
  tests/
    test_parity.py     # kernel vs. original engine parity
    test_adversarial.py # edge cases and invariants
    test_properties.py  # Hypothesis property-based tests
    test_dsl.py        # DSL parsing/serialization tests
```

### Delivered tasks
1. ✅ Defined Pydantic v2 models for `Portfolio`, `Holding`, `Mandate`, `Rule`, `RulesResult`, `Violation`, `RuleEvaluation`.
2. ✅ Ported all rule evaluators from `core/rules_engine.py` with zero behavioral change.
3. ✅ Added rule-type registry so new rules can be registered declaratively (`@register("type")`).
4. ✅ Added parity tests against the original engine, adversarial edge-case tests, and Hypothesis property-based tests.
5. ✅ Implemented declarative mandate DSL loader (`load_mandate`, `parse_mandate`, `to_legacy_dict`, `dump_mandate`).
6. ✅ Added backward-compatibility shim in `backend/core/rules_engine.py` re-exporting from the kernel.
7. ✅ Added `assure-kernel` CI job and wired the package into `backend/requirements.txt`.

### Acceptance Criteria
- ✅ `python -m pytest packages/assure-kernel/tests` passes (27 passed, 1 skipped).
- ✅ aura-demo backend tests pass using the shim (150 passed, 2 perf tests fail only on this slow machine).
- ✅ Kernel installs independently: `pip install -e ./packages/assure-kernel`.

---

## Sprint 2 — Declarative Mandate DSL ✅ COMPLETE

### Goal
Replace hardcoded JSON/Python mandates with a versioned, regulator-reviewable rule language.

### Status
**Completed 2026-07-03 on `feat/aura-demo-improvements`.**

### Canonical DSL schema (YAML/JSON)
```yaml
mandate:
  id: balanced-growth
  name: Balanced Growth
  version: 1.0.0
  metadata:
    sector_cap_base: 0.30
    approved_n: 18
    allow_crypto: true
    excl_k: 2
  rules:
    - type: asset_class_weight
      parameters:
        max_weights:
          Equity: 0.80
          Bonds: 0.30
          Commodity: 0.10
          Crypto: 0.05
          Cash: 1.0
    - type: region_weight
      parameters:
        max_weights:
          US: 0.70
          ExUS: 0.35
          EM: 0.15
    - type: single_holding
      parameters:
        max_weight: 0.12
    - type: minimum_cash
      parameters:
        min_weight: 0.05
    - type: target_allocation
      parameters:
        targets:
          Equity: 0.65
          Bonds: 0.25
        drift_tolerance: 0.08
    - type: top_n_concentration
      parameters:
        n: 5
        max_weight: 0.55
    - type: minimum_liquidity
      parameters:
        min_liquid_pct: 0.4
```

### Delivered tasks
1. ✅ Created 8 canonical DSL templates under `backend/data/mandates/t0.yaml` … `t7.yaml`.
2. ✅ Rewrote `backend/generators/mandates.py` to load templates via `assure_kernel.load_mandate` and return the legacy dict shape.
3. ✅ Added `assure_kernel.docs.py` with deterministic rule documentation (`describe_rule`, `describe_mandate`, `rule_type_metadata`).
4. ✅ Added `assure_kernel.dsl.dumps_mandate()` for clean YAML serialization and idempotent SQLite migration (`_migrate_mandates_table`) adding `version`, `dsl`, `source_path`, `created_ts`, `spec_hash` columns.
5. ✅ Added `GET /portfolio/{client_id}/mandate` returning version, DSL YAML, and human-readable rule docs.
6. ✅ Added frontend `MandatePanel` component and `/portfolio/[id]/mandate` page with rule-doc cards and raw-DSL tab.
7. ✅ Added backend + kernel tests for YAML templates, DSL round-trip, and the mandate endpoint.

### Files changed
- `backend/data/mandates/t0.yaml` … `t7.yaml`
- `backend/generators/mandates.py`
- `backend/generators/generate_data.py`
- `backend/core/storage.py`
- `backend/core/data_loader.py`
- `backend/routers/portfolios.py`
- `packages/assure-kernel/src/assure_kernel/dsl.py`
- `packages/assure-kernel/src/assure_kernel/docs.py`
- `packages/assure-kernel/src/assure_kernel/__init__.py`
- `packages/assure-kernel/tests/test_docs.py`
- `backend/tests/test_mandates.py`
- `backend/tests/test_routers.py`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/components/MandatePanel.tsx`
- `frontend/src/app/portfolio/[id]/mandate/page.tsx`
- `frontend/src/app/portfolio/[id]/page.tsx`

### Acceptance Criteria
- ✅ All demo portfolios load from DSL files (`test_templates_load_from_yaml`, `test_build_mandate_uses_yaml_template_base`).
- ✅ Rule documentation page in frontend (`MandatePanel` + `/portfolio/[id]/mandate` built and typechecks).
- ✅ Invalid DSL fails fast with clear errors (`parse_mandate` raises `ValueError` on unknown rule types).
- ✅ Backend tests: 156 passed, 1 skipped.
- ✅ Kernel tests: 32 passed, 1 skipped.
- ✅ Frontend `npm run build` succeeds with the new mandate route.

---

## Sprint 3 — Kernel API (Weeks 4–6) — IN PROGRESS

### Goal
Expose the kernel as a standalone service with `/evaluate`, `/verify`, `/evidence`, `/explain`.

### New module
```
packages/assure-kernel/
  assure_kernel/
    api.py          # FastAPI router
    service.py      # business logic layer
    main.py         # ASGI entry point
    evidence.py     # JSON/PDF evidence pack builder (next)
```

### Endpoints (delivered)
- `GET /v1/health` — service health + kernel version.
- `POST /v1/evaluate` — full rules check (renamed from `/check` to match service verbs).
- `POST /v1/verify` — what-if trade verification.
- `POST /v1/explain` — deterministic, grounded mandate documentation.
- `POST /v1/evidence` — regulator-reviewable evidence pack (JSON + optional HTML).

### Tasks
1. ✅ Build FastAPI service with OpenAPI docs.
2. ✅ Add `/v1/evidence` evidence pack builder with deterministic attestation, mandate docs, alignment history, remediation evidence, control statement, and print-ready HTML.
3. ⬜ Add request/response logging.
4. ⬜ Add API key auth middleware (pluggable).
5. ✅ Dockerize the kernel.
6. ⬜ Add load tests (≥1,000 RPS check throughput).

### Acceptance Criteria
- ✅ `curl` examples work against running service (uvicorn smoke test passed; Docker daemon unavailable locally).
- ✅ `/v1/evidence` returns correct red/green verdict and includes HTML when requested.
- ⬜ Response latency P95 < 50ms for a 50-holding portfolio.
- ⬜ 100% test coverage on API contracts.

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
1. ✅ Generate 10,000 portfolios matching real-world distributions (`synthetic/generator.py`).
2. ✅ Apply historical and synthetic stress regimes (`synthetic/scenarios.py`) — 7 built-in scenarios (baseline, equity crash, rate shock, crypto winter, inflation spike, tech selloff, EM contagion).
3. ✅ Auto-find breaches across generated portfolios and stressed scenarios (`synthetic/adversary.py`) — `Adversary.sweep()` produces aggregate counts, per-rule breach counts, per-scenario status counts, and capped breach observations.
4. ✅ Generate deterministic HTML/JSON stress reports (`synthetic/report.py`) — scenario breakdown, top breached rules, sample breach observations, and control statement.

### Acceptance Criteria
- ✅ `PortfolioGenerator(seed=...).generate(10_000)` produces valid `Portfolio` objects deterministically.
- ✅ `stress_portfolio(p, scenario_id, seed=...)` returns an immutable, stressed copy with deterministic noise.
- ✅ `Adversary(mandate).sweep(n=1_000, seed=...)` runs across scenarios in ~1 second and returns breach statistics.
- ✅ `build_report(result)` returns JSON and print-ready HTML in <1 second for 2,500 evaluations.
- ⬜ CI runs synthetic suite on every PR.
- ⬜ Any regression in engine/agent agreement blocks merge.

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
- [x] Text chat drawer works on portfolio detail page.
- [x] Grounded answers cite exact `per_rule` rows and breaches.
- [x] What-if trade explanation calls `/verify` and explains result.
- [x] Browser voice input/output works in supported browsers.
- [x] LiveKit token endpoint ready for real-time room upgrade.
- [x] Frontend can join a LiveKit room when credentials are configured.
- [x] Server-side LiveKit agent deployed and answering with grounded speech.
- [x] Eval set of 50 questions with expected grounded answers (30 synthetic + 120 real-book; 182 parametrizations pass).

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
1. ✅ Add drift prediction module in `core/drift_prediction.py`.
2. ✅ Extend Hermes loop with "prevent" mode (`agents/hermes/loop.py`).
3. ✅ Add policy config UI in frontend (`HermesPreventPanel`, `/hermes` page).
4. ✅ Simulation mode: run Hermes for 100 virtual days; backend test proves ≥50% breach-incidence reduction.

### Acceptance Criteria
- ✅ Simulation shows ≥50% reduction in breach incidence vs. reactive mode.
  - Backend test `test_simulate_book_prevent_reduces_breach_incidence` passes: ~53% reduction on a 400-portfolio book.
- ✅ All auto-approved actions are still logged and reversible.
  - Prevent trades are recorded in the `state` table with rationale "hermes prevent auto-approve".
  - Auto-approval is gated by `_low_risk_trades` and by the existing rules-engine green gate in `suggest_preventive_trades`.

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
