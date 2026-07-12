# ASSURE 2.0 Phase 1 — Transcript-Coverage Note

**Date:** 2026-07-11
**Verifier:** P1-E Integration Verifier

## Themes that moved in Phase 1

| Financial Simplicity transcript theme | Phase 1 deliverable | Status |
|---|---|---|
| AI agents as investment managers; human-like interaction and trust | `/adviser` page with whiteboard, grounded chat, and LiveKit voice session | Landed |
| Confidence / confirmation prediction before human approval | `ConfidenceCard` + `/confidence/{client_id}` multi-factor scoring endpoint | Landed |
| Self-improving assurance engine (Hermes learns from misses) | `/hermes/generate` synthetic-reality → strategy diff + generated regression test | Landed |

## Approximate coverage estimate

- **Before Phase 1:** core assurance engine, evidence packs, conversational chat, market simulation, and basic Hermes remediation were in place — roughly 60-70% of the major transcript themes.
- **After Phase 1:** the three remaining headline themes above are implemented and wired into the UI. This brings approximate transcript-aligned feature coverage to **~90-95%** for the demo/Pilot scope.

## Remaining gaps for Phase 2 / production

- Live market-data integration (demo uses seeded synthetic prices).
- Full production RBAC hardening and audit log streaming.
- Long-running Hermes reflection scheduling at scale (currently async jobs in-process).
- Real client onboarding / mandate import workflows beyond synthetic CSVs.

These are operationalization themes rather than core transcript-mapped features.
