# A11y evidence — `CommandPalette` (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024). The three-layer
> accessibility stack for the `CommandPalette` component pattern (the OD-1 ⌘K: `Dialog.Portal`
> wrapping `Command.Root`): (1) **axe-core** on the **real Chromium AND WebKit** engines, (2)
> **Playwright keyboard** assertions, (3) the noted **screen-reader matrix**. Layers (1)+(2) are
> mechanical and re-run by `bash ./ctl.sh a11y` (a `phase-gate qa` blocker); layer (3) is the
> human-noted matrix recorded here. This file is the evidence; the executable proof is
> `tests-a11y/specs/command-palette.spec.ts` (13 tests × 2 engines = 26, all PASS).

## Pinned environment (the evidence is only valid for these versions)

| Component                              | Version / build                          |
| -------------------------------------- | ---------------------------------------- |
| `svelte`                               | 5.43.5 (runes)                           |
| `bits-ui` (behavior layer, RD-16/OD-1) | 2.18.1                                   |
| `@eden/theme` (token source)           | workspace `0.0.0` (C21 seed, light mode) |
| `@playwright/test`                     | 1.60.0                                   |
| Chromium browser build                 | `chromium-1223` (Playwright 1.60.0)      |
| WebKit browser build                   | `webkit-2287` (Playwright 1.60.0)        |
| `axe-core`                             | 4.12.1                                   |

Re-run: `bash ./ctl.sh a11y` (devcontainer; browsers at `~/.cache/ms-playwright`). A pin change to
any row above invalidates this record until the lane is re-run and the table updated.

## Composition (the OD-1-proven ⌘K)

The palette is composed exactly as the OD-1 spike proved out: a bits-ui `Dialog.Root` →
`Dialog.Portal` → `Dialog.Overlay` + `Dialog.Content`, with a bits-ui `Command.Root` inside the
content (`Command.Input` + a scrollable `Command.List`/`Command.Viewport` of grouped
`Command.Group`/`Command.GroupHeading`/`Command.GroupItems`/`Command.Item`, plus `Command.Empty`
and `Command.Separator`). The Eden tokens are injected at/above the document, so they cascade through
the Portal host (`document.body`) to the portalled content — the RD-16/OD-1 portal-token pattern.

OD-1 integration lessons carried in: **two-way `bind:value`** on both the dialog `open` state and the
command `value` (the host opens it on ⌘K and reads the selection); the **scrollable results region
carries `tabindex={0}`** so the overflow region is keyboard-focusable.

## Layer 1 — axe-core (automated WCAG audit), Chromium AND WebKit

Result: **PASS on both engines** — 0 serious/critical violations with the palette OPEN, audited
through the Portal against the Eden tokens injected at/above the document (the real reading surface).

- `axe.run(document)` with the palette open — 0 serious/critical violations. Weaken-to-confirm: the
  audit walked a non-trivial WCAG rule set (`ruleCount > 30`, `passCount > 0`), so the pass is not
  vacuous.
- `axe.run([data-eden-command], { runOnly: color-contrast })` with a filtered query (the active item
  painting the selected primary-container pair) — **0 color-contrast violations**. This is the
  design-correctness contrast gate independently re-proven by the axe engine in a real browser: the
  in-process `*.design.test.ts` proves every painted pair from `@eden/theme`'s own WCAG formula; axe
  proves it from the _rendered, cascade-computed_ colors — two independent witnesses agree, including
  for the SELECTED item (on-primary-container over primary-container) and the group heading.

## Layer 2 — Playwright keyboard operability + the ARIA pattern, Chromium AND WebKit

Result: **PASS on both engines.**

