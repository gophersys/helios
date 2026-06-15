# ADR-0024: TypeScript/Svelte library engineering pipeline; the design system re-homed in-repo

- **Status:** Accepted (amends ADR-0005's separate-repo home; resolves OD-1; mirrors ADR-0020 for
  TypeScript/Svelte)
- **Date:** 2026-06-14
- **Deciders:** Mateo (ratified the four UI-track decisions D1–D4, 2026-06-14)

## Context

Eden's UI direction is settled at the platform level — Svelte 5 + runes, SvelteKit for
`apps/frontend`, one Vite bundle shipping as web **and** Tauri v2 desktop (ADR-0004/0006/0012/0015) —
and the F6 token law (DTCG ThemeDoc + component manifest + usage rules → validated UI generation,
mode × density × brand axes, OKLCH generative theming with WCAG gates) is a ratified *direction*. But
nothing of it is built: `libs/typescript/` is an empty `.gitkeep`; there is no TS/Svelte library
pipeline (ADR-0020 + the 8-dimension taxonomy are Go-only, and `.ci/ctl.sh lib-gate` is hardcoded to
`libs/go/`); the devcontainer bakes a JS *runtime* (bun + node) but **zero UI-test tooling** (no
vitest, no Playwright browsers/system-libs, no eslint, no axe, no Stryker, no size-limit); there is no
tokens build step; and ADR-0005 still homed the design system in a *separate* published
`gophersys/photosphere` repo.

The Go library track already proves the shape to mirror: four phases
(`architecture → implementation → testing → qa`), a thin per-lib `ctl.sh` dispatcher over a shared
`_ctl/lib.sh`, `project.json` of `nx:run-commands → bash ./ctl.sh` (every target `cache:false`), a
frozen `.apibaseline` whose breach is "the cardinal sin", the 8-dimension test taxonomy, per-package
coverage floors, "absent tool = FAIL not skip", and the `project-go` AI-enforcement plugin
(SessionStart inject / PostToolUse lint / PreToolUse git-gate / Stop phase-check) plus Go `.githooks`.

This ADR rules the **TypeScript/Svelte library-engineering pipeline** — the ADR-0020 analog for UI —
and, with it, the home of the design system. The detailed build spec is the design-foundations
research note `docs/research/05-design-foundations.md` (the empirical math the `@eden/theme` engine
encodes) and the open forks recorded in `open-decisions.md`. Grounded in the UI/TypeScript-track
handoff ratified by Mateo 2026-06-14.

## Decision

### 1. The design system lives in-repo at `libs/typescript/`, scope `@eden/*` (amends ADR-0005, D1)

The UI component/design-system library is **in this monorepo** at `libs/typescript/<kebab>` (npm and
code scope `@eden/*`), **not** a separate published `gophersys/photosphere` repo. This **amends
ADR-0005**: the framework-agnostic theming theses ADR-0005 retained (runtime theming engine, DTCG
ThemeDoc contract, "stabilize schema, vary values", CSS custom properties as runtime substrate,
mode × density × brand axes, OKLCH generative theming with WCAG gates, behavior/appearance seam) are
unchanged — only their *home* and *delivery* move in-repo. HNS-1 holds: `typescript` not `ts`;
`util`/`common`/`core` banned; no `helios` (E7).

### 2. A TS/Svelte pipeline that mirrors ADR-0020, recast for the UI toolchain

`libs/typescript/` reuses the ADR-0020 shape: a shared `libs/typescript/_ctl/lib.sh` (verb bodies
once), thin per-lib `ctl.sh` dispatchers + `project.json` Nx wiring, the four phases with one
`phase-gate <architecture|implementation|testing|qa|all>` each, a frozen per-lib `.apibaseline`, and
"absent tool = FAIL not skip". The exported-surface baseline for a UI library is the
**component/prop/event/slot public-API snapshot** (`.d.ts` / api-extractor) — breaking it is the
cardinal sin, exactly as a `go doc -short` break is for Go. A library is "done" only past
`phase-gate qa`. TDD order (fake binding + conformance cases red, then bodies green) carries over.

### 3. The 8-dimension test taxonomy, recast for UI — plus a ninth: design-correctness

The Go taxonomy maps onto the UI toolchain dimension-for-dimension:

