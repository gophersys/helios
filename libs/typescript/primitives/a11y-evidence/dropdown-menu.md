# A11y evidence — `DropdownMenu` (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024). The three-layer
> accessibility stack for the `DropdownMenu` overlay pattern: (1) **axe-core** on the **real Chromium
> AND WebKit** engines **through the bits-ui Portal**, (2) **Playwright keyboard** assertions (roving
> arrow navigation + Enter activation + focus return + the 44px item tap floor), (3) the noted
> **screen-reader matrix**. Layers (1)+(2) are mechanical and re-run by `bash ./ctl.sh a11y` (a
> `phase-gate qa` blocker); layer (3) is the human-noted matrix recorded here. This file is the
> evidence; the executable proof is `tests-a11y/specs/overlay.spec.ts`.

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

Result: **PASS on both engines** — 0 serious/critical violations with the menu open, audited against
the Eden tokens carried THROUGH `DropdownMenu.Portal` (host `document.body`) via the inline
`--eden-overlay-*` style on the portaled Content (inherited by every menu item).

- `axe.run(document)` with the menu open — 0 serious/critical violations. Weaken-to-confirm:
  `ruleCount > 30`, `passCount > 0` (the pass is not vacuous).
- The portaled menu's computed `background-color` **equals** the resolved `--color-surface` token
  (the tokens crossed the Portal). The surface/on-surface pair clears the WCAG AA contrast target in
  `src/overlay/overlay.design.test.ts` (the in-process ninth-dimension witness).

## Layer 2 — Playwright keyboard operability, Chromium AND WebKit

Result: **PASS on both engines.**

| Assertion | Result |
|---|---|
| The menu opens from its trigger and exposes `role="menu"` with one `role="menuitem"` per data row | PASS |
| `ArrowDown` highlights the first item (roving), `Enter` activates it (the `onSelect` fires) | PASS |
| The menu **closes on selection** and focus **returns to the trigger** | PASS |
| Every ENABLED item's bounding box meets the **44px AAA tap floor** in the real browser | PASS |
| The DISABLED item is present (`role="menuitem"`) but carries `data-disabled` (not operable) | PASS |

Roving arrow navigation, typeahead, Enter/Space activation, Escape close, and focus return are all
delegated to the bits-ui `DropdownMenu`/`Menu` primitive (RD-16/OD-1). Each item's
`min-block-size: var(--eden-overlay-hit-target)` = the theme's decoupled `hitTargetPx` (≥ 44), so the
tap-floor evidence is also token-provenance evidence — a dense visual row never shrinks the target.

## Layer 3 — Screen-reader matrix (noted)

The DropdownMenu renders the native ARIA menu pattern via `bits-ui` (`role="menu"` /
`role="menuitem"`, `aria-disabled` on disabled rows, the trigger's `aria-haspopup`/`aria-expanded`).
The expected announcement matrix:

| Screen reader + browser | Expected announcement | Status |
|---|---|---|
| VoiceOver + WebKit (Safari/macOS) | "&lt;label&gt;, menu" then "&lt;item&gt;, N of M" per item; "dimmed" on disabled | Expected-correct (native menu pattern); on-device pass to be recorded |
| NVDA + Chromium (Windows) | "&lt;label&gt; menu" then "&lt;item&gt; N of M"; "unavailable" on disabled | Expected-correct (native menu pattern); on-device pass to be recorded |
| Orca + Chromium (Linux) | "&lt;label&gt; menu" then each menu item | Expected-correct (native menu pattern); on-device pass to be recorded |

Rationale for "expected-correct": the component adds NO `role`/`aria-*` override on top of bits-ui's
menu semantics — the roles, the roving focus, and `aria-disabled` are bits-ui's; the axe `aria-*` and
`aria-required-children`/`aria-required-parent` rules pass on both engines (the automated proxy for
the menu-structure portion of this matrix). On-device SR runs are the manual confirmation step
(tracked separately).

## Provenance note (why this is design-correctness evidence too)

Every color and size the menu paints is a CSS custom property whose value is **derived** from an
`@eden/theme` token (`src/overlay/tokens.ts`); the markup carries no literal color/px. The layer-1
token-equality + contrast pass and the 44px item-floor assertion therefore double as proof that the
math-generated tokens clear the accessibility floors **as rendered through the Portal**. MATH IS
SOURCE OF TRUTH.
