---
date: 2026-07-03
status: accepted
title: ASSURE Kernel Extraction
---

# ADR 003 — Extract `core/rules_engine.py` into `packages/assure-kernel/`

## Context

The deterministic rules engine in `backend/core/rules_engine.py` was the single source of truth for mandate compliance, but it was embedded inside the aura-demo application. To make ASSURE reusable as a platform and to prepare for the external `f/s labs 2.0` API, the engine needed to become a standalone, versioned Python package.

## Decision

Extract the engine into `packages/assure-kernel/`:

- Pure functions, no I/O, no HTTP, no database access.
- Pydantic v2 models: `Portfolio`, `Holding`, `Mandate`, `Rule`, `RulesResult`.
- Extensible rule registry via `@register("rule_type")`.
- Declarative mandate DSL loader (`load_mandate`, `parse_mandate`).
- Backward-compatibility shim in `backend/core/rules_engine.py` so existing imports continue to work.

## Consequences

- Positive: The kernel can be installed independently, tested in isolation, and reused by future services.
- Positive: New rule types can be added by registering evaluators without modifying aura-demo code.
- Positive: The DSL makes mandates human-readable and regulator-reviewable.
- Negative: Aura-demo imports still pass through the shim; new code should import `assure_kernel` directly.

## Migration path

1. `packages/assure-kernel/` is the new home for all rule-engine development.
2. Existing `from core.rules_engine import check` continues to work via the shim.
3. New backend code should `from assure_kernel import evaluate_portfolio`.
4. Mandates can be authored as YAML/JSON using the DSL and loaded with `assure_kernel.dsl.load_mandate`.