| Go dimension | UI analog |
|---|---|
| correctness / property | `vitest` + `@testing-library/svelte`; `fast-check`; the fake≡real two-binding (fake store vs real Connect-ES) |
| resource / leak | mount→unmount: no leaked listeners/effects (runes-effect teardown probe) |
| lifecycle | mount→update→unmount→remount idempotent; no orphan DOM/effect |
| **integration** | **Playwright** on real browser + real backend — the **forced-CRUD** journey (no-mocks, ADR-0016) |
| load | render-N / interaction-storm without leak |
| security | `npm audit` / `osv-scanner` + eslint-security/semgrep + **gitleaks (reused as-is)** + a SeededCanary DOM-redaction property |
| performance | bundle-size (`size-limit`) + render budget vs baseline |
| maintainability | eslint + `svelte-check` + the a11y matrix (**axe**) + **Stryker** mutation + cover-floor + an HNS-1 name lint |
| **apidiff** | component/prop/event/slot public-API snapshot (the cardinal-sin gate) |

A **ninth dimension — design-correctness — is added** (the novel contribution): aesthetics are made
*computable*. Every color must be **derived** (no hand-set hex → a token-provenance lint); every
fg/bg pair must **pass the contrast gate** (mechanical, from the unrounded WCAG formula); every
size/space must come from the **scale formula** (asserted, not eyeballed); plus axe a11y matrix,
visual-regression snapshots, and Playwright forced-CRUD through the real UI. "Looks right" becomes a
passing gate. (The taxonomy recast is INFERENCE-grade in the handoff and is ratified here; per-tool
specifics live in the pipeline spec and `libs/.claude/rules/21-test-taxonomy.md`'s UI counterpart.)

### 4. The `@eden/*` library set and its phasing

The set is decomposed the way the Go libs are — small, one-concept-one-home, each its own Nx project
+ `ctl.sh` + `.apibaseline` + full gate:

- **Phase 0 (foundation):** `@eden/tsconfig`, `@eden/lint-config` (shared strict TS/Svelte config —
  the `.golangci.yml` analog, final shape gated by OD-3), `@eden/testing` (vitest +
  `@testing-library/svelte` + Playwright + axe + visual-regression + conformance helpers), and
  **`@eden/theme`** — the math core: a DTCG token contract + the generative engine (brand seed →
  complete token set via the research tables, with the **WCAG/APCA contrast gate as a hard
  constraint**), emitting runtime CSS custom properties + a typed token API and owning the
  mode × density × brand axes and the "paste a theme-doc, get full coverage" F6 ingestion. No
  components — pure tokens + math. Gate: `@eden/theme` green through `phase-gate qa`.
- **Phase 1 (core components):** `@eden/behavior` (the OD-1 headless layer — see #5),
  `@eden/primitives` (atoms/molecules, themed *only* via `@eden/theme` tokens), `@eden/patterns`
  (organisms incl. the generic Wizard engine seeded from `apps/frontend`'s `ProductWizard`, a
  DataGrid, dashboard/layout shells), `@eden/visualization` (D3 scales + Svelte renderer, themed),
  `@eden/icons`, `@eden/editor` (the golden markdown editor for workflow files, a themed CodeMirror 6
  wrap). Each through the full gate, each with an `a11y-evidence/<component>.md` record (#5).
- **Phase 2 (agent surface):** `@eden/agent-ui` (or `apps/frontend/src/modules/agent/`) — the
  flagship consumer: virtualized message stream, the streaming "thinking" status line, tool-call +
  permission cards, todo/plan sidebar, file tree + markdown editor, run timeline, ⌘K palette — built
  entirely from the libs above, so it *is* the proof the core set is complete. Quality bar: at or
  above the Claude Code desktop app (D3). Forced-CRUD Playwright E2E.

The first deliverable (D3) is **both** the foundation **and** the agent/chat interface, complete —
enough to "build Eden from Eden" (invariant E5 dogfood).

### 5. Behavior layer = Bits-UI-primary hybrid (resolves OD-1, D4)

The OD-1 spike (fixed WAI-ARIA APG rubric → three candidate profiles → adversarial refutation →
verified ruling) is **executed and ruled**: adopt **Bits UI** (`bits-ui@2.18.1`, Svelte-5-native,
MIT) as the primary behavior layer for overlays / menus / the ⌘K command palette; **hand-roll the
data grid** on Svelte 5 runes over `@tanstack/table-core` (the universal gap no candidate fills);
compose the wizard from Bits `Tabs` + Eden runes. A **Bits-primary hybrid**, not a pure pick
(adversarially-adjusted weighted totals: Bits 4.18 · hand-rolled 3.52 · Melt 3.13; confidence ≈ 0.8).
Melt next-gen is rejected (pre-1.0, single-maintainer, ~3-month stall, ships none of the menu
stack / Command / grid, and its dominant *classic* store/action API is a corpus-hallucination trap in
an agent-authored codebase). Two confirming **runtime** spikes (nested Dialog + LIFO stack; ⌘K
palette ~500 items virtualized) are defined with go/no-go criteria for once the toolchain exists; the
no-go fallback is **hand-rolled**, not Melt. The a11y obligation is Eden's to *produce* (no vendor
attestation): a three-layer evidence stack per pattern — axe on Chromium **and WebKit**, Playwright
keyboard assertions, a manual SR matrix — recorded in a version-pinned `a11y-evidence/<component>.md`
wired as a `phase-gate qa` / Stop-hook blocker. Full ruling: the OD-1 entry in `open-decisions.md`
and the design-foundations note. A required `@eden/theme` design constraint follows: define tokens
**at or above the Portal host** so portalled markup keeps CSS-custom-property token inheritance.

### 6. The AI-enforcement plugin + pipeline plumbing (`project-svelte` / `project-enforcement`)

A `libs/plugins/project-svelte` plugin mirrors `project-go`'s four hooks (SessionStart inject /
PostToolUse lint / PreToolUse git-gate / Stop phase-check), factoring the shared ~60% into a
**`project-enforcement`** abstraction (already named in ADR-0010): reuse `project-go`'s
submodule-aware gating, deny/block channels, touched-lib detection, and phase-probe verbatim; swap
tool resolution to `node_modules/.bin` and the verb bodies to the TS tools. The devcontainer image
gains the pinned UI toolchain (vitest + `@vitest/coverage-v8`, Playwright + browsers + `install-deps`
system libs, eslint flat config + `eslint-plugin-svelte` + `typescript-eslint`, prettier +
`prettier-plugin-svelte`, `@axe-core/playwright`, Stryker, size-limit). `.githooks/{pre-commit,
pre-push}` + `common.sh` gain `*.svelte`/`*.ts` staged-file filters, per-`package.json` resolution,
and the UI verb lanes; `.ci/ctl.sh` gains a non-Go `lib-gate`.

### 7. The scale source is math; C21 seeds are immutable; spacing is brand-invariant (D2)

The generative engine is the **source of truth** for the type / spacing / color-ramp / contrast /
density scales, derived from the research tables. C21's 5 brand colors + 3 font families stay as
**immutable seeds**; C21's mathematically-irregular hand-picked type sizes are **re-derived** for
harmony (full-generative, not the hybrid/pin option — founder confirmation on re-derived literal
sizes is the open item in OD-17-c21). Spacing carries no brand information and is **brand-invariant**.

## Consequences

- **Easier:** standing up a UI library — instantiate the pipeline, gate it, and the toolchain,
  baseline, taxonomy, and AI enforcement come for free and uniform with the Go track. "The theme is
  accessible" becomes a *checked property of the build* (the contrast gate fails rather than ships an
  inaccessible pair), and "looks right" becomes a passing gate via design-correctness. The agent UI
  proves the core set by consuming it.
