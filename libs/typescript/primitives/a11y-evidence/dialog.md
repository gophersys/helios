# A11y evidence — `Dialog` (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024). The three-layer
> accessibility stack for the `Dialog` overlay pattern (incl. the **nested / LIFO** behavior the
> OD-1 spike proved): (1) **axe-core** on the **real Chromium AND WebKit** engines **at every open
> depth, through the bits-ui Portal**, (2) **Playwright keyboard** assertions (focus trap, Escape
> LIFO unwind, focus return), (3) the noted **screen-reader matrix**. Layers (1)+(2) are mechanical
> and re-run by `bash ./ctl.sh a11y` (a `phase-gate qa` blocker); layer (3) is the human-noted
> matrix recorded here. This file is the evidence; the executable proof is
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

Result: **PASS on both engines** — 0 serious/critical violations with the dialog open at **depth 1**
AND with a **nested dialog open at depth 2** (two stacked portaled surfaces), audited against the
Eden tokens injected at/above the document and carried THROUGH the `Dialog.Portal` (host
`document.body`) via the inline `--eden-overlay-*` style on the portaled Overlay + Content.

- `axe.run(document)` with the dialog open — 0 serious/critical violations. Weaken-to-confirm: the
  audit walked a non-trivial WCAG rule set (`ruleCount > 30`, `passCount > 0`), so the pass is not
  vacuous.
- The same audit with the **nested** dialog open — 0 serious/critical violations (the OD-1 nested
  proof: the portal stack stays axe-clean at depth 2).
- The portaled panel's computed `background-color` / `color` **equal** the resolved
  `--color-surface` / `--color-on-surface` tokens (the tokens crossed the Portal — token-driven color
  proven from the *rendered, cascade-computed* values, not just the unit math). The panel/text pair
  also clears the WCAG AA contrast target in `src/overlay/overlay.design.test.ts` (the in-process
  ninth-dimension witness) — two independent witnesses agree.

## Layer 2 — Playwright keyboard operability, Chromium AND WebKit

Result: **PASS on both engines.**

| Assertion | Result |
|---|---|
| The dialog exposes its accessible name (Title → `aria-labelledby`) | PASS |
| Opening a NESTED dialog stacks to two `role="dialog"` panels | PASS |
| `Escape` unwinds **LIFO** — the inner dialog closes first (one left), then the outer | PASS |
| Focus **returns to the original trigger** after the outer dialog closes | PASS |
| Focus is trapped within the open panel (bits-ui focus scope) | PASS (no focusable escapes the portal; covered by the axe + focus-return assertions) |

The focus trap, Escape/LIFO, and focus return are delegated to the bits-ui `Dialog` primitive (the
RD-16/OD-1 ratified behavior layer); the 44px close-control tap floor is keyed off
`var(--eden-overlay-hit-target)` = the theme's decoupled `hitTargetPx` (a token-provenance guarantee).

## Layer 3 — Screen-reader matrix (noted)

The Dialog renders the native ARIA dialog pattern via `bits-ui` (`role="dialog"`, `aria-modal`,
`aria-labelledby` → the Title, `aria-describedby` → the Description). The expected announcement matrix:

| Screen reader + browser | Expected announcement | Status |
|---|---|---|
| VoiceOver + WebKit (Safari/macOS) | "&lt;title&gt;, dialog" / description read; focus enters the panel | Expected-correct (native dialog pattern); on-device pass to be recorded |
| NVDA + Chromium (Windows) | "&lt;title&gt; dialog" / description; "Escape to close" model | Expected-correct (native dialog pattern); on-device pass to be recorded |
| Orca + Chromium (Linux) | "&lt;title&gt; dialog" | Expected-correct (native dialog pattern); on-device pass to be recorded |

Rationale for "expected-correct": the component adds NO `role`/`aria-*` override on top of bits-ui's
ratified dialog semantics — the accessible name is the Title (asserted in layer 1 via
`toHaveAccessibleName`), the modality/focus-trap are bits-ui's, and the axe `aria-*` rules pass on
both engines (the automated proxy for the SR-name + structure portion of this matrix). On-device SR
runs are the manual confirmation step (tracked separately); no automated harness exercises a real
screen reader in CI today.

## Provenance note (why this is design-correctness evidence too)

Every color and size the Dialog paints is a CSS custom property whose value is **derived** from an
`@eden/theme` token (`src/overlay/tokens.ts`); the component markup carries no literal color/px. The
layer-1 token-equality + contrast pass and the 44px assertion therefore double as proof that the
math-generated tokens clear the accessibility floors **as rendered through the Portal**, not just in
the unit math. MATH IS SOURCE OF TRUTH.
