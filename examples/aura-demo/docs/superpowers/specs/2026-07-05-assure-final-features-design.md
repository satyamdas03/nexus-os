# ASSURE 2.0 Final Features Design

**Date:** 2026-07-05
**Scope:** Complete the three remaining Financial Simplicity transcript-aligned features:
1. AI Investment Manager Agent (voice + whiteboard math)
2. Confidence / Confirmation Prediction Card
3. Synthetic-Test → Strategy Diff + Regression Test Generator

**Out of scope:** Bull autonomous trading agent; IP/legal separation.

---

## 1. Goals

| Transcript theme | Feature that satisfies it |
|---|---|
| AI agents as investment managers; human-like interaction and trust | AI Adviser page + embedded voice drawer |
| Confidence predictions for compliance officers | Confidence card per proposal |
| Infinite synthetic data stress-tests; code generation | Hermes generate diff + regression test |
| Deterministic math core + flexible AI interfaces | All three features sit on top of `rules_engine.py` and never override it |

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Next.js)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────────┐  │
│  │ /adviser     │  │ Confidence   │  │ /hermes "Synthetic → Code"     │  │
│  │ voice + canvas│  │ card         │  │ panel                          │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────────────┘  │
│         │                 │                       │                       │
│         └─────────────────┴───────────────────────┘                       │
│                              api.ts (Bearer auth)                       │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
┌──────────────────────────────┼─────────────────────────────────────────┐
│                              │ Backend (FastAPI)                       │
│  ┌──────────────┐  ┌────────┴──────────┐  ┌────────────────────────┐  │
│  │ /adviser/*   │  │ /confidence/*     │  │ /hermes/generate       │  │
│  │ /voice/token │  │                   │  │ /hermes/run-test       │  │
│  └──────┬───────┘  └────────┬──────────┘  └──────────┬───────────────┘  │
│         │                  │                        │                   │
│         └──────────────────┼────────────────────────┘                   │
│                            ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Hermes loop + rules_engine.py + GBM simulator + Claude reasoning │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Feature 1 — AI Investment Manager Agent

### 3.1 Surfaces

1. **New page `/adviser`**
   - Portfolio selector (autocomplete over `/portfolios`).
   - Voice controls: join room, mute/unmute, leave.
   - Whiteboard canvas area showing the current explanation.
   - Text chat as fallback / transcript.
   - Route added to `AppShell` mobile tabs.

2. **Embedded drawer upgrade**
   - Existing `/portfolio/[id]` `ChatDrawer` gains a "Voice Adviser" toggle.
   - When toggled, the drawer expands and renders `VoiceRoom` + `AdviserCanvas`.

### 3.2 Backend endpoints

| Endpoint | Purpose |
|---|---|
| `POST /adviser/session` | Create a session for a portfolio; return LiveKit token + session id. |
| `POST /adviser/chat` | Text-only adviser grounded in rules output; returns explanation + whiteboard payload. |
| `POST /adviser/whiteboard` | Return structured `{breaches[], proposedTrades[], postStatus, impact}` for canvas rendering. |

### 3.3 Whiteboard payload

```json
{
  "client_id": "C12345",
  "client_name": "Eldon Endowment",
  "current_status": "red",
  "breaches": [
    {
      "rule": "max_region_weight",
      "limit": 0.35,
      "current": 0.52,
      "offending_holdings": ["AAPL", "MSFT"],
      "explanation": "US weight 52% exceeds 35% cap."
    }
  ],
  "proposed_trades": [
    {"action": "sell", "ticker": "AAPL", "units": 120, "value": 24000, "rationale": "Trim US large-cap to meet region cap."}
  ],
  "post_status": "green",
  "impact": {"aum_impact_pct": 0.024, "trades_count": 1}
}
```

### 3.4 Safety constraints

- Every response must include a deterministic-rules citation and a disclaimer that it is advisory only.
- No trade execution from the adviser page. Primary CTA is "Open in Workbench".
- Voice room inherits existing LiveKit token + `VoiceRoom` component.

### 3.5 Components

- `frontend/src/app/adviser/page.tsx`
- `frontend/src/components/adviser/AdviserCanvas.tsx`
- `frontend/src/components/adviser/AdviserChat.tsx`
- `frontend/src/components/adviser/AdviserControls.tsx`
- `backend/routers/adviser.py`
- `backend/agents/adviser/prompts.py` (system prompt + whiteboard prompt)

---

## 4. Feature 2 — Confidence / Confirmation Prediction Card

### 4.1 Backend endpoint

`POST /confidence/{client_id}` accepts a proposed trade set and returns:

```json
{
  "confidence": 0.93,
  "model_confidence": 0.94,
  "rule_engine_certainty": 1.0,
  "data_freshness": 1.0,
  "simulation_baseline": 0.85,
  "historical_approval_success": 0.95,
  "human_review_recommended": false,
  "factors": [
    {"name": "rules_engine", "score": 1.0, "weight": 0.5},
    {"name": "simulation_baseline", "score": 0.85, "weight": 0.3},
    {"name": "historical_approval_success", "score": 0.95, "weight": 0.2}
  ],
  "explanation": "Deterministic rules gate is green. Prevent simulation shows 85% projected success. No human review required."
}
```

### 4.2 Factor definitions

| Factor | How computed | Weight |
|---|---|---|
| `rules_engine` | 1.0 if green, 0.7 if only watches, 0.0 if red. | 0.5 |
| `simulation_baseline` | Run `simulate` in prevent mode on the same seed and compare projected breach count vs. current strategy. | 0.3 |
| `historical_approval_success` | Fraction of prior approved trades with the same `breach_type` that resolved the breach. | 0.2 |

`confidence` is the weighted average. `human_review_recommended` is true if any factor is below 0.8 or overall confidence < 0.85.

### 4.3 Frontend usage

- `ConfidenceCard` rendered inside:
  - Hermes queue `QueueRow` expansion.
  - Workbench fixed footer near "Approve & Log".
  - `/adviser` page before voice explanation.
- Visual: segmented confidence bar, human-review badge, expandable factor list.

### 4.4 Components

- `frontend/src/components/ConfidenceCard.tsx`
- `frontend/src/components/ConfidenceMeter.tsx`
- `backend/routers/confidence.py`
- `backend/core/confidence.py` (pure scoring logic, no I/O)

---

## 5. Feature 3 — Synthetic-Test → Strategy Diff + Regression Test Generator

### 5.1 Backend endpoints

| Endpoint | Purpose |
|---|---|
| `POST /hermes/generate` | Run reactive + prevent simulations; generate a YAML diff and a pytest regression test if an improvement is found. |
| `POST /hermes/run-test` | Execute the generated test in a sandboxed subprocess; return pass/fail + output. |

### 5.2 `/hermes/generate` behavior

1. Load current `strategy.yaml` as baseline.
2. Run `simulate(mode="reactive", seed=42)` and `simulate(mode="prevent", seed=42)`.
3. For each tunable variable, use a small deterministic grid or Claude to propose a single-variable change.
4. Re-run simulation with the candidate strategy.
5. If breach incidence improves by >= 5%, return a diff.
6. Generate a Python regression test that asserts the improvement on the same seed.
7. Do **not** auto-adopt; return diff + test for human review.

### 5.3 Diff output

```json
{
  "ok": true,
  "diff": {
    "variable": "prevent_risk_threshold",
    "from": 0.5,
    "to": 0.45,
    "rationale": "Synthetic run with seed 42 showed 12% fewer projected breaches when threshold lowered to 0.45."
  },
  "test": {
    "filename": "test_strategy_v5_prevent_threshold_20260705_121000.py",
    "source": "def test_strategy_v5_lowers_prevent_threshold():\n    ..."
  },
  "simulation": {
    "reactive_incidence": 120,
    "prevent_incidence_before": 95,
    "prevent_incidence_after": 83,
    "improvement_pct": 12.6
  }
}
```

### 5.4 Test sandbox

- `subprocess.run([sys.executable, "-m", "pytest", test_path, "-v"], timeout=60, capture_output=True)`.
- Tests run against the in-process DB via the test seam or a temporary copy.
- No network access; only local simulator + rules engine.

### 5.5 Storage

- Generated tests written to `backend/agents/hermes/generated_tests/` with timestamped filenames.
- `HermesHistoryEntry` gains `generated_by: {simulation_seed, test_filename}` field.

### 5.6 Frontend usage

New panel in `/hermes` called **"Synthetic Reality → Code"**:
- Reactive vs. prevent delta.
- Generated YAML diff with "Adopt as v{N+1}" button (uses existing `/hermes/adopt`).
- Generated test code block with "Copy" and "Run test" buttons.

### 5.7 Components

- `frontend/src/components/hermes/HermesGeneratePanel.tsx`
- `frontend/src/components/hermes/StrategyDiff.tsx`
- `frontend/src/components/hermes/GeneratedTestView.tsx`
- `backend/routers/hermes.py` additions
- `backend/agents/hermes/generator.py`
- `backend/agents/hermes/test_generator.py`

---

## 6. Data flow and error handling

### 6.1 Common patterns

- All new endpoints use existing `require_mutation` (for mutating operations) or `get_current_user_or_dev` (for read-only).
- All Claude calls are wrapped with a timeout (30 s) and a deterministic fallback if the LLM fails.
- Any failure in the confidence or adviser endpoints returns a graceful degradation object instead of a 500, so the UI can still show the deterministic data.

### 6.2 Voice room errors

- If LiveKit is not configured, the UI shows "Voice not configured" and keeps text chat.
- If microphone permission is denied, the mute button reflects the real device state.

### 6.3 Test generation errors

- If no improvement is found, return `{"ok": true, "diff": null, "message": "No statistically significant improvement found for the tested variables."}`.
- If the generated test fails when run, return the pytest output so the user can inspect it.

---

## 7. Testing plan

### 7.1 Backend tests

| Test | File |
|---|---|
| `/adviser/whiteboard` returns structured payload | `tests/test_adviser.py` |
| `/adviser/chat` refuses to execute trades | `tests/test_adviser.py` |
| `/confidence/{id}` returns expected scores and human-review flag | `tests/test_confidence.py` |
| `/hermes/generate` produces a diff when simulation improves | `tests/test_hermes_generate.py` |
| `/hermes/run-test` passes for a generated test | `tests/test_hermes_generate.py` |
| All new endpoints respect role-based access | reuse `tests/test_auth.py` patterns |

### 7.2 Frontend tests

| Test | File |
|---|---|
| `ConfidenceCard` renders score + factors | new test or story |
| `AdviserCanvas` renders whiteboard payload | `tests/` |
| `/hermes` generate panel calls API and shows diff | integration test |

### 7.3 Manual verification

1. Open `/adviser`, select a red portfolio, join voice, ask "Why is this red?" → answer cites deterministic rules.
2. Open Hermes queue, expand a row → confidence card shows rule-engine certainty.
3. Click "Generate" in `/hermes` → diff + test appear; click "Run test" → passes.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinates advisory content | Ground every response in `rules_engine.check` output; include disclaimer. |
| Confidence score is over-trusted | Always show factor breakdown; `human_review_recommended` is conservative. |
| Generated tests are brittle | Generate deterministic assertions tied to a fixed seed; allow re-generation. |
| Voice room adds complexity | Keep text fallback; LiveKit token endpoint already exists. |

---

## 9. Open questions resolved during design

- AI agent surface: both standalone `/adviser` page and embedded drawer. ✅
- Confidence card: multi-dimensional with human-review flag. ✅
- Code generation: YAML diff + generated pytest regression test. ✅

---

## 10. Out of scope

- Bull autonomous trading agent (separate project).
- IP separation / personal-vs-company legal process.
- Billing, multi-tenant SaaS, or non-Alpaca brokerage integrations.
