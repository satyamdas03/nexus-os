---
name: assure-evidence-pack-design
description: "Design for a read-only, per-portfolio Evidence Pack that assembles existing rules-engine, status-history, and audit data into a regulator-ready compliance proof artifact."
metadata:
  type: project
  date: 2026-06-26
  project: ASSURE / AURA demo
  status: design-draft
---

# ASSURE Evidence Pack — Design Spec (2026-06-26)

## 1. Purpose

Add a single, isolated, read-only capability to ASSURE: the **Evidence Pack**.

The Evidence Pack turns the existing recorded data (rules-engine result, alignment history, remediation audit trail) into a timestamped, human-readable, print-to-PDF compliance proof artifact for one portfolio. It directly supports the founder's "from advice to evidence" thesis: after a portfolio is remediated, a manager can click **Generate Evidence Pack** and produce a document that proves the portfolio is now aligned, shows when it drifted, and documents what was approved and why.

This is a **read-only assembly** feature. It does **not** modify portfolio state, approve trades, change strategy, or write to the audit log.

## 2. Scope

**In scope (strictly per-portfolio):**
- `backend/agents/evidence.py` — pure assembly functions.
- `backend/routers/evidence.py` — two new endpoints:
  - `GET /evidence/portfolio/{client_id}` → structured JSON.
  - `GET /evidence/portfolio/{client_id}/html` → print-ready HTML.
- One additive `app.include_router(...)` line in `backend/main.py`.
- `backend/tests/test_evidence.py` — new tests only.
- `frontend/src/components/evidence/EvidencePackButton.tsx` and `EvidencePackView.tsx`.
- Additive types in `frontend/src/lib/types.ts`.
- Additive API client entries in `frontend/src/lib/api.ts`.
- Add an `EvidencePackButton` on the Diagnosis page near the header / "Open Remediation" area.

**Explicitly out of scope for this cut:**
- Book-level evidence (2b).
- Audit-log write on pack generation.
- PDF binary generation (browser print-to-PDF is the delivery mechanism).
- Any changes to rules_engine.py, agents, Hermes engine, effective.py, trades.py, market.py, storage schema, or existing endpoint behavior.

## 3. Design Principles

1. **Additive and isolated.** New files only, plus one `include_router` line. Deleting the new code restores today's app exactly.
2. **100% read-only.** No state writes. No audit append. No mutation of portfolio data.
3. **Deterministic and reproducible.** The plain-English summary is composed from `rules_result` facts only; it never infers or invents details.
4. **Grounded in the rules engine.** The compliance attestation is exactly `rules_engine.check()` on the effective portfolio, exposed via existing helpers.
5. **Native ASSURE look.** Muted Light Matrix theme: JetBrains Mono, aura:* tokens, navy/emerald/ochre/crimson status colors.
6. **Print-clean PDF output.** Dedicated `@media print` CSS so `Save as PDF` produces a tidy, single-flow, institutional document with the synthetic-data banner visible.
7. **Synthetic-data disclaimer** on every generated pack.

## 4. Backend Design

### 4.1 New module: `backend/agents/evidence.py`

Pure assembly. No state mutation. No audit writes.

#### Functions

**`build_portfolio_evidence(client_id: str) -> dict`**

Reads existing data and returns a structured evidence dict with the following sections:

| Section | Source | Notes |
|---|---|---|
| `header` | `data_loader.get_portfolio()`, `data_loader._clock()`, current UTC timestamp | client_name, client_id, adviser, fum, report day, generated_at, synthetic-data banner. |
| `current_attestation` | `effective.get_effective()` + `rules_engine.check()` | Uses existing helpers exactly like `/portfolio/{id}/check`. Contains overall status and `per_rule` pass/fail table (rule, current, limit, pass, severity). |
| `deterministic_summary` | Composed from `rules_result` | 2–3 grounded sentences. Labels facts: status, breach rule names, watch rule names. No inference. Clearly marked "Deterministic summary — generated from rules-engine result." |
| `alignment_history` | SQLite `status_history` table for `client_id` | Days available, status per day, breach/watch counts. Sorted ascending by day. |
| `remediation_evidence` | Existing audit log (`data/audit.jsonl`) filtered by `client_id` and relevant `action_type` values | explain, verify, remediate_propose, approve, hermes queue/approve events. Each entry shows timestamp, actor, action, rationale, payload summary, rules status where present. |
| `control_statement` | Fixed boilerplate | Text explaining the deterministic rules engine is the source of truth, AI is advisory, material actions are human-approved, mandate rules are immutable. |
| `footer` | Computed | generated_at, reference id, synthetic-data disclaimer. |

