# a11y evidence — HotspotMap (`@eden/visualization`)

> The third layer of the ADR-0024 a11y-evidence stack (the version-pinned record). Layers 1+2 (axe on
> real Chromium + WebKit, and the Playwright keyboard/hit-target assertions) are mechanical and run in
> `tests-a11y/specs/hotspot-map.spec.ts` via `bash ./ctl.sh a11y`; this note records the screen-reader
> matrix + the accessibility model a human verified.

## Component

`HotspotMap` — the signature codebase-insight view (codeinsight contract §5): a churn × complexity
scatter. Payload-driven over a `Report`'s `entities` + an `encoding` channel→field map.

## Accessibility model

A scatter plot is not readable as pixels by assistive technology, so the widget exposes THREE layers:

1. **A named figure.** The root is `role="group"` named by the chart `title`, with a visually-hidden
   `<p>` describing the encoding ("Scatter of N entities. Horizontal axis churnRelative, vertical axis
   cyclomatic, dot area lines, colour hotspotScore."). The SVG is deliberately **not** `role="img"` —
   an img role presents-away its subtree, which would both hide the interactive points and nest
   interactive controls under an image (axe `nested-interactive`). The SVG's decorative marks (axes,
   dots, tick text) are `aria-hidden`.
2. **Focusable point targets.** Each entity is a real, keyboard-focusable `role="button"` `<rect>` (an
   invisible ≥44px AAA hit target, decoupled from the small visual dot radius) carrying the full
   accessible name: the path + the four encoded metrics (`x`, `y`, `size`, `color`) — so a point is
   reachable by Tab, announced in words, and **colour is never the only signal** (WCAG 1.4.1).
3. **An offscreen data-table fallback.** A real `<table>` (visually hidden, fully in the a11y tree)
   enumerates every point's path + metrics with `<th scope>` row/column headers — the structure a
   screen reader reads as data.

## Mechanical evidence (layers 1+2 — `bash ./ctl.sh a11y`)

Both engines, 16 tests green (8 × Chromium, 8 × WebKit):

- **axe-core, ZERO serious/critical** across the chart (rule set > 30 rules walked — non-vacuous).
- **axe `color-contrast` clean** for the painted chart text over the Eden reading surface (the
  design-correctness contrast gate, re-proven by the independent axe engine in a real browser).
- **Keyboard:** the point targets participate in the natural Tab order in DOM order; each announces
  its path + metrics; a focused point shows a visible (non-`none`) focus outline.
- **Hit target:** every interactive point measures ≥ 44 × 44 px in the real browser (the AAA floor).
- **Data table:** the offscreen `<table>` has a header row + one row per entity; the top hotspot's
  row carries its path + metrics in text.
- **Token-driven colour:** the plot paints the resolved `surface` / `on-surface` tokens (a real,
  distinct, non-transparent fg/bg pair).

## Screen-reader matrix (layer 3 — noted)

| AT + engine | Result |
|---|---|
| VoiceOver + WebKit (Safari) | Figure announced by title; the encoding description read; each point reachable in the focus order announcing "path, churnRelative …, cyclomatic …" as a button; the data table navigable as a table. |
| NVDA + Chromium | Equivalent: group name, description, per-point button labels, and the offscreen table in browse mode. |

> Recorded against the pinned harness toolchain (devcontainer `ghcr.io/gophersys/base`, Playwright
> 1.60, axe-core 4.12.1, svelte 5.43.5). Re-run `bash ./ctl.sh a11y` after any markup change.
