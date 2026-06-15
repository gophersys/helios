# A11y evidence — chat surfaces (`@eden/primitives`)

> The version-pinned a11y-evidence record (RD-16 / ADR-0004 / ADR-0024). The three-layer
> accessibility stack for the CHAT-SURFACE component group — `Message`, `StreamingText`,
> `ToolCall`, `PermissionRequest`, `UsageMeter`, `ThinkingBlock`: (1) **axe-core** on the **real
> Chromium AND WebKit** engines, (2) **Playwright keyboard** assertions, (3) the noted
> **screen-reader matrix**. Layers (1)+(2) are mechanical and re-run by `bash ./ctl.sh a11y` (a
> `phase-gate qa` blocker; the chat lane has its own isolated config on a non-colliding port). Layer
> (3) is the human-noted matrix recorded here. This file is the evidence; the executable proof is
> `tests-a11y/specs/chat.spec.ts`.

## Pinned environment (the evidence is only valid for these versions)

| Component | Version / build |
|---|---|
| `svelte` | 5.43.5 (runes) |
| `bits-ui` (behavior layer, RD-16/OD-1 — Collapsible + Button) | 2.18.1 |
| `@eden/theme` (token source) | workspace `0.0.0` (C21 seed, light mode) |
| `@playwright/test` | 1.60.0 |
| Chromium browser build | `chromium-1223` (Playwright 1.60.0) |
| WebKit browser build | `webkit-2287` (Playwright 1.60.0) |
| `axe-core` | 4.12.1 |

Re-run: `bash ./ctl.sh a11y` (the shared lane, all specs on port 5180), or the isolated chat lane:
`(cd tests-a11y && bun x vite build --config vite.config.ts && bun x playwright test --config
playwright.chat.config.ts)` (port 5182). Browsers at `~/.cache/ms-playwright`. A pin change to any
row above invalidates this record until the lane is re-run and the table updated.

## Layer 1 — axe-core (automated WCAG audit), Chromium AND WebKit

Result: **PASS on both engines** — **0 serious/critical violations** across every chat surface,
audited against the Eden tokens injected at/above the document (the real reading surface, not a UA
default white). The audit covers all six surfaces mounted together: the `Message` log (user +
assistant bubbles), a live `StreamingText`, three `ToolCall` cards (`running`/`success`/`error`), the
`PermissionRequest` human prompt with its three actions, three `UsageMeter` tiers
(`under`/`near`/`over`), and a collapsed `ThinkingBlock`. The WCAG **`color-contrast`** rule is also
run NARROWED to the painted chat surfaces and passes on both engines — the independent axe engine
confirms the design-correctness contrast gate (`*.design.test.ts`) in a real browser.

Two real defects were caught by this lane during bring-up and FIXED (the value of a real-browser
gate over a formula-only check):

- `aria-progressbar-name` (serious) — the `UsageMeter` `role="progressbar"` had no accessible name;
  fixed by adding `aria-label="Token usage"` (the `aria-valuetext` already speaks the human readout).
- `aria-allowed-role` (minor) — `Message` rendered `<article role="listitem">`, an
  implicit/explicit role conflict; fixed by rendering a plain `<div role="listitem">`. The `ToolCall`,
  `PermissionRequest`, and `UsageMeter` roots were also moved from `<section>` (a region landmark) to
  `role="group"` so a long chat log does not flood the a11y tree with landmarks (`landmark-unique`).

## Layer 2 — Playwright keyboard, Chromium AND WebKit

Result: **PASS on both engines.** Mechanical assertions in `tests-a11y/specs/chat.spec.ts`:

- The three `PermissionRequest` actions (Allow once / Allow for session / Deny — real bits-ui
  Buttons) are each **Tab-reachable** and participate in the tab order **in DOM order**.
- A focused permission action **activates on Enter and on Space** (the native button activation
  contract; click counter increments for each key).
- The `ThinkingBlock` disclosure **toggles on Enter** and its `aria-expanded` flips `false`↔`true`
  (the bits-ui Collapsible behavior layer, keyboard-driven).
- A keyboard-focused action shows a **visible (non-`none`) focus outline** (`:focus-visible`, keyed
  off the foreground token).
- **Hit target:** every interactive chat control (the three actions + the thinking toggle) measures
  **≥ 44×44 px** in the real browser (the AAA tap floor, measured `boundingBox`, not just asserted).
- **Token-driven color:** the user `Message` computed `color`/`background-color` are real, distinct,
  non-transparent values (the on-primary / primary gated pair painted through the cascade).
- **Progressbar:** the over-budget `UsageMeter` exposes `aria-valuenow="100"` and an
  `aria-valuetext` that speaks "over budget".

## Layer 3 — Screen-reader matrix (human-noted)

The expected announced experience per surface. Mechanical layers (1)+(2) prove the wiring; this
matrix is the human-noted expectation that wiring produces. Not yet re-verified live on each SR for
this group (the wiring it depends on IS mechanically proven above) — to be confirmed in a manual SR
pass and dated here.

| Surface | Role / semantics | Expected SR announcement |
|---|---|---|
| `Message` (user) | `role="listitem"`, `aria-label="User message"`, visible author | "User message, list item — User: <prose>" |
| `Message` (assistant) | `role="listitem"`, `aria-label="Assistant message"` | "Assistant message, list item — Assistant: <prose>" |
| `StreamingText` | `role="status"`, `aria-live="polite"`, `aria-busy` | appended tokens announced politely without interrupting; busy state conveyed |
| `ToolCall` | `role="group"`, `aria-label="Tool call: <tool>"`; status in a polite live region | "Tool call: <tool>, group — <tool>, <Running/Succeeded/Failed>"; status word changes announced |
| `PermissionRequest` | `role="group"` ask; `<h3>` heading; nested action group | "Permission required to run <tool>, group — heading Permission required; <reason>; Allow once button, Allow for session button, Deny button" |
| `UsageMeter` | `role="group"`; `role="progressbar"` with `aria-label` + `aria-valuetext` | "Usage and cost, group — Token usage, progress bar, <n> of <budget> tokens (<pct>%, <within/near/over> budget)" |
| `ThinkingBlock` | bits-ui Collapsible; trigger button + `aria-expanded`; content region | "Thinking, button, collapsed/expanded — <reasoning> when expanded" |

### SR matrix target set (the planned manual pass)

| Screen reader | Browser | Status |
|---|---|---|
| VoiceOver | Safari (WebKit) | planned — wiring mechanically proven on WebKit (layers 1+2) |
| NVDA | Firefox/Chromium | planned — wiring mechanically proven on Chromium (layers 1+2) |
| Orca | Chromium | planned |

## Provenance

- Every surface is GENERATED FROM THE MATH: colors/sizes/spaces are `--eden-*` CSS variables whose
  values are DERIVED from `@eden/theme` (via the shared `chat-surface` vocabulary) — no hand-set
  literal (the design-correctness provenance lint is green; the `*.design.test.ts` contrast/scale
  gate is green; this a11y lane confirms it in two real engines).
- The behavior is delegated to bits-ui (RD-16/OD-1): `Button` for the permission actions,
  `Collapsible` for the thinking disclosure.
