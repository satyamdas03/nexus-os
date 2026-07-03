# AURA — Institutional Precision Design Spec

**Date:** 2026-06-18  
**Project:** AURA Demo for Financial Simplicity  
**Designer:** frontend-design skill + user approval  

## Subject, Audience, Page Job

- **Subject:** AURA, an AI-assisted portfolio assurance platform.
- **Audience:** Professional portfolio managers / compliance reviewers.
- **Page job:** Surface a prioritized list of portfolio compliance actions, guide the reviewer through deterministic diagnosis, and let a human approve AI-proposed remediation trades — with the rules engine, never the LLM, deciding final compliance.

## Design System

### Palette

| Token | Hex | Use |
|---|---|---|
| Canvas | `#F8F9FB` | page background |
| Card | `#FFFFFF` | cards/panels |
| Primary | `#0F2A4A` | sidebar, primary buttons, deep headings |
| On-Primary | `#FFFFFF` | text on primary surfaces |
| On-Primary-Container | `#7A92B7` | muted nav text on sidebar |
| Primary-Container | `#0F2A4A` | active nav background |
| Accent (Teal) | `#0E7C7B` / `#006A69` | AI insight bars, active focus rings, data highlights, secondary actions |
| Secondary-Fixed | `#98F2F0` | aligned/green status backgrounds |
| Tertiary-Fixed | `#FFDCBE` | attention/amber status backgrounds |
| Error-Container | `#FFDAD6` | breached/red status backgrounds |
| Error | `#BA1A1A` | error text, red dots |
| On-Error-Container | `#93000A` | text on error backgrounds |
| On-Tertiary-Fixed-Variant | `#633F18` | text on amber backgrounds |
| Border | `#E2E8F0` / `#C4C6CF` | card/input borders, dividers |
| Ink | `#191C1E` | primary text |
| Muted | `#74777F` | secondary text, labels |

### Typography

- **Family:** Inter everywhere.
- **Tabular figures** (`font-variant-numeric: tabular-nums`) for all FUM, weights, prices, percentages.
- **Display:** `font-semibold text-3xl leading-10 tracking-tight` (desktop); `text-2xl leading-8` (mobile).
- **Headline:** `text-xl leading-7 font-medium tracking-tight`.
- **Data Mono style:** `text-sm leading-5 font-medium tabular-nums`.
- **Label Caps:** `text-[11px] leading-4 font-semibold tracking-[0.05em] uppercase`.

### Shapes

- Cards / panels: `rounded-xl` (12px).
- Buttons / inputs: `rounded-lg` (8px).
- Status chips: `rounded-full` (pill).
- Status dots: `rounded-full` w-2.5 h-2.5.
- Elevation: only a single ambient shadow `0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.03)` for floating elements.

### Layout

- **Desktop (≥1024px):** fixed 240px navy sidebar left; 64px white topbar across remaining width; content area with 32px gutter and max-width 1440px.
- **Mobile (<1024px):** hamburger icon opens the full 240px navy drawer overlay. The home screen (`/`) also shows a bottom tab bar (Command Centre / Portfolios / Remediation / Audit) for one-tap top-level switching. Diagnosis and Workbench hide the bottom tab so the page scrolls cleanly; use the drawer + page back link.

## Screen Designs

### 1. Command Centre (`/`)

- AI Assurance Summary banner at top: teal left accent, sparkle icon, one-line summary of aligned/breached/attention counts.
- 4 KPI stat cards in a row:
  1. Total FUM (with trend vs last month).
  2. Aligned % (with mini progress bar).
  3. Needs Attention count.
  4. Breached count.
- Filter bar above heatmap: adviser, status, asset class dropdowns + search. V1 search filters client-side on the already-loaded list.
- Heatmap: reskinned recharts Treemap. Box size = FUM; color = status (aligned `#98F2F0`, attention `#FFDCBE`, breached `#FFDAD6`). Click routes to `/portfolio/{id}`. Custom legend below.
- Triage Queue: scrollable card on right listing red/orange portfolios by FUM desc, with status pill and one-line reason.

### 2. Diagnosis (`/portfolio/[id]`)

- Back link ← Back to Portfolios.
- Header row: client name + status chip left; total portfolio value + “Open Remediation” primary button right.
- Plain-English Assurance Narrative card: left teal accent bar, sparkle icon, narrative paragraph, breach/watch chips below.
- Confidence footnote: rule checks are deterministic; narrative is advisory.
- 2-column grid below:
  - Left 2/3: Major Holdings table. Breach-contributing rows get light red background + warning icon. Numbers right-aligned, tabular nums.
  - Right 1/3: Sector Allocation donut + Value History line chart, stacked.

### 3. Remediation Workbench (`/portfolio/[id]/workbench`)

- Header: portfolio name + status chip; AUM impact top-right (static or computed from trades).
- Left 8 cols:
  - AI Remediation Strategy card: teal left accent, rationale text, confidence tag.
  - Proposed Execution Ledger table: holding, current weight, proposed action chip, value, new weight.
- Right 4 cols (sticky on desktop):
  - Assurance Check hero card: before/after status indicators + mandate verification checklist.
- Fixed bottom action bar on desktop: info message + Modify secondary button + Approve & Log primary button.
- Mobile: action buttons sit below the verification card.
- Audit Trail and Suggestion Chip below the main grid.

## Components to Create / Modify

- `frontend/tailwind.config.ts` — extend palette, spacing, type tokens.
- `frontend/src/app/globals.css` — Inter import, tabular-nums, custom scrollbar, ambient shadow utility.
- `frontend/src/app/layout.tsx` — wrap children in `AppShell`.
- `frontend/src/components/AppShell.tsx` — sidebar, topbar, mobile drawer, mobile bottom nav on `/`.
- `frontend/src/components/Heatmap.tsx` — reskin.
- `frontend/src/components/SummaryBar.tsx` — replace with KPI cards.
- `frontend/src/app/page.tsx` — assemble banner, KPIs, filters, heatmap, triage.
- `frontend/src/app/portfolio/[id]/page.tsx` — diagnosis layout.
- `frontend/src/components/NarrativePanel.tsx`, `BreachChips.tsx`, `HoldingsTable.tsx`, `AllocationDonut.tsx`, `PerformanceChart.tsx` — reskin.
- `frontend/src/app/portfolio/[id]/workbench/page.tsx` — workbench layout.
- `frontend/src/components/WorkbenchTable.tsx`, `VerifyPanel.tsx`, `AuditTrail.tsx`, `SuggestionChip.tsx` — reskin.

## Signature Element

The **Assurance Check transition card** on the Remediation Workbench — before/after circular indicators with a directional arrow and a rule-by-rule verify list. It embodies the product thesis: AI recommends, Assurance verifies.

## Responsiveness

- `lg` breakpoint switches between permanent sidebar and hamburger drawer.
- Mobile grid stacks to single column.
- Tables horizontally scroll on narrow screens.
- Bottom action bar becomes inline below verification card on mobile.
- Touch targets ≥ 44px; font sizes do not shrink below 11px label caps.

## Rules Engine Source of Truth

No design change alters this architectural rule. Colors map directly to `RulesResult.status` and `Breach.severity`. LLM-generated narrative is visually marked as advisory (teal accent) and never styled as a compliance verdict.
