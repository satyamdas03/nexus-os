# ASSURE 2.0 — AI-Assured Portfolio Compliance

## Executive Summary

ASSURE 2.0 is an AI assurance layer for wealth management that turns mandate compliance from a per-portfolio, spreadsheet-bound task into a live, book-wide, explainable workflow. A deterministic rules engine remains the final authority; Claude agents narrate, propose, and learn without ever touching mandate rules. Every material action is human-gated, audited, and exportable as a regulator-ready Evidence Pack.

In synthetic pilot testing across 34,000 portfolios, ASSURE 2.0's proactive Hermes 2.0 engine reduced projected breach incidence by approximately **53%** compared with a purely reactive remediation loop.

---

## The Problem

Typical portfolio-assurance workflows are:

- **Fragmented** — data lives across custody screens, compliance tools, and spreadsheets.
- **Slow** — a breach is a row of numbers that a human must decode.
- **Risky** — remediation is done by hand with no simulated "does this fix it?" step.
- **Opaque** — little audit trail ties a decision to the data that justified it.
- **Reactive** — teams fix breaches after they happen instead of preventing drift.

---

## The ASSURE Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js Command Centre · Diagnosis · Workbench · /hermes   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────────┐
│  FastAPI backend: portfolios, explain, remediate, evidence, │
│  market, chat, voice, Hermes scan + prevent, audit log       │
└──────────┬─────────────────────────────┬────────────────────┘
           │                             │
  ┌────────▼────────┐          ┌─────────▼─────────┐
  │  agents/hermes/ │          │  core/            │
  │  proposer · loop│          │  rules_engine     │
  │  reflect · score│          │  effective state  │
  └────────┬────────┘          │  market model     │
           │                   └─────────┬─────────┘
           │                             │
  ┌────────▼────────┐          ┌─────────▼─────────┐
  │  packages/        │          │  SQLite / Postgres│
  │  assure-kernel    │          │  34k synthetic    │
  │  (deterministic)  │          │  portfolios       │
  └───────────────────┘          └───────────────────┘
```

### Two-tier safety cage

| Layer | What | Mutable by AI? |
|---|---|---|
| **Mandate rules = LAW** | Hard client limits enforced by `assure-kernel` | Never |
| **Remediation strategy = JUDGMENT** | How Hermes prioritizes fixes, stored in `strategy.yaml` | Only via human-gated adopt |

---

## Key Results

### Sprint 5 — Conversational Assurance
- 182 grounded NL eval cases pass.
- The explainer cites specific rule values, portfolio weights, and breach counts.

### Sprint 6 — Hermes 2.0 Proactive Drift Prevention
- Deterministic GBM projection looks 5–30 days ahead.
- Preventive trades are rules-engine gated and queued for human or policy-band approval.
- 100-day simulation: **~53% reduction** in breach incidence vs. reactive mode.

---

## Deployment and Compliance

- Docker Compose stack for local pilot: `docker-compose up --build`.
- Cloud deployment guides for Render/Vercel, AWS, GCP, and Azure in `docs/DEPLOYMENT.md`.
- SOC 2 readiness checklist mapped to AICPA Trust Services Criteria in `docs/SOC2-CHECKLIST.md`.

---

## Conclusion

ASSURE 2.0 demonstrates that a deterministic compliance core combined with a tightly constrained, human-gated AI layer can scale assurance to tens of thousands of portfolios while remaining explainable, reversible, and regulator-ready.
