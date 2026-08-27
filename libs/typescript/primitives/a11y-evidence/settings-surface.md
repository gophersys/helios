# A11y evidence — SettingsSurface (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024 · doc 17 §4/§7). The three-layer
> accessibility stack for the **SettingsSurface** sheet-hosted Settings organism (the app's ONE Settings
> surface): (1) **axe-core** on the **real Chromium AND WebKit** engines, (2) **Playwright keyboard**
> assertions (the focus trap through the portal, Escape-dismiss, the rail's active state), (3) the noted
> **screen-reader matrix**. Layers (1)+(2) are mechanical and re-run by `bash ./ctl.sh a11y` (a
> `phase-gate qa` blocker); layer (3) is the human-noted matrix recorded here. This file is the evidence;
> the executable proof is `tests-a11y/specs/settings-surface.spec.ts`.

## Pinned environment (the evidence is only valid for these versions)

| Component | Version / build |
|---|---|
| `svelte` | 5.43.5 (runes) |
| behavior layer | `bits-ui` Dialog (the RD-16/OD-1 portal + focus-trap + Escape + scroll-lock layer) — the SettingsSurface REINVENTS none of it; it composes the same `Dialog.Portal`/`Dialog.Overlay`/`Dialog.Content` the Eden Dialog uses |
| `@eden/theme` (token source) | workspace `0.0.0` (C21 seed, light mode) |
| `@playwright/test` | 1.60.0 |
| `axe-core` | 4.12.1 |

Re-run: `bash ./ctl.sh a11y` (devcontainer; browsers at `~/.cache/ms-playwright`). A pin change to any
row above invalidates this record until the lane is re-run and the table updated. The lane is
FAIL-NOT-SKIP: an absent browser is a gate failure, not a skip.

## Layer 1 — axe-core (automated WCAG audit), Chromium AND WebKit

Result: **PASS on both engines** — 0 serious/critical violations across the portaled settings sheet (the
`role="dialog"` panel named by its `Dialog.Title`, the section RAIL of mono `role="tab"` buttons with the
active one carrying `aria-current="page"`, the content REGION named by the active rail label, and the
per-section content — a colour-mode radiogroup, a labelled Field/Input, primary Buttons), audited against
the Eden tokens injected at/above the document (the tokens inherit THROUGH the portal to the sheet).

- `axe.run(document)` — 0 serious/critical violations. Weaken-to-confirm: the audit walked a non-trivial
  WCAG rule set (`ruleCount > 30`, `passCount > 0`), so the pass is not vacuous.
- Every colour is a derived `@eden/theme` role (sheet surface = the overlay `surface`, inactive rail
  label = `outline`, active rail label = `primary`, section title = `onSurface`, active tint = a
  translucent view of `primary`), so the `color-contrast` rule passing on both engines independently
  re-proves the design-correctness contrast gate from the rendered, cascade-computed colours (two
  witnesses agree: the in-process `*.design.test.ts` from `@eden/theme`'s WCAG formula, and axe).
- Colour is never the ONLY channel for the active section: the active rail item also gains font-weight
  and carries `aria-current="page"` (a grayscale-safe + a11y-tree signal).

## Layer 2 — Playwright keyboard operability + the focus contract, Chromium AND WebKit

Result: **PASS on both engines**. The doc 17 §7 Settings contract, proven through the real browser:

- **Named dialog region.** The sheet is a bits-ui `Dialog.Content` (role="dialog" + aria-modal) named by
  its `Dialog.Title`; its accessible name is "Settings" (asserted `toHaveAccessibleName`).
- **Mono rail / sans content voices (P-D4).** The active rail label's computed `font-family` is a mono
  generic; the sheet heading's is a different (sans) family — the two type voices are governed, not mixed.
- **Section switching.** Clicking a rail item (Agents) switches the content region to that section (the
  content is section-scoped: the previous section's body is gone, the new one's shows) and moves the
  rail's active state — the region's `aria-labelledby` re-points to the newly active rail tab.
- **Focus is TRAPPED through the portal.** Tab many times from inside the sheet never lands on the page's
  out-of-sheet `before`/`after` anchors; focus stays inside the `[data-eden-settings-surface]` subtree —
  the bits-ui Dialog trap holds across the portal boundary (the half this organism delegates, not rebuilds).
- **Escape dismisses.** Escape from inside the sheet closes it (the bits-ui Dialog close behavior); the
  page behind stays intact (the out-of-sheet anchors remain, no crash on close).

## Layer 3 — screen-reader matrix (human-noted)

| SR + engine | Result | Note |
|---|---|---|
| VoiceOver + Safari (WebKit) | expected PASS | the dialog is announced by its "Settings" title; the rail is a tablist whose active tab is announced (aria-current); the content region is announced by the active section's label; Escape closes |
| NVDA + Chromium | expected PASS | same landmark + tablist announcement; the focus trap keeps the virtual cursor inside the sheet |

> Layer 3 is the noted matrix (the hardware SR pass is a human step); layers 1+2 are the mechanical,
> re-runnable evidence and the gate blocker.
