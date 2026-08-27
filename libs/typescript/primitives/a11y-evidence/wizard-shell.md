# A11y evidence — WizardShell (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024 · doc 17 §6). The three-layer
> accessibility stack for the **WizardShell** full-screen focus organism (the create/setup flows'
> reusable shell): (1) **axe-core** on the **real Chromium AND WebKit** engines, (2) **Playwright
> keyboard** assertions (the focus trap, Escape-exit, Enter-advance, first-field autofocus), (3) the
> noted **screen-reader matrix**. Layers (1)+(2) are mechanical and re-run by `bash ./ctl.sh a11y` (a
> `phase-gate qa` blocker); layer (3) is the human-noted matrix recorded here. This file is the
> evidence; the executable proof is `tests-a11y/specs/wizard-shell.spec.ts`.

## Pinned environment (the evidence is only valid for these versions)

| Component | Version / build |
|---|---|
| `svelte` | 5.43.5 (runes) |
| behavior layer | none — WizardShell is a NATIVE focus organism (not a bits-ui portal); the focus trap + Enter/Escape contract are the component's own keyboard handler, no bits-ui primitive |
| `@eden/theme` (token source) | workspace `0.0.0` (C21 seed, light mode) |
| `@playwright/test` | 1.60.0 |
| `axe-core` | 4.12.1 |

Re-run: `bash ./ctl.sh a11y` (devcontainer; browsers at `~/.cache/ms-playwright`). A pin change to
any row above invalidates this record until the lane is re-run and the table updated. The lane is
FAIL-NOT-SKIP: an absent browser is a gate failure, not a skip.

## Layer 1 — axe-core (automated WCAG audit), Chromium AND WebKit

Result: **PASS on both engines** — 0 serious/critical violations across the full-screen wizard (the
thin progress bar, the mono `1 / 3` counter + eyebrow, the serif display title as the `<h1>` naming
the `role="dialog"` region, the one-sentence lead, the answer input, the Back/Next footer buttons),
audited against the Eden tokens injected at/above the document (the real reading surface).

- `axe.run(document)` — 0 serious/critical violations. Weaken-to-confirm: the audit walked a
  non-trivial WCAG rule set (`ruleCount > 30`, `passCount > 0`), so the pass is not vacuous.
- Every colour is a derived `@eden/theme` role (title = `onSurface`, lead = `outline`, eyebrow +
  counter + progress fill = `primary`, surface = `surface`), so the `color-contrast` rule passing on
  both engines independently re-proves the design-correctness contrast gate from the rendered,
  cascade-computed colours (two witnesses agree: the in-process `*.design.test.ts` from `@eden/theme`'s
  own WCAG formula, and axe from the browser).
- The progress bar is `aria-hidden` (a purely visual reinforcement) — the same progress information
  reaches the a11y tree via the mono counter's `aria-label="Step 1 / 3"`, so there is no double
  announcement.

## Layer 2 — Playwright keyboard operability + the focus contract, Chromium AND WebKit

Result: **PASS on both engines** (20 assertions, 10 per engine). The doc 17 §6 keyboard contract,
proven through the real browser:

- **Named region.** The wizard is a `role="dialog"` with `aria-labelledby` → the serif `<h1>` title;
  its accessible name is the active step's question (asserted `toHaveAccessibleName`).
- **First-field autofocus.** On mount the answer input holds focus with no click — the slot-forwarded
  `use:autofocus` action (the consumer places it on its first input; the shell forwards the action
  through the `body` snippet param).
- **Enter advances.** Enter on the focused input fires `onAdvance` (an advanceable step) — the counter
  moves `1 / 3` → `2 / 3` and the serif title updates to the next step's question.
- **Escape offers exit.** Escape fires `onExit` (the shell fires the intent; the consumer renders the
  confirm).
- **Focus is TRAPPED.** Tab from the last focusable wraps back INSIDE the wizard subtree (never the
  page's out-of-shell `before`/`after` anchors); Shift+Tab from the first field wraps to the last. The
  page behind the full-screen surface is never reachable by keyboard.
- **Reduced-motion.** Under `prefers-reduced-motion: reduce` the progress fill carries NO transition
  (`transition-duration: 0s`) — a static bar; the fill still reflects the fraction, only the animated
  growth is removed. The default context animates the fill on the theme's `medium.2` (300ms) duration
  + the `standard` easing curve.
- **Progress fraction.** The `--eden-wizard-shell-progress` scaleX var reads `0` on the first step
  (an empty bar) and `0.5` on the middle of the 3-step wizard (arrival = a full bar on the last step).

## Layer 3 — screen-reader matrix (human-noted)

| SR + engine | Result | Note |
|---|---|---|
| VoiceOver + Safari (WebKit) | expected PASS | the dialog region is announced by its serif title; the mono counter is read as "Step 1 / 3"; the input is reached and announced by its label; Escape/Enter behave per the visual contract |
| NVDA + Chromium | expected PASS | same landmark + label announcement; the focus trap keeps the virtual cursor inside the wizard |

> Layer 3 is the noted matrix (the hardware SR pass is a human step); layers 1+2 are the mechanical,
> re-runnable evidence and the gate blocker.
