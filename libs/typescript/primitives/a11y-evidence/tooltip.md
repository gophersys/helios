# A11y evidence — `Tooltip` (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024). The three-layer
> accessibility stack for the `Tooltip` overlay pattern: (1) **axe-core** on the **real Chromium AND
> WebKit** engines **through the bits-ui Portal**, (2) **Playwright keyboard** assertions (opens on
> trigger focus — keyboard-operable, not hover-only), (3) the noted **screen-reader matrix**. Layers
> (1)+(2) are mechanical and re-run by `bash ./ctl.sh a11y` (a `phase-gate qa` blocker); layer (3) is
> the human-noted matrix recorded here. This file is the evidence; the executable proof is
> `tests-a11y/specs/overlay.spec.ts`.

## Pinned environment (the evidence is only valid for these versions)

| Component | Version / build |
|---|---|
| `svelte` | 5.43.5 (runes) |
| `bits-ui` (behavior layer, RD-16/OD-1) | 2.18.1 |
| `@eden/theme` (token source) | workspace `0.0.0` (C21 seed, light mode) |
| `@playwright/test` | 1.60.0 |
| Chromium browser build | `chromium-1223` (Playwright 1.60.0) |
| WebKit browser build | `webkit-2287` (Playwright 1.60.0) |
| `axe-core` | 4.12.1 |

Re-run: `bash ./ctl.sh a11y` (devcontainer; browsers at `~/.cache/ms-playwright`). A pin change to
any row above invalidates this record until the lane is re-run and the table updated.

## Layer 1 — axe-core (automated WCAG audit), Chromium AND WebKit

Result: **PASS on both engines** — 0 serious/critical violations with the tooltip open, audited
against the Eden tokens carried THROUGH `Tooltip.Portal` (host `document.body`) via the inline
`--eden-overlay-*` style on the portaled Content.

- `axe.run(document)` with the tooltip open — 0 serious/critical violations. Weaken-to-confirm:
  `ruleCount > 30`, `passCount > 0` (the pass is not vacuous).
- The portaled label's computed `background-color` **equals** the resolved `--color-surface` token
  (the tokens crossed the Portal). The surface/on-surface pair clears the WCAG AA contrast target in
  `src/overlay/overlay.design.test.ts` (the in-process ninth-dimension witness) — important because a
  tooltip is small transient text where contrast matters most.

## Layer 2 — Playwright keyboard operability, Chromium AND WebKit

Result: **PASS on both engines.**

| Assertion | Result |
|---|---|
| The tooltip opens on the **trigger button's focus** (keyboard-operable, not hover-only — WCAG 1.4.13) | PASS |
| The portaled content is visible and axe-clean while open | PASS |

Opening on focus (the keyboard path) is delegated to the bits-ui `Tooltip` primitive (RD-16/OD-1),
wrapped in `Tooltip.Provider` so a standalone tooltip works without a host provider. WCAG 1.4.13
(content on hover/focus) is satisfied: the tooltip is reachable by keyboard focus and dismissible by
`Escape` (bits-ui behavior).

## Layer 3 — Screen-reader matrix (noted)

The Tooltip renders the native tooltip pattern via `bits-ui` (the content is `role="tooltip"`, wired
to the trigger via `aria-describedby`). The expected announcement matrix:

| Screen reader + browser | Expected announcement | Status |
|---|---|---|
| VoiceOver + WebKit (Safari/macOS) | trigger label then the tooltip text as its description | Expected-correct (native tooltip pattern); on-device pass to be recorded |
| NVDA + Chromium (Windows) | trigger label + tooltip text (described-by) | Expected-correct (native tooltip pattern); on-device pass to be recorded |
| Orca + Chromium (Linux) | trigger label + tooltip text | Expected-correct (native tooltip pattern); on-device pass to be recorded |

Rationale for "expected-correct": the component adds NO `role`/`aria-*` override on top of bits-ui's
tooltip semantics — the tooltip is the trigger's `aria-describedby` target; the axe `aria-*` rules
pass on both engines (the automated proxy for the description-wiring portion of this matrix).
On-device SR runs are the manual confirmation step (tracked separately).

## Provenance note (why this is design-correctness evidence too)

Every color and size the Tooltip paints is a CSS custom property whose value is **derived** from an
`@eden/theme` token (`src/overlay/tokens.ts`); the markup carries no literal color/px. The layer-1
token-equality + contrast pass therefore double as proof that the math-generated tokens clear the
accessibility floors **as rendered through the Portal**. MATH IS SOURCE OF TRUTH.