**`_compose_deterministic_summary(rules_result: dict) -> str`**

- If `status == "green"`: state that the portfolio is fully aligned, list no breaches/watches.
- If `status == "orange"`: state it is under watch, list watch rule names (from `watches[].rule`), no breaches.
- If `status == "red"`: state it is in breach, list breach rule names (from `breaches[].rule`).
- All values come from `rules_result`; no invented thresholds or interpretations.

**`_status_history_for_client(client_id: str) -> list[dict]`**

Queries `status_history` for the client, ordered by `day ASC`. Returns compact rows.

**`_audit_entries_for_client(client_id: str) -> list[dict]`**

Reads `data/audit.jsonl` (via the existing path helper if available; otherwise an internal read function), filters by `client_id`, and keeps action types relevant to compliance evidence. Does not call `append_audit`.

**`_reference_id(client_id: str, day: int, generated_at: str) -> str`**

Stable short hash for display only, e.g. SHA-256 of `client_id|day|generated_at` truncated to 12 hex chars.

**`_render_html(evidence: dict) -> str`**

Builds a complete, standalone HTML document with inline CSS. Uses Python string building only (no Jinja2). CSS includes both screen and `@media print` rules.

HTML document structure:
- `<!DOCTYPE html><html><head>` with `<meta charset="utf-8">`, `<title>ASSURE Evidence Pack — {client_id}</title>`, inline CSS.
- `<body>` with a synthetic-data banner fixed at the top.
- Header block: client name/ID/adviser/FUM/day/generated_at/reference id.
- Current attestation block: status badge, per-rule table.
- Deterministic summary block (clearly labeled).
- Alignment history block: compact table + optional status strip.
- Remediation evidence block: audit entries table.
- Control statement block.
- Footer: generated_at, reference id, synthetic disclaimer.
- A "Print / Save as PDF" button visible on screen (`@media print { display: none; }`).

### 4.2 New router: `backend/routers/evidence.py`

```python
from fastapi import APIRouter, HTTPException
from agents.evidence import build_portfolio_evidence

router = APIRouter()

@router.get("/evidence/portfolio/{client_id}")
def portfolio_evidence_json(client_id: str):
    # raises 404 if portfolio not found
    return build_portfolio_evidence(client_id)

@router.get("/evidence/portfolio/{client_id}/html")
def portfolio_evidence_html(client_id: str):
    evidence = build_portfolio_evidence(client_id)
    html = evidence["_html"]  # pre-rendered by builder
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html, status_code=200)
```

404 handling: if `data_loader.get_portfolio(client_id)` returns `None`, return HTTP 404.

### 4.3 Edit to existing file

`backend/main.py`: add one line after existing router includes:

```python
from routers import evidence
app.include_router(evidence.router)
```

This is the **only** edit to an existing backend file.

## 5. Frontend Design

### 5.1 New components: `frontend/src/components/evidence/`

**`EvidencePackButton.tsx`**
- Props: `clientId: string`, `variant?: "primary" | "secondary"` (default secondary).
- Uses existing `SecondaryButton` / `PrimaryButton` with optional `loading` state.
- Label: "Generate Evidence Pack".
- On click: opens `api.evidence.portfolioHtmlUrl(clientId)` in a new tab (`window.open(url, "_blank", "noopener,noreferrer")`).
- No local state beyond transient loading.

**`EvidencePackView.tsx`**
- This component renders the structured JSON view inline if we later want a modal; for this cut it is included as a thin wrapper that can fetch `api.evidence.portfolio(clientId)` and display a compact preview. The primary demo path is the HTML route in a new tab.
- Includes a helper `PrintButton` that calls `window.print()`.

