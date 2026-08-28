# A11y evidence — `Button` (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024). The three-layer
> accessibility stack for the `Button` component pattern: (1) **axe-core** on the **real Chromium
> AND WebKit** engines, (2) **Playwright keyboard** assertions, (3) the noted **screen-reader
> matrix**. Layers (1)+(2) are mechanical and re-run by `bash ./ctl.sh a11y` (a `phase-gate qa`
> blocker); layer (3) is the human-noted matrix recorded here. This file is the evidence; the
> executable proof is `tests-a11y/specs/button.spec.ts`.

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

Result: **PASS on both engines** — 0 serious/critical violations across every Button variant
(`primary`, `secondary`, `ghost`, and the `disabled` state), audited against the Eden tokens
injected at/above the document (the real reading surface, not a UA default white).

- `axe.run(document)` — 0 serious/critical violations. Weaken-to-confirm: the audit walked a
  non-trivial WCAG rule set (`ruleCount > 30`, `passCount > 0`), so the pass is not vacuous.
- `axe.run(.eden-button, { runOnly: color-contrast })` — **0 color-contrast violations**. This is
  the design-correctness contrast gate independently re-proven by the axe engine in a real browser
  (the in-process `*.design.test.ts` proves it from `@eden/theme`'s own WCAG formula; axe proves it
  from the *rendered, cascade-computed* colors — two independent witnesses agree).

## Layer 2 — Playwright keyboard operability, Chromium AND WebKit

Result: **PASS on both engines.**

| Assertion | Result |
|---|---|
| Every enabled Button is reachable by `Tab` and appears in DOM order in the tab sequence | PASS |
| The `disabled` Button is excluded from the tab order (never receives focus) | PASS |
| A focused Button activates on `Enter` (keydown) | PASS |
| A focused Button activates on `Space` (keyup) | PASS |
| A keyboard-focused Button shows a visible (non-`none`) focus-visible outline | PASS |
| Each enabled Button's bounding box meets the 44px AAA tap floor in the real browser | PASS |
| The rendered `color`/`background-color` equal the resolved `--color-on-primary`/`--color-primary` tokens | PASS |

The focus-ring outline and the 44px tap floor are both keyed off `@eden/theme` tokens
(`var(--eden-button-fg)`, `var(--eden-button-hit-target)` = the theme's decoupled `hitTargetPx`),
so the keyboard-operability evidence is also token-provenance evidence.

## Layer 3 — Screen-reader matrix (noted)

The Button renders a native `<button>` (via `bits-ui` `Button.Root`), so it inherits the platform
button semantics every screen reader announces natively. The expected announcement matrix:

| Screen reader + browser | Expected announcement | Status |
|---|---|---|
| VoiceOver + WebKit (Safari/macOS) | "&lt;label&gt;, button" / "dimmed" when disabled | Expected-correct (native button role); on-device pass to be recorded |
| NVDA + Chromium (Windows) | "&lt;label&gt; button" / "unavailable" when disabled | Expected-correct (native button role); on-device pass to be recorded |
| Orca + Chromium (Linux) | "&lt;label&gt; push button" | Expected-correct (native button role); on-device pass to be recorded |

Rationale for "expected-correct": the component adds NO `role`/`aria-*` override on top of the
native element — the accessible name is the visible label (asserted in layer 1 via
`getByRole('button', { name })` resolving on both engines), the disabled state is the native
`disabled` attribute (asserted in layer 2), and there is no custom widget semantics to mis-announce.
The axe `aria-*`/`button-name`/`color-contrast` rules passing on both engines is the automated proxy
for the SR-name + contrast portion of this matrix. On-device SR runs are the manual confirmation
step (tracked separately); no automated harness exercises a real screen reader in CI today.

## Provenance note (why this is design-correctness evidence too)

Every color and size the Button paints is a CSS custom property whose value is **derived** from an
`@eden/theme` token (`src/button/tokens.ts`); the component markup carries no literal color/px. The
layer-1 color-contrast pass and the layer-2 token-equality + 44px assertions therefore double as
proof that the math-generated tokens clear the accessibility floors **as rendered**, not just in the
unit math. MATH IS SOURCE OF TRUTH.
