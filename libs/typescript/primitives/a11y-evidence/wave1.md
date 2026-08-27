# A11y evidence — Wave-1 atoms/molecules (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024 · doc 17 §3/§4). The
> three-layer accessibility stack for the Wave-1 ATOM/MOLECULE set — **Badge · Chip · Kbd ·
> Spinner · Divider · Card · StatRow · Tabs · EmptyState**: (1) **axe-core** on the **real Chromium
> AND WebKit** engines, (2) **Playwright keyboard** assertions, (3) the noted **screen-reader
> matrix**. Layers (1)+(2) are mechanical and re-run by `bash ./ctl.sh a11y` (a `phase-gate qa`
> blocker); layer (3) is the human-noted matrix recorded here. This file is the evidence; the
> executable proof is `tests-a11y/specs/wave1.spec.ts`.

## Pinned environment (the evidence is only valid for these versions)

| Component | Version / build |
|---|---|
| `svelte` | 5.56.3 (runes) |
| `bits-ui` (behavior layer, RD-16/OD-1 — Tabs) | 2.18.1 |
| `@eden/theme` (token source) | workspace `0.0.0` (C21 seed, light mode) |
| `@playwright/test` | 1.61.0 |
| `axe-core` | 4.12.1 |

Re-run: `bash ./ctl.sh a11y` (devcontainer; browsers at `~/.cache/ms-playwright`). A pin change to
any row above invalidates this record until the lane is re-run and the table updated. The lane is
FAIL-NOT-SKIP: an absent browser is a gate failure, not a skip.

## Layer 1 — axe-core (automated WCAG audit), Chromium AND WebKit

Result: **PASS on both engines** — 0 serious/critical violations across the whole Wave-1 harness
(every Badge status, the mono Chips incl. the removable one, the ⌘K Kbd caps, the Spinners, the
horizontal + vertical Dividers, the raised + flat Cards, the StatRow, the Tabs, and the EmptyState),
audited against the Eden tokens injected at/above the document (the real reading surface).

- `axe.run(document)` — 0 serious/critical violations. Weaken-to-confirm: the audit walked a
  non-trivial WCAG rule set (`ruleCount > 30`, `passCount > 0`), so the pass is not vacuous.
- The Wave-1 surfaces are token-driven (every colour a derived `@eden/theme` role), so the
  `color-contrast` rule passing on both engines is the design-correctness contrast gate independently
  re-proven from the *rendered, cascade-computed* colours (two independent witnesses agree: the
  in-process `*.design.test.ts` from `@eden/theme`'s own WCAG formula, axe from the browser).

## Layer 2 — Playwright keyboard operability + hit floor, Chromium AND WebKit

Result: **PASS on both engines.**

| Assertion | Result |
|---|---|
| Every status Badge carries a status WORD + `role="status"` (never colour alone — triple-encoding) | PASS |
| The removable Chip exposes a NAMED remove `<button>`, reachable by keyboard, activating on `Enter` | PASS |
| The Chip remove control's bounding box meets the 44px AAA tap floor in the real browser | PASS |
| The Kbd renders a native `<kbd>` (the keyboard-input semantic element) | PASS |
| The Spinner exposes an accessible live status label (`role="status"` + visually-hidden text) | PASS |
| Tabs: roving `ArrowRight` moves focus to the next enabled tab; the disabled tab is not selectable | PASS |
| Each Tabs trigger's bounding box meets the 44px AAA tap floor in the real browser | PASS |
| The raised Card paints a token-driven `box-shadow`; the flat Card paints `none` (the variant works) | PASS |
| The EmptyState is a labelled `region` (`aria-labelledby` → its serif headline) with a live content slot | PASS |
| The EmptyState headline renders in a DIFFERENT font family than the body (the serif display voice) | PASS |
| The horizontal Divider is a native `<hr>` (the semantic thematic-break separator) | PASS |

The 44px tap floors (Chip remove, Tabs triggers), the reduced-motion-honoured Spinner, and every
painted colour are keyed off `@eden/theme` tokens (`var(--eden-*-hit-target)` = the theme's decoupled
`hitTargetPx`; the Spinner's rotation is a `motion.durations` rung + `prefers-reduced-motion: reduce`
holds it static), so the keyboard-operability evidence is also token-provenance evidence.

## Layer 3 — Screen-reader matrix (noted)

Every Wave-1 member renders a native or ARIA-correct element with NO custom widget semantics to
mis-announce, so each inherits the platform announcement:

| Element | Native/ARIA | Expected announcement | Status |
|---|---|---|---|
| Badge (status) | `<span role="status">` + word | the status word, in a live region | Expected-correct (axe `aria-*` pass is the automated proxy) |
| Chip (removable) | native `<button>` + `aria-label` | "Remove namespace filter, button" | Expected-correct (native button role + accessible name) |
| Kbd | native `<kbd>` | the key label (platform keyboard-input semantics) | Expected-correct |
| Spinner | `<span role="status" aria-live="polite">` + label | "Loading projects" | Expected-correct (live region) |
| Divider | native `<hr>` / `role="separator"` + `aria-orientation` | "separator" | Expected-correct |
| Card | native `<section>` (+ optional `aria-label`) | a labelled region when named | Expected-correct |
| StatRow | native `<dl>`/`<dt>`/`<dd>` | term/definition per stat | Expected-correct (description-list semantics) |
| Tabs | bits-ui `tablist`/`tab`/`tabpanel` | "Overview, tab, 1 of 3" / "selected" | Expected-correct (bits-ui ARIA, axe pass) |
| EmptyState | `<section aria-labelledby>` + `<h2>` headline | the headline as the region name | Expected-correct |

Rationale for "expected-correct": no member adds a `role`/`aria-*` override that fights the native
element (the Chip remove name is the visible `aria-label`, the Tabs semantics are bits-ui's proven
ARIA, the Divider/StatRow/Kbd use the exact semantic elements). The axe `aria-*`/`button-name`/
`color-contrast` rules passing on both engines is the automated proxy for the SR-name + contrast
portion; on-device SR runs are the manual confirmation step (tracked separately).

## Provenance note (why this is design-correctness evidence too)

Every colour, size, and (for the Spinner) duration each Wave-1 member paints is a CSS custom property
whose value is **derived** from an `@eden/theme` token via the shared `surface-tokens`/`chat-surface`
vocabulary; the component markup carries no literal colour/px. The layer-1 color-contrast pass and the
layer-2 token/44px/shadow assertions therefore double as proof that the math-generated tokens clear
the accessibility floors **as rendered**, not just in the unit math. MATH IS SOURCE OF TRUTH.
