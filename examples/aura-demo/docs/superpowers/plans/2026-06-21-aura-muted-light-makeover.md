# AURA Muted Light Matrix UI Makeover — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the AURA/Assure Next.js frontend with the "Muted Light Matrix" institutional design system while preserving every existing feature, API contract, and recent fix.

**Architecture:** Replace the dark Matrix Tailwind theme and components with a new slate/navy light theme derived from `newUI_matrixPLUSbright/stitch_aura_portfolio_assurance_platform/muted_light_matrix/DESIGN.md`. Build shared UI primitives first, then restyle each page and component one at a time. No backend changes.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, React 18, Recharts, clsx, Material Symbols.

## Global Constraints

- Background: `#F1F5F9` (`slate-100`).
- Surface/panels: `#E2E8F0` (`slate-200`) with 1px `#CBD5E1` (`slate-300`) borders.
- Primary: deep navy `#0F172A` (`slate-900`). Secondary: electric slate `#334155` (`slate-700`).
- Status: emerald (`#10B981`) success, ochre (`#D97706`) warning, crimson (`#DC2626`) error.
- Font: **JetBrains Mono** exclusively.
- Corner radius: `4px` on all interactive elements, containers, inputs.
- Circles reserved for status indicators and avatars only.
- Shadows: micro only — low opacity (5-8%), neutral grey, 2px offset.
- 4px base grid, 12-col desktop / 8-col tablet / 4-col mobile, 24px outer margins.
- All API calls remain unchanged; all component props and behavior remain unchanged unless restyling requires equivalent markup.
- Work in a feature branch; keep old Matrix component backups until final E2E passes.
- No `NEXT_PUBLIC_*` changes; deployment still uses same `API_URL` server-only env.

---

## File Structure Plan

### New shared primitives
- `frontend/src/components/ui/Panel.tsx` — bordered card with header.
- `frontend/src/components/ui/SectionHeader.tsx` — uppercase label + title.
- `frontend/src/components/ui/PrimaryButton.tsx` — navy fill button.
- `frontend/src/components/ui/SecondaryButton.tsx` — outlined slate button.
- `frontend/src/components/ui/StatusDot.tsx` — 8px circle status indicator.
- `frontend/src/components/ui/DataTable.tsx` — zebra-striped table shell.
- `frontend/src/components/ui/Sidebar.tsx` — left navigation rail.
- `frontend/src/components/ui/TopMetricCard.tsx` — metric card with optional sparkline slot.

### Updated theme/config
- `frontend/tailwind.config.ts` — extend with `aura` colors/spacing/typography; keep existing token names for gradual migration.
- `frontend/src/app/globals.css` — update base styles, scrollbar, remove CRT/scanline utilities.
- `frontend/src/app/layout.tsx` — remove `dark` class, switch to light background, use new Sidebar.

### Updated AppShell / pages
- `frontend/src/components/AppShell.tsx` — restyle with muted-light tokens.
- `frontend/src/app/page.tsx` — no logic change; consumes restyled `CommandCentreView`.
- `frontend/src/components/CommandCentreView.tsx` — new layout with `TopMetricCard`, `Heatmap`, `MarketPanel`, `TriageQueue`.
- `frontend/src/app/portfolio/[id]/page.tsx` — restyle header, narrative, breach lists, holdings table, allocation chart.
- `frontend/src/app/portfolio/[id]/workbench/page.tsx` — restyle ledger, recommendation, assurance checks, action bar.
- `frontend/src/app/hermes/page.tsx` — restyle cage banner, score, queue, strategy, history.

### Updated components
- `frontend/src/components/StatusBadge.tsx` — muted-light variant.
- `frontend/src/components/Heatmap.tsx` — new treemap colors and filter bar.
- `frontend/src/components/SummaryBar.tsx` — restyled KPI cards.
- `frontend/src/components/AssuranceBanner.tsx` — light banner with status pills.
- `frontend/src/components/MarketPanel.tsx` — light panel and chart colors.
- `frontend/src/components/NarrativePanel.tsx` — light narrative card.
- `frontend/src/components/BreachChips.tsx` — diagnostics chips/buttons.
- `frontend/src/components/HoldingsTable.tsx` — ledger table with zebra striping.
- `frontend/src/components/AllocationDonut.tsx` — allocation bar chart (replacing donut).
- `frontend/src/components/PerformanceChart.tsx` — light area chart.
- `frontend/src/components/WorkbenchTable.tsx` — trades ledger.
- `frontend/src/components/VerifyPanel.tsx` — before/after cards and rule checklist.
- `frontend/src/components/AuditTrail.tsx` — light timeline.
- `frontend/src/components/SuggestionChip.tsx` — light learning card.
- `frontend/src/components/hermes/HermesScorePanel.tsx` — score cards.
- `frontend/src/components/hermes/HermesQueue.tsx` — queue rows and bulk action.
- `frontend/src/components/hermes/HermesStrategyPanel.tsx` — strategy + reflection card.
- `frontend/src/components/hermes/HermesHistory.tsx` — history timeline.

---

## Task 1: Create feature branch and backup legacy components

**Files:**
- Modify: `frontend/tailwind.config.ts`
- Create branch: `feature/muted-light-makeover`
- Create backup directory: `frontend/src/components/_legacy/`

**Interfaces:**
- Consumes: existing Matrix theme config.
- Produces: isolated branch, legacy component backups.

- [ ] **Step 1: Create and switch branch**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping
git checkout -b feature/muted-light-makeover
```

Expected: branch created and checked out.

- [ ] **Step 2: Backup all existing components to `_legacy/`**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend/src/components
mkdir -p _legacy/hermes
cp -r *.tsx _legacy/ 2>/dev/null || true
cp hermes/*.tsx _legacy/hermes/ 2>/dev/null || true
```

Expected: `frontend/src/components/_legacy/` contains copies of all current components.

- [ ] **Step 3: Add new color primitives to tailwind config**

Modify `frontend/tailwind.config.ts` by inserting the following `extend` additions **alongside** the existing theme (do not delete existing keys yet):

```typescript
      colors: {
        // ... keep existing colors ...
        aura: {
          background: "#F1F5F9",
          surface: "#E2E8F0",
          "surface-low": "#F8FAFC",
          border: "#CBD5E1",
          "border-strong": "#94A3B8",
          navy: "#0F172A",
          "navy-hover": "#1E293B",
          slate: "#334155",
          "slate-light": "#64748B",
          text: "#1B1B1D",
          "text-muted": "#45464D",
          "text-subtle": "#76777D",
          emerald: "#10B981",
          "emerald-soft": "#D1FAE5",
          ochre: "#D97706",
          "ochre-soft": "#FEF3C7",
          crimson: "#DC2626",
          "crimson-soft": "#FEE2E2",
        },
      },
      fontFamily: {
        sans: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        display: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        aura: "4px",
      },
      boxShadow: {
        "aura-sm": "0 2px 4px rgba(15, 23, 42, 0.05)",
        "aura-md": "0 4px 6px rgba(15, 23, 42, 0.06)",
      },
```

Expected: `aura-*` utility classes become available in Tailwind.

- [ ] **Step 4: Commit**

```bash
git add frontend/tailwind.config.ts frontend/src/components/_legacy/
git commit -m "chore(makeover): branch + legacy backups + aura theme tokens

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Update global styles and layout

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/app/layout.tsx`
- Create: `frontend/src/components/ui/Sidebar.tsx`

**Interfaces:**
- Consumes: `aura-*` Tailwind classes.
- Produces: light-themed global CSS, `Sidebar` component exported as `{ Sidebar }`.

- [ ] **Step 2.1: Rewrite globals.css for muted-light base**

Replace the contents of `frontend/src/app/globals.css` with:

```css
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html {
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    font-variant-numeric: tabular-nums;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    background: #F1F5F9;
    color: #1B1B1D;
  }

  body {
    @apply bg-aura-background text-aura-text;
  }

  .material-symbols-outlined {
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  }
  .material-symbols-filled {
    font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  }
}

@layer utilities {
  .tabular {
    font-variant-numeric: tabular-nums;
  }

  .label-mono {
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .text-balance {
    text-wrap: balance;
  }
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: #E2E8F0;
}
::-webkit-scrollbar-thumb {
  background: #94A3B8;
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: #0F172A;
}
```

Expected: no CRT/scanline classes, light background, JetBrains Mono base.

- [ ] **Step 2.2: Create Sidebar component**