- **Harder / now invalid:** authoring UI from hand-set hex, off-scale sizes, or a blank component
  with no `.apibaseline`; treating a11y as a vendor claim instead of Eden-produced evidence; landing a
  component whose `a11y-evidence/<component>.md` is not green on all layers; or shipping a behavior
  layer choice without the confirming runtime spikes. A breach of a UI library's exported-surface
  baseline aborts the gate (the cardinal sin).
- **Propagation:** ADR-0005 is annotated as amended by this ADR (its theming theses survive). The
  architecture doc set gains a TS/Svelte-pipeline reference; the design-foundations research note is
  `docs/research/05-design-foundations.md`. `open-decisions.md`: OD-1 moves to Resolved (this ADR),
  and the ten Part-D design forks + the C21 reconciliation + the devcontainer-toolchain
  hold-and-confirm land as OD-17-* entries. **Shared surfaces** (the `libs/` submodule pointer,
  `nx.json`, root `package.json`, the devcontainer image, `harnesses/versions.env`) change only by
  **hold-and-confirm** with the Go-backend track, never silently. The HTML render
  (`node docs/tools/render-html.mjs`) must be regenerated (not done here by hand — generated-artifact
  rule).
- **Alternatives rejected:** (a) keep the design system in a separate published `photosphere` repo
  (ADR-0005's original home) — rejected for the cross-repo version-bump tax and because in-repo
  assembly lets the agent UI dogfood the libs directly under one gate. (b) A Go-only pipeline with UI
  bolted onto app-local tests — rejected: it leaves UI ungated, off-system, and drift-prone, with no
  `.apibaseline` and no design-correctness gate. (c) Pure Bits or pure hand-rolled or Melt for the
  behavior layer — rejected per #5 (Bits ships three of four hard patterns, but ships no grid; Melt
  ships none and carries the corpus-hallucination trap; hand-rolling pays the entire a11y cost where
  it is hardest). (d) Hand-picked literal type sizes pinned from C21 — rejected per D2 for the
  re-derived harmonic scale (seeds retained).
