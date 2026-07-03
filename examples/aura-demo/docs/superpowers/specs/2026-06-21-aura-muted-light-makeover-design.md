---
name: aura-muted-light-makeover-design
description: Complete UI makeover from Matrix dark theme to Muted Light Matrix institutional design while preserving all features.
metadata:
  type: project
  date: 2026-06-21
---

# AURA — Muted Light Matrix UI Makeover (Design Spec)

## Goal

Transform the existing AURA/Assure demo frontend from the current neon-on-black Matrix theme to the institutional "Muted Light Matrix" design system provided at:

`newUI_matrixPLUSbright/stitch_aura_portfolio_assurance_platform/muted_light_matrix/DESIGN.md`

The makeover must be applied to all four existing pages:

1. `/` — Command Centre
2. `/portfolio/[id]` — System Diagnosis
3. `/portfolio/[id]/workbench` — Remediation Workbench
4. `/hermes` — Hermes Mission Control

All existing features, API contracts, behavior, and recent fixes must be preserved. The backend does not change.

## Design System (from DESIGN.md)

### Color palette
- Background: `#F1F5F9` (`slate-100`)
- Surface/panels: `#E2E8F0` (`slate-200`), layered surfaces `#F8FAFC`, `#F1F5F9`
- Text: `#1B1B1D` on-surface, `#45464D` on-surface-variant, `#76777D` outline
- Primary: deep navy `#0F172A` (`slate-900`), on-primary white
- Secondary: electric slate `#334155` (`slate-700`)
- Status: emerald success, ochre warning, crimson error
- Borders: 1px solid `#CBD5E1` (`slate-300`)

### Typography
- Font: **JetBrains Mono** exclusively
- Headline-lg: 24px/32px, weight 700, tracking -0.02em
- Headline-md: 20px/28px, weight 600, tracking -0.01em
- Body-lg: 16px/24px, weight 400
- Body-md: 14px/20px, weight 400
- Label-md: 12px/16px, weight 600, uppercase
- Label-sm: 10px/14px, weight 500, uppercase

### Layout
- 4px base grid unit
- 12-column desktop grid, 8-column tablet, 4-column mobile
- 24px outer margins
- High-density internal padding: 8px or 12px typical
- 4px corner radius on cards, buttons, inputs, chips
- Circles reserved for status indicators and avatars only
- Micro-shadows: low opacity (5-8%), neutral grey, 2px offset

## Implementation Strategy

### Approach: Full component rebuild
Token-swap alone cannot reproduce the new screenshot layouts (different card structures, sidebar navigation, table styling, barcharts). We will rebuild components using new shared primitives while preserving all props, API calls, state logic, and behavior.

### New Tailwind theme extension
Add an `aura` color/typography extension to `frontend/tailwind.config.ts` (or a parallel `theme.ts` if config extension is awkward). Do not delete the old theme until after full E2E passes.

### Shared primitives to create

| Component | Purpose |
|-----------|---------|
| `Sidebar` | Left navigation rail with Command Centre, Diagnosis, Audit Log, Settings |
| `TopMetricCard` | Metric card with label, value, delta, mini sparkline |
| `StatusBadge` | 8px circle + uppercase status label (emerald/ochre/crimson) |
| `Panel` | Bordered card with optional header, 4px radius, 1px slate border |
| `DataTable` | Zebra-striped, high-density table with monospace cells |
| `SectionHeader` | Uppercase label-sm + headline-md title |
| `PrimaryButton` | Navy block, white text, 4px radius |
| `SecondaryButton` | Outlined slate border, navy text, 4px radius |
| `StatusChip` | Small rectangular tag tinted by status |

### Page redesign mappings

#### `/` Command Centre
- Add `Sidebar`.
- Top row: four `TopMetricCard`s (Portfolios, Aligned, Breached, FUM or similar)
- Main content: global asset matrix treemap, preserved logic but new muted-light colors.
- Right column: timeline feed (recent events/audits).
- Status indicators use new `StatusBadge`.

