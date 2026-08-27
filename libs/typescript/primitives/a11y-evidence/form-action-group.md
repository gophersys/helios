# A11y evidence — form-action group (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024). The three-layer
> accessibility stack for the FORM/ACTION component group — **Button** (primary / secondary / ghost /
> **danger**), **IconButton**, **Input**, **Textarea**, and the form **Field** (label + control +
> error): (1) **axe-core** on the **real Chromium AND WebKit** engines, (2) **Playwright keyboard**
> assertions, (3) the noted **screen-reader matrix**. Layers (1)+(2) are mechanical and re-run by
> `bash ./ctl.sh a11y` (a `phase-gate qa` blocker); layer (3) is the human-noted matrix recorded
> here. This file is the evidence; the executable proof is `tests-a11y/specs/form.spec.ts`, run
> against the dedicated form harness page (`tests-a11y/form.html` → `harness/FormHarness.svelte`).

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

Re-run: `bash ./ctl.sh a11y` (runs every `tests-a11y/specs/*.spec.ts` on both engines), or the
form-only isolated lane on a dedicated port (avoids contention with the Button lane on 5180):
`(cd tests-a11y && EDEN_FORM_A11Y_PORT=5181 bun x playwright test --config playwright.form.config.ts)`.
A pin change to any row above invalidates this record until the lane is re-run and the table updated.

## Components and the token vars each cites

Every color/size/space below is a CSS custom property whose value is **derived** from an
`@eden/theme` token (`src/<component>/tokens.ts`); no component markup carries a literal color/px.

| Component | Token-derivation home | Variant→role selection | Hit floor |
|---|---|---|---|
| `Button` (primary/secondary/ghost/danger) | `src/button/tokens.ts` | primary→`primary`/`on-primary`; secondary→`surface`/`on-surface`/`outline`; ghost→`surface`/`on-surface`; **danger→`error`/`on-error`** | `controlGeometry.hitTargetPx` (≥44) |
| `IconButton` | `src/icon-button/tokens.ts` (CITES `deriveButtonTokens`) | same as Button; square edge = `componentHeightPx`, glyph = `iconSizePx` | `hitTargetPx` (≥44) |
| `Input` / `Textarea` | `src/input/tokens.ts` (shared) | text=`on-surface`, fill=`surface`, border=`outline`, invalid-border=`error`, placeholder=`outline` | `hitTargetPx` (≥44) |
| `Field` | `src/field/tokens.ts` | label=`on-surface`, error=`error`, surface=`surface`; label type = `label` typography role; gap = `controlGeometry.insetPx` | (control owns its own floor) |

## Layer 1 — axe-core (automated WCAG audit), Chromium AND WebKit

Result: **PASS on both engines** — 0 serious/critical violations across the whole form-action group,
audited against the Eden tokens injected at/above the document (the real reading surface, not a UA
default white).

- `axe.run(document)` — 0 serious/critical violations. Weaken-to-confirm: the audit walked a
  non-trivial WCAG rule set (`ruleCount > 30`, `passCount > 0`), so the pass is not vacuous.
- `axe.run(.eden-button, .eden-icon-button, .eden-input, .eden-textarea, { color-contrast })` —
  **0 color-contrast violations**. The design-correctness contrast gate (the in-process
  `*.design.test.ts` proves it from `@eden/theme`'s own WCAG formula) re-proven by the independent
  axe engine on the *rendered, cascade-computed* colors — two witnesses agree, including the danger
  (error-role) Button and the invalid-state field border.
- `axe.run(.eden-icon-button, { button-name })` — **0 violations**: every icon-only button has an
  accessible name (its required `label` prop → `aria-label`).

## Layer 2 — Playwright keyboard operability, Chromium AND WebKit

Result: **PASS on both engines.**

| Assertion | Result |
|---|---|
| The four enabled Button variants (incl. danger) are reachable by `Tab` and appear in DOM order | PASS |
| The `disabled` Button is excluded from the tab order (never receives focus) | PASS |
| A focused Button activates on `Enter` (keydown) and on `Space` (keyup) | PASS |
| A keyboard-focused Button AND a keyboard-focused Input show a visible (non-`none`) focus ring | PASS |
| The Input and Textarea are reachable and accept typed text | PASS |
| Every enabled Button, IconButton (square), Input, and Textarea meets the 44px AAA tap floor (real bounding box) | PASS |
| The danger Button paints the resolved `--color-on-error` / `--color-error` tokens (token-driven color) | PASS |
| Field wiring: the `<label for>` names the control; an error sets `aria-invalid` + links the `role="alert"` message via `aria-describedby` | PASS |

The focus-ring outline, the field border, and the 44px tap floor are all keyed off `@eden/theme`
tokens, so the keyboard-operability evidence is also token-provenance evidence.

## Layer 3 — Screen-reader matrix (noted)

Each control renders a **native element** (Button/IconButton → native `<button>` via `bits-ui`
`Button.Root`; Input → native `<input>`; Textarea → native `<textarea>`), so each inherits the
platform semantics every screen reader announces natively. The Field adds only the standard
relationship attributes (`<label for>`, `aria-describedby`, `aria-invalid`, `role="alert"`).

| Screen reader + browser | Expected announcement | Status |
|---|---|---|
| VoiceOver + WebKit (Safari/macOS) | Button: "&lt;label&gt;, button" / "dimmed" when disabled. IconButton: "&lt;label&gt;, button". Field input: "&lt;label&gt;, edit text"; invalid: "invalid data" + the alert text | Expected-correct (native roles + standard ARIA); on-device pass to be recorded |
| NVDA + Chromium (Windows) | Button: "&lt;label&gt; button" / "unavailable" when disabled. Field input: "&lt;label&gt; edit"; on error, the alert text is announced and "invalid entry" | Expected-correct; on-device pass to be recorded |
| Orca + Chromium (Linux) | Button: "&lt;label&gt; push button". Field input: "&lt;label&gt; entry" | Expected-correct; on-device pass to be recorded |

Rationale for "expected-correct": no component adds a `role`/`aria-*` override on top of its native
element except the Field's standard relationship attributes. The accessible name is the visible
label (the IconButton's required `label`, the Field's `<label for>`) — asserted in layer 1 via
`getByRole(..., { name })` resolving on both engines and the axe `button-name` rule. The disabled
state is the native `disabled` attribute (asserted in layer 2). The invalid state is `aria-invalid`
+ a `role="alert"` message linked by `aria-describedby` (asserted in layer 2). The axe
`aria-*`/`button-name`/`label`/`color-contrast` rules passing on both engines is the automated proxy
for the SR-name + contrast portion of this matrix. On-device SR runs are the manual confirmation
step (tracked separately); no automated harness exercises a real screen reader in CI today.

## Provenance note (why this is design-correctness evidence too)

Every color and size each control paints is a CSS custom property whose value is **derived** from an
`@eden/theme` token; the component markup carries no literal color/px (the no-hand-set-hex provenance
lint is green by construction). The layer-1 color-contrast pass and the layer-2 token-equality + 44px
assertions therefore double as proof that the math-generated tokens clear the accessibility floors
**as rendered**, not just in the unit math — for the danger (error-role) Button and the invalid-state
field border as well as the resting states. MATH IS SOURCE OF TRUTH.