| Assertion                                                                                                                             | Result |
| ------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| Opening the palette moves focus into the input; the modal traps focus (`Dialog.Content`)                                              | PASS   |
| The input is `role=combobox` with `aria-expanded=true` + `aria-controls` (the listbox)                                                | PASS   |
| The results region is `role=listbox`; items are `role=option` inside labelled `role=group`s                                           | PASS   |
| `ArrowDown` advances `aria-activedescendant`; the active id resolves to the `aria-selected` option                                    | PASS   |
| `Enter` on the active command fires `onSelect` (the bound value updates) and closes the palette                                       | PASS   |
| `Escape` closes the palette and returns focus to the page (dismissable; focus not trapped when closed)                                | PASS   |
| The scrollable results list (`Command.List`) is keyboard-focusable (`tabindex=0` — the OD-1 lesson)                                   | PASS   |
| The rendered selected `color`/`background-color` equal the resolved `--color-on-primary-container`/`--color-primary-container` tokens | PASS   |
| The input + every option's bounding box meets the 44px AAA tap floor in the real browser                                              | PASS   |
| Fuzzy search filters on label AND keywords (`"preferences"` → "Open Settings"); a no-match query shows the empty message              | PASS   |
| The `disabled` command is `aria-disabled` and excluded from activation                                                                | PASS   |

The focus ring, the selected-item pair, and the 44px tap floor are all keyed off `@eden/theme`
tokens (`var(--eden-command-*)` derived from the role set + the decoupled `hitTargetPx`), so the
keyboard-operability evidence is also token-provenance evidence — the navigation lands on rows whose
colors and sizes are math-generated, proven as rendered.

## Layer 3 — Screen-reader matrix (noted)

The palette delegates its semantics entirely to the bits-ui `Dialog` + `Command` ARIA combobox
pattern: a labelled dialog (`Dialog.Title`/`Dialog.Description` provide the accessible name), an
input announced as a combobox with the active option fed via `aria-activedescendant`, a listbox of
options grouped under labelled groups, and the native `aria-disabled` for non-selectable items. The
expected announcement matrix:

| Screen reader + browser           | Expected announcement                                                                                                                                          | Status                                                                              |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| VoiceOver + WebKit (Safari/macOS) | dialog name on open → "Command palette, combobox" → each option label + "selected" as the active descendant moves; "dimmed"/"unavailable" on the disabled item | Expected-correct (combobox+activedescendant pattern); on-device pass to be recorded |
| NVDA + Chromium (Windows)         | "Command palette dialog" → "combobox" + "list with N items" → each option label as `aria-activedescendant` advances; "unavailable" on the disabled item        | Expected-correct (combobox+activedescendant pattern); on-device pass to be recorded |
| Orca + Chromium (Linux)           | dialog → combobox → option labels announced from the listbox as the active descendant changes                                                                  | Expected-correct (combobox+activedescendant pattern); on-device pass to be recorded |

Rationale for "expected-correct": the component adds NO custom `role`/`aria-*` beyond what bits-ui's
`Dialog` + `Command` already manage (the combobox `aria-expanded`/`aria-controls`/
`aria-activedescendant`, the listbox `role`, the option `aria-selected`/`aria-disabled`, the group
`role`+`aria-labelledby`). The axe `aria-*`/`aria-required-children`/`color-contrast` rules passing on
both engines (layer 1) plus the `aria-activedescendant` movement assertion (layer 2) are the
automated proxy for the SR-name + active-tracking portion of this matrix. On-device SR runs are the
manual confirmation step (tracked separately); no automated harness exercises a real screen reader in
CI today.

## Provenance note (why this is design-correctness evidence too)

Every color and size the palette paints is a CSS custom property whose value is **derived** from an
`@eden/theme` token (`src/command-palette/tokens.ts` — the input/item/selected/heading role pairs, the
spacing-ramp panel radius + list max-height, the decoupled `hitTargetPx`); the component markup
carries no literal color/px. The layer-1 color-contrast pass and the layer-2 token-equality + 44px
assertions therefore double as proof that the math-generated tokens clear the accessibility floors
**as rendered through the Portal**, not just in the unit math. MATH IS SOURCE OF TRUTH.
