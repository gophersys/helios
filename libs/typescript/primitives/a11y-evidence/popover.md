# A11y evidence — `Popover` (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024). The three-layer
> accessibility stack for the `Popover` overlay pattern: (1) **axe-core** on the **real Chromium AND
> WebKit** engines **through the bits-ui Portal**, (2) **Playwright keyboard** assertions (Escape
> dismissal + focus return), (3) the noted **screen-reader matrix**. Layers (1)+(2) are mechanical
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

Result: **PASS on both engines** — 0 serious/critical violations with the popover open, audited
against the Eden tokens carried THROUGH `Popover.Portal` (host `document.body`) via the inline
`--eden-overlay-*` style on the portaled Content.

- `axe.run(document)` with the popover open — 0 serious/critical violations. Weaken-to-confirm:
  `ruleCount > 30`, `passCount > 0` (the pass is not vacuous).
- The portaled content's computed `background-color` **equals** the resolved `--color-surface` token
  (the tokens crossed the Portal). The surface/on-surface pair clears the WCAG AA contrast target in
  `src/overlay/overlay.design.test.ts` (the in-process ninth-dimension witness).

## Layer 2 — Playwright keyboard operability, Chromium AND WebKit

Result: **PASS on both engines.**

| Assertion | Result |
|---|---|
| The popover opens from its trigger and the portaled content is visible | PASS |
| `Escape` closes the popover (the content is removed) | PASS |
| Focus **returns to the trigger** after `Escape` | PASS |

Escape dismissal and focus return are delegated to the bits-ui `Popover` primitive (RD-16/OD-1). The
content's minimum size is keyed off `var(--eden-overlay-hit-target)` (a token-provenance guarantee).

## Layer 3 — Screen-reader matrix (noted)

The Popover renders the native non-modal popover pattern via `bits-ui` (the trigger carries
`aria-haspopup` + `aria-expanded`; the content is an anchored region). The expected announcement matrix:

| Screen reader + browser | Expected announcement | Status |
|---|---|---|
| VoiceOver + WebKit (Safari/macOS) | trigger: "&lt;label&gt;, pop-up button, collapsed/expanded"; content read on entry | Expected-correct (native popover pattern); on-device pass to be recorded |
| NVDA + Chromium (Windows) | trigger: "&lt;label&gt; button, collapsed/expanded" | Expected-correct (native popover pattern); on-device pass to be recorded |
| Orca + Chromium (Linux) | trigger: "&lt;label&gt; button expanded" | Expected-correct (native popover pattern); on-device pass to be recorded |

Rationale for "expected-correct": the component adds NO `role`/`aria-*` override on top of bits-ui's
trigger/content semantics; the axe `aria-*` rules pass on both engines (the automated proxy for the
SR-state portion of this matrix). On-device SR runs are the manual confirmation step (tracked
separately).

## Provenance note (why this is design-correctness evidence too)

Every color and size the Popover paints is a CSS custom property whose value is **derived** from an
`@eden/theme` token (`src/overlay/tokens.ts`); the markup carries no literal color/px. The layer-1
token-equality + contrast pass therefore double as proof that the math-generated tokens clear the
accessibility floors **as rendered through the Portal**. MATH IS SOURCE OF TRUTH.