#### `/portfolio/[id]` System Diagnosis
- Add `Sidebar`.
- Header: client name + status.
- Left/main: `DiagnosticsList` (breaches) + `SystemDiagnosticsLedger` (holdings table).
- Right column: `AllocationBarChart` (screenshot shows vertical grouped bars) + AI recommendation / assurance checks panel.
- Keep explain targeting: row-level Explain buttons and donut/chart Explain still call `api.explain(clientId, metric)`.

#### `/portfolio/[id]/workbench` Remediation Workbench
- Add `Sidebar`.
- Header: page title + Approve/Reset actions.
- Main: `FlaggedLedgerEntries` grouped by breach type, showing trades to apply.
- Right: AI Recommendation panel + Assurance Checks list (✓/✗ result cards).
- Keep Verify/Approve flow, CSV export, RFC-4180 escaping.

#### `/hermes` Mission Control
- Add `Sidebar`.
- Top: scan controls + Book Score cards (alignment rate, avg trades, acceptance, breaches remaining).
- Main: Hermes Queue table with row selection and Approve Batch.
- Right/lower: Strategy panel + Reflection proposal card + History list.
- Keep scan job polling, queue pagination, reflect/adopt/rollback, approve-batch marking processed.

## Functional Preservation Requirements

The following must continue to work identically after the redesign:

- All API calls through `frontend/src/lib/api.ts` remain unchanged.
- React state management and hooks remain unchanged.
- Routing and Next.js App Router structure remain unchanged.
- Explain targeting (`frontend/src/lib/explainMetric.ts`) remains in use.
- Hermes bulk approve with queue refresh remains in use.
- Workbench propose → verify → approve → audit flow remains in use.
- Market simulation tick/advance/auto remains in use.
- CSV export with RFC-4180 escaping remains in use.
- Responsive behavior is preserved (mobile scaling).
- Accessibility: no nested interactive elements, buttons have visible focus states.

## Risk Mitigation

1. Work in a feature branch (`feature/muted-light-makeover`).
2. Implement page-by-page in this order: shared primitives → Command Centre → Diagnosis → Workbench → Hermes.
3. Test each page locally in browser before moving to the next.
4. Keep old Matrix component files in a `frontend/src/components/_legacy/` folder during development; remove only after full E2E passes.
5. After all pages, run: backend pytest, frontend `tsc --noEmit`, `next build`, `vitest run`, and `python scripts/e2e_screenshots.py`.
6. Regenerate `AURA_Demo_Guide.docx` only after UI is finalized.
7. Get user sign-off on screenshots before commit/push.

## Testing & Acceptance Criteria

- [ ] All four pages render in the muted-light style.
- [ ] No blocking console errors or 404s in Playwright screenshot test.
- [ ] Backend pytest passes.
- [ ] Frontend TypeScript and build pass.
- [ ] Vitest component tests pass.
- [ ] Workbench approve flips status green and persists on reload.
- [ ] Hermes scan → queue → approve batch marks rows processed.
- [ ] Explain buttons return grounded rule-specific narratives.
- [ ] Market tick advances day and updates summary counts.
- [ ] CSV export produces valid RFC-4180 output.

## Files likely to change

- `frontend/tailwind.config.ts`
- `frontend/src/app/globals.css`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/portfolio/[id]/page.tsx`
- `frontend/src/app/portfolio/[id]/workbench/page.tsx`
- `frontend/src/app/hermes/page.tsx`
- New shared components under `frontend/src/components/ui/` and `frontend/src/components/`
- Most existing component files in `frontend/src/components/`

## Out of scope

- Backend changes (no API changes).
- New features not already present.
- Deploy environment changes beyond Vercel's standard Next.js build.

---

## Notes

The new design screenshots show:
- Command Centre: metric cards, treemap, timeline sidebar.
- Diagnosis: diagnostics list, system diagnostics ledger, allocation bar chart.
- Workbench: flagged ledger entries grouped by breach, AI recommendation, assurance checks.

Hermes does not have a screenshot but will be designed using the same tokens and component library, with layout analogous to the workbench (ledger left, summary + controls right).
