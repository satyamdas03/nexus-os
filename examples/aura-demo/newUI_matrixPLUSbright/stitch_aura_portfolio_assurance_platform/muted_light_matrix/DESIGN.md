---
name: Muted Light Matrix
colors:
  surface: '#fcf8fa'
  surface-dim: '#dcd9db'
  surface-bright: '#fcf8fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f5'
  surface-container: '#f0edef'
  surface-container-high: '#eae7e9'
  surface-container-highest: '#e4e2e4'
  on-surface: '#1b1b1d'
  on-surface-variant: '#45464d'
  inverse-surface: '#303032'
  inverse-on-surface: '#f3f0f2'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#515f74'
  on-secondary: '#ffffff'
  secondary-container: '#d5e3fd'
  on-secondary-container: '#57657b'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#271901'
  on-tertiary-container: '#98805d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#d5e3fd'
  secondary-fixed-dim: '#b9c7e0'
  on-secondary-fixed: '#0d1c2f'
  on-secondary-fixed-variant: '#3a485c'
  tertiary-fixed: '#fcdeb5'
  tertiary-fixed-dim: '#dec29a'
  on-tertiary-fixed: '#271901'
  on-tertiary-fixed-variant: '#574425'
  background: '#fcf8fa'
  on-background: '#1b1b1d'
  surface-variant: '#e4e2e4'
typography:
  headline-lg:
    fontFamily: JetBrains Mono
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: JetBrains Mono
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
  code-snippet:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  gutter: 16px
  margin: 24px
  container-max: 1440px
---

## Brand & Style

The design system bridges the gap between high-precision terminal environments and professional institutional software. It targets a demographic that values technical density and system-level control but requires the legibility and "bright mode" comfort of modern enterprise tools. 

The aesthetic is **Sophisticated Tech-Minimalism**. It moves away from the neon-on-black tropes of cyberpunk, instead adopting a "Paper-Terminal" approach. The interface should feel like a high-end physical console—engineered, structured, and authoritative. It avoids pure white to reduce eye strain, using a layered palette of slates and greys that provide depth without relying on vibrant color.

## Colors

The palette is anchored by a **Cool Slate** foundation. The background is never pure white; it uses `#F1F5F9` to establish a neutral, industrial base. 

- **Primary & Secondary:** We use Deep Navy (`#0F172A`) for primary actions and "Electric Slate" (`#334155`) for secondary UI elements. These colors provide the "darkish tone" requested, ensuring high contrast against the light background while maintaining a professional, institutional character.
- **Tonal Logic:** UI layers are built using increments of the Slate palette. Borders should use a slightly darker shade than the surface they sit upon to maintain the "system-level" structure.
- **Institutional Status:** Signal colors are tuned for legibility. We use Emerald for success, Ochre for warnings, and Crimson for errors. These are saturated enough to stand out as status indicators but muted enough to fit the professional tone.

## Typography

This design system utilizes **JetBrains Mono** exclusively to maintain its technical pedigree. The monospaced nature of the font ensures that data-heavy grids and terminal-style lists remain perfectly aligned, reinforcing the "system-level" character of the software.

- **Headlines:** Keep sizing modest to preserve information density. Use bold weights to establish hierarchy.
- **Labels:** Use uppercase for small labels and metadata to mimic technical documentation and hardware markings.
- **Scalability:** For mobile, headlines scale down by 15-20%, but the mono spacing remains consistent to ensure technical data remains readable on narrow viewports.

## Layout & Spacing

The layout follows a **High-Density Fluid Grid** model. It is designed to maximize the amount of information visible on a single screen without creating visual clutter.

- **Rhythm:** A strict 4px base unit controls all padding and margins. 
- **Grid:** A 12-column grid is used for desktop. On tablet, this shifts to an 8-column grid, and 4 columns for mobile.
- **Density:** Elements are packed tightly. Internal component padding is usually 8px or 12px to maintain a compact, "instrument-panel" feel. 
- **Safe Areas:** 24px outer margins are maintained to ensure the UI doesn't feel cramped against the edge of the display.

## Elevation & Depth

Hierarchy is achieved through **Tonal Layering** and **Subtle Outlines** rather than dramatic shadows or neon glows.

- **The Stack:** Level 0 is the background (`#F1F5F9`). Level 1 is the primary surface (`#E2E8F0`). Level 2 consists of floating panels or modals.
- **Borders:** Every container must have a 1px solid border (`#CBD5E1`). This mimics the structured partitions of a console terminal.
- **Shadows:** Use only "Micro-Shadows"—extremely low opacity (5-8%), neutral grey, with a 2px offset. They should provide just enough lift to distinguish a modal from the background without feeling "soft" or "cloud-like."
- **Focus States:** Use a 1px inset border of the Primary Navy (`#0F172A`) to indicate focus, maintaining the sharp, mechanical feel.

## Shapes

The shape language is defined by **Precision**. We utilize a strict **4px corner radius** (Soft, Level 1) for all interactive elements, containers, and inputs. 

This specific radius provides a subtle nod to modern software usability while retaining the architectural, "blocked-out" feel of a technical terminal. Circles are reserved exclusively for status indicators and user avatars to provide a sharp visual contrast against the rectangular grid.

## Components

- **Buttons:** High-contrast Navy blocks with white text for primary actions. Secondary actions use an outlined style with a 1px Slate border. Interactive states should involve a subtle background color shift (darker for primary, lighter for secondary) rather than a glow.
- **Chips / Tags:** Small, rectangular tags with 4px corners. Backgrounds should be a tint of the status color (e.g., light emerald) with dark text for maximum legibility.
- **Lists:** Use alternating row stripes (Zebra striping) with very low contrast (`#F8FAFC` vs `#F1F5F9`) to guide the eye across dense data.
- **Inputs:** Fields are defined by a 1px border. The label is placed above the field in `label-sm` (uppercase). Use a monospaced "block" cursor animation if possible to lean into the terminal aesthetic.
- **Cards:** Cards are defined more by their borders than their background color. Use a 1px Slate-300 border for all cards. No heavy dropshadows.
- **Status Indicators:** Use small 8px circles with the defined status colors. For critical alerts, the border of the relevant container should also adopt the status color (e.g., a Red border for an error-state input field).