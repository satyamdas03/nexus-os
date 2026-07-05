---
name: Digital Monolith
colors:
  surface: '#121414'
  surface-dim: '#121414'
  surface-bright: '#37393a'
  surface-container-lowest: '#0c0f0f'
  surface-container-low: '#1a1c1c'
  surface-container: '#1e2020'
  surface-container-high: '#282a2b'
  surface-container-highest: '#333535'
  on-surface: '#e2e2e2'
  on-surface-variant: '#b9ccb2'
  inverse-surface: '#e2e2e2'
  inverse-on-surface: '#2f3131'
  outline: '#84967e'
  outline-variant: '#3b4b37'
  surface-tint: '#00e639'
  primary: '#ebffe2'
  on-primary: '#003907'
  primary-container: '#00ff41'
  on-primary-container: '#007117'
  inverse-primary: '#006e16'
  secondary: '#69df5c'
  on-secondary: '#003a03'
  secondary-container: '#2ca62a'
  on-secondary-container: '#003202'
  tertiary: '#fcf8f8'
  on-tertiary: '#313030'
  tertiary-container: '#dfdcdb'
  on-tertiary-container: '#626060'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#72ff70'
  primary-fixed-dim: '#00e639'
  on-primary-fixed: '#002203'
  on-primary-fixed-variant: '#00530e'
  secondary-fixed: '#85fd75'
  secondary-fixed-dim: '#69df5c'
  on-secondary-fixed: '#002201'
  on-secondary-fixed-variant: '#005306'
  tertiary-fixed: '#e5e2e1'
  tertiary-fixed-dim: '#c9c6c5'
  on-tertiary-fixed: '#1c1b1b'
  on-tertiary-fixed-variant: '#474646'
  background: '#121414'
  on-background: '#e2e2e2'
  surface-variant: '#333535'
typography:
  headline-lg:
    fontFamily: JetBrains Mono
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: JetBrains Mono
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-sm:
    fontFamily: JetBrains Mono
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.4'
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  container-max: 1440px
---

## Brand & Style

This design system draws inspiration from the "Matrix" aesthetic, blending high-tech industrialism with precise terminal interfaces. The brand personality is authoritative, technical, and hyper-focused, designed to evoke a sense of deep-system access for high-stakes wealth management.

The style is a hybrid of **Cyber-Brutalism** and **Terminal Minimalism**. It prioritizes high-contrast legibility and data density. Visual interest is generated through light emission (glows) rather than physical depth, suggesting a digital-first environment where data is the primary architecture. The interface should feel like a sophisticated command center—efficient, professional, and uncompromisingly clear.

## Colors

The palette is strictly nocturnal, anchored by a deep charcoal background to prevent pure-black crushing while maintaining maximum contrast. 

- **Primary (Matrix Green):** Used for active states, primary actions, and critical data highlights. It should be treated as a light source.
- **Secondary (Terminal Green):** Used for borders, inactive accents, and secondary icons to provide hierarchy without visual noise.
- **Neutrals:** Pure White is reserved for high-priority body text and labels to ensure WCAG AAA compliance against the dark backdrop. Dimmer greys are used for metadata.
- **Semantic Neon:** Status colors use high-saturation variants. They are designed to "pop" off the screen, signaling urgency or health with a luminous quality.

## Typography

The typographic system utilizes a dual-font strategy to balance the "terminal" aesthetic with institutional readability. 

**JetBrains Mono** is the structural typeface. Use it for all headers, data tables, and interactive labels. It emphasizes the technical precision of the platform. For headers, use tighter letter spacing to maintain a modern, "hacker-elite" look.

**Inter** is the functional typeface. Use it for all long-form reading, descriptions, and explanatory tooltips. Its humanist qualities provide a necessary relief from the rigid monospace, ensuring that complex financial reports remain legible during extended use.

## Layout & Spacing

The layout is governed by a **strict 4px grid system**, reinforcing the "coded" nature of the design system. 

- **Grid:** Use a 12-column fluid grid for desktop with fixed 16px gutters. For mobile, collapse to a 1-column layout with 16px side margins.
- **Rhythm:** Spacing should be mathematical and consistent. Elements should be grouped using 8px (Small), 16px (Medium), or 32px (Large) increments.
- **Density:** High information density is encouraged. Use minimal padding within data cells to allow for maximum screen-real-estate utility, fitting for wealth management dashboards.

## Elevation & Depth

This design system eschews traditional shadows in favor of **Luminous Elevation**. Depth is created through stacking and light emission rather than physical occlusion.

1.  **Base Layer:** `#050505` (Deep Charcoal).
2.  **Surface Layer:** `#0D0D0D` (Slightly lighter grey) with a 1px solid border of `#008F11` (Terminal Green) at 30% opacity.
3.  **Active Layer:** Elements that are focused or active should utilize a `0px 0px 8px` outer glow using the Primary Green color.
4.  **Scanlines:** For large cards or background areas, apply a subtle horizontal scanline pattern (1px dark lines at 2px intervals) at 5% opacity to simulate a CRT terminal.

## Shapes

The shape language is architectural and sharp. A universal border radius of **4px (Soft)** is applied to all interactive elements to provide a hint of modern refinement without losing the technical edge.

- **Buttons & Inputs:** 4px radius.
- **Cards & Modals:** 4px radius.
- **Selection Indicators:** Sharp 0px corners are permitted for data-table row highlights to maintain a "block cursor" feel.

## Components

### Buttons
- **Primary:** Background `#00FF41`, Text `#000000`. On hover, add a vibrant green glow (`box-shadow: 0 0 15px #00FF41`).
- **Secondary:** Transparent background, 1px border of `#00FF41`, Text `#00FF41`.
- **Ghost:** Text `#008F11`, no border.

### Input Fields
- **Default:** 1px border of `#008F11`, background `#000000`.
- **Focus:** 1px border of `#00FF41`, with a subtle 2px glow. Placeholder text in dim green.

### Cards
- Background: `#0D0D0D`.
- Border: 1px solid `#008F11` (low opacity).
- Optional: A "glitch" header—a 2px thick Primary Green top-border that extends slightly beyond the card edges.

### Data Tables
- Headers: JetBrains Mono, Bold, All-Caps, Primary Green.
- Rows: Alternating backgrounds (Zebra striping) using `#050505` and `#080808`.
- Hover State: Row turns `#0D0D0D` with a Primary Green left-accent bar (2px width).

### Status Indicators
- Use small circular "LED" icons. When active, they should have a CSS pulse animation and a localized glow effect matching their semantic color.

### Iconography
- All icons should use thin 1.5px strokes. For the brand logo, apply a subtle "RGB split" glitch effect (red/blue offsets at 1px) on hover.