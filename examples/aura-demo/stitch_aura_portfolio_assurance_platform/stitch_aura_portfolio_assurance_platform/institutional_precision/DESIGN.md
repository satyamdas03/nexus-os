---
name: Institutional Precision
colors:
  surface: '#f8f9fb'
  surface-dim: '#d9dadc'
  surface-bright: '#f8f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#edeef0'
  surface-container-high: '#e7e8ea'
  surface-container-highest: '#e1e2e4'
  on-surface: '#191c1e'
  on-surface-variant: '#43474e'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f3'
  outline: '#74777f'
  outline-variant: '#c4c6cf'
  surface-tint: '#485f82'
  primary: '#00152f'
  on-primary: '#ffffff'
  primary-container: '#0f2a4a'
  on-primary-container: '#7a92b7'
  inverse-primary: '#b0c8f0'
  secondary: '#006a69'
  on-secondary: '#ffffff'
  secondary-container: '#98f2f0'
  on-secondary-container: '#00706f'
  tertiary: '#231000'
  on-tertiary: '#ffffff'
  tertiary-container: '#402200'
  on-tertiary-container: '#b6875a'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d4e3ff'
  primary-fixed-dim: '#b0c8f0'
  on-primary-fixed: '#001c3a'
  on-primary-fixed-variant: '#304869'
  secondary-fixed: '#98f2f0'
  secondary-fixed-dim: '#7cd5d3'
  on-secondary-fixed: '#002020'
  on-secondary-fixed-variant: '#00504f'
  tertiary-fixed: '#ffdcbe'
  tertiary-fixed-dim: '#f1bc8b'
  on-tertiary-fixed: '#2d1600'
  on-tertiary-fixed-variant: '#633f18'
  background: '#f8f9fb'
  on-background: '#191c1e'
  surface-variant: '#e1e2e4'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  data-mono:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar_width: 240px
  topbar_height: 64px
  container_max_width: 1440px
  gutter: 24px
  card_padding: 20px
  stack_gap_sm: 8px
  stack_gap_md: 16px
---

## Brand & Style

This design system is built for high-stakes portfolio assurance, prioritizing institutional-grade reliability and calm, efficient data management. The aesthetic is a fusion of **Modern SaaS Minimalism** and **Financial Professionalism**, drawing inspiration from tools where information density must be balanced with visual clarity.

The UI avoids decorative flourishes, favoring precise alignment, intentional whitespace, and a monochromatic foundation. The emotional goal is to evoke a sense of "quiet authority"—reassuring the user that the underlying AI is rigorous, systematic, and error-free. Every pixel serves a functional purpose, ensuring that critical remediation tasks are never obscured by visual noise.

## Colors

The palette is anchored by a deep navy primary, providing the "institutional" weight required for a financial platform.

- **Canvas & Backgrounds:** The primary workspace uses `#F7F8FA` to reduce eye strain compared to pure white, creating a sophisticated, layered look when paired with white cards.
- **Primary & Accent:** Deep Navy (`#0F2A4A`) is used for core navigation and primary actions. Calm Teal (`#0E7C7B`) serves as the "intelligent" accent, used for data visualizations, AI-assisted highlights, and active selection states.
- **Semantic Logic:** Green, Amber, and Red are reserved strictly for status reporting and risk levels. They should be used with low-saturation backgrounds or as small indicator pips to maintain the minimal aesthetic.

## Typography

Inter is the sole typeface, utilized for its exceptional legibility in data-dense environments. 

- **Numerical Precision:** All numerical data, financial figures, and timestamps must use **tabular figures** (`tnum`). This ensures columns of numbers align perfectly for easy scanning and comparison.
- **Hierarchy:** We use a tight scale. Headlines are never overly large, maintaining a compact, "dashboard" feel. 
- **Labels:** Small caps with slight tracking are used for table headers and section labels to differentiate them from interactive body text.

## Layout & Spacing

The layout follows a disciplined structural grid designed for "Command Centre" workflows.

- **Sidebar:** A fixed 240px slim sidebar in `#0F2A4A`. The 'AURA' logo sits at the top with 24px padding. Navigation items are low-contrast until hovered or active.
- **Top Bar:** A 64px white utility bar containing global search, environment switching (e.g., Production vs. Staging), and user profile.
- **Content Area:** A fluid center that accommodates 12-column layouts. On desktop, margins are a generous 32px; on mobile, they compress to 16px. 
- **Rhythm:** We use an 8px base unit. Gaps between related data points are 8px, while distinct card sections use 24px or 32px to provide breathing room.

## Elevation & Depth

Depth is handled through **Low-contrast outlines** and **Tonal layering** rather than heavy shadows.

- **Surface 0 (Canvas):** `#F7F8FA`
- **Surface 1 (Cards/Panels):** Pure white `#FFFFFF`.
- **Borders:** All cards and interactive inputs use a 1px solid border in a subtle neutral (`#E2E8F0`).
- **Shadows:** A single, extremely soft ambient shadow is used for floating elements (modals, dropdowns). 
  - *Value:* `0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.03)`
- **Hover States:** Elements lift slightly with a subtle increase in border-color contrast rather than a larger shadow.

## Shapes

The system uses a "Medium-Soft" geometric language.

- **Standard Containers:** Cards, panels, and large containers use a **12px - 16px** radius to soften the high-density data and make the professional interface feel modern.
- **Interactive Elements:** Buttons and inputs follow a **8px** radius for a sharper, more functional appearance.
- **Status Chips:** Specifically defined as **Pill-shaped** (full round) to distinguish them instantly from buttons or data cells.

## Components

- **Buttons:** 
  - *Primary:* Solid `#0F2A4A` with white text. High-contrast, no shadow.
  - *Secondary:* Ghost style with 1px `#E2E8F0` border and `#0F2A4A` text.
- **Status Chips:** Pill-shaped with light background tints (e.g., 10% opacity of the status color) and dark text of the same hue.
- **Cards:** White background, 1px border, 12px rounded corners. Header sections within cards should have a subtle bottom border.
- **Input Fields:** 1px border, 8px radius. Active state uses a 1px solid `#0E7C7B` border and a soft teal outer glow (2px).
- **Data Tables:** No vertical borders. Horizontal dividers are 1px `#F1F5F9`. Rows use a subtle highlight on hover.
- **AI Insight Component:** Uses a subtle gradient border or a left-accent bar in Calm Teal (`#0E7C7B`) to denote content generated or verified by AURA's AI.