### 5.2 API client additions: `frontend/src/lib/api.ts`

Add an `evidence` group to the existing `api` object:

```typescript
evidence: {
  portfolio: (clientId: string) => j<EvidencePack>(`/evidence/portfolio/${clientId}`),
  portfolioHtmlUrl: (clientId: string) => `${base()}/evidence/portfolio/${clientId}/html`,
}
```

### 5.3 Type additions: `frontend/src/lib/types.ts`

```typescript
export interface EvidencePack {
  header: {
    client_name: string;
    client_id: string;
    adviser: string;
    fum: number;
    day: number;
    generated_at: string;
    reference_id: string;
    synthetic_data: boolean;
  };
  current_attestation: {
    status: "green" | "orange" | "red";
    per_rule: Array<{
      rule: string;
      current: number | string | string[];
      limit: number | string | string[];
      pass: boolean;
      severity: "green" | "orange" | "red";
    }>;
  };
  deterministic_summary: string;
  alignment_history: Array<{
    day: number;
    status: "green" | "orange" | "red";
    breach_count: number;
    watch_count: number;
  }>;
  remediation_evidence: Array<{
    timestamp: string;
    action_type: string;
    actor: string;
    tier: string;
    rationale: string;
    payload_summary: string;
    rules_status?: string;
  }>;
  control_statement: string;
  footer: {
    generated_at: string;
    reference_id: string;
    synthetic_disclaimer: string;
  };
}
```

### 5.4 Wiring

**Diagnosis page** (`frontend/src/app/portfolio/[id]/page.tsx`):
- Import `EvidencePackButton` from `components/evidence/EvidencePackButton`.
- Place it near the header / "Open Remediation" button group, using the same button row pattern.
- Pass `clientId={id}`.
- No layout restructuring; additive only.

The Command Centre book-level affordance is **not** included in this cut.

## 6. HTML / Print Styling

The HTML route is a standalone document with inline CSS. Key rules:

**Screen:**
- `body` uses `font-family: 'JetBrains Mono', monospace;`.
- Background `#F1F5F9`, text `#0F172A`, surfaces `#FFFFFF`/`#E2E8F0`.
- Synthetic banner: `background: #DC2626; color: #FFFFFF;` (crimson on white) with bold uppercase text.
- Status badges: green `#10B981`, orange `#D97706`, red `#DC2626`.
- A floating "Print / Save as PDF" button bottom-right.

**Print (`@media print`):**
- `body { background: #fff; color: #000; }`.
- Synthetic banner stays visible (required on the printed PDF).
- Print button hidden.
- Page margins set via `@page { margin: 18mm; }`.
- Tables avoid page breaks inside rows (`tr { page-break-inside: avoid; }`).
- Sections break reasonably (`section { page-break-inside: avoid; }` where possible).
- Links show plain text (no underlines, no browser URL hints).
- Header and footer repeat naturally via normal document flow.

## 7. Testing

### 7.1 New backend tests: `backend/tests/test_evidence.py`

| Test | Assertion |
|---|---|
| `test_green_portfolio_evidence` | Build pack for a known green client. Header present, current_attestation.status == "green", per_rule all pass, deterministic_summary states alignment, synthetic disclaimer present. |
| `test_red_portfolio_evidence` | Build pack for a known red client. Status == "red", at least one failing per_rule, summary lists breach rule names, remediation_evidence empty or present depending on prior actions. |
| `test_orange_portfolio_evidence` | Build pack for a known orange/watch client. Status == "orange", summary lists watch rule names, no breaches claimed. |
| `test_attestation_matches_rules_engine` | Compare `current_attestation` to a direct `rules_engine.check(effective_portfolio(p), p["mandate"])` call; they must match exactly. |
| `test_no_state_mutation` | Call `build_portfolio_evidence` twice and verify the portfolio's effective rules result and audit log length are unchanged. |
| `test_synthetic_disclaimer_present` | Both JSON and HTML contain the required synthetic-data text. |
| `test_html_route_returns_200` | Hit `/evidence/portfolio/{client_id}/html` via TestClient; assert 200, content-type `text/html; charset=utf-8`, body contains client name, status, and synthetic banner. |
| `test_404_for_unknown_client` | `GET /evidence/portfolio/unknown` returns 404. |