Create `frontend/src/components/ui/Sidebar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

const navItems = [
  { id: "command", label: "Command Centre", icon: "dashboard", href: "/" },
  { id: "diagnosis", label: "Diagnosis", icon: "stethoscope", href: "#" },
  { id: "hermes", label: "Hermes Engine", icon: "auto_awesome", href: "/hermes" },
  { id: "audit", label: "Audit Log", icon: "history_edu", href: "#" },
  { id: "settings", label: "Settings", icon: "settings", href: "#" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex fixed left-0 top-0 h-full w-[220px] flex-col bg-aura-surface border-r border-aura-border z-30">
      <div className="h-[64px] flex items-center px-5 border-b border-aura-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-aura-navy flex items-center justify-center">
            <span className="material-symbols-outlined text-white text-[18px]">terminal</span>
          </div>
          <div>
            <div className="font-mono text-sm font-bold text-aura-text">AURA</div>
            <div className="font-mono text-[10px] uppercase text-aura-text-subtle">Assurance</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-4 px-3 flex flex-col gap-1">
        {navItems.map((item) => {
          const active = item.href !== "#" && (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href));
          return (
            <Link
              key={item.id}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded text-sm font-medium transition-colors",
                active
                  ? "bg-aura-navy text-white"
                  : "text-aura-text-muted hover:bg-aura-surface-low hover:text-aura-text"
              )}
            >
              <span className={clsx("material-symbols-outlined text-[18px]", active && "material-symbols-filled")}>{item.icon}</span>
              <span className="font-mono">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-aura-border">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-aura-emerald" />
          <span className="font-mono text-[10px] uppercase text-aura-text-subtle">System Live</span>
        </div>
      </div>
    </aside>
  );
}
```

Expected: `Sidebar` renders a fixed left rail with Command Centre, Diagnosis, Hermes, Audit Log, Settings.

- [ ] **Step 2.3: Update layout.tsx**

Replace `frontend/src/app/layout.tsx`:

```tsx
import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata = { title: "AURA — Portfolio Assurance" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-aura-background text-aura-text antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
```

Expected: removes `className="dark"`, applies light background.

- [ ] **Step 2.4: Restyle AppShell**

Replace `frontend/src/components/AppShell.tsx`:

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { Sidebar } from "@/components/ui/Sidebar";

const mobileTabs = [
  { id: "command", label: "Command", icon: "dashboard", href: "/" },
  { id: "hermes", label: "Hermes", icon: "auto_awesome", href: "/hermes" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isHome = pathname === "/";

  return (
    <div className="min-h-screen bg-aura-background">
      <Sidebar />

      <header className="fixed top-0 left-0 lg:left-[220px] right-0 h-[64px] bg-aura-surface border-b border-aura-border flex items-center justify-between px-4 lg:px-6 z-20">
        <div className="flex items-center gap-3">
          <button
            className="lg:hidden p-2 -ml-2 rounded hover:bg-aura-surface-low text-aura-text"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
          >
            <span className="material-symbols-outlined">menu</span>
          </button>
          <div className="hidden lg:block font-mono text-[10px] uppercase text-aura-text-subtle">
            AURA / Portfolio Assurance Platform
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded bg-aura-surface-low border border-aura-border">
            <span className="w-2 h-2 rounded-full bg-aura-emerald" />
            <span className="font-mono text-[10px] uppercase text-aura-navy">Live</span>
          </div>
        </div>
      </header>

      {drawerOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-aura-navy/30" onClick={() => setDrawerOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-[220px] bg-aura-surface border-r border-aura-border flex flex-col">
            <div className="h-[64px] flex items-center px-5 border-b border-aura-border justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-aura-navy flex items-center justify-center">
                  <span className="material-symbols-outlined text-white text-[18px]">terminal</span>
                </div>
                <span className="font-mono text-sm font-bold text-aura-text">AURA</span>
              </div>
              <button onClick={() => setDrawerOpen(false)} aria-label="Close navigation">
                <span className="material-symbols-outlined text-aura-text">close</span>
              </button>
            </div>
            <nav className="flex-1 py-4 px-3 flex flex-col gap-1">
              {mobileTabs.map((tab) => {
                const active = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
                return (
                  <Link
                    key={tab.id}
                    href={tab.href}
                    onClick={() => setDrawerOpen(false)}
                    className={clsx(
                      "flex items-center gap-3 px-3 py-2 rounded text-sm font-medium",
                      active ? "bg-aura-navy text-white" : "text-aura-text-muted hover:bg-aura-surface-low"
                    )}
                  >
                    <span className="material-symbols-outlined text-[18px]">{tab.icon}</span>
                    <span className="font-mono">{tab.label}</span>
                  </Link>
                );
              })}
            </nav>
          </aside>
        </div>
      )}

      <main className="pt-[64px] lg:pl-[220px] min-h-screen bg-aura-background">
        <div className="pb-24">{children}</div>
      </main>

      {isHome && (
        <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-aura-surface border-t border-aura-border z-40 flex justify-around items-center h-16">
          {mobileTabs.map((tab) => {
            const active = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.id}
                href={tab.href}
                className={clsx(
                  "flex flex-col items-center justify-center gap-0.5 w-full h-full text-[11px] font-medium",
                  active ? "text-aura-navy" : "text-aura-text-muted"
                )}
              >
                <span className={clsx("material-symbols-outlined text-[22px]", active && "material-symbols-filled")}>{tab.icon}</span>
                <span className="font-mono uppercase">{tab.label}</span>
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
```

Expected: `AppShell` uses new `Sidebar`, light topbar, no CRT overlay, proper layout offsets.

- [ ] **Step 2.5: Verify build**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 2.6: Commit**

```bash
git add frontend/src/app/globals.css frontend/src/app/layout.tsx frontend/src/components/AppShell.tsx frontend/src/components/ui/Sidebar.tsx
git commit -m "feat(makeover): global styles, layout, and sidebar

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Build shared UI primitives

**Files:**
- Create: `frontend/src/components/ui/Panel.tsx`
- Create: `frontend/src/components/ui/SectionHeader.tsx`
- Create: `frontend/src/components/ui/PrimaryButton.tsx`
- Create: `frontend/src/components/ui/SecondaryButton.tsx`
- Create: `frontend/src/components/ui/StatusDot.tsx`
- Create: `frontend/src/components/ui/DataTable.tsx`
- Create: `frontend/src/components/ui/TopMetricCard.tsx`

**Interfaces:**
- Consumes: `aura-*` Tailwind classes.
- Produces: reusable primitives used by all page components.

- [ ] **Step 3.1: Create Panel.tsx**

```tsx
import { clsx } from "clsx";

export function Panel({
  children,
  className,
  header,
  subheader,
  right,
}: {
  children: React.ReactNode;
  className?: string;
  header?: React.ReactNode;
  subheader?: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className={clsx("bg-aura-surface-low border border-aura-border rounded overflow-hidden", className)}>
      {(header || subheader || right) && (
        <div className="px-4 py-3 border-b border-aura-border bg-aura-surface flex items-center justify-between gap-4">
          <div>
            {header && <h3 className="font-mono text-base font-semibold text-aura-text">{header}</h3>}
            {subheader && <p className="font-mono text-xs text-aura-text-subtle mt-0.5">{subheader}</p>}
          </div>
          {right && <div>{right}</div>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
```

- [ ] **Step 3.2: Create SectionHeader.tsx**

```tsx
export function SectionHeader({ label, title }: { label?: string; title: string }) {
  return (
    <div className="mb-3">
      {label && <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">{label}</p>}
      <h2 className="font-mono text-lg font-semibold text-aura-text">{title}</h2>
    </div>
  );
}
```

- [ ] **Step 3.3: Create PrimaryButton.tsx**

```tsx
import { clsx } from "clsx";

export function PrimaryButton({
  children,
  onClick,
  disabled,
  type = "button",
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "px-4 py-2 rounded bg-aura-navy text-white font-mono text-sm font-medium",
        "hover:bg-aura-navy-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
        className
      )}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 3.4: Create SecondaryButton.tsx**

```tsx
import { clsx } from "clsx";

export function SecondaryButton({
  children,
  onClick,
  disabled,
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "px-4 py-2 rounded border border-aura-border text-aura-navy font-mono text-sm font-medium",
        "hover:bg-aura-surface disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
        className
      )}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 3.5: Create StatusDot.tsx**

```tsx
import { clsx } from "clsx";
import type { Status } from "@/lib/types";

const MAP: Record<Status, string> = {
  green: "bg-aura-emerald",
  orange: "bg-aura-ochre",
  red: "bg-aura-crimson",
};

export function StatusDot({ status, className }: { status: Status; className?: string }) {
  return <span className={clsx("w-2 h-2 rounded-full", MAP[status], className)} />;
}
```

- [ ] **Step 3.6: Create DataTable.tsx**

```tsx
import { clsx } from "clsx";

export function DataTable({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("overflow-x-auto", className)}>
      <table className="w-full text-left border-collapse">{children}</table>
    </div>
  );
}

export function DataTableHead({ children }: { children: React.ReactNode }) {
  return <thead className="bg-aura-surface border-b border-aura-border">{children}</thead>;
}

export function DataTableBody({ children }: { children: React.ReactNode }) {
  return <tbody className="divide-y divide-aura-border">{children}</tbody>;
}

export function DataTableRow({
  children,
  highlighted,
}: {
  children: React.ReactNode;
  highlighted?: boolean;
}) {
  return (
    <tr
      className={clsx(
        "hover:bg-aura-surface transition-colors",
        highlighted ? "bg-aura-crimson-soft" : "even:bg-aura-surface-low"
      )}
    >
      {children}
    </tr>
  );
}

export function DataTableCell({
  children,
  align = "left",
  className,
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}) {
  return (
    <td
      className={clsx(
        "px-3 py-3 font-mono text-sm text-aura-text",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className
      )}
    >
      {children}
    </td>
  );
}

export function DataTableHeader({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
}) {
  return (
    <th
      className={clsx(
        "px-3 py-2.5 font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold",
        align === "right" && "text-right",
        align === "center" && "text-center"
      )}
    >
      {children}
    </th>
  );
}
```

- [ ] **Step 3.7: Create TopMetricCard.tsx**

```tsx
import { clsx } from "clsx";

export function TopMetricCard({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "emerald" | "ochre" | "crimson";
}) {
  const toneClasses = {
    neutral: "border-aura-border",
    emerald: "border-aura-emerald bg-aura-emerald-soft/30",
    ochre: "border-aura-ochre bg-aura-ochre-soft/30",
    crimson: "border-aura-crimson bg-aura-crimson-soft/30",
  };
  const valueClasses = {
    neutral: "text-aura-text",
    emerald: "text-aura-emerald",
    ochre: "text-aura-ochre",
    crimson: "text-aura-crimson",
  };

  return (
    <div className={clsx("border rounded p-4 flex flex-col justify-between", toneClasses[tone])}>
      <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider">{label}</p>
      <div className={clsx("font-mono text-2xl font-bold mt-2 tabular-nums", valueClasses[tone])}>{value}</div>
      {sub && <p className="font-mono text-xs text-aura-text-muted mt-1">{sub}</p>}
    </div>
  );
}
```

- [ ] **Step 3.8: Verify build**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3.9: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat(makeover): shared UI primitives

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Update status badge and rebuild Command Centre components

**Files:**
- Modify: `frontend/src/components/StatusBadge.tsx`
- Modify: `frontend/src/components/SummaryBar.tsx`
- Modify: `frontend/src/components/AssuranceBanner.tsx`
- Modify: `frontend/src/components/Heatmap.tsx`
- Modify: `frontend/src/components/TriageQueue.tsx`
- Modify: `frontend/src/components/MarketPanel.tsx`
- Modify: `frontend/src/components/CommandCentreView.tsx`

**Interfaces:**
- Consumes: `Panel`, `TopMetricCard`, `SectionHeader`, `StatusDot`, `aura-*` classes.
- Produces: restyled Command Centre page.

- [ ] **Step 4.1: Update StatusBadge.tsx**

Replace with:

```tsx
import { clsx } from "clsx";
import type { Status } from "@/lib/types";
import { StatusDot } from "@/components/ui/StatusDot";

const LABEL: Record<Status, string> = {
  green: "ALIGNED",
  orange: "ATTENTION",
  red: "BREACH",
};

const STYLE: Record<Status, string> = {
  green: "bg-aura-emerald-soft border-aura-emerald text-aura-emerald",
  orange: "bg-aura-ochre-soft border-aura-ochre text-aura-ochre",
  red: "bg-aura-crimson-soft border-aura-crimson text-aura-crimson",
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border font-mono",
        STYLE[status]
      )}
    >
      <StatusDot status={status} />
      {LABEL[status]}
    </span>
  );
}
```

Expected: existing tests in `StatusBadge.test.tsx` still pass.

- [ ] **Step 4.2: Update SummaryBar.tsx**

Replace with:

```tsx
import { TopMetricCard } from "@/components/ui/TopMetricCard";

export function SummaryBar({ counts, breach_count, total, totalFum }: {
  counts: Record<string, number>;
  breach_count: number;
  total: number;
  totalFum: number;
}) {
  const aligned = counts.green ?? 0;
  const alignedPct = total ? ((aligned / total) * 100).toFixed(1) : "0.0";
  const fumBillions = totalFum / 1e9;
  const fumLabel = fumBillions >= 1 ? `$${fumBillions.toFixed(2)}B` : `$${(totalFum / 1e6).toFixed(1)}M`;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <TopMetricCard label="Total Managed FUM" value={fumLabel} />
      <TopMetricCard label="Aligned" value={`${alignedPct}%`} sub={`${aligned} of ${total} portfolios`} tone="emerald" />
      <TopMetricCard label="Needs Attention" value={String(counts.orange ?? 0)} sub={`${counts.orange ?? 0} Portfolios`} tone="ochre" />
      <TopMetricCard label="Breached" value={String(counts.red ?? 0)} sub={`${breach_count} mandate breaches`} tone="crimson" />
    </div>
  );
}
```

- [ ] **Step 4.3: Update AssuranceBanner.tsx**

Replace with:

```tsx
export function AssuranceBanner({ summary, aiNarrative }: {
  summary: { total: number; counts: Record<string, number>; breach_count: number };
  aiNarrative?: string;
}) {
  const { green = 0, orange = 0, red = 0 } = summary.counts;
  const breach_count = summary.breach_count ?? 0;

  return (
    <div className="bg-aura-surface-low border border-aura-border rounded p-4 mb-6">
      <div className="flex items-start gap-4">
        <div className="p-2 bg-aura-navy rounded text-white flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined material-symbols-filled text-[20px]">fact_check</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h2 className="font-mono text-base font-bold text-aura-text">System Assurance Summary</h2>
            <span className="font-mono text-[10px] uppercase px-1.5 py-0.5 rounded border border-aura-emerald text-aura-emerald">AI-Grounded</span>
          </div>
          <div className="font-mono text-sm text-aura-text-muted space-y-1">
            <p>{summary.total} portfolios loaded // {green} aligned // {orange} attention // {red} breach.</p>
            <p>{breach_count} mandate breaches detected across {red} portfolios.</p>
            {aiNarrative && <p className="text-aura-text">AI summary: {aiNarrative}</p>}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatPill value={green} label="ALIGNED" tone="emerald" />
            <StatPill value={orange} label="ATTENTION" tone="ochre" />
            <StatPill value={red} label="BREACH" tone="crimson" />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatPill({ value, label, tone }: { value: number; label: string; tone: "emerald" | "ochre" | "crimson" }) {
  const map = {
    emerald: "border-aura-emerald text-aura-emerald bg-aura-emerald-soft",
    ochre: "border-aura-ochre text-aura-ochre bg-aura-ochre-soft",
    crimson: "border-aura-crimson text-aura-crimson bg-aura-crimson-soft",
  };
  return (
    <div className={`px-2.5 py-1 rounded border font-mono text-xs flex items-center gap-2 ${map[tone]}`}>
      <span className="font-bold text-sm">{value}</span>
      <span className="opacity-80">{label}</span>
    </div>
  );
}
```

- [ ] **Step 4.4: Update Heatmap.tsx colors only**

Keep all existing logic, filters, pagination, treemap behavior. Replace the color constants at the top and className strings to use muted-light palette:

```typescript
const COLOR: Record<string, string> = {
  green: "#10B981",
  orange: "#D97706",
  red: "#DC2626",
};
const BORDER: Record<string, string> = {
  green: "#059669",
  orange: "#B45309",
  red: "#B91C1C",
};
const TEXT: Record<string, string> = {
  green: "#FFFFFF",
  orange: "#FFFFFF",
  red: "#FFFFFF",
};
```

Replace `className` occurrences referencing Matrix tokens with equivalent `aura-*` tokens:
- `bg-matrix-panel` → `bg-aura-surface-low`
- `border-matrix-line` → `border-aura-border`
- `bg-matrix-void` → `bg-aura-surface`
- `text-matrix-text` → `text-aura-text`
- `text-matrix-muted` → `text-aura-text-muted`
- `text-matrix-green` → `text-aura-emerald`
- `hover:border-matrix-green` → `hover:border-aura-navy`
- `hover:text-matrix-green` → `hover:text-aura-navy`
- Remove `scanlines` overlay div inside treemap container.
- Tooltip: `bg-matrix-void` → `bg-aura-surface`, `border-matrix-green` → `border-aura-border`, text classes → `text-aura-text`/`text-aura-text-muted`/`text-aura-ochre`.

Do not change data shape, page size, sorting, filtering, routing.

- [ ] **Step 4.5: Update TriageQueue.tsx**

Replace Matrix class names with aura equivalents, keeping Link behavior and urgent logic:
- `bg-matrix-panel` → `bg-aura-surface-low`
- `border-matrix-line` → `border-aura-border`
- `bg-matrix-void` → `bg-aura-surface`
- `text-matrix-text` → `text-aura-text`
- `text-matrix-muted` → `text-aura-text-muted`
- `bg-matrix-red-soft` → `bg-aura-crimson-soft`
- `border-matrix-red` → `border-aura-crimson`
- `text-matrix-red` → `text-aura-crimson`
- `bg-matrix-amber-soft` → `bg-aura-ochre-soft`
- `border-matrix-amber` → `border-aura-ochre`
- `text-matrix-amber` → `text-aura-ochre`
- `hover:bg-matrix-surface` → `hover:bg-aura-surface`
- `hover:text-matrix-green` → `hover:text-aura-navy`
- `text-matrix-green` → `text-aura-navy`
- Remove `pulse-red` from emergency icon.
- Remove `glow-hover`.

- [ ] **Step 4.6: Update MarketPanel.tsx**

Keep all logic, state, polling, API calls, error handling. Replace class names:
- `bg-matrix-panel` → `bg-aura-surface-low`
- `border-matrix-line` → `border-aura-border`
- `text-matrix-text` → `text-aura-text`
- `text-matrix-muted` → `text-aura-text-muted`
- `text-matrix-green` → `text-aura-emerald`
- `border-matrix-green` → `border-aura-emerald`
- `hover:bg-matrix-green/10` → `hover:bg-aura-emerald-soft`
- `bg-matrix-void` → `bg-aura-surface`
- Chart area: change gradient stops to `#0F172A` with opacity, grid stroke `#CBD5E1`, tooltip light styles.
- Remove Matrix-specific button copy (`▶`, `❚❚`) to plain text: `Tick`, `Auto-run`, `Pause`.

- [ ] **Step 4.7: Update CommandCentreView.tsx layout**

Replace the inner layout to match the new top metric row / heatmap / triage / market panel arrangement:

```tsx
return (
  <div className="p-4 lg:p-6 max-w-[1440px] mx-auto">
    <div className="mb-6">
      <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">Command Centre</p>
      <h1 className="font-mono text-2xl font-bold text-aura-text">Global Portfolio Assurance</h1>
    </div>
    <AssuranceBanner summary={summary} aiNarrative={aiNarrative} />
    <MarketPanel onTick={onTick} />
    <SummaryBar counts={summary.counts} breach_count={summary.breach_count} total={summary.total} totalFum={totalFum} />
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div className="lg:col-span-8 xl:col-span-9">
        <Heatmap portfolios={heatmapPortfolios} syncing={syncing} rest={rest} />
      </div>
      <div className="lg:col-span-4 xl:col-span-3">
        <TriageQueue portfolios={heatmapPortfolios} />
      </div>
    </div>
  </div>
);
```

Expected: Command Centre renders in new layout with all existing data and behavior preserved.

- [ ] **Step 4.8: Run tests and build**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend
npx vitest run
npx tsc --noEmit
```

Expected: vitest passes, tsc clean.

- [ ] **Step 4.9: Commit**

```bash
git add frontend/src/components/StatusBadge.tsx frontend/src/components/SummaryBar.tsx frontend/src/components/AssuranceBanner.tsx frontend/src/components/Heatmap.tsx frontend/src/components/TriageQueue.tsx frontend/src/components/MarketPanel.tsx frontend/src/components/CommandCentreView.tsx
git commit -m "feat(makeover): command centre page restyled

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Rebuild Diagnosis page

**Files:**
- Modify: `frontend/src/components/NarrativePanel.tsx`
- Modify: `frontend/src/components/BreachChips.tsx`
- Modify: `frontend/src/components/HoldingsTable.tsx`
- Modify: `frontend/src/components/AllocationDonut.tsx` → convert to bar chart
- Modify: `frontend/src/components/PerformanceChart.tsx`
- Modify: `frontend/src/app/portfolio/[id]/page.tsx`

**Interfaces:**
- Consumes: `Panel`, `SectionHeader`, `PrimaryButton`, `SecondaryButton`, `StatusDot`, `DataTable`, `StatusBadge`, `aura-*` classes.
- Produces: restyled `/portfolio/[id]` page.

- [ ] **Step 5.1: Update NarrativePanel.tsx**

Keep API call and state logic. Replace markup:

```tsx
return (
  <div className="bg-aura-surface-low border border-aura-border rounded p-4 mb-6 relative overflow-hidden">
    <div className="absolute left-0 top-0 bottom-0 w-1 bg-aura-navy" />
    <div className="pl-4">
      <div className="flex items-center gap-2 text-aura-navy mb-2">
        <span className="material-symbols-outlined material-symbols-filled">auto_awesome</span>
        <h3 className="font-mono text-lg font-semibold">Assurance Narrative</h3>
      </div>
      {loading ? (
        <p className="font-mono text-sm text-aura-text-muted">Reading portfolio...</p>
      ) : (
        <div className="font-mono text-sm text-aura-text-muted leading-relaxed max-w-3xl space-y-2">
          {narr.split(/(?<=[.!?])\s+/).map((sentence, i) => (
            <p key={i}>{sentence}</p>
          ))}
        </div>
      )}
    </div>
  </div>
);
```

- [ ] **Step 5.2: Update BreachChips.tsx**

Keep state, API calls, Explain behavior, popover logic. Replace class names with aura equivalents:
- `bg-matrix-red-soft` → `bg-aura-crimson-soft`
- `border-matrix-red/30` → `border-aura-crimson`
- `text-matrix-red` → `text-aura-crimson`
- `bg-matrix-amber-soft` → `bg-aura-ochre-soft`
- `border-matrix-amber/30` → `border-aura-ochre`
- `text-matrix-amber` → `text-aura-ochre`
- `ring-matrix-green` → `ring-aura-navy`
- `ring-offset-matrix-black` → `ring-offset-aura-background`
- `bg-matrix-void` → `bg-aura-surface`
- `border-matrix-green/30` → `border-aura-border`
- `shadow-[...green...]` → `shadow-aura-md`
- `text-matrix-green` → `text-aura-navy`
- `text-matrix-muted` → `text-aura-text-muted`

Remove uppercase tracking-wide from the chip text if it hurts readability, or keep it. Use `font-mono text-xs`.

- [ ] **Step 5.3: Update HoldingsTable.tsx**

Keep all state, API calls, highlight logic, explain targeting. Replace table markup to use `DataTable` primitives or equivalent aura classes:
- Wrap table in `Panel` from `ui/Panel`.
- Header: `bg-aura-surface border-b border-aura-border`.
- Rows: zebra striping via `even:bg-aura-surface-low`; highlighted rows use `bg-aura-crimson-soft` and left border `border-l-4 border-aura-crimson`.
- Text: `text-aura-text`, `text-aura-text-muted`, `text-aura-crimson` for highlighted weights.
- Status indicator: use `StatusDot` + label.
- Explain button: small secondary button style.
- Remove `glow-hover`.

- [ ] **Step 5.4: Convert AllocationDonut to AllocationBarChart**

Create `frontend/src/components/AllocationBarChart.tsx`:

```tsx
"use client";

import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";
import type { Holding, Mandate, RulesResult } from "@/lib/types";
import { api } from "@/lib/api";
import { metricForAssetClass } from "@/lib/explainMetric";
import { Panel } from "@/components/ui/Panel";

const PALETTE = ["#0F172A", "#334155", "#64748B", "#94A3B8", "#CBD5E1", "#E2E8F0"];

export function AllocationBarChart({ holdings, clientId, mandate, rulesResult }: {
  holdings: Holding[];
  clientId?: string;
  mandate?: Mandate;
  rulesResult?: RulesResult;
}) {
  const [explain, setExplain] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const by: Record<string, number> = {};
  for (const h of holdings) by[h.asset_class] = (by[h.asset_class] || 0) + h.market_value;
  const data = Object.entries(by)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const top = data[0];

  const offending = new Set<string>();
  if (rulesResult) {
    for (const b of rulesResult.breaches) {
      if (b.rule.startsWith("max_asset_class_weight:")) offending.add(b.rule.split(":")[1]);
    }
    for (const w of rulesResult.watches) {
      if (w.rule.startsWith("drift:")) offending.add(w.rule.split(":")[1]);
    }
  }

  const explainTop = async () => {
    if (!clientId || !top) return;
    setLoading(true);
    try {
      const metric = metricForAssetClass(rulesResult, top.name);
      const r = await api.explain(clientId, metric ?? undefined);
      setExplain(r.narrative);
    } catch {
      setExplain("Explain unavailable");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel header="Allocation Profile" subheader="Current vs mandate" right={clientId && (
      <button onClick={explainTop} disabled={loading} className="font-mono text-xs text-aura-navy hover:underline disabled:opacity-50">
        {loading ? "Asking..." : "Explain"}
      </button>
    )}>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 40, bottom: 0 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", fill: "#334155" }} axisLine={{ stroke: "#CBD5E1" }} tickLine={false} />
            <Tooltip
              cursor={{ fill: "#F1F5F9" }}
              contentStyle={{ backgroundColor: "#FFFFFF", border: "1px solid #CBD5E1", borderRadius: "4px", fontSize: "12px", fontFamily: "JetBrains Mono, monospace" }}
              formatter={(value: number) => [`${((value / total) * 100).toFixed(1)}%`, "Weight"]}
              labelFormatter={() => ""}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {data.map((d, i) => (
                <Cell key={i} fill={offending.has(d.name) ? "#DC2626" : PALETTE[i % PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {explain && (
        <div className="mt-3 bg-aura-surface border border-aura-border rounded p-3 font-mono text-xs text-aura-text-muted">
          <span className="text-aura-navy">AI Explain:</span> {explain}
        </div>
      )}
      <div className="mt-4 grid grid-cols-2 gap-2 font-mono text-xs text-aura-text-muted">
        {data.map((d, i) => {
          const cap = mandate?.max_asset_class_weight?.[d.name];
          return (
            <div key={d.name} className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: offending.has(d.name) ? "#DC2626" : PALETTE[i % PALETTE.length] }} />
              <span className={offending.has(d.name) ? "text-aura-crimson font-medium" : i === 0 ? "text-aura-navy font-medium" : ""}>
                {d.name} ({((d.value / total) * 100).toFixed(0)}%{cap ? `/${(cap * 100).toFixed(0)}%` : ""})
              </span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
```

Expected: replaces donut with vertical bar chart; explain targeting preserved.

- [ ] **Step 5.5: Update PerformanceChart.tsx**

Keep chart data generation. Replace colors:
- Container: `bg-aura-surface-low border border-aura-border`.
- Gradient stops: `#0F172A` with opacity.
- Stroke: `#0F172A`.
- Grid stroke: `#CBD5E1`.
- Tooltip: light styles.
- Title: `text-aura-text`, subtitle `text-aura-text-muted`.

- [ ] **Step 5.6: Update Diagnosis page**

Replace `frontend/src/app/portfolio/[id]/page.tsx` with new layout:

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Portfolio } from "@/lib/types";
import { NarrativePanel } from "@/components/NarrativePanel";
import { BreachChips } from "@/components/BreachChips";
import { HoldingsTable } from "@/components/HoldingsTable";
import { AllocationBarChart } from "@/components/AllocationBarChart";
import { PerformanceChart } from "@/components/PerformanceChart";
import { StatusBadge } from "@/components/StatusBadge";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Diagnosis({ params }: { params: { id: string } }) {
  const { id } = params;
  const [p, setP] = useState<Portfolio | null>(null);
  const [hl, setHl] = useState<string[]>([]);
  const [err, setErr] = useState(false);

  useEffect(() => {
    api.getPortfolio(id).then((portfolio) => {
      setP(portfolio);
      const offenders = new Set<string>();
      portfolio.rules_result?.breaches.forEach((b) => b.offending_holdings.forEach((t) => offenders.add(t)));
      portfolio.rules_result?.watches.forEach((w) => w.offending_holdings.forEach((t) => offenders.add(t)));
      setHl(Array.from(offenders));
    }).catch(() => setErr(true));
  }, [id]);

  if (err) return <div className="p-8 font-mono text-aura-crimson">Backend unreachable. Check backend and retry.</div>;
  if (!p) return <div className="p-8 font-mono text-aura-navy">Loading entity data...</div>;
  const rr = p.rules_result!;
  const totalValue = p.holdings.reduce((s, h) => s + h.market_value, 0) + p.cash;

  return (
    <div className="p-4 lg:p-6 max-w-[1440px] mx-auto">
      <Link href="/" className="inline-flex items-center gap-1.5 text-aura-text-muted hover:text-aura-navy font-mono text-xs mb-4">
        <span className="material-symbols-outlined text-[16px]">arrow_back</span>
        <span className="uppercase tracking-wide">Back to Command Centre</span>
      </Link>

      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-6">
        <div className="w-full">
          <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">Entity // {p.client_id}</p>
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <h1 className="font-mono text-2xl font-bold text-aura-text">{p.client_name}</h1>
            <StatusBadge status={rr.status} />
          </div>
          <div className="flex flex-wrap items-center gap-4 text-aura-text-muted font-mono text-xs">
            <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px]">person</span>Adviser: {p.adviser}</span>
            <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-aura-emerald">verified</span>Deterministic checks + AI narrative advisory</span>
          </div>
        </div>
        <div className="text-right flex flex-col items-end gap-3 w-full md:w-auto">
          <div>
            <p className="font-mono text-[10px] uppercase text-aura-text-subtle mb-0.5">Total Portfolio Value</p>
            <p className="font-mono text-xl font-bold tabular-nums text-aura-navy">${totalValue.toLocaleString()}</p>
          </div>
          <Link href={`/portfolio/${id}/workbench`}>
            <PrimaryButton className="flex items-center gap-2">
              <span className="uppercase tracking-wide">Open Remediation</span>
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            </PrimaryButton>
          </Link>
        </div>
      </div>

      <NarrativePanel clientId={id} rules_result={rr} />

      {rr.breaches.length > 0 && (
        <section className="mb-6">
          <SectionHeader label="Diagnostics" title={`${rr.breaches.length} Mandate Breach${rr.breaches.length > 1 ? "es" : ""}`} />
          <BreachChips items={rr.breaches} onPick={setHl} clientId={id} />
        </section>
      )}

      {rr.watches.length > 0 && (
        <section className="mb-6">
          <SectionHeader label="Watchlist" title={`${rr.watches.length} Drift Watch${rr.watches.length > 1 ? "es" : ""}`} />
          <BreachChips items={rr.watches} onPick={setHl} clientId={id} />
        </section>
      )}

      <div className="mb-6 p-3 rounded bg-aura-surface border border-aura-border font-mono text-xs text-aura-text-muted">
        <span className="text-aura-text">Confidence line:</span> rule checks are{" "}
        <span className="text-aura-emerald font-bold">deterministic (100% rule maths)</span>. The narrative is{" "}
        <span className="text-aura-ochre font-bold">advisory (AI-inferred)</span>. The rules engine decides compliance.
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <HoldingsTable holdings={p.holdings} cash={p.cash} highlight={hl} clientId={id} rulesResult={rr} />
        </div>
        <div className="lg:col-span-1 space-y-6">
          <AllocationBarChart holdings={p.holdings} clientId={id} mandate={p.mandate} rulesResult={rr} />
          <PerformanceChart seed={id.length * 7} />
        </div>
      </div>
    </div>
  );
}
```

Expected: Diagnosis page renders with new layout; all explain/highlight logic preserved.

- [ ] **Step 5.7: Remove AllocationDonut.tsx or leave in place**

Since the page now imports `AllocationBarChart`, remove the old `AllocationDonut.tsx` import dependency. The file can remain in `_legacy/` backup. If any other file imports it, update to `AllocationBarChart`.

Check with grep:

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend/src
grep -R "AllocationDonut" --include="*.tsx" --include="*.ts" .
```

Expected: only the backup file or none.

- [ ] **Step 5.8: Verify build and tests**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend
npx vitest run
npx tsc --noEmit
```

Expected: passes.

- [ ] **Step 5.9: Commit**

```bash
git add frontend/src/app/portfolio/[id]/page.tsx frontend/src/components/NarrativePanel.tsx frontend/src/components/BreachChips.tsx frontend/src/components/HoldingsTable.tsx frontend/src/components/AllocationBarChart.tsx frontend/src/components/PerformanceChart.tsx
git rm frontend/src/components/AllocationDonut.tsx 2>/dev/null || true
git commit -m "feat(makeover): diagnosis page restyled with allocation bar chart

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Rebuild Workbench page

**Files:**
- Modify: `frontend/src/components/WorkbenchTable.tsx`
- Modify: `frontend/src/components/VerifyPanel.tsx`
- Modify: `frontend/src/components/AuditTrail.tsx`
- Modify: `frontend/src/components/SuggestionChip.tsx`
- Modify: `frontend/src/app/portfolio/[id]/workbench/page.tsx`

**Interfaces:**
- Consumes: `Panel`, `SectionHeader`, `PrimaryButton`, `SecondaryButton`, `DataTable`, `StatusBadge`, `aura-*` classes.
- Produces: restyled `/portfolio/[id]/workbench` page.

- [ ] **Step 6.1: Update WorkbenchTable.tsx**

Keep all state, CSV export logic, editable units, rationale, exportCsv function. Replace table markup with aura classes:
- Wrap in `Panel` with header "Flagged Ledger Entries" and right-side `SecondaryButton` for Export CSV.
- Use `DataTable` primitives or equivalent aura classes.
- Header: `bg-aura-surface border-b border-aura-border`, uppercase label text.
- Rows: zebra striping, `text-aura-text`, `text-aura-text-muted`.
- Action cells: use small outlined buttons for +/- and the delete action.
- Inputs: `border border-aura-border rounded px-2 py-1 bg-white text-aura-text font-mono text-sm focus:outline-none focus:border-aura-navy`.
- Keep RFC-4180 CSV escaping unchanged.

- [ ] **Step 6.2: Update VerifyPanel.tsx**

Keep props and logic. Replace markup with aura classes:
- Panel wrapper: `bg-aura-surface-low border border-aura-border rounded`.
- Header icon: navy background, white icon.
- Before/After cards: use `Panel` or bordered divs with status colors.
- Current state: green/amber/crimson soft backgrounds and text.
- Post-trade: emerald or crimson based on `resolved`.
- Rule checklist: use `StatusDot` or check/cancel icons in `text-aura-emerald`/`text-aura-crimson`.
- Progress bars if any: `bg-aura-border` track with `bg-aura-emerald`/`bg-aura-crimson` fill.

- [ ] **Step 6.3: Update AuditTrail.tsx**

Keep API call and filtering. Replace markup:
- Wrap in `Panel` header "Audit Trail".
- Entries: `border-b border-aura-border` list.
- Timestamp `text-aura-text-muted`.
- Tier badge: `bg-aura-emerald-soft border-aura-emerald text-aura-emerald` for deterministic, `bg-aura-ochre-soft border-aura-ochre text-aura-ochre` for advisory.

- [ ] **Step 6.4: Update SuggestionChip.tsx**

Keep API call and adopt/dismiss logic. Replace markup:
- `bg-aura-ochre-soft border border-aura-ochre rounded p-4`.
- Buttons: `PrimaryButton` for Adopt, `SecondaryButton` for Dismiss.

- [ ] **Step 6.5: Update Workbench page.tsx**

Replace with new layout:

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Portfolio, RemediationResult, Trade, RulesResult } from "@/lib/types";
import { WorkbenchTable } from "@/components/WorkbenchTable";
import { VerifyPanel } from "@/components/VerifyPanel";
import { AuditTrail } from "@/components/AuditTrail";
import { SuggestionChip } from "@/components/SuggestionChip";
import { StatusBadge } from "@/components/StatusBadge";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Workbench({ params }: { params: { id: string } }) {
  const { id } = params;
  const [p, setP] = useState<Portfolio | null>(null);
  const [res, setRes] = useState<RemediationResult | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [liveVerify, setLiveVerify] = useState<RulesResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [approved, setApproved] = useState(false);
  const [newStatus, setNewStatus] = useState<string | null>(null);
  const [err, setErr] = useState(false);
  const [approveErr, setApproveErr] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [approvedRulesResult, setApprovedRulesResult] = useState<RulesResult | null>(null);

  useEffect(() => {
    setApprovedRulesResult(null);
    api.getPortfolio(id).then(setP).catch(() => setErr(true));
  }, [id]);

  if (err) return <div className="p-8 font-mono text-aura-crimson">Backend unreachable. Check backend and retry.</div>;
  if (!p) return <div className="p-8 font-mono text-aura-navy">Loading workbench...</div>;

  const propose = () => {
    setBusy(true);
    api.remediate(id).then((r) => { setRes(r); setTrades(r.trades); setLiveVerify(null); }).finally(() => setBusy(false));
  };

  const onTradesChange = (next: Trade[]) => {
    setTrades(next);
    api.verify(id, next).then(setLiveVerify).catch(() => setLiveVerify(null));
  };

  const approve = async () => {
    setApproveErr(null);
    try {
      const r = await api.approve(id, {
        trades,
        rationale: res?.resolved && !liveVerify ? "approved AI proposal" : "approved with manual edits",
        breach_type: p.rules_result!.breaches[0]?.rule,
        choice: trades[0] ? `${trades[0].action} ${trades[0].ticker}` : "manual",
      });
      setApproved(true);
      setNewStatus(r?.new_status ?? null);
      if (r?.rules_result) {
        setApprovedRulesResult(r.rules_result);
        setP((prev) => (prev ? { ...prev, rules_result: r.rules_result } : prev));
      }
    } catch (e) {
      setApproveErr(String((e as Error).message ?? e ?? "Approve failed. Check backend and retry."));
    }
  };

  const aumImpact = trades.reduce((s, t) => s + Math.abs(t.value), 0) || 0;
  const verifyResult = liveVerify ?? approvedRulesResult ?? res?.verification ?? null;
  const resolved = verifyResult ? verifyResult.status === "green" : res?.resolved ?? false;

  const perRule = verifyResult?.per_rule ?? res?.verification?.per_rule ?? [];
  const rulesPass = perRule.filter((r) => r.pass).length;
  const rulesTotal = perRule.length;
  const confidenceLabel = verifyResult
    ? rulesTotal ? `Rules: ${rulesPass}/${rulesTotal} pass${res?.retried ? " - retried" : ""}` : `Verified by rules engine${res?.retried ? " - retried" : ""}`
    : null;

  const resetDemo = () => {
    if (!window.confirm("Reset demo state? This clears all applied trades across the book and resets the Hermes runtime. This cannot be undone.")) return;
    setResetting(true);
    api.reset().then(() => window.location.reload()).catch(() => { setResetting(false); window.alert("Reset failed. Check backend and retry."); });
  };

  return (
    <div className="p-4 lg:p-6 max-w-[1440px] mx-auto pb-32">
      <Link href={`/portfolio/${id}`} className="inline-flex items-center gap-1.5 text-aura-text-muted hover:text-aura-navy font-mono text-xs mb-4">
        <span className="material-symbols-outlined text-[16px]">arrow_back</span>
        <span className="uppercase tracking-wide">Back to Diagnosis</span>
      </Link>

      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-6">
        <div className="w-full">
          <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">Portfolio Delta Sync // {id}</p>
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <h1 className="font-mono text-2xl font-bold text-aura-text">Remediation Workbench</h1>
            <StatusBadge status={p.rules_result!.status} />
          </div>
          <p className="font-mono text-xs text-aura-text-muted">Entity: {p.client_name}</p>
        </div>
        <div className="text-right w-full md:w-auto flex flex-col items-end gap-3">
          <div>
            <p className="font-mono text-[10px] uppercase text-aura-text-subtle mb-1">AUM Impact</p>
            <p className="font-mono text-base font-bold tabular-nums text-aura-navy">${(aumImpact / 1e3).toFixed(0)}k ({((aumImpact / p.fum) * 100).toFixed(1)}%)</p>
          </div>
          <SecondaryButton onClick={resetDemo} disabled={resetting} className="flex items-center gap-2 text-aura-crimson border-aura-crimson hover:bg-aura-crimson-soft">
            <span className="material-symbols-outlined text-[16px]">restart_alt</span>
            {resetting ? "Resetting..." : "Reset demo state"}
          </SecondaryButton>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-8 flex flex-col gap-4">
          <div className="bg-aura-surface-low border border-aura-border rounded p-4 relative overflow-hidden">
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-aura-navy" />
            <div className="pl-4">
              <div className="flex items-center gap-2 text-aura-navy mb-2">
                <span className="material-symbols-outlined material-symbols-filled">auto_awesome</span>
                <h3 className="font-mono text-base font-semibold">AI Remediation Strategy</h3>
                {confidenceLabel && <span className="ml-2 font-mono text-[10px] uppercase px-2 py-0.5 rounded border border-aura-emerald text-aura-emerald bg-aura-emerald-soft">{confidenceLabel}</span>}
              </div>
              <p className="font-mono text-sm text-aura-text-muted">
                {trades.length
                  ? `Proposed: ${trades.map((t) => `${t.action.toUpperCase()} ${t.ticker}`).join(", ")} to resolve mandate breaches and restore compliance. Edit units to test alternatives — re-verified live by the rules engine.`
                  : "Click 'Propose a fix' to generate an AI-assisted remediation strategy grounded in the deterministic rules engine."}
              </p>
            </div>
          </div>

          <WorkbenchTable trades={trades} portfolio={p} editable={!!res} onTradesChange={onTradesChange} />
          <SuggestionChip clientId={id} />
        </div>

        <div className="xl:col-span-4">
          <div className="xl:sticky xl:top-6 space-y-4">
            {verifyResult ? (
              <VerifyPanel verification={verifyResult} resolved={resolved} retried={res?.retried ?? false} priorStatus={p.rules_result?.status ?? "unknown"} />
            ) : (
              <div className="bg-aura-surface-low border border-aura-border rounded p-4">
                <p className="font-mono text-sm text-aura-text-muted">Click "Propose a fix" to generate compliant trades.</p>
              </div>
            )}
            {liveVerify && (
              <div className="bg-aura-ochre-soft border border-aura-ochre rounded p-3 font-mono text-xs text-aura-ochre">
                Live re-verify: trader edit rechecked by rules engine.
              </div>
            )}
          </div>
        </div>
      </div>

      {approveErr && (
        <div className="my-6 bg-aura-crimson-soft border border-aura-crimson rounded p-4 flex items-center gap-3">
          <span className="material-symbols-outlined text-aura-crimson">error</span>
          <div className="font-mono text-xs text-aura-crimson"><span className="font-medium">Approve failed.</span> {approveErr}</div>
        </div>
      )}

      {approved && (
        <div className="my-6 bg-aura-emerald-soft border border-aura-emerald rounded p-4 flex items-center gap-3">
          <span className="material-symbols-outlined text-aura-emerald material-symbols-filled">check_circle</span>
          <div className="font-mono text-xs">
            <span className="text-aura-text">Approved and logged.</span>{" "}
            <span className="text-aura-text-muted">Rules engine re-checked the effective portfolio: status <span className={newStatus === "green" ? "text-aura-emerald" : "text-aura-ochre"}>{newStatus?.toUpperCase() ?? "GREEN"}</span>. Audit trail appended.</span>
          </div>
        </div>
      )}

      <AuditTrail clientId={id} />

      <div className="hidden lg:flex fixed bottom-0 right-0 w-[calc(100%-220px)] bg-aura-surface/95 backdrop-blur border-t border-aura-border p-4 px-6 justify-between items-center z-40">
        <div className="flex items-center gap-2 text-aura-text-muted max-w-xl">
          <span className="material-symbols-outlined text-[20px]">info</span>
          <span className="font-mono text-xs">Nothing executes automatically. Approving logs the intent and queues orders for manual trader review.</span>
        </div>
        <div className="flex items-center gap-3">
          <SecondaryButton onClick={propose} disabled={busy}>{busy ? "Proposing..." : "Propose a fix"}</SecondaryButton>
          <PrimaryButton onClick={approve} disabled={!res || approved} className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px]">gavel</span>
            {approved ? "Approved" : "Approve & Log"}
          </PrimaryButton>
        </div>
      </div>

      <div className="lg:hidden mt-8 flex flex-col gap-3">
        <p className="font-mono text-xs text-aura-text-muted flex items-start gap-2">
          <span className="material-symbols-outlined text-[18px]">info</span>
          Nothing executes automatically. Approving logs the intent and queues orders for manual review.
        </p>
        <div className="flex gap-3">
          <SecondaryButton onClick={propose} disabled={busy} className="flex-1">{busy ? "Proposing..." : "Propose a fix"}</SecondaryButton>
          <PrimaryButton onClick={approve} disabled={!res || approved} className="flex-1 flex items-center justify-center gap-2">
            <span className="material-symbols-outlined text-[18px]">gavel</span>
            {approved ? "Approved" : "Approve & Log"}
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}
```

Expected: Workbench renders in new layout with all propose/verify/approve/reset/CSV logic preserved.

- [ ] **Step 6.6: Verify build and tests**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend
npx vitest run
npx tsc --noEmit
```

Expected: passes.

- [ ] **Step 6.7: Commit**

```bash
git add frontend/src/app/portfolio/[id]/workbench/page.tsx frontend/src/components/WorkbenchTable.tsx frontend/src/components/VerifyPanel.tsx frontend/src/components/AuditTrail.tsx frontend/src/components/SuggestionChip.tsx
git commit -m "feat(makeover): workbench page restyled

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Rebuild Hermes Mission Control page

**Files:**
- Modify: `frontend/src/app/hermes/page.tsx`
- Modify: `frontend/src/components/hermes/HermesScorePanel.tsx`
- Modify: `frontend/src/components/hermes/HermesQueue.tsx`
- Modify: `frontend/src/components/hermes/HermesStrategyPanel.tsx`
- Modify: `frontend/src/components/hermes/HermesHistory.tsx`

**Interfaces:**
- Consumes: `Panel`, `SectionHeader`, `PrimaryButton`, `SecondaryButton`, `StatusBadge`, `StatusDot`, `DataTable`, `aura-*` classes.
- Produces: restyled `/hermes` page.

- [ ] **Step 7.1: Update HermesScorePanel.tsx**

Keep all logic, localStorage trend, heartbeat parsing. Replace class names:
- `bg-matrix-void` → `bg-aura-surface-low`
- `border-matrix-line` → `border-aura-border`
- `text-matrix-text` → `text-aura-text`
- `text-matrix-muted` → `text-aura-text-muted`
- `text-matrix-green` → `text-aura-emerald`
- `text-matrix-red` → `text-aura-crimson`
- `text-matrix-amber` → `text-aura-ochre`
- Metric boxes: `bg-aura-surface border border-aura-border rounded p-3`.
- Remove Matrix-specific tone logic and use aura color names.

- [ ] **Step 7.2: Update HermesQueue.tsx**

Keep all queue state, expand/verify, approve, reject, bulk approve logic. Replace class names:
- `bg-matrix-void` → `bg-aura-surface-low`
- `border-matrix-line` → `border-aura-border`
- `bg-matrix-surface` → `bg-aura-surface`
- `text-matrix-text` → `text-aura-text`
- `text-matrix-muted` → `text-aura-text-muted`
- `text-matrix-green` → `text-aura-emerald`
- `text-matrix-red` → `text-aura-crimson`
- `text-matrix-amber` → `text-aura-ochre`
- `bg-matrix-green-soft` → `bg-aura-emerald-soft`
- `border-matrix-green/40` → `border-aura-emerald`
- `bg-matrix-red-soft` → `bg-aura-crimson-soft`
- `border-matrix-red/40` → `border-aura-crimson`
- `bg-matrix-amber-soft` → `bg-aura-ochre-soft`
- `border-matrix-amber/40` → `border-aura-ochre`
- Buttons: use `PrimaryButton` and `SecondaryButton` where appropriate.
- Remove `glow-green-sm` and Matrix glow classes.
- Keep `VerifyPanel` nested usage; its own restyle handles appearance.

- [ ] **Step 7.3: Update HermesStrategyPanel.tsx**

Keep reflect/adopt/dismiss logic. Replace class names with aura equivalents and use `PrimaryButton`/`SecondaryButton`:
- `bg-matrix-void` → `bg-aura-surface-low`
- `border-matrix-line` → `border-aura-border`
- `bg-matrix-surface` → `bg-aura-surface`
- `text-matrix-text` → `text-aura-text`
- `text-matrix-muted` → `text-aura-text-muted`
- `text-matrix-green` → `text-aura-emerald`
- `text-matrix-amber` → `text-aura-ochre`
- `bg-matrix-green-soft` → `bg-aura-emerald-soft`
- `border-matrix-green/40` → `border-aura-emerald`
- `bg-matrix-amber-soft` → `bg-aura-ochre-soft`
- `border-matrix-amber/40` → `border-aura-ochre`

- [ ] **Step 7.4: Update HermesHistory.tsx**

Keep sorting, rollback logic. Replace class names with aura equivalents and update timeline dots:
- `bg-matrix-void` → `bg-aura-surface-low`
- `border-matrix-line` → `border-aura-border`
- `bg-matrix-surface` → `bg-aura-surface`
- `text-matrix-text` → `text-aura-text`
- `text-matrix-muted` → `text-aura-text-muted`
- `text-matrix-green` → `text-aura-emerald`
- `text-matrix-amber` → `text-aura-ochre`
- Latest marker: `bg-aura-emerald border-aura-emerald`.
- Inactive marker: `bg-aura-surface border-aura-border`.
- Rollback button: `SecondaryButton` with ochre styling.

- [ ] **Step 7.5: Update Hermes page.tsx**

Keep all state, scan, polling, adopt, rollback, approve, batch logic. Replace markup:

```tsx
return (
  <div className="relative p-4 lg:p-6 max-w-[1440px] mx-auto pb-32">
    {scanning && (
      <div className="pointer-events-none fixed inset-0 z-40 bg-aura-navy/5" aria-hidden="true" />
    )}

    <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-6">
      <div>
        <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">Hermes // Self-Improving Assurance Engine</p>
        <h1 className="font-mono text-2xl font-bold text-aura-text mb-2">Mission Control</h1>
        <p className="font-mono text-xs text-aura-text-muted max-w-2xl leading-relaxed">
          Autonomous book-wide remediation. Hermes proposes from strategy.yaml, the deterministic rules engine verifies, a human approves. Reflection learns from misses and tunes the strategy — never the mandate.
        </p>
      </div>
      <PrimaryButton onClick={scan} disabled={scanning} className="flex items-center gap-2">
        <span className="material-symbols-outlined text-[18px]">radar</span>
        {scanning ? "Scanning..." : "Scan Book"}
      </PrimaryButton>
    </div>

    <div className="mb-6 bg-aura-surface-low border border-aura-border rounded p-4">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-aura-navy text-[20px]">shield</span>
        <span className="font-mono text-[10px] uppercase text-aura-navy tracking-wider">Assurance Cage // 4-Stage Gate</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2 items-stretch">
        {CAGE_STAGES.map((s, i) => (
          <div key={s.label} className="flex items-stretch gap-2">
            <div className="flex-1 border border-aura-border rounded p-3 bg-aura-surface flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className={`material-symbols-outlined text-[18px] ${s.tone}`}>{s.icon}</span>
                <span className="font-mono text-sm text-aura-text">{s.label}</span>
              </div>
              <span className="font-mono text-xs text-aura-text-muted leading-snug">{s.sub}</span>
            </div>
            {i < CAGE_STAGES.length - 1 && <div className="hidden md:flex items-center text-aura-navy font-mono text-sm">&rarr;</div>}
          </div>
        ))}
      </div>
      <p className="font-mono text-xs text-aura-text-muted mt-4 leading-relaxed">
        <span className="text-aura-text">Two-tier cage.</span> Mandate rules = LAW (enforced only by deterministic rules_engine.py). Remediation strategy = JUDGMENT (strategy.yaml, Hermes-tunable). Hermes reflection writes only strategy.yaml. Nothing auto-executes; nothing self-adopts; every change is versioned + reversible.
      </p>
    </div>

    {err && (
      <div className="mb-6 bg-aura-crimson-soft border border-aura-crimson rounded p-3 font-mono text-xs text-aura-crimson">
        Backend unreachable: {err}. Check backend and retry.
      </div>
    )}

    <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
      <div className="xl:col-span-7 flex flex-col gap-6">
        <HermesScorePanel heartbeat={heartbeat} />
        <HermesQueue queue={queue} heartbeat={heartbeat} onApprove={handleApprove} onApproveBatch={handleApproveBatch} onRefreshQueue={loadQueue} />
      </div>
      <div className="xl:col-span-5 flex flex-col gap-6">
        <HermesStrategyPanel strategy={strategy} onAdopted={onAdopted} />
        <HermesHistory history={history} onRollback={handleRollback} />
      </div>
    </div>
  </div>
);
```

Note: `CAGE_STAGES` tone values need updating from Matrix to aura:

```typescript
const CAGE_STAGES: { label: string; sub: string; icon: string; tone: string }[] = [
  { label: "Hermes proposes", sub: "strategy.yaml // judgment", icon: "auto_awesome", tone: "text-aura-ochre" },
  { label: "Rules engine verifies", sub: "rules_engine.py // LAW", icon: "verified_user", tone: "text-aura-emerald" },
  { label: "Human approves", sub: "final authority", icon: "gavel", tone: "text-aura-text" },
  { label: "Feeds back to Hermes", sub: "reflection // learn", icon: "loop", tone: "text-aura-ochre" },
];
```

Expected: Hermes page renders in new layout; scan, queue, strategy, history all functional.

- [ ] **Step 7.6: Verify build and tests**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend
npx vitest run
npx tsc --noEmit
```

Expected: passes.

- [ ] **Step 7.7: Commit**

```bash
git add frontend/src/app/hermes/page.tsx frontend/src/components/hermes/HermesScorePanel.tsx frontend/src/components/hermes/HermesQueue.tsx frontend/src/components/hermes/HermesStrategyPanel.tsx frontend/src/components/hermes/HermesHistory.tsx
git commit -m "feat(makeover): hermes mission control restyled

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Final cleanup, verification, and documentation

**Files:**
- Modify: `frontend/tailwind.config.ts`
- Modify: `frontend/src/app/globals.css`
- Delete: `frontend/src/components/_legacy/` (after verification)
- Modify: `README.md`, `docs/WALKTHROUGH.md`, `AURA_Demo_Guide.docx`

**Interfaces:**
- Consumes: all restyled components.
- Produces: clean build, updated docs, commit to branch.

- [ ] **Step 8.1: Remove leftover Matrix-specific CSS utilities**

In `frontend/src/app/globals.css`, ensure no `.glow-green`, `.heat-red`, `.scanlines`, `.pulse-*` remain. They were replaced in Step 2.1; if any slipped back in during component edits, remove them.

- [ ] **Step 8.2: Optionally remove old Matrix colors from tailwind.config.ts**

If every component now uses `aura-*` classes, the `matrix` color block can be deleted. However, to minimize risk, leave it in place until the full E2E passes. After E2E passes, remove it and commit separately.

- [ ] **Step 8.3: Run full test suite**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping/backend
.venv/Scripts/python.exe -m pytest -q
cd /c/Users/point/projects/financialSimplicity/prototyping/frontend
npx tsc --noEmit
npx next build
npx vitest run
```

Expected:
- backend: 143 passed, 1 skipped.
- frontend: TypeScript clean, build succeeds, vitest passes.

- [ ] **Step 8.4: Run Playwright screenshot validation**

With backend and frontend dev servers running:

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping
python scripts/e2e_screenshots.py
```

Expected: PASS with only benign recharts warnings.

- [ ] **Step 8.5: Manual page walkthrough**

1. Command Centre loads, heatmap clickable, summary counts visible, market panel tick works.
2. Click red tile → Diagnosis loads, narrative appears, breach chips highlight holdings, Explain returns grounded text.
3. Workbench → Propose a fix → Verify → Approve → status flips green, persists on reload.
4. Hermes → Scan Book → queue populates → Approve individual/batch → queue marks processed.
5. Reflect → Adopt → strategy version bumps, history updates.

- [ ] **Step 8.6: Delete `_legacy/` backups**

```bash
rm -rf /c/Users/point/projects/financialSimplicity/prototyping/frontend/src/components/_legacy
```

- [ ] **Step 8.7: Update README and WALKTHROUGH**

In `README.md` and `docs/WALKTHROUGH.md`, update references to the old Matrix UI (e.g., "MATRIX theme") to describe the new muted-light institutional design. Add note about JetBrains Mono, slate/navy palette, and 4px precision shapes.

- [ ] **Step 8.8: Regenerate AURA_Demo_Guide.docx**

```bash
cd /c/Users/point/projects/financialSimplicity/prototyping
.venv/Scripts/python.exe scripts/generate_aura_demo_guide.py
```

Expected: `AURA_Demo_Guide.docx` updated with new UI description.

- [ ] **Step 8.9: Final commit**

```bash
git add -A
git commit -m "feat(makeover): complete muted-light Matrix UI rebuild

- Rebuilt all four pages with institutional slate/navy light theme.
- Added shared UI primitives: Panel, Sidebar, buttons, StatusDot, DataTable, TopMetricCard.
- Replaced AllocationDonut with AllocationBarChart.
- Preserved every API contract, feature, and recent fix.
- Updated docs and regenerated AURA_Demo_Guide.docx.
- Full verification: backend pytest 143, frontend tsc + build + vitest, Playwright PASS.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 8.10: Push branch**

```bash
git push origin feature/muted-light-makeover
```

Expected: branch pushed to origin.

---

## Spec Coverage Check

| Spec requirement | Task |
|---|---|
| Muted-light color palette | Task 1 (tailwind), Task 2 (globals.css), applied in all component tasks |
| JetBrains Mono typography | Task 1 (tailwind font), Task 2 (globals.css base) |
| 4px radius, 1px slate borders | Task 3 (Panel, buttons), applied across components |
| 12-col grid, 24px margins | Task 2 (AppShell layout), Task 4–7 page grids |
| Circles only for status | Task 3 (StatusDot), Task 4 (StatusBadge) |
| Micro-shadows only | Task 1 (tailwind shadow), Task 3 (Panel) |
| Sidebar navigation | Task 2 (Sidebar), Task 4 (CommandCentre layout) |
| Command Centre metric cards | Task 3 (TopMetricCard), Task 4 (SummaryBar) |
| Diagnosis breach list + ledger + bar chart | Task 5 |
| Workbench flagged ledger + assurance checks | Task 6 |
| Hermes score/queue/strategy/history | Task 7 |
| Preserve all features/APIs | Each task explicitly keeps logic |
| Backend unchanged | No backend file in plan |
| Tests and Playwright | Task 8 |
| Docs/docx update | Task 8 |

## Placeholder Scan

No TBD/TODO placeholders. All code blocks are concrete. All commands have expected outputs.

## Type Consistency Check

- `StatusBadge` accepts `Status` type — unchanged.
- `StatusDot` accepts `Status` — new primitive consistent with `StatusBadge`.
- `DataTable` subcomponents (`Head`, `Body`, `Row`, `Cell`, `Header`) use consistent naming.
- `AllocationBarChart` replaces `AllocationDonut` with same props interface (`holdings`, `clientId`, `mandate`, `rulesResult`).
- `WorkbenchTable`, `VerifyPanel`, `HermesQueue`, etc. keep their existing prop signatures.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-21-aura-muted-light-makeover.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?