Tests must run against the existing seeded test fixtures or use a known client ID from the generated book. Use `data_loader.set_conn()` with a fresh in-memory test DB if needed.

### 7.2 Regression pass (required before deploy)

After all code is green:
1. `cd backend && .venv/Scripts/python.exe -m pytest tests/` → must remain **143 passed, 1 skipped**.
2. `cd frontend && npm run build` → must succeed.
3. `cd frontend && npx vitest run` → must pass.
4. Cold-load click-through of all four existing screens:
   - Command Centre (`/`)
   - Diagnosis (`/portfolio/{id}`)
   - Workbench (`/portfolio/{id}/workbench`)
   - Hermes Mission Control (`/hermes`)
   Confirm no console errors, no 404s, no layout regressions, existing tour unaffected.
5. Verify the new endpoint manually for a red and a green portfolio.
6. Only then consider deployment / live verification.

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Contradicting the rules engine | `current_attestation` is computed only by calling `rules_engine.check()` via existing helpers; the pack never re-implements rule logic. |
| State mutation | No writes in `evidence.py`; router has no POST/PUT/DELETE; tests assert no mutation. |
| Breaking existing tests | New files only + one router include; regression pass before deploy. |
| HTML looks unprofessional in PDF | Dedicated `@media print` CSS, synthetic banner visible, tables page-break-safe, print button hidden. |
| Touching existing agents / state layer | Explicitly forbidden by spec; module only reads from `data_loader`, `effective`, `rules_engine`, `audit` log. |

## 9. Build Order

1. `backend/agents/evidence.py` assembly functions + `_render_html`.
2. `backend/tests/test_evidence.py` — run against the module.
3. `backend/routers/evidence.py` — JSON + HTML endpoints.
4. One-line edit in `backend/main.py`.
5. Backend endpoint tests via `pytest`.
6. Frontend types + API additions.
7. Frontend `EvidencePackButton` + `EvidencePackView`.
8. Wire button into Diagnosis page.
9. Regression pass (backend tests, frontend build, cold click-through).
10. Manual verification of HTML print output.

## 10. Files Changed

### New files
- `backend/agents/evidence.py`
- `backend/routers/evidence.py`
- `backend/tests/test_evidence.py`
- `frontend/src/components/evidence/EvidencePackButton.tsx`
- `frontend/src/components/evidence/EvidencePackView.tsx`

### Additive edits to existing files
- `backend/main.py` — one `include_router` line.
- `frontend/src/lib/api.ts` — `evidence` group.
- `frontend/src/lib/types.ts` — `EvidencePack` type.
- `frontend/src/app/portfolio/[id]/page.tsx` — one `<EvidencePackButton />` placement.

No existing logic, rules engine, agents, Hermes, market sim, effective state, storage schema, or endpoint behavior is modified.

## 11. Future Work (Phase 2, Not Now)

- Book-level evidence summary (`GET /evidence/book`, `GET /evidence/book/html`) and a Command Centre affordance.
- Optional audit-log entry on pack generation (only if a future requirement explicitly requires provenance of the pack itself).
- Optional PDF binary generation if browser print-to-PDF proves insufficient.

## 12. Related Memories / Context

- [[assure-session-2026-06-24-deep-rundown-excel-readme]] — latest session state, live URLs, verification numbers.
- [[assure-session-2026-06-23-market-reset]] — market simulation, reset mechanics.
- [[hermes-scan-fix-2026-06-22]] — Hermes engine details.
- [[aura_phase2_2026-06-20-session-completion]] — UI makeover, test commands, deployment.
- [[assure-self-guiding-layer-2026-06-20]] — tour mechanics; this feature does not modify them.

---

**Spec status:** draft, awaiting review.
