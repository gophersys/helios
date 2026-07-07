# Handoff — UI / TypeScript track → the single orchestrator

> **Status:** Handoff (transient working artifact — NOT a canonical spec). To be re-homed by
> the orchestrator into proper ADRs / research-notes per the doc-10 four-class scheme.
> **Authored by:** the UI/TypeScript-track agent · **Date:** 2026-06-14 · **Branch:** `init/seed`.
> **Epistemic legend:** ✅ robust/primary-sourced · 🔶 convention/single-study · ⚠️ contested/myth · 🧩 engine decision.

## TL;DR — what this is

A clean context handoff so the UI/TypeScript track converges under one orchestrator with nothing
lost. I touched **zero repo files** (working tree is clean apart from this one new doc); my value
lived only in context, so it is captured here in full:

1. **§1** the four ratified decisions (Mateo, 2026-06-14);
2. **§2** the repo-state map (DECIDED / OPEN / MISSING + file pointers);
3. **§3** the three surprises the orchestrator asked me to record;
4. **§4** the proposed UI-library architecture (decomposition, the "design-correctness gate", the
   pipeline/instrumentation plan, the deconfliction map, the phasing);
5. **§5 + Appendix B** the OD-1 behavior-layer ruling (the spike resolved → **Bits-UI-primary hybrid**);
6. **§6 + Appendix A** the commissioned design-research foundation — the **math tables** (type/
   spacing/OKLCH-color/contrast/motion/density) the generative theme engine is built on, web-sourced,
   adversarially fact-checked, 4 corrections applied;
7. **§7** open items + the rulings still needed;
8. **§8** WIP, number-collision notes, and how to pick this up.

This doc is **uncommitted** in the working tree — I did not commit it (no surprise commits during a
handoff). Integrate/commit it as you see fit.

---

## §1 — Ratified decisions (Mateo, 2026-06-14)

| # | Decision | Ruling | Consequence |
|---|---|---|---|
| **D1** | **Home of the UI component library** | Lives **in this monorepo** at `libs/typescript/<kebab>` (npm/code scope `@eden/*`). | **AMENDS ADR-0005** (the design system is no longer a separate published `gophersys/photosphere` repo — it is in-repo). Mirror the ADR-0020 Go-pipeline shape (per-lib thin `ctl.sh` dispatcher + shared `_ctl/lib.sh`, `project.json` of `nx:run-commands → bash ./ctl.sh`, frozen `.apibaseline`, the 8-dimension taxonomy recast for UI, devcontainer-native). |
| **D2** | **Scale source: math vs the C21 lock** | **Math is the source of truth.** The generative engine produces the type / spacing / color-ramp / contrast / density scales from the research tables. | C21's **5 brand colors + 3 font families stay as immutable SEEDS**; C21's hand-picked (mathematically irregular) **type sizes are RE-DERIVED** for harmony. (Mateo chose full-generative, **not** the hybrid/pin option — confirm founder is OK with re-deriving the literal sizes; see §7.) |
| **D3** | **First deliverable** | **BOTH** the **foundation** (the TS/Svelte library pipeline + the `@eden/theme` generative engine) **AND** the **agent/chat interface** — both complete and thorough. | Enough to "**build Eden from Eden**" (invariant E5 dogfood). Agent-UI quality target: at or above the Claude Code desktop app — streaming "thinking" status words, todo/plan sidebar, in-app golden markdown editor for custom-workflow files, configuration. |
| **D4** | **OD-1 behavior layer** | **Decide by spike**, scoring the a11y + maintenance + LLM-legibility matrix ADR-0004 demands. | **RULED** (evidence-based spike executed — see §5): **Bits-UI-primary hybrid** + hand-rolled grid. Two confirming *runtime* spikes are defined for when the toolchain exists. |

---

## §2 — Repo-state map (grounding)

Established by a six-reader sweep of the repo. **DECIDED / OPEN / MISSING**, with file pointers.

### DECIDED (the rails)
- **Stack:** Svelte 5 + runes; **SvelteKit** for `apps/frontend`; one Vite bundle ships as web **and**
  Tauri v2 desktop — web/desktop parity mandated. (`adr/0004`, `adr/0006`, `adr/0012`, `adr/0015`.)
- **Clients are control surfaces** — never run project compute (`adr/0012`).
- **Token law (F6 contract):** DTCG ThemeDoc + component manifest + usage rules → *validated* UI
  generation; "no off-system colors/components"; themes-as-data, runtime CSS custom properties,
  **mode × density × brand** axes, **OKLCH generative theming with WCAG gates**. This is *exactly*
  the dynamic-theme + "paste-a-theme-doc" vision — ratified direction, just unbuilt.
  (`05-connector-model.md:59`, `03-system-decomposition.md:134-138`, `adr/0005:16-22`.)
- **Naming (HNS-1):** UI libs are **TypeScript** libs → `libs/typescript/<kebab>`, scope `@eden/<kebab>`;
  `typescript` not `ts`; `util/common/core` banned; no `helios` (E7). (`10-library-system.md:145,153,327`,
  `libs/.claude/rules/11-naming.md`.)
- **Planned `@eden/*` inventory** (decided slugs, unbuilt): `@eden/domain`, `@eden/api` (Connect-ES,
  the only backend seam), `@eden/state` (runes), `@eden/commands` (⌘K registry), `@eden/platform`
  (Tauri bridge), `@eden/machines`, `@eden/testing` (vitest + Svelte testing library), `@eden/tsconfig`,
  `@eden/lint-config`. (`10-library-system.md:362-373`.)
- **The Go library pipeline (the template to mirror):** four phases (`architecture → implementation →
  testing → qa`), one `ctl.sh` verb per dimension, `project.json` of `nx:run-commands → bash ./ctl.sh`
  (every target `cache:false`), frozen `.apibaseline` ("the cardinal sin" = breaking exported surface),
  the 8-dimension test taxonomy, per-package coverage floors (80 leaf / 70 substrate), a blind-gate-proof
  PASS/FAIL summary, "absent tool = FAIL not skip". The AI-enforcement plugin `project-go` (SessionStart
  inject rules / PostToolUse lint / PreToolUse git-gate / Stop phase-check) + `.githooks/{pre-commit,pre-push}`.
  (`adr/0020`, `14-library-engineering-pipeline.md`, `libs/go/_ctl/lib.sh`, `libs/go/secrets/{ctl.sh,project.json}`,
  `libs/plugins/project-go/`.)
- **Existing frontend (real, good, app-local):** `apps/frontend` (SvelteKit 5, Vite 8, `@playwright/test`).
  The **`ProductWizard`** (`src/lib/chat/wizard/`) is a high-quality pure-form multi-step wizard (typed
  step machine, async-gated step 0→1, per-step validation, bindable sub-fields, full a11y) — the right
  seed for a generic `<Wizard>`. The design tokens are real but **hand-transcribed inline** in
  `src/routes/+layout.svelte` (`:37-176`) — not importable, drift-prone. The Playwright **forced-CRUD
  E2E** (`tests/e2e/`) drives the real gateway over real REST+SSE (no mocks) — a strong reusable pattern,
  but not wired into Nx/CI.

### OPEN (forks)
- **OD-1** behavior layer — **now ruled by the spike** (§5).
- **OD-3** client state / query / machine layers (runes + TanStack Svelte Query; XState adapter); also
  gates the TS exported-API-diff toolchain + `@eden/tsconfig`/`@eden/lint-config`. (`open-decisions.md:11`.)
- **10 design rulings** the research surfaced (Appendix A, Part D) — APCA gate-or-advisory, type-ratio
  default, density-default-per-surface, shadow model, etc. (§7).

### MISSING (greenfield — what must be built)
- `libs/typescript/` is an **empty `.gitkeep`**. No TS/Svelte library exists.
- **No TS/Svelte library pipeline.** ADR-0020 + the 8-dim taxonomy are **Go-only**; `.ci/ctl.sh lib-gate`
  is hardcoded to `libs/go/`. No `libs/typescript/_ctl/lib.sh`, no non-Go `phase-gate`, no `.apibaseline`
  mechanism for components.
- **Devcontainer bakes a JS *runtime* (bun 1.3.14 + node 24) but ZERO UI-test tooling** — no vitest, no
  Playwright browsers/system-libs, no eslint, no axe, no Stryker, no size-limit. ("Absent tool = FAIL"
  is wired only for the Go toolchain.)
- **No tokens build step** (the `tokens.json → CSS/TS` generator) — today it's manual transcription.
- **No `project-svelte`/`project-enforcement` plugin**; `.githooks` are Go-only (`*.go` + `go.mod`).
- The "how Apple designs UIs to feel human" research **did not exist** — now commissioned (§3a, Appendix A).

**Best file pointers for the next builder:** `libs/go/_ctl/lib.sh` (verb-body template) ·
`libs/go/secrets/{ctl.sh,project.json}` (thin dispatcher + 22-target Nx shape) · `14-library-engineering-pipeline.md`
· `libs/plugins/project-go/` (plugin to clone) · `libs/.claude/rules/{00-identity,11-naming,20-library-pipeline,21-test-taxonomy}.md`
· `10-library-system.md` (§5 naming, §7.2 app architecture, §12 inventory) · `12-presentation-layer.md` (IA spec) ·
`adr/{0004,0005,0006,0012,0015,0016,0020}` · `apps/frontend/src/lib/chat/wizard/` + `apps/frontend/tests/e2e/`
· `documents/design-system/tokens.json` + `documents/design-brief.md`.

---

## §3 — The three surprises (recorded for handoff)

**(a) The Apple / "how UIs feel human" research did not exist — it has been commissioned fresh.**
A repo-wide search found nothing (the only "Apple" hit is *Apple Music* as a Svelte proof-point; the one
existing research note `docs/research/04-platform-ui-paradigms.md` is learnability/IA, not aesthetics). It
is **now written** — see Appendix A: Apple HIG + human-factors "feel" principles **plus** the concrete
proportion/type/spacing/color/contrast/motion/density **math tables**, web-sourced and fact-checked.

**(b) ADR-0005 is amended.** The design system lives **in `libs/typescript/`** (this monorepo), **not** a
separate `photosphere` repo, consumed published. (Ratified decision D1.) Needs a written ADR amendment.

**(c) The entire TS/Svelte library pipeline + the UI-test toolchain are greenfield.** No vitest /
Playwright-browsers+system-libs / eslint / axe / Stryker in the devcontainer; `libs/typescript/` is empty;
no non-Go `phase-gate`, no component `.apibaseline`, no `project-svelte` plugin, no tokens build step.

---

## §4 — Proposed UI-library architecture

The *structure* below is firm; the two research jobs (§5/§6) refine its **contents** (the math inside
`@eden/theme`, the `@eden/behavior` choice). Decomposed the way the Go libs are: small, one-concept-one-home,
each its own Nx project + `ctl.sh` + frozen `.apibaseline` + full gate.

### 4.1 The library set (`libs/typescript/`, scope `@eden/*`)

**Foundation (Phase 0):**
- **`@eden/tsconfig` · `@eden/lint-config`** — shared strict TS/Svelte config (the `.golangci.yml` analog). Prereq for every lib. (Final shape gated by OD-3.)
- **`@eden/theme`** — *the math core.* DTCG token **contract** + the **generative engine**: brand seed → complete token set via the research tables (type scale from a modular ratio, spacing scale, OKLCH color ramps, the **WCAG/APCA contrast gate as a hard constraint**, motion/elevation, density). Emits runtime CSS custom properties + a typed token API. Owns **mode × density × brand** axes + the "paste a theme-doc, get full coverage" ingestion + validation (the F6 contract). No components — pure tokens + math. (Encodable spec = Appendix A, Part C.)
- **`@eden/testing`** — vitest + `@testing-library/svelte` + Playwright + axe harness + visual-regression + the conformance-suite helpers (the fake≡real two-binding, the a11y matrix). The `libs/go/.../testing` analog.

**Core components (Phase 1):**
- **`@eden/behavior`** — the OD-1 headless layer. **Ruling (§5): a thin Eden-opinionated layer over Bits UI** for overlays/menus/⌘K, + hand-rolled `role="grid"` over `@tanstack/table-core`, + a Wizard shell from Bits `Tabs` + runes.
- **`@eden/primitives`** — atoms + molecules: Button, Input, Select, Checkbox/Radio/Switch, Chip, Badge, Tooltip, Popover, **Dialog**, **Menu**, Tabs, Accordion, Toast, Spinner, Progress… themed **only** via `@eden/theme` tokens.
- **`@eden/patterns`** — organisms: the generic **Wizard engine** (seeded from `ProductWizard`), Form builder, **DataGrid**, Dashboard/layout shells.
- **`@eden/visualization`** — graphs, **gauges**, charts, observability tiles (dataviz core wrapping D3 scales + a Svelte renderer; themed by tokens).
- **`@eden/icons`** — icon set, sized by the scale.
- **`@eden/editor`** — the **golden markdown editor** for workflow files (CodeMirror 6 wrap, themed).

**Agent surface (Phase 2 — the flagship consumer):**
- **`@eden/agent-ui`** (or `apps/frontend/src/modules/agent/`) — message stream (virtualized), the
  **streaming "thinking" status line** with rotating words, tool-call + permission cards, **todo/plan
  sidebar**, file tree + the markdown editor, run timeline, ⌘K palette. Built entirely from the libs above
  → it *is* the proof that the core set is complete. (Claude-Code-desktop quality bar, D3.)

### 4.2 The "design-correctness gate" — the novel contribution

This is the answer to "programmatic UI design/testing isn't good today": **make aesthetics computable.**
The math engine turns taste into checkable properties. The UI recast of the test taxonomy **adds a
design-correctness dimension**:
- every color is **derived** (no hand-set hex) → a lint asserts token provenance;
- every fg/bg pair must **pass the contrast gate** (mechanical, from the WCAG formula, unrounded — Appendix A B.4);
- every size/space comes from the **scale formula** (asserted, not eyeballed);
- **axe** a11y matrix + **visual-regression** snapshots + **Playwright forced-CRUD** (create→read→update→delete
  *through the UI*, real browser, real backend — the "full integration CRUD" requirement).

"Looks right" becomes a passing gate.

### 4.3 The 8-dimension taxonomy, recast for UI (INFERENCE — to be ratified in the new pipeline ADR)

| Go dimension | Go tool | UI analog |
|---|---|---|
| correctness (`test`,`property`) | go test -race, rapid | `vitest` + `@testing-library/svelte`; `fast-check`; the fake≡real two-binding (fake store vs real Connect-ES) |
| resource/leak | goleak | mount→unmount: no leaked listeners/effects (runes-effect teardown probe) |
| lifecycle | AssertLifecycle | mount→update→unmount→remount idempotent; no orphan DOM/effect |
| **integration** | REAL docker+k3d+kind | **Playwright** on real browser + real backend — the **forced-CRUD** journey (the "no-mocks" rule, ADR-0016) |
| load | fan-out under -race | render-N / interaction-storm without leak |
| security (`vuln`,`sast`,`secretscan`) | govulncheck/gosec/gitleaks | `npm audit`/`osv-scanner` + eslint-security/semgrep + **gitleaks (reuse as-is)** + the **SeededCanary DOM-redaction** property |
| performance (`bench-guard`) | benchstat vs `.benchbaseline` | bundle-size (`size-limit`) + render budget vs baseline |
| maintainability | golangci+hnslint+cohesion+gremlins | eslint+`svelte-check` + a11y matrix (**axe**) + **Stryker** mutation + cover-floor + an HNS-1 name lint |
| **apidiff** (`.apibaseline`) | go doc -short snapshot | component/prop/event/slot public-API snapshot (`.d.ts`/api-extractor) — the "cardinal sin" gate (pending OD-3 toolchain ruling) |
| **(new) design-correctness** | — | token-provenance lint + contrast gate + scale-provenance assertions + visual-regression (§4.2) |

### 4.4 Pipeline / instrumentation (built alongside Phase 0)
- `libs/typescript/_ctl/lib.sh` — shared verb bodies (the ADR-0020 engine, recast for the §4.3 tools).
- `libs/plugins/project-svelte` — the AI-enforcement plugin (SessionStart/PostToolUse/PreToolUse/Stop),
  factoring the shared ~60% into **`project-enforcement`** (ADR-0010 already names this abstraction). Reuse
  `project-go`'s submodule-aware gating, deny/block channels, touched-lib detection, phase-probe verbatim;
  swap tool resolution to `node_modules/.bin` and the verb bodies to the TS tools.
- **Devcontainer image additions** (vitest, `@vitest/coverage-v8`, Playwright + **browsers + `install-deps`
  system libs** pinned at build time, eslint flat config + `eslint-plugin-svelte` + `typescript-eslint`,
  prettier + `prettier-plugin-svelte`, `@axe-core/playwright`, Stryker, size-limit). **Shared-config change
  → hold-and-confirm** with the Go-backend agent before it lands.
- **Two ADRs to write** (numbers left to the orchestrator — see §8): an **ADR-0005 amendment** (re-home the
  design system into `libs/typescript/`) + a new **"TS/Svelte library engineering pipeline"** ADR (the
  ADR-0020 analog: phases, gates, the §4.3 tool mapping, the design-correctness dimension).
- `.githooks/{pre-commit,pre-push}` + `common.sh` — add `*.svelte`/`*.ts` staged-file filters + per-`package.json`
  resolution + the UI verb lanes.

### 4.5 Deconfliction map

| Mine (UI/TS track) | Theirs (Go-backend track) |
|---|---|
| `libs/typescript/**`, `libs/plugins/project-svelte/**` (+ `project-enforcement`) | `libs/go/**` |
| new UI ADRs + specs in `docs/` | their backend docs |
| `apps/frontend/src/modules/agent/**` (or `@eden/agent-ui`) | backend services / `apps/agentgateway` |

Disjoint files. **Shared surfaces** (`libs/` submodule pointer, `nx.json`, root `package.json`, the
devcontainer image, `harnesses/versions.env`) = **hold-and-confirm**, never silently committed.

### 4.6 Phasing (aligned to D3 — foundation + agent UI, both complete)
- **Phase 0 — Foundation:** the TS/Svelte pipeline + toolchain + `@eden/tsconfig`/`@eden/lint-config`/`@eden/testing`
  + `@eden/theme` (the math engine + the design-correctness gate operational). Gate: `@eden/theme` green
  through `phase-gate qa`.
- **Phase 1 — Core components:** `@eden/behavior` (Bits-hybrid, after the confirming spikes) + `@eden/primitives`
  + `@eden/patterns` (incl. the Wizard engine) + `@eden/icons` + `@eden/visualization` + `@eden/editor`. Each
  through the full gate, each with an `a11y-evidence/<component>.md` record (§5/Appendix B).
- **Phase 2 — Agent/chat surface:** `@eden/agent-ui` + the agent page, Claude-Code-grade, consuming everything;
  forced-CRUD Playwright E2E.

---

## §5 — OD-1 ruling (behavior layer) — the spike resolved

**The "spike all three" (D4) was executed as an evidence-based evaluation** (fixed WAI-ARIA APG rubric →
three candidate profiles → adversarial refutation → verified ruling). **Full decision = Appendix B.**

**Ruling:** adopt **Bits UI** (`bits-ui@2.18.1`, Svelte-5-native, MIT, ~754k weekly downloads, shadcn-svelte's
foundation) as the primary behavior layer for overlays / menus / the ⌘K command palette; **hand-roll the data
grid** on Svelte 5 runes over `@tanstack/table-core` (the universal gap *no* candidate fills); compose the
**wizard** from Bits `Tabs` + Eden runes. A **Bits-primary hybrid**, not a pure pick. **Confidence ≈ 0.8.**

**Adversarially-adjusted scoring (weighted total):** **Bits 4.18** · Hand-rolled 3.52 · Melt 3.13. Both gates
(a11y/APG, theming-cleanliness) pass for all three; the decision rests on **coverage of the hard patterns**
(Bits ships Dialog/Menu/Command first-class; Melt next-gen ships none; both unbuilt are a full hand-roll) and
**LLM-authorability** (a typed Radix/shadcn-lineage compound-component API an agent has seen thousands of
times beats contract-free ARIA an agent re-derives — and silently gets wrong — every time).

**Why not Melt:** next-gen `melt@0.44.0` is pre-1.0, single-maintainer, ~3-month stall, 6.5k weekly downloads,
ships no menu stack / no Command / no grid; agents will reach for the dominant *classic* store/action API
(~25:1 corpus dominance) which is structurally incompatible with the next-gen model — a daily failure mode in
an agent-authored codebase. (Bits + Melt share one maintainer, so "fall back to Melt" is not bus-factor diversity.)

**Key risks + mitigations:** single-maintainer SPOF (MIT, de-facto standard, and Eden owns 100% of appearance →
a fork touches only behavior wiring); no vendor a11y attestation (Eden must *produce* the ADR-0004 evidence —
true of every candidate); Portal/top-layer **markup leak** can break CSS-custom-property token inheritance that
relies on DOM ancestry → **define tokens at/above the Portal host** (a required `@eden/theme` design constraint).

**A11y evidence-story plan (ADR-0004) — a three-layer stack per pattern, all green before a component merges:**
(1) **axe** via `@axe-core/playwright` on real Chromium **and WebKit** (the WKWebView/Tauri proxy), every state;
(2) **Playwright keyboard assertions** (axe can't see keyboard) — focus-trap wrap, LIFO Escape, roving-tabindex,
`aria-activedescendant` realized+`scrollIntoView`'d under virtualization, grid cell-nav; (3) **manual SR matrix**
(NVDA+FF / VoiceOver+Safari / JAWS+Chrome). Artifact: a version-pinned `a11y-evidence/<component>.md`, wired as a
`phase-gate qa`/Stop-hook blocker.

**Two confirming RUNTIME spikes (build once the toolchain exists, before committing the lib to Bits):** (1) a
focus-trapped **nested Dialog + LIFO stack** styled entirely with Eden tokens through the Portal; (2) the **⌘K
palette**, ~500 items, grouped + virtualized (`@tanstack/svelte-virtual`) + Eden's own fuzzy scorer. **Go** if
both pass axe at every depth on Chromium+WebKit with correct LIFO/scroll-lock/focus-return and tokens render
through the Portal; **No-Go → fall back to hand-rolled** (3.52, already the grid plan), **not** Melt.

---

## §6 — Design-research foundation (the math the engine encodes)

**Full canonical note = Appendix A** (web-sourced, adversarially fact-checked; 4 load-bearing corrections
applied). It is the empirical foundation for the generative `@eden/theme` engine. The thesis: **a small brand
seed + research tables ⇒ a complete, proportional, accessible token system**, with the **contrast gate as a
hard constraint** (the build *fails* rather than ship an inaccessible pair). It is scrupulous about **evidence
vs. convention vs. myth** — e.g. the golden ratio φ as a "beauty law", "the 8pt grid is scientific", and
"complementary colors are harmonious" are flagged ⚠️ and demoted; the 4/8px grid's *real* justification is
integer device-pixel rendering, not aesthetics.

**Load-bearing constants/formulas the engine must encode (corrected values — see Appendix A for derivations & cites):**
- **Contrast (the hard gate, ✅ exact, no rounding):** sRGB linearization threshold **0.04045** (not the stale
  0.03928); luminance `L = 0.2126R + 0.7152G + 0.0722B`; ratio `(L1+0.05)/(L2+0.05)`; thresholds **4.5:1** body /
  **3:1** large+UI / **7:1** AAA. **APCA** (advisory only — WCAG 2.x is the legal gate): cross-walk **Lc 45≈3:1,
  Lc 60≈4.5:1, Lc 75≈7:1**. The generator *inverts* the gate: bisect OKLCH lightness to the nearest on-brand
  foreground that passes.
- **Type:** geometric scale `size(i)=base·ratio^i`; **default ratio 1.20** (minor third) for UI, 1.25 marketing,
  φ opt-in only; the exact **fluid clamp** formula (keep a `rem` term for WCAG 1.4.4); line-height falls with
  size (body ≥ **1.5×**, WCAG 1.4.12); measure 60–66ch.
- **Color (OKLCH):** the verbatim sRGB↔OKLab matrices; lightness ladder (Tailwind-v4 tuned) + **chroma envelope
  peaking mid-tone**; **gamut-map** (CSS Color 4, JND=2); seed snapped to nearest ramp step + pinned; **dark mode
  is a role→tone remap, NOT a lightness flip** (elevation by lighter surfaces, accent L+chroma correction, never
  pure black/white); semantic state hues near-static.
- **Spacing:** brand-**invariant**, 4px grid, the Eden ramp (2/4/8/12/16/20/24/32/40/48/64/96…); Material window-class
  breakpoints (600/840/1200/1600); touch targets **24px AA / 44px Apple-AAA / 48dp Material**.
- **Motion/elevation:** M3 duration ladder (50ms steps→600, 100ms→1000); M3 easing beziers verbatim — **`emphasized`
  is a two-segment spline, ship a CSS `linear()` fallback**; iOS-17 spring `(duration, bounce)` math; **reduced-motion
  is a first-class mode** (collapse transforms, keep fades); layered parametric shadows (tint, don't blacken).
- **Density:** one continuous **scalar over a fixed base** (4px/step), named tiers spacious/comfortable/compact/condensed
  (**compact = Eden default for IDE/agent surfaces**); scales geometry + leading **only** — never font/icon size, hit
  targets, or contrast (clamps applied LAST; density can never beat a floor).

**Unified token model (Appendix A, Part C):** DTCG `$type`s = `color`, `dimension`, `number`, `typography`,
`shadow`, `duration`, `cubicBezier`, `transition`, + `$extensions.eden.*` (spring, z-index, elevation overlay,
**contrast audit sidecar**, density policy). Axes **mode × density × brand** (+ orthogonal breakpoint), with strict
ownership (color on mode×brand; geometry on density; spacing brand-invariant). The `generateTheme(seed, axes)`
pipeline is specified as pure functions with the contrast gate wired in as the keystone hard constraint — **this is
the next build target** (`@eden/theme`).

---

## §7 — Open items & rulings still needed

1. **OD-1 confirming runtime spikes** (§5) — pending the TS/Svelte toolchain; go/no-go criteria defined.
2. **The 10 design rulings** the research surfaced (Appendix A, Part D) — each needs an explicit ruling before
   `@eden/theme` encodes it: APCA advisory-vs-gate; type/spacing coupled-vs-decoupled (recommend decoupled, shared
   16px origin); **default type ratio 1.20 vs 1.25** (recommend 1.20 UI); density-default-per-surface map (recommend
   compact for IDE/agent); breakpoint axis (semantic + device aliases); shadow model (parametric + M3 anchors); spring
   constants provenance; fluid-vs-fixed spacing (fixed default); M3 tone-table spec revision to pin; brand→motion-personality
   coupling in v1 or defer. → These belong in `open-decisions.md`.
3. **C21 reconciliation (D2):** the math re-derives the literal type sizes — confirm the founder accepts re-derived
   sizes (the 5 colors + 3 families remain). The brief itself calls the visual language "deliberately OPEN pending OD-1",
   which gives latitude, but the C21 intake "locked" the sizes — reconcile explicitly.
4. **Devcontainer UI toolchain additions** (§4.4) — a shared-config change; hold-and-confirm with the Go-backend agent.
5. **Stand up the TS pipeline** (`libs/typescript/_ctl/lib.sh`, `project-svelte`/`project-enforcement`, `.githooks` extension,
   `.ci/ctl.sh` non-Go `lib-gate`) and write the two ADRs (§4.4).
6. **Build Phase 0** (`@eden/theme` first — it unblocks every component).

---

## §8 — WIP, collision notes, pickup

**WIP / files touched:** **none in the repo.** The working tree is clean apart from **this one new doc**
(`docs/architecture/handoff-ui-libs.md`, **uncommitted**). The only other artifacts I wrote are two **memory**
files *outside* the repo (in the user's `~/.claude` project memory dir): `eden-ui-libs-rulings.md` + an index
pointer — purely my own recall, not repo state.

**Number-collision avoidance:** I claimed **no ADR/doc numbers**. You are on **ADR-0023 + doc-16** — avoided.
Suggested artifacts for you to number/place when you re-home this:
- an **ADR-0005 amendment** (design system → `libs/typescript/`);
- a new **"TS/Svelte library engineering pipeline"** ADR (the ADR-0020 analog, incl. the §4.3 taxonomy + the
  design-correctness dimension);
- a **research-note** for the design foundation (Appendix A) — class "research note", per doc-10;
- **close OD-1** in `open-decisions.md` with the §5 ruling (record the a11y-evidence-story obligation);
- **add the 10 Part-D forks** to `open-decisions.md` (§7.2).

**Pickup:** read Appendix A (the math) + Appendix B (the OD-1 ruling), then Phase 0 starts with the devcontainer
toolchain + `libs/typescript/_ctl/lib.sh` + `@eden/theme`. Integrate via the OpenAPI seam, not through Mateo.

---
---

# Appendix A — Design foundations (commissioned research note, full text)

*Web-sourced and adversarially fact-checked; the 4 load-bearing corrections are applied inline. This is the
empirical foundation for `@eden/theme`. To be re-homed as a canonical research-note.*

# Design foundations: human-feel principles and the generative proportion/color/contrast tables

**Status:** research-note (DRAFT for human review) · **Domain:** the empirical foundation for Eden's math-based theming engine · **Audience:** the team building the token/proportion generator and the Svelte 5 component library.

**Epistemic legend** (matches the Eden registry convention):
✅ robust, primary-sourced, math-verified · 🔶 sound practitioner-canon / single-study / strong convention with weak perceptual proof · ⚠️ contested or mythologized — flagged with what the evidence actually supports · 🧩 engineering decision left to / made by the engine (defensible, not "discovered").

> **Provenance & verification.** This note synthesizes seven domain reports (human-feel/HIG, typography, spacing/layout, color-science/OKLCH, contrast/accessibility, motion/elevation, density/adaptivity), each independently web-researched against primary sources, then adversarially fact-checked. Four load-bearing corrections from that verification pass are applied here and are the *corrected* values: (1) the WCAG linearization threshold is **0.04045** (not the stale 0.03928); (2) the APCA↔WCAG cross-walk is **Lc 45≈3:1, Lc 60≈4.5:1, Lc 75≈7:1** (an earlier draft was off by one tier); (3) the musical-interval ratio *table* is cited to type-scale.com / spec.fm, with Spencer Mortensen credited only for the geometric-progression *formula*; (4) Material's `emphasized` easing is a **two-segment spline**, not the single `cubic-bezier(0.2,0,0,1)` (that bezier is literally the `standard` curve), and must ship a CSS `linear()` fallback.

---

## 1. Executive summary

**The thesis.** A small brand *seed* — a primary hue (plus optional secondary/tertiary/neutral hues and fixed state hues), one or two font families, and a couple of scalar preferences (a type ratio, a base unit) — is sufficient to **generate a complete, proportional, accessible design-token system** by feeding it through research-derived tables and pure deterministic functions. The seed carries *taste*; the tables carry *perceptual floors and proportional structure*; the generator composes them. The accessibility **contrast gate is a hard constraint** that the pipeline must satisfy by construction, repairing on-brand colors that fail rather than shipping them.

**What is evidence vs. convention** — stated up front, because the engine's credibility depends on not dressing convention as science:

- **Genuinely evidence-backed (✅):** WCAG luminance/contrast math and thresholds (legally load-bearing, exact, no-rounding); touch-target minimums (Apple 44pt / Material 48dp / WCAG 24px AA / 44px AAA); the optimal reading **measure** of ~45–75 characters/line (~66 ideal); the perceptual-uniformity argument for OKLab/OKLCH; the perceptual-response-time limits (100ms / 1s / 10s); WCAG text-spacing and motion-accessibility floors.
- **Strong convention, weak/absent perceptual proof (🔶):** the 4px/8px base grid (real justification is *device-pixel-ratio integer rendering*, not aesthetics); geometric type & spacing scales (motivated by log-perception, not proven for UI); Material's duration ladder and easing curves (internally consistent, not psychophysical constants); the layered-shadow depth model.
- **Mythologized — flagged and demoted (⚠️):** the golden ratio φ=1.618 as a beauty law; "the 8pt grid is scientific"; "complementary colors are harmonious" as a prescriptive rule; the rule of thirds; "OKLCH equal ΔL ⇒ equal contrast"; Hick's-law as a blanket "fewer options = better."

The deliverable below is in three movements: **Part A** the qualitative human-feel invariants a component library must honor; **Part B** the concrete generative tables and formulas (typography, spacing, color, contrast, motion/elevation, density), each as *principles + the table/formula + how-to-encode*; **Part C** the unified DTCG token model and the seed→complete-token-set pipeline with the contrast gate wired in as a hard constraint. Part D records the open questions the team must rule on.

---

## 2. Part A — Human-feel principles (the qualitative invariants)

These are the perceptual/cognitive invariants the component library must honor regardless of brand. Each is encodable as a lint, a test, or a token constraint (the encodings are collected in Part C).

### A.1 The spine: content primacy, layered depth, cross-context consistency

Apple's HIG rests on three stable themes — **Clarity** (legible at every size, minimal adornment, hierarchy through negative space), **Deference** (the UI recedes so content leads; fluid, unobtrusive motion), and **Depth** (visual layers and realistic motion convey hierarchy). The 2025 "Liquid Glass" restatement (Hierarchy / Harmony / Consistency) re-expresses the same spine: chrome floats in a distinct functional layer *above* content so content stays primary. ✅ The continuity across a decade is the signal: **content primacy + layered depth + cross-context consistency are the stable invariants**, not any specific material. ([Apple HIG core themes](https://gist.github.com/eonist/f4ba31012815731284d867232f6c70e4); [WWDC25 "Meet Liquid Glass"](https://developer.apple.com/videos/play/wwdc2025/219/); [createwithswift](https://www.createwithswift.com/liquid-glass-redefining-design-through-hierarchy-harmony-and-consistency/))

**Division of labor for the engine:** Apple supplies the *philosophy/invariants*; Material supplies the *tokenized numbers* (durations, easing curves, elevation steps, tone→role tables) that are publicly specified and directly encodable. Eden borrows Apple's rules of feel and Material's numbers.

### A.2 "Intuitive" decomposes into named mechanisms

"Intuitive" is not a vibe; it is a set of research-named mechanisms the library must express:

- **Direct manipulation** — continuous representation of objects, physical/reversible actions, immediate visible feedback. ✅ ([Apple HIG](https://www.nadcab.com/blog/apple-human-interface-guidelines-explained))
- **Norman's six principles** — affordances, signifiers, constraints, mappings, feedback, conceptual model. A control is intuitive when its signifier reveals its affordance, it maps to its outcome, and feedback confirms every action. ✅ ([Norman, *Design of Everyday Things*](https://en.wikipedia.org/wiki/The_Design_of_Everyday_Things))
- **Recognition over recall** (Nielsen heuristic #6) — make options visible rather than forcing memorized input. ✅
- **Jakob's Law / consistency** (heuristic #4) — users expect your product to work like the others they already know; consistency lets them reuse existing mental models. ✅ ([Nielsen's 10 heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/))

### A.3 Aesthetics are a measurable trust & perceived-usability instrument (not cosmetic)

- **Aesthetic–usability effect:** Kurosu & Kashimura (Hitachi, 1995; 252 participants, 26 ATM-UI variants) found perceived ease-of-use correlated *more* with aesthetic appeal than with actual usability — establishing *apparent vs. inherent* usability. **Honest limit:** it is a *perception* gap; beauty does **not** improve task performance and cannot mask severe defects. ✅⚠️ ([NN/G](https://www.nngroup.com/articles/aesthetic-usability-effect/); [Kurosu & Kashimura 1995](https://www.semanticscholar.org/paper/Apparent-usability-vs.-inherent-usability:-analysis-Kurosu-Kashimura/3fdc532133d09dff92a1a555c1754c06e9cece7c))
- **50 ms to a first impression:** Lindgaard et al. (2006, *Behaviour & Information Technology* 25(2)) — visual-appeal ratings at 50 ms correlate highly with 500 ms ratings. ✅ ([Lindgaard 2006](https://www.tandfonline.com/doi/abs/10.1080/01449290500330448))
- **Looks dominate credibility:** Stanford Web Credibility (Fogg, n≈2,600+) — 46.1% of credibility comments referenced "design look," more than any other factor. ✅ ([Stanford](https://credibility.stanford.edu/guidelines/index.html))

**Engine implication:** a generated theme is, measurably, a trust and perceived-usability instrument — its proportional/contrast/rhythm correctness is the controllable input to the 50 ms judgment. This is *why* the generator must be rigorous, not why it may be merely pretty.

### A.4 Latency budgets & feedback tiers (perceptual constants)

The Nielsen response-time limits are technology-independent perceptual constants; Doherty sharpens the responsiveness target; INP gives the modern web operationalization. These are **invariant** — the brand axis cannot weaken them. ([Nielsen](https://www.nngroup.com/articles/response-times-3-important-limits/); [Doherty, via Laws of UX](https://lawsofux.com/doherty-threshold/))

| Tier | Threshold | Perceptual meaning | Required feedback |
|---|---|---|---|
| Instant / direct-manipulation | **≤ 100 ms** | Feels instantaneous; user feels they caused the result | Show the result; no spinner |
| Responsive (Doherty) | **≤ 400 ms** | Productivity/flow zone | Begin a visible state change (press/active) within this window |
| Modern web target | **≤ 200 ms INP** (p75) | Google "good" Interaction-to-Next-Paint | Paint a response within 200 ms |
| Uninterrupted thought | **≤ 1 s** | Delay noticed; flow of thought intact | Optional subtle busy cue |
| Attention ceiling | **≤ 10 s** | Upper limit to hold attention | **Percent-done progress + cancel** |
| Beyond | **> 10 s** | User task-switches | Progress bar mandatory; notify on completion |

**Perceived-performance levers** (when real latency can't drop): skeleton screens > spinner > blank for waits under ~10 s; switch to percent-done past 10 s. 🔶 ([NN/G skeletons](https://www.nngroup.com/articles/skeleton-screens/))

> ⚠️ **Don't conflate** "respond within 400 ms" (system responsiveness, Doherty) with "animate *for* 400 ms" (motion duration). They are different axes; see B.5.

### A.5 Fitts's Law & hit-target sizing

Fitts's Law (Shannon form, the HCI standard): `MT = a + b·log₂(D/W + 1)`, with `ID = log₂(D/W+1)` in bits and throughput `TP = ID_e/MT` using effective width `W_e = 4.133·SD_x`. The encodable consequence: larger and closer targets are always faster; **never emit an interactive target below the platform minimum.** ✅ ([Fitts's law](https://en.wikipedia.org/wiki/Fitts%27s_law); [MacKenzie CHI'92](https://www.yorku.ca/mack/CHI92.html)) Concrete minimums are in B.2 (Table B2-D) — they recur across the spacing, contrast, and density domains and are the single most-cited hard floor in this note.

### A.6 Hick's Law — and its critical caveat

Hick's Law: `T = a + b·log₂(n+1)`, with `b` commonly cited ≈ 0.155 s/doubling. ⚠️ **Treat `b` as illustrative, not a real-latency constant** (population/device-dependent). The deeper caveat: Hick's law assumes **equiprobable, undifferentiated** choices and a single decision. It does **not** hold for scanning ordered lists (linear, not log), familiar/learned items, or well-categorized menus. **The lever is *structure* (chunking, grouping, progressive disclosure), not raw option count.** A "fewer options = always better" reading is false. ⚠️ ([Hick's law](https://en.wikipedia.org/wiki/Hick's_law))

### A.7 Progressive disclosure & visibility of system status

- **Progressive disclosure:** show only the core path; defer advanced/rare options to a secondary layer. Lowers cognitive load and the *effective* Hick `n`. ✅ ([Nielsen, 2006](https://www.uxpin.com/studio/blog/what-is-progressive-disclosure/))
- **Visibility of system status:** every state change (loading, success, error, empty) has a defined visual; nothing happens silently. ✅ ([Nielsen heuristic #1](https://www.nngroup.com/articles/ten-usability-heuristics/))

### A.8 Motion-as-meaning (the qualitative rule; numbers in B.5)

Motion exists to **focus attention and maintain continuity** during state change — spatial/causal orientation — *not* decoration. Three sub-rules that the motion generator must honor: (1) **asymmetric easing reads as natural** (decelerate into rest); (2) **duration scales with travel/area, not a single constant**; (3) **enter ≠ exit** (exits are shorter — a departing element no longer deserves attention). And **reduce-motion is mandatory**: `prefers-reduced-motion` swaps positional/scale/parallax motion for cross-fades and is a first-class mode, not an afterthought. ✅ ([M3 motion](https://m3.material.io/styles/motion/overview/how-it-works); [M2 speed](https://m2.material.io/design/motion/speed.html); [WAI C39](https://www.w3.org/WAI/WCAG21/Techniques/css/C39))

### A.9 The human-feel invariant checklist (component-library contract)

Each is encodable as a lint/test/token constraint (encodings in Part C):

1. Every interactive element **≥ 44 px hit area** (transparent padding allowed); **never < 24 px**; sub-44 targets pass the WCAG 24px spacing-circle test.
2. Press/active feedback paints **within ≤ 100 ms**; never leave an action unacknowledged.
3. Operations 100 ms–1 s: no spinner; ≥1 s busy state; **≥10 s percent-done + cancel**; skeletons over spinners under 10 s.
4. Transitions preserve continuity (enter/exit from/to spatial origin); brief & precise (feedback 100–200 ms, transitions 250–400 ms).
5. **`prefers-reduced-motion` honored** — positional motion → cross-fade; parallax/autoplay removed; functional `transitionend`/`animationend` still fire.
6. Affordance = signifier: every state (default/hover/focus/active/disabled/loading/error/empty) present and distinct.
7. Recognition over recall; 8. Consistency / Jakob's Law; 9. Progressive disclosure; 10. Visibility of system status.
11. Aesthetic floor for the 50 ms judgment: theme passes contrast + rhythm + alignment.
12. Depth conveys hierarchy, not decoration (elevation maps to interaction priority).

---

## 3. Part B — The generative tables & formulas

Each subsection: **principles → the concrete table/formula → how to encode**. These are the numbers a generator function encodes directly.

### B.1 Typography & the type scale

**Principles.** A type scale is a **geometric (exponential) progression**, not arithmetic: equal *perceptual* steps require equal *multiplicative* steps (Weber–Fechner-style log perception — the one genuinely principled justification, independent of musical or golden mysticism). The **ratio controls hierarchy contrast vs. resolution**, not "beauty": larger ratio = fewer, more dramatic steps; smaller = finer granularity. **Line-height is a function of size AND measure** — it falls as size grows and rises as measure grows. There is a real **measure** optimum (~45–75 ch, ~66 ideal). **Tracking** is size- and weight-driven and crosses zero (positive for small, negative for display). ([Geometric-progression formula: Spencer Mortensen](https://spencermortensen.com/articles/typographic-scale/); [WCAG 1.4.12](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html))

**Table B1-A — canonical ratio table** (musical-interval names are *labels/mnemonics*; the values are standard ratios). *Citation: the ratio names/values are the type-scale.com / spec.fm canonical set; Mortensen is cited only for the `fᵢ = f₀·r^(i/n)` formula.* ([type-scale.com / spec.fm](https://spec.fm/specifics/type-scale))

| Interval | Ratio | Character / when |
|---|---|---|
| Minor second | **1.067** | Dense data UIs, tables — barely-there steps, max resolution |
| Major second | **1.125** | Compact app UI; subtle hierarchy |
| Minor third | **1.200** | **Default for general UI/web** — clear but not loud |
| Major third | **1.250** | Marketing-leaning UI; a touch more drama |
| Perfect fourth | **1.333** | Content/docs — strong heading/body contrast |
| Augmented fourth | **1.414** (√2) | ISO-216 paper ratio; editorial/print flavor |
| Perfect fifth | **1.500** | Landing pages, posters — big jumps, few steps |
| Golden | **1.618** (φ) | Hero/display-dominant; coarse for UI text — ⚠️ opt-in only, never the default (see D / B-myths) |

**Formula — the scale generator:** `size(i) = base · ratio^i`. Worked example (base 16px, ratio 1.250, `i ∈ [−2…+5]`, rounded at render, float kept internally): 10 / 13 / 16 / 20 / 25 / 31 / 39 / 49 px (xs…3xl).

**Formula B1-B — fluid type (clamp), exact constants.** Given min/max sizes `S₁,S₂` (px) and min/max viewports `V₁,V₂` (px):
- slope `m = (S₂−S₁)/(V₂−V₁)`; intercept (px) `b = S₁ − m·V₁`; express slope in vw as `100·m`.
- CSS (rem-normalized, REM=16): `clamp( S₁/16 rem , (b/16)rem + (100·m)vw , S₂/16 rem )`.
- **Verified worked example:** 36px→52px over 600→1400px ⇒ `clamp(2.25rem, 2vw + 1.5rem, 3.25rem)` (slope `100·16/800 = 2vw`, intercept `24px = 1.5rem`). ✅ ([Smashing, Modern Fluid Typography](https://www.smashingmagazine.com/2022/01/modern-fluid-typography-css-clamp/))
- **Accessibility constraint (must encode):** always keep a `rem` term in the preferred value, or zoom can't enlarge text → WCAG 1.4.4 fail. ✅

**Table B1-C — line-height & tracking lookup** (empirical anchor: Material 3 type scale; note line-height *ratio* falls monotonically with size, tracking crosses zero). ✅ ([M3 type-scale tokens](https://m3.material.io/styles/typography/type-scale-tokens))

| Role | Size px | Line-height px | LH ratio | Tracking px |
|---|---|---|---|---|
| Display L | 57 | 64 | **1.123** | −0.25 |
| Display S | 36 | 44 | 1.222 | 0 |
| Headline M | 28 | 36 | 1.286 | 0 |
| Title L | 22 | 28 | 1.273 | 0 |
| Body L | 16 | 24 | **1.500** | +0.5 |
| Body M | 14 | 20 | 1.429 | +0.25 |
| Label S | 11 | 16 | 1.455 | +0.5 |

**Encodable line-height function** (smooth, calibrated to M3): `lineHeight(sizePx, measureCh) = clamp(1.1, A − B·ln(sizePx) + C·(measureCh−50)/50, 1.7)` with `A≈2.6, B≈0.38, C≈0.10` → ≈1.50 @16px, ≈1.33 @28px, ≈1.15 @57px. **WCAG 1.4.12 hard floor: body line-height must survive a user override to ≥1.5×**, so body roles default at/above 1.5. ✅

**Tracking function:** `tracking_em(sizePx, weight) = clamp(−0.03, K·(16−sizePx)/16 + W·(weight−400)/400, +0.05)`, `K≈0.02`. WCAG 1.4.12 floor: user must be able to set letter-spacing 0.12em / word 0.16em without breakage — never hard-clip on tracking changes.

**Measure:** target **60–66 ch**, cap ≤75 ch (satisfies Bringhurst 45–75/~66, Dyson & Haselgrove ~55, WCAG AAA ≤80). Bias low — `ch` overshoots (the "0" glyph is wider than average). ✅ ([Bringhurst via webtypography](http://webtypography.net/2.1.2); [Dyson & Haselgrove 2001](https://www.sciencedirect.com/science/article/abs/pii/S1071581901904586))

> ⚠️ **Don't generate body sizes below ~12px** (legibility + iOS ≥16px input rule to avoid auto-zoom). Display floor 1.1 line-height.

**How to encode.** Emit one composite DTCG `typography` token per semantic role: `fontSize` (rem, with px float in `$extensions`), `lineHeight` (number, clamped ≥1.5 for body), `letterSpacing` (em), `fontFamily` (alias to brand families), `fontWeight`. Display/heading roles also carry a resolved `clamp(...)` fluid value with `{minVp,maxVp,slopeVw}` in `$extensions`. Free parameters: `ratio` (brand), `baseSizePx` (brand/density); WCAG floors are hard clamps overriding any generated value.

---

### B.2 Spacing, grid & layout

**Principles.** The base unit (4/8) is a **manufacturing convention, not a perceptual law**: its real justifications are (1) integer rendering across device-pixel-ratios (1×/1.5×/2×/3×) — odd values like 5px land on half-pixels and blur; (2) common viewport widths (320/360/768/1024/1440/1920) divide by 8. 🔶 Spacing ramps should be **hybrid (fine linear at the bottom, multiplicative widening at the top)**, not pure-linear (wastes decisions among large near-equal values) or pure-geometric (leaves holes). Vertical rhythm couples spacing to **line-height** (baseline unit = body line-height = e.g. 24px). Spacing should **share an origin with type (16px) but not its generating function** (type ratio produces fractional px; spacing must stay on the 4px grid). ✅🔶 ([8pt rationale/critique: breakdance](https://breakdance.com/the-8-point-grid-system-a-practical-guide/); [Curtis, Space in Design Systems](https://medium.com/eightshapes-llc/space-in-design-systems-188bcbae0d62); [Refactoring UI notes](https://mohitkhare.me/blog/notes-refactoring-ui/))

**Decision (🧩):** base unit = **4px**, with 8px as the preferred subset. This is the universal convergence (Material 4dp baseline + 8dp components, Tailwind 4px, Carbon 2/4/8, Atlassian 8px base + 2/4 quarter/half).

**Table B2-A — the Eden spacing ramp** (every value an integer multiple of 4, integer at 1×/1.5×/2×/3×; matches Refactoring UI 4,8,12,16,24,32,48,64,96,128,192,256,384,512 with finer low-end from Tailwind/Carbon):

| Token | px | rem | T-shirt | | Token | px | rem | T-shirt |
|---|---|---|---|---|---|---|---|---|
| space-0.5 | 2 | 0.125 | 3xs | | space-10 | 40 | 2.5 | — |
| space-1 | 4 | 0.25 | 2xs | | space-12 | 48 | 3.0 | 2xl |
| space-2 | 8 | 0.5 | xs | | space-16 | 64 | 4.0 | 3xl |
| space-3 | 12 | 0.75 | sm | | space-24 | 96 | 6.0 | 4xl |
| space-4 | 16 | 1.0 | md (base) | | space-32 | 128 | 8.0 | 5xl |
| space-5 | 20 | 1.25 | — | | space-48 | 192 | 12 | 6xl |
| space-6 | 24 | 1.5 | lg (baseline) | | space-64 | 256 | 16 | 7xl |
| space-8 | 32 | 2.0 | xl | | space-96 | 384 | 24 | 8xl |

**Table B2-B — breakpoints (semantic, Material window size classes — recommended canonical axis):** ([M3 layout](https://m3.material.io/foundations/layout/applying-layout))

| Class | Min width | Columns | Margin | Gutter | Panes |
|---|---|---|---|---|---|
| compact | 0 | 4 | 16 | 16 | 1 |
| medium | 600 | 8 | 24 | 24 | 1–2 |
| expanded | 840 | 12 | 24 | 24 | 2 |
| large | 1200 | 12 | 24+ | 24 | 2–3 |
| extra-large | 1600 | 12 | 24+ | 24 | 3 |

*(Device-width aliases — Tailwind 640/768/1024/1280/1536, Bootstrap 576/768/992/1200/1400 — mapped on top for developer familiarity. 🧩 Capability-based classes are more principled than device-chasing; the specific dp numbers are still device-histogram curve-fits — no breakpoint set is "correct.")*

**Formula B2-C — column/container math:** `content_width = W − 2M`; `column_width = (content_width − (N−1)·G)/N`; `span(k) = k·column_width + (k−1)·G`. Prose container: `max-width = 66ch` clamped to `[45ch, 75ch]`.

**Table B2-D — touch/click target minimums (the hard floors — recurs across A.5, B.4, B.6):**

| Context | Min size | Source |
|---|---|---|
| **WCAG 2.2 SC 2.5.8 (AA)** | **24×24 CSS px** (or 24px-circle non-intersection) | [W3C 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) |
| **WCAG SC 2.5.5 (AAA)** | **44×44 CSS px** | [W3C 2.5.5](https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html) |
| **Apple HIG** | **44×44 pt** | Apple HIG |
| **Material / Android** | **48×48 dp** (≈9mm), gap ≥8dp | [Android a11y](https://support.google.com/accessibility/android/answer/7101858) |

*Note (verifier): 44pt at 163ppi ≈ 6.86mm; the "≈9mm" figure is **48dp**, not 44pt — both correct, don't conflate.* **Engine rule:** default 44px; never < 24px; enforce the 24px spacing-circle test for sub-44 targets; visual box may be smaller than the hit area (extend with invisible padding).

**How to encode.** Spacing is **brand-invariant** (a key honesty point — color/font seeds carry no defensible spatial information). Generator inputs: `baseUnit=4, rootFontSize=16, bodyLineHeight=1.5 (→baseline 24), density`. Emit primitive `dimension` tokens from the fixed multiplier set; add semantic `inset/stack/inline` aliases; breakpoints/grid as a config map; `target.min=44px` (floor 24), `measure.prose=66ch`, `layout.baseline={space-6}`. **Default to fixed (non-fluid) spacing**; reserve fluid spacing (same clamp machinery as B1-B) for section-level gaps (`space-16`+).

---

### B.3 Color & OKLCH ramps

**Principles.** OKLab/OKLCH (Björn Ottosson, 2020) is perceptually uniform — **equal numeric steps ≈ equal perceived steps**, with **decorrelated axes** (changing L doesn't shift hue/chroma). This is precisely why it beats HSL for token generation. It fixed CIELAB's blue-purple hue-shift, but is **not perfect**: residual non-uniformity in high-chroma blues and near the gamut edge; L does not model the Helmholtz–Kohlrausch effect. ✅⚠️ ([Ottosson, OKLab](https://bottosson.github.io/posts/oklab/); [gamut clipping](https://bottosson.github.io/posts/gamutclipping/))

**Formula B3-A — sRGB↔OKLab (encode verbatim).** Linear sRGB → LMS (M1), cube-root, LMS'→OKLab (M2):
```
l = 0.4122214708·r + 0.5363325363·g + 0.0514459929·b
m = 0.2119034982·r + 0.6806995451·g + 0.1073969566·b
s = 0.0883024619·r + 0.2817188376·g + 0.6299787005·b
l_=cbrt(l); m_=cbrt(m); s_=cbrt(s)
L = 0.2104542553·l_ + 0.7936177850·m_ − 0.0040720468·s_
a = 1.9779984951·l_ − 2.4285922050·m_ + 0.4505937099·s_
b = 0.0259040371·l_ + 0.7827717662·m_ − 0.8086757660·s_
C = sqrt(a²+b²);  H = atan2(b,a)
```
sRGB gamma transfer (linear↔encoded boundary) — **use the corrected threshold 0.04045** (see B.4 / correction #1):
```
encoded→linear: c_lin = (c<=0.04045) ? c/12.92 : ((c+0.055)/1.055)^2.4
linear→encoded: c     = (c<=0.0031308)? 12.92·c : 1.055·c^(1/2.4) − 0.055
```
✅ ([Ottosson; W3C relative-luminance](https://www.w3.org/TR/WCAG21/relative-luminance.html))

**Table B3-B — the lightness ladder** (Tailwind v4 OKLCH L, empirically tuned, light-biased; the de-facto industry ramp):

| Step | 50 | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 950 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **L (0–1)** | 0.978 | 0.936 | 0.881 | 0.827 | 0.742 | 0.648 | 0.573 | 0.469 | 0.394 | 0.320 | 0.238 |

Parametric form: `L(i) = Lmax − (Lmax−Lmin)·t^gamma`, `t=i/(N−1)`, gamma≈0.85 (light-biased) … 1.0 (even). ([Evil Martians, OKLCH in Tailwind](https://evilmartians.com/chronicles/better-dynamic-themes-in-tailwind-with-oklch-color-magic))

**Formula B3-C — chroma curve (load-bearing).** Chroma must **peak in the mid-tones and fall toward both extremes** — gamut geometry, not aesthetics (sRGB narrows near white/black; forcing high chroma there produces muddy, clipped, off-hue tints). Reference array (peaks ~0.147 at step 400): `C = [0.011, 0.032, 0.061, 0.091, 0.140, 0.147, 0.130, 0.107, 0.090, 0.073, 0.054]`. Parametric: `C_target(i) = Cseed · envelope(L(i))` with `envelope(L) = 1 − (|L−Lpeak|/max(Lpeak,1−Lpeak))^p`, `p≈1.4–2.0`, `Lpeak≈0.55–0.65`, then gamut-clamped. **Default strategy = "consistent"** (curve-set C, no hue gaps) over "vivid/max-chroma" (drifts hue at the bright end).

**Algorithm B3-D — gamut mapping (mandatory, CSS Color 4):** binary-search chroma reduction with a clip-distance escape; thresholds **JND=2 (ΔE2000)**, `eps=0.0001`, L≥1→white, L≤0→black, `deltaEOK` for the comparison. Naive chroma reduction destroys yellows (P3 yellow C≈103 under CSS-mapping vs ≈25 under pure reduction). ✅ ([Color.js gamut-mapping](https://colorjs.io/docs/gamut-mapping))

**Hue:** hold **H constant** across the ramp (OKLCH's whole advantage); optional intentional drift (blue shadows / yellow highlights) is stylistic, not required.

**Table B3-E — seed→role mapping (Material 3 baseline, light/dark tones).** Roles are **tone assignments on a tonal palette**, so contrast is structural, not per-pair luck. The seed is **snapped to its nearest ramp step and pinned** (typically 500/600) so brand identity survives generation. ✅ ([M3 how-the-system-works](https://m3.material.io/styles/color/system/how-the-system-works))

| Role | Light tone | Dark tone | | Role | Light tone | Dark tone |
|---|---|---|---|---|---|---|
| Primary | 40 | 80 | | Surface | 98–99 | 6–10 |
| On-Primary | 100 | 20 | | On-Surface | 10 | 90 |
| Primary-Container | 90 | 30 | | Outline | 50 | 60 |
| On-Primary-Container | 30 | 90 | | Inverse-Surface | 20 | 90 |

**Contrast-guaranteeing tone math (M3, confirmed):** Tone **50 + 98 ⇒ ≈3:1** (AA large/UI); Tone **30 + 98 ⇒ ≈7:1** (AAA body); tones ≤49 reliably carry white text at ≥4.5:1; foreground flips lighter/darker at the **tone-60** boundary. **Eden rule:** define each role as `(palette, tone)`, run the real contrast metric (B.4) on every text/bg pair, and if it fails push the foreground tone toward 0/100 by the minimum that clears the threshold. ✅

**State & semantic roles.** State (hover/active/focus/disabled): derive by **L-nudges** — hover ΔL≈±0.04, active ±0.08, disabled drop chroma to ~38% + pull L toward surface; M3 state-layer overlays 8% hover / 12% focus-press. **Semantic hues (success/warning/error/info): keep near-static** (cultural signals — red=danger, green=success, amber=warning) — generate each as its own ramp from a fixed hue (error H≈25–30°, warning ≈70–85°, success ≈145°, info ≈brand or 230°); do **not** derive them by harmony from the brand. ✅

**Dark mode is NOT a lightness flip.** Naive `L→1−L` fails (halation on pure black, ~30% saturation loss for accents on dark, shadow-elevation stops working). The procedure: (a) **re-map roles to different tones** (Primary 40→80, Surface 99→~6–10, On-Surface 10→90); (b) **elevation = lighter surface tones, not shadows** (+0.02–0.04 L per layer, slight tint toward primary); (c) accent correction (raise L ~+0.05–0.08, reduce chroma ~10–15% — i.e. pick a lighter, less-saturated step of the same ramp); (d) **never pure black/white** (cap dark surface L≥~0.08, on-dark text L≤~0.93). The same generated ramps are reused — only the role→step mapping flips. ✅ ([M3](https://m3.material.io/styles/color/system/how-the-system-works); [M2 dark theme](https://m2.material.io/design/color/dark-theme.html))

**How to encode.** Two-tier color tokens (`$type:"color"`, `$value` as OKLCH): **Tier 1** primitive ramps (generated, brand-only, mode-agnostic); **Tier 2** semantic roles as aliases that resolve per mode (light `$value` + dark override in `$extensions.eden.dark`). Color lives on **mode × brand**; density is orthogonal. Hard invariants: every color in-gamut; every text pair meets its contrast contract (build fails otherwise); seed is a literal ramp step; dark = role→step remap, not inversion; state hues near-static; harmony offsets are suggestions validated by contrast.

---

### B.4 The contrast gate (the hard constraint)

**Principles.** This domain is unlike the rest: contrast is a **hard, numeric, legally-load-bearing gate** — a pair passes or fails, the threshold is exact, and **the spec forbids rounding**. Two regimes coexist and disagree: **WCAG 2.x is the mandatory legal gate** (luminance-only, polarity-blind); **APCA (WCAG 3 draft) is a better perceptual predictor but non-normative** — advisory only, adopting it *instead of* WCAG 2 carries legal risk. **Eden's gate = WCAG 2.x-mandatory, APCA-advisory.** The generator *inverts* the gate: given a background + brand hue, produce the nearest on-brand foreground that passes (a 1-D search along OKLCH lightness). ✅⚠️ ([w3c/wcag3 #29](https://github.com/w3c/wcag3/issues/29); [Roselli, Apr 2026](https://adrianroselli.com/2026/04/wcag3-contrast-as-of-april-2026.html))

**Formula B4-A — WCAG 2.x relative luminance & contrast (exact constants).**
```
Csrgb = C8/255
Clin  = (Csrgb<=0.04045) ? Csrgb/12.92 : ((Csrgb+0.055)/1.055)^2.4   # threshold 0.04045 ✅ (corrected)
L     = 0.2126·Rlin + 0.7152·Glin + 0.0722·Blin
ratio = (L1+0.05)/(L2+0.05)    # L1=lighter; range 1..21; compare UNROUNDED, ratio >= threshold
```
> ⚠️ **Correction #1 applied:** the linearization threshold is **0.04045** (W3C May-2021 errata), **not** the stale 0.03928 some libraries still ship. The two bracket the same single 8-bit channel value (~10.0 vs ~10.3 / 255) so **no pass/fail ever flips** — but hard-code **0.04045** and document it. **No-rounding is normative:** `4.499:1` does NOT meet `4.5:1`. ✅ ([W3C relative-luminance / #308](https://www.w3.org/TR/WCAG21/relative-luminance.html))

**Table B4-B — WCAG threshold table:**

| Content class | Level | Required ratio |
|---|---|---|
| Normal text (<24px reg / <18.66px bold) | AA | **≥ 4.5:1** |
| Large text (≥24px reg or ≥18.66px bold) | AA | **≥ 3.0:1** |
| Normal text | AAA | **≥ 7.0:1** |
| Large text | AAA | **≥ 4.5:1** |
| UI component / focus indicator / graphic | AA | **≥ 3.0:1** |

Large text = ≥18pt reg or ≥14pt bold (≈24px / ≈18.66px at 96dpi). **Exemptions (exempt, don't fail):** logo/brand-name text, disabled/inactive components, pure decoration, invisible text, text within a meaningful picture, UA-default controls. ✅ ([Understanding 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html))

**Formula B4-C — APCA (SA98G, advisory).** Constants confirmed verbatim: `mainTRC 2.4`, coeffs `0.2126729/0.7151522/0.0721750`, `blkThrs 0.022`, `blkClmp 1.414`, `normBG 0.56 / normTXT 0.57 / revTXT 0.62 / revBG 0.65`, `scale 1.14`, `loClip 0.1`, `loOffset 0.027`, `deltaYmin 0.0005`. ✅
```
Ys = 0.2126729·(R/255)^2.4 + 0.7151522·(G/255)^2.4 + 0.0721750·(B/255)^2.4   # txt and bg
if Y < 0.022:  Y = Y + (0.022−Y)^1.414                 # soft black-clamp
if |Ybg−Ytxt| < 0.0005:  return Lc=0
if Ybg > Ytxt:   SAPC = (Ybg^0.56 − Ytxt^0.57)·1.14;  Lc = (SAPC<0.1)? 0 : SAPC−0.027   # dark-on-light (+)
else:            SAPC = (Ybg^0.65 − Ytxt^0.62)·1.14;  Lc = (SAPC>−0.1)? 0 : SAPC+0.027  # light-on-dark (−)
Lc = Lc·100        # signed, ~−108..+106; use |Lc| against the table
```
([apca-w3 source](https://github.com/Myndex/apca-w3/blob/master/src/apca-w3.js); [APCA in a Nutshell](https://git.apcacontrast.com/documentation/APCA_in_a_Nutshell.html))

**Table B4-D — APCA |Lc| → use:** 90 preferred body · 75 minimum body (≈16px/400) · 60 large/non-body · 45 large-bold/headlines · 30 absolute min any text · 15 non-text floor.

> ⚠️ **Correction #2 applied — the APCA↔WCAG cross-walk.** The corrected approximate mapping (narrow light-bg range only, **never a real conversion**) is:
> **Lc 45 ≈ 3:1 · Lc 60 ≈ 4.5:1 · Lc 75 ≈ 7:1.**
> An earlier draft had this off by one tier (60/75/90) and was self-inconsistent with its own Lc-75-as-minimum-body row. APCA is polarity-aware: WCAG 2 systematically **under-protects dark mode** (a pair that "passes" 4.5:1 can read worse than its light-mode mirror), so compute APCA as an advisory check especially on dark surfaces. ✅ ([Myndex SAPC-APCA Discussion #42](https://github.com/Myndex/SAPC-APCA/discussions/42))

**Geometric gates (same accessibility layer, not contrast):** SC 2.5.8 ≥24px AA, SC 2.5.5 ≥44px AAA (Table B2-D).

**Algorithm B4-E — the inverse gate (nearest on-brand passing foreground).** Runs in OKLCH (hue/chroma stay on-brand; only L moves), eval converts to sRGB8 for the WCAG math:
1. Trivial accept if `wcag_ratio(seed_fg, bg) ≥ target`.
2. Pick direction: bg light → darken fg; bg dark → lighten fg.
3. **Bisect OKLCH.L** (hue/chroma fixed) to the *smallest* |ΔL| that hits the unrounded target — exact because contrast is monotone in luminance and L is monotone in luminance at fixed hue/chroma (~20 iters → 1e-6). Prefer the smallest passing shift (maximally on-brand); optional `safety_margin` `+0.05` for render-time AA.
4. **Chroma fallback** if even L=0/1 can't reach target: reduce OKLCH.C stepwise and re-bisect; last resort snap to nearest ink/paper token.
5. Advisory APCA cross-check (non-blocking warn, esp. dark mode).

**Return contract:** `{pass, achieved_ratio, target_ratio, suggested_fg, deltaL, apca_lc, apca_warn, action}`. **Never silently mutate a brand seed** — emit the suggestion + delta for the wizard.

**How to encode.** The gate is a **build-time validator + a generator pass, not a token**. For every surface token it emits the paired `on-*` foreground via the inverse gate, guaranteed to pass at the configured level, with `$extensions.eden.contrast = {ratio, target, level, apcaLc}` for auditability. Axes: **mode** flips search direction (and is where APCA-advisory matters most); **high-contrast** raises level AA→AAA; **density** never relaxes a ratio (only changes which role — body vs large — a token resolves to, and clamps interactive sizes to 24/44px). **CI gate:** every emitted `on-*`/state/focus token re-runs `passes()` with no rounding; a sub-threshold pair is a **build failure**, APCA warnings non-blocking.

---

### B.5 Motion & elevation

**Principles.** Motion serves cognition (focus attention, maintain continuity) — the only defensible reason to ship it. Asymmetric easing reads natural; symmetric reads mechanical. Duration scales with travel/area, not a constant. **Enter ≠ exit** (exits shorter). Two models, two jobs: **duration+easing** (deterministic, fixed-end — entrances/exits, fades, color/elevation) vs **spring** (velocity-preserving, interruptible — gesture-driven motion). Depth is a *light* simulation (sharp near umbra + soft far penumbra) requiring multiple stacked shadows. ✅🔶 ([M3 motion](https://m3.material.io/styles/motion/overview/how-it-works); [Comeau, Designing Shadows](https://www.joshwcomeau.com/css/designing-shadows/))

**Table B5-A — duration ladder (Material 3, verified): 50ms steps to 600, then 100ms to 1000.**

| short.1–4 | 50 / 100 / 150 / 200 | small UI feedback, exits |
|---|---|
| medium.1–4 | 250 / 300 / 350 / 400 | component/container transitions |
| long.1–4 | 450 / 500 / 550 / 600 | full-screen / large |
| extra-long.1–4 | 700 / 800 / 900 / 1000 | expressive/hero only |

**Encoder rules (🧩, grounded):** desktop/`pointer:fine` subtracts one ladder step (floor short.1); **exit = enter − one step**; distance multiplier `duration = base × clamp((travel/ref)^0.5, 0.7, 1.6)` snapped to a rung; hard guards never <50ms / never >1000ms for functional UI.

**Table B5-B — easing (M3, verified verbatim):**

| Token | cubic-bezier | Use |
|---|---|---|
| linear | `0,0,1,1` | cross-fades, color-only |
| standard | `0.2,0,0,1` | **default**, on-screen moves |
| standard-decelerate | `0,0,0,1` | **enter** |
| standard-accelerate | `0.3,0,1,1` | **exit** |
| emphasized-decelerate | `0.05,0.7,0.1,1` | emphasized enter |
| emphasized-accelerate | `0.3,0,0.8,0.15` | emphasized exit |

> ⚠️ **Correction #4 applied — `emphasized` is NOT a single cubic-bezier.** It is a two-segment spline a single bezier cannot represent:
> `M 0,0 C 0.05,0 0.133333,0.06 0.166666,0.4 C 0.208333,0.82 0.25,1 1,1`
> The value `cubic-bezier(0.2,0,0,1)` is literally the **`standard`** curve and is only an *approximation* of emphasized. **Eden must emit a CSS `linear()` fallback** (sample the spline) for `emphasized`, and true beziers for the rest. ✅ ([MDC-Android Motion.md](https://github.com/material-components/material-components-android/blob/master/docs/theming/Motion.md))

**Pairing rule (enforce in presets):** decelerate↔enter, accelerate↔exit, standard↔on-screen moves.

**Formula B5-C — spring math (iOS-17 two-parameter, corrected damping).** Two perceptual knobs: `duration` (settling time) and `bounce ∈ [−1,1]`.
```
mass=1;  stiffness=(2π/duration)²
bounce ≥ 0:  damping = 4π·(1−bounce)/duration
bounce < 0:  damping = 4π/(duration·(1+bounce))
ζ = damping/(2·√(stiffness·mass));   for bounce ≥ 0:  ζ = 1 − bounce   # bounce is just 1−ζ
```
bounce 0 = critically damped (no overshoot); 0.3 ≈ ζ 0.7 (visible overshoot). ✅ ([WWDC23](https://developer.apple.com/videos/play/wwdc2023/10158/); corrected damping per [kvin.me](https://www.kvin.me/posts/effortless-ui-spring-animations))

**Table B5-D — spring presets:** smooth (d 0.5, bounce 0, ζ 1.0) · snappy (0.5, 0.15, ~0.85) · bouncy (0.5, 0.30, ~0.70) · interactive (response 0.15, ζ 0.86) · legacy default (response **0.55**, dampingFraction **0.825**). **Legacy↔new bridge (verified by re-derivation):** since `dampingFraction = ζ` and `bounce = 1−ζ`, legacy `(0.55, 0.825)` ≈ new `(duration 0.55, bounce 0.175)`. ✅ ⚠️ The `.snappy`/`.bouncy` bounce constants are practitioner-measured, not first-party documented — tag accordingly.

**Reduced-motion (non-negotiable, reduce ≠ remove):** gate on `prefers-reduced-motion: reduce`; collapse **transform/position/scale/parallax** to ~0.001ms, **keep opacity/color cross-fades** (functional so `transitionend`/`animationend` still fire). **Hard WCAG invariants brand may NOT override:** 2.3.1 no flash >3Hz; 2.2.2 auto-motion >5s must be pausable; 2.3.3 interaction motion disable-able. ✅ ([WAI C39](https://www.w3.org/WAI/WCAG21/Techniques/css/C39))

**Table B5-E — elevation → shadow.** Material 3-component opacities: **umbra 0.20, penumbra 0.14, ambient 0.12** (verified). The recommended **parametric/layered generator** (Comeau, 🔶): vertical offset = 2× horizontal; **blur ≈ 2× y-offset**; higher elevation → larger offset/blur, lower per-layer opacity; **tint don't blacken** (shadow = bg hue, lower L, *raised* saturation); stack ~3–5 layers.
```
base_offset(e)=round(a·e^p)  # a≈0.5, p≈1.3
y_i = base_offset·(2^i)/(2^k);  x_i = y_i/2;  blur_i = 2·y_i
alpha_i = a0·(1−i/(k+1))      # a0≈0.10–0.13 light / 0.18–0.22 dark
```
**Dark-mode rule:** shadows nearly invisible on dark — carry depth by **surface lightening** (white overlay rising with elevation: 1dp≈5% … 24dp≈16%) *plus* raised shadow opacity. ✅ ([MDC elevation](https://github.com/material-components/material-components-web/blob/master/packages/mdc-elevation); [M2 dark theme](https://m2.material.io/design/color/dark-theme.html))

**Table B5-F — z-index (ordinal, gapped 100):** base 0 · raised 1–10 · dropdown 1000 · sticky 1100 · drawer 1200 · modal 1300 · snackbar 1400 · tooltip 1500 · max 2147483647. Z-index (stacking *order*) and elevation (shadow *intensity*) are distinct axes a component preset maps together (a modal is `z.modal` + `elevation.24`). ([MUI z-index](https://mui.com/material-ui/customization/z-index/))

**How to encode.** Token types: `duration` (`{value,unit}`), `cubicBezier` (`[x1,y1,x2,y2]`), `shadow` (composite, multi-layer array), `transition` composite; spring/elevation/z-index under `$extensions.eden.*`. Axes: **reduced-motion is a *mode*** (swaps the whole motion slice → durations ~0, transforms off, fades kept, emitted as a real `@media` block); **density** scales duration ±one ladder step (easing/z-index density-invariant); **brand** feeds spring `personality ∈ {calm, default, lively} → bounce {0, 0.15, 0.30}` + duration multiplier `{0.9, 1.0, 1.1}` and shadow tint — but **never** touches the WCAG motion invariants or easing geometry. Svelte mapping: easing → `svelte/easing`; springs → `svelte/motion Spring` (re-normalize — Svelte uses normalized stiffness/damping ∈ (0,1], not raw N/m).

---

### B.6 Density & adaptivity

**Principles.** Density is **one continuous axis applied as a scalar transform over a fixed base scale** — not a forked "simple mode." Every mature system (Material/Flutter, Carbon, Ant, Apple) treats it as a transform of an invariant geometric base where **spacing and component heights shrink/grow** but **touch targets, color/contrast, font *size*, icon *size*, and information architecture do NOT**. The transform is **piecewise-linear in fixed pixel increments (4px/step)**, not a free multiplier on everything. Flutter's `VisualDensity` is explicit: density "affects only the spacing between and within components… does not affect text sizes, icon sizes." ✅ ([Flutter VisualDensity](https://api.flutter.dev/flutter/material/VisualDensity-class.html); [Una Kravets, Material Density on the Web](https://medium.com/google-design/using-material-density-on-the-web-59d85f1918f0))

> ⚠️ **The naive trap:** a single global multiplier on *everything* (type + space + radius + targets) **breaks accessibility** — it shrinks targets below floors and fonts below legibility. Every mature system excludes type, icons, and targets from the density transform. Do not do the naive thing.

**Table B6-A — invariants density may never violate (clamps applied LAST):**

| # | Invariant | Value | Source |
|---|---|---|---|
| I1 | Min target (AA) | **24×24 px** | WCAG 2.5.8 |
| I2 | Enhanced/native targets | **44** (AAA/Apple) / **48dp** (Material) | WCAG 2.5.5; "all targets ≥48px no matter the density" |
| I3 | Min line-height (body) | **≥ 1.5× font** | WCAG 1.4.12 |
| I4 | Min paragraph spacing | **≥ 2× font** | WCAG 1.4.12 |
| I5 | Min letter/word spacing | **≥ 0.12× / 0.16×** | WCAG 1.4.12 |
| I6 | Color/contrast | **never changed by density** | owned by mode×brand |
| I7 | Font size & icon size | **never scaled by density** | Flutter VisualDensity |

**Critical clamp (I1+I2):** density may shrink the *visual box* below the floor only if the *hit area* is preserved by external padding — `hitTarget = max(visualHeight, FLOOR)`, visual and target are **separate tokens**, only the visual one scales.

**Formula B6-B — the density scalar (Material/Flutter reference):** `STEP=4px`; `Δpx(d)=4·d`; `componentHeight(d)=base+4·d`; named Flutter presets standard 0 / comfortable −1 / compact −2.

**Table B6-C — Eden named tiers (discrete, backed by the continuous scalar — Carbon/Ant curation + Material math):**

| Mode | densityStep d | Default surface |
|---|---|---|
| spacious | +1 | marketing, onboarding, empty states |
| comfortable | 0 | general app default, touch contexts |
| compact | −2 | working tool, tables, forms (**Eden default for IDE/agent surfaces**) |
| condensed | −3 | data grids, log views, power panels |

**Generator (per-token transform):** geometry scaled — `componentHeight = clampToTarget(snap4(base+4d))`, `inset = snap4(max(base+4d, 4))`, `stack = snap4(base+4d)`, `radius = clamp(base + ~1·d, RADIUS_MIN, base)`; **leading scaled with floor** — `lineHeight = max(base+~1·d, 1.5·fontSize)`; **invariants** — `fontSize=base`, `iconSize=base`, `hitTarget=max(visualH, FLOOR[ctx])`, color untouched. `snap4(x)=round(x/4)·4`; `FLOOR = {web/pointer:24, touch:44, android:48}`.

**Worked example (base d=0: row 40, inset-Y 12, gap 16, LH 20, font 14, radius 8, target 44):** at condensed (−3) → row 28, inset-Y 4 (floor), gap 4, **LH clamps at 21 (=1.5×14)**, font **14** (invariant), **hitTarget 44** (decoupled), radius 5. Note WCAG 1.4.12 *stops* over-tightening leading even at the densest tier. ✅

> ⚠️ Note: density tunes **leading, not font size** (Carbon's `body-compact` keeps 14/16px font, tightens line-height) — the cleanest evidence for I7.

**Size-class ≠ density (keep orthogonal):** Apple `UIUserInterfaceSizeClass` / Material window classes describe *available space* and drive *layout/pane structure*, not control density. Both axes may be active at once; a breakpoint may *select a default density* per viewport but is not the density dial.

**How to encode.** Three-layer graph: primitive geometry scale (brand/mode-agnostic) → semantic geometry tokens → **density transform as a generator**, not stored variants. Per-token policy in `$extensions.eden.density.scale ∈ {linear (geometry), leading (LH with floor), none (invariants)}`; a token without an explicit scale defaults to `none` (fail-safe). Output: static (`[data-density="compact"]{…}` with font/target/color emitted *identically* across scopes, proving invariance) or runtime (`--density-d` + `calc()`, with target/font as plain non-`calc` vars so they're provably immune). **Precedence: brand → mode → density → breakpoint default → CLAMP(floors)** — invariants applied last; density can never win against a floor. Validation: assert `target≥24`, `lineHeight≥1.5·font`, `fontSize==base`, `iconSize==base`, contrast unchanged, for every (brand×mode×density×breakpoint) combo; reject a tier that can't satisfy them at generation time.

---

## 4. Part C — The unified token model

### C.1 DTCG token types needed

The generated system spans these DTCG `$type`s (the last few are draft/extension modules):

| `$type` | Carries | Generated from |
|---|---|---|
| `color` | OKLCH ramps + semantic roles | seed hues → B.3 ramp algorithm, B.4 gate |
| `dimension` | spacing, sizes, radii, measure, target | B.2 ramp, B.1 sizes, B.6 density transform |
| `number` | line-height, type ratio, z-index, opacity | B.1, B.6 |
| `typography` (composite) | role = {family, size, weight, lineHeight, letterSpacing} | B.1 |
| `shadow` (composite, multi-layer) | elevation levels | B.5 parametric shadow |
| `duration` | motion durations | B.5 ladder |
| `cubicBezier` | easing curves (+ `linear()` fallback for emphasized in `$extensions`) | B.5 |
| `transition` (composite) | {duration, timingFunction, delay} | B.5 |
| `$extensions.eden.*` | spring, z-index, elevation overlay, contrast audit, density policy | B.3–B.6 |

### C.2 The axes — `mode × density × brand` (and the orthogonal `breakpoint`)

| Axis | Values | What it owns | What it must NOT touch |
|---|---|---|---|
| **brand** | seed: primary hue (+secondary/tertiary/neutral, fixed state hues), font families, `type ratio`, `spring personality` | color ramps, type families/ratio, spring bounce, shadow tint, base radius | motion/latency/target floors, easing geometry, spacing ramp, WCAG invariants |
| **mode** | light / dark / high-contrast / **reduced-motion** | color role→step remap + elevation map (dark); contrast level (HC raises AA→AAA); motion slice swap (reduced) | spacing, type *size*, density |
| **density** | spacious / comfortable / compact / condensed | geometry (heights, padding, gaps) + leading; one duration-ladder step | font/icon size, hit targets, color/contrast, IA |
| **breakpoint** *(orthogonal)* | compact / medium / expanded / large / extra-large | layout / pane count; may *select* a default density | control sizes, color |

**Orthogonality is the discipline:** color lives on `mode × brand`; geometry on `density (× breakpoint for layout)`; motion on `mode (reduced) × density (duration) × brand (spring/tint)`. Spacing is **brand-invariant** (stated explicitly to forbid pseudo-scientific brand→spacing coupling). A token resolves as `resolve(token, {brand, mode, density, breakpoint})`.

### C.3 The generator pipeline (seed → complete token set)

```
generateTheme(seed, {mode, density, breakpoint}):

  # 1. COLOR (brand × mode)                                    [B.3, B.4]
  for family in [primary, secondary?, tertiary?, neutral, error, warning, success, info]:
      ramp = for step,L in LADDER:
                 C = Cseed·envelope(L);  (L,C,H) = gamutMap(L, C, familyHue)   # CSS Color4, JND=2
      ramp[nearestStep(seed.L)] = snapToSeed(seed)            # pin identity
  roles = assignRoles(ramps)            # M3 tone→role table, light + dark
  for (fg,bg) in textPairs(roles):                            # HARD CONSTRAINT
      if wcag_ratio(fg,bg) < target(role,level):              # unrounded, threshold 0.04045
          roles[fg] = bisectL_until_pass(fg, bg, target)      # nearest on-brand passing
          warn if |apca(fg,bg)| < apcaTarget                  # advisory
      attach $extensions.eden.contrast = {ratio,target,level,apcaLc}

  # 2. TYPOGRAPHY (brand × density)                            [B.1]
  for i: size = base·ratio^i
         lh   = max(lineHeight(size, measure), 1.5·size if body)   # WCAG 1.4.12 clamp
         trk  = tracking_em(size, weight)
  display/heading roles → clamp() fluid value (keep a rem term — WCAG 1.4.4)

  # 3. SPACING + GRID (brand-INVARIANT, × density for components)  [B.2, B.6]
  space = [4·m for m in FIXED_MULTIPLIERS]                    # integer-px on 4px grid
  componentGeometry = densify(base, d) clamped by floors      # I1..I7 applied LAST
  breakpoints/grid = config map (Material window classes)

  # 4. MOTION + ELEVATION (mode-reduced × density-duration × brand-spring)  [B.5]
  durations = LADDER shifted by density step, reduced-mode→~0 for transforms
  easing    = M3 bezier set verbatim; emphasized→linear() fallback
  springs   = from seed.personality → bounce {0,0.15,0.30}; stiffness=(2π/d)², damping=4π(1−bounce)/d
  shadows   = layered parametric per elevation; dark→ + white surface overlay
  zIndex    = static ordinal scale

  # 5. INVARIANTS (un-overridable, asserted)
  assert every text pair passes its contrast contract (else BUILD FAILS)
  assert every target ≥ 24px (44/48 touch); lineHeight ≥ 1.5·font; fontSize/iconSize == base
  assert reduced-motion @media emitted; no flash >3Hz; auto-motion >5s pausable
  return emitDTCG(...)   # light $value + dark $extensions; CSS custom props + Svelte bindings
```

**The contrast gate as a hard constraint** is the keystone: it is the only place where a *brand* input can be *overridden* by the generator. Color tokens are not "done" until every declared text/UI pair clears WCAG (unrounded), and the artifact carries the proof (`eden.contrast`) so "the theme is accessible" is a *checked property of the build*, not a claim. APCA is computed and stored as an advisory signal (blocking only if the team opts into an APCA gate — see D).

### C.4 Build outputs

- **CSS custom properties:** `--color-*`, `--space-*`, `--size-*`, `--font-*` (composite expanded), `--duration-*`, `--ease-*` (cubic-bezier + linear() for emphasized), `--shadow-elevation-*` (multi-layer), `--z-*`; plus `[data-theme=dark]`, `[data-density=*]`, and the `@media (prefers-reduced-motion: reduce)` override block.
- **Svelte 5 bindings:** typography/color as CSS vars; easing → `svelte/easing`; springs → `svelte/motion Spring` (re-normalized stiffness/damping).
- **Audit sidecar:** the `eden.contrast` extension on every `on-*` pair → a machine-checkable accessibility report.

---

## 5. Part D — Open questions / contested points the team must rule on

These are unruled forks (per the Eden convention, they belong in `open-decisions.md`, not buried in prose). Each needs an explicit ruling before the engine encodes it.

1. **APCA: advisory or gate?** Consensus across reports: **WCAG 2.x is the mandatory legal gate; APCA is advisory** (non-normative, removed-to-placeholder in WCAG 3, no finalization expected before ~2030; adopting it *as* the gate carries legal risk). **Ruling needed:** do we (a) store APCA as a non-blocking warning (recommended default), or (b) offer an opt-in "APCA-strict" tenant mode that *also* gates on |Lc|≥75 body / ≥60 large? Note the corrected cross-walk (Lc 45/60/75 ≈ 3/4.5/7) is *only* a rough light-bg heuristic, never a conversion.

2. **Coupled vs decoupled type/spacing scales.** Utopia couples spacing to the type ratio; Material/Carbon/Refactoring-UI decouple (type = geometric ratio, spacing = 4px-quantized hybrid). The note recommends **shared origin (16px), separate generating functions** (🧩). **Ruling needed:** confirm decoupled, or adopt Utopia-style coupling for fluid surfaces.

3. **Default type ratio.** 1.20 (minor third) vs 1.25 (major third) — both defensible; the feel report defaulted 1.25, the typography report 1.20. **Ruling needed:** pick the canonical default (recommend **1.20** for general UI, 1.25 for marketing surfaces) and confirm φ=1.618 is **opt-in only**, never privileged (the golden-ratio-as-beauty claim is ⚠️ myth — Naini, Godkewitsch 1974).

4. **Density default per surface.** The density report proposes **`compact` as the default for IDE/agent working surfaces**, `comfortable`/`spacious` for human-facing/marketing. **Ruling needed:** confirm the per-surface default map (this is the "earned density" call — 🔶).

5. **Breakpoint axis.** Semantic Material window classes (600/840/1200/1600) as canonical vs device-width (Tailwind/Bootstrap) as canonical. Recommendation: **semantic canonical + device-width aliases** (🧩). **Ruling needed:** confirm.

6. **Shadow model.** Material's literal 3-layer table vs the Comeau/Ahlin parametric layered generator (more formula-amenable, more convincing, but practitioner-canon 🔶). Recommendation: **parametric generator** with Material opacities (0.20/0.14/0.12) as anchors. **Ruling needed:** confirm.

7. **Spring constants provenance.** `.snappy` (bounce 0.15) and `.bouncy` (0.30) are **practitioner-measured, not first-party Apple-documented** (⚠️). **Ruling needed:** ship them tagged as such, or pin to a first-party-documented set only.

8. **Fluid vs fixed spacing.** Recommendation: **fixed by default**, fluid reserved for section-level gaps (`space-16`+). **Ruling needed:** confirm, or enable a fluid-spacing mode axis.

9. **Tone-table spec drift.** M3's `On-Primary-Container` light tone moved 10→30 in the 2025 spec. **Ruling needed:** pin which M3 spec revision the tone→role table tracks (the engine should cite a frozen revision, not "latest").

10. **Brand → motion personality coupling.** The motion report lets the brand seed pick a spring `personality` (calm/default/lively) and shadow tint. This is the one place brand touches motion. **Ruling needed:** is brand-driven motion personality in scope for v1, or do we ship a single neutral motion personality and defer this?

---

### Consolidated primary-source registry

**Accessibility / W3C (✅ load-bearing):** [WCAG relative-luminance / 0.04045 errata](https://www.w3.org/TR/WCAG21/relative-luminance.html) · [1.4.3 Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [1.4.6 Enhanced](https://www.w3.org/WAI/WCAG22/Understanding/contrast-enhanced.html) · [1.4.11 Non-text](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) · [1.4.12 Text Spacing](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html) · [2.5.8 Target Min](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) · [2.5.5 Target Enhanced](https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html) · [C39 reduced-motion](https://www.w3.org/WAI/WCAG21/Techniques/css/C39)
**Apple:** [HIG core themes](https://gist.github.com/eonist/f4ba31012815731284d867232f6c70e4) · [WWDC25 Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/) · [WWDC23 Animate with springs](https://developer.apple.com/videos/play/wwdc2023/10158/) · [UIUserInterfaceSizeClass](https://developer.apple.com/documentation/uikit/uiuserinterfacesizeclass)
**Material:** [M3 color system](https://m3.material.io/styles/color/system/how-the-system-works) · [M3 type-scale tokens](https://m3.material.io/styles/typography/type-scale-tokens) · [M3 motion tokens](https://m3.material.io/styles/motion/easing-and-duration/tokens-specs) · [MDC-Android Motion.md](https://github.com/material-components/material-components-android/blob/master/docs/theming/Motion.md) · [M3 layout/breakpoints](https://m3.material.io/foundations/layout/applying-layout) · [Flutter VisualDensity](https://api.flutter.dev/flutter/material/VisualDensity-class.html) · [M2 dark theme](https://m2.material.io/design/color/dark-theme.html) · [Android a11y 48dp](https://support.google.com/accessibility/android/answer/7101858)
**Color science:** [Ottosson OKLab](https://bottosson.github.io/posts/oklab/) · [gamut clipping](https://bottosson.github.io/posts/gamutclipping/) · [Color.js gamut-mapping](https://colorjs.io/docs/gamut-mapping) · [Evil Martians OKLCH](https://evilmartians.com/chronicles/better-dynamic-themes-in-tailwind-with-oklch-color-magic)
**APCA:** [apca-w3 source](https://github.com/Myndex/apca-w3/blob/master/src/apca-w3.js) · [APCA in a Nutshell](https://git.apcacontrast.com/documentation/APCA_in_a_Nutshell.html) · [SAPC-APCA Discussion #42 (cross-walk)](https://github.com/Myndex/SAPC-APCA/discussions/42) · [Roselli, WCAG3 contrast Apr 2026](https://adrianroselli.com/2026/04/wcag3-contrast-as-of-april-2026.html)
**HCI research:** [Lindgaard 2006 (50ms)](https://www.tandfonline.com/doi/abs/10.1080/01449290500330448) · [Kurosu & Kashimura 1995](https://www.semanticscholar.org/paper/Apparent-usability-vs.-inherent-usability:-analysis-Kurosu-Kashimura/3fdc532133d09dff92a1a555c1754c06e9cece7c) · [Nielsen response limits](https://www.nngroup.com/articles/response-times-3-important-limits/) · [10 heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) · [Fitts's law](https://en.wikipedia.org/wiki/Fitts%27s_law) · [Hick's law](https://en.wikipedia.org/wiki/Hick's_law) · [Dyson & Haselgrove 2001 (measure)](https://www.sciencedirect.com/science/article/abs/pii/S1071581901904586) · [Schloss & Palmer (color harmony)](https://pubmed.ncbi.nlm.nih.gov/21264737/)
**Typography/spacing canon:** [type-scale.com / spec.fm ratios](https://spec.fm/specifics/type-scale) · [Mortensen (formula only)](https://spencermortensen.com/articles/typographic-scale/) · [Smashing fluid clamp](https://www.smashingmagazine.com/2022/01/modern-fluid-typography-css-clamp/) · [Bringhurst measure](http://webtypography.net/2.1.2) · [Curtis, Space in Design Systems](https://medium.com/eightshapes-llc/space-in-design-systems-188bcbae0d62) · [Refactoring UI notes](https://mohitkhare.me/blog/notes-refactoring-ui/) · [Comeau shadows](https://www.joshwcomeau.com/css/designing-shadows/) · [MUI z-index](https://mui.com/material-ui/customization/z-index/)
**Myth-busting (⚠️):** [Naini, golden-ratio dispelling the myth](https://pmc.ncbi.nlm.nih.gov/articles/PMC10792139/) · [plus.maths.org / Godkewitsch 1974](https://plus.maths.org/content/golden-ratio-and-aesthetics) · [Amirshahi 2014 rule of thirds](https://brill.com/view/journals/artp/2/1-2/article-p163_11.xml?language=en) · [8pt grid is convention not science](https://breakdance.com/the-8-point-grid-system-a-practical-guide/)

---

*End of draft. Four verifier corrections applied (0.04045 threshold; APCA cross-walk Lc 45/60/75; type-scale.com/spec.fm citation for the ratio table; emphasized-easing spline + linear() fallback). All ten open decisions in Part D require explicit team rulings before encoding. This note is the empirical foundation; the generator implementation (the pure functions in C.3) is the next build target.*


---
---

# Appendix B — OD-1 behavior-layer decision (full text)

*The spike (fixed APG rubric → 3 candidate profiles → adversarial refutation → verified ruling). To be re-homed: close OD-1 in open-decisions.md and record in the pipeline ADR.*

# OD-1 DECISION DOCUMENT — Eden UI Behavior Layer

**Decision:** Adopt **Bits UI** (`bits-ui@2.18.1`) as Eden's headless behavior layer for overlays, menus, and the command palette; **hand-roll the data grid** on Svelte 5 runes (the universal gap no candidate fills); compose the wizard from Bits `Tabs` + Eden runes state. This is a **Bits-primary hybrid**, not a pure pick.
**Confidence:** High (≈0.8) on the primary choice; Medium-high on the grid-is-hand-rolled corollary.
**Status of inputs:** All load-bearing facts re-verified at source on 2026-06-14 (see verification log at end). The adversarial corrections held on every checked point and I have applied them — discounting overstated profile claims accordingly.

---

## 1. SCORING MATRIX (adversarially-adjusted)

Scores are the **post-correction** values. Where an adversarial review moved a score or invalidated its *reasoning* (without moving the number), the adjustment is reflected and footnoted. Weights are the fixed rubric's.

| # | Dimension | Wt | **Melt UI** | **Bits UI** | **Hand-rolled** |
|---|---|---:|:--:|:--:|:--:|
| D1 | a11y / APG conformance **(GATE)** | 18% | 4 | **4** | 2.5 |
| D2 | Theming cleanliness **(GATE)** | 14% | 5 | 5 | 5 |
| D3 | LLM-legibility / agent-authorability | 13% | 3.5 | **4** | 2.5 |
| D4 | Coverage of the 4 hard patterns | 12% | 1.5 | **4** | 2 |
| D5 | Control over markup / DOM | 10% | 5 | 4 | 5 |
| D6 | Svelte-5 runes-nativeness | 9% | 5 | 5 | 5 |
| D7 | Maintenance health & longevity | 8% | 2 | **4** | 4 |
| D8 | API ergonomics | 6% | 4 | 4 | 3 |
| D9 | SSR + Tauri/WebView | 5% | 3 | 4 | 4 |
| D10 | Bundle size & runtime perf | 5% | 3.5 | 4 | 5 |
| | **Weighted total** | 100% | **≈ 3.13** | **≈ 4.18** | **≈ 3.52** |
| | **Gate verdicts** | | PASS / PASS | **PASS / PASS** | PASS(thin) / PASS |

**Adversarial adjustments applied (vs. raw profiles):**
- **Melt D4 3.30→3.13**: D4 cut to **1.5** (three of four hard patterns unbuilt: no Command, no Menu/Menubar/ContextMenu, no Table, no Stepper — verified by source-file absence, not just roadmap); D10 cut to **3.5** (the `sideEffects`-clean tree-shaking justification is **fabricated** — the field is *absent*/`null`, so bundlers conservatively assume side effects); D3 nudged to **3.5** (the ~25:1 corpus dominance of the *classic* store/action API is a real hallucination trap). D7 stays **2** (now *less*-cushioned: repo `pushed_at` 2026-03-04 = ~3-month stall, package 5+ months stale on npm, single maintainer ≈75% of commits, 6.5k weekly downloads).
- **Bits D7 raised to 4 and held; D1 reasoning rebuilt, score held at 4**: the profile's two "open focus defects" (#1307, #755) are **both CLOSED/completed** (2025-03-31 and 2025-02-15), and #755's root cause was the *old melt-era* architecture Bits no longer ships. So there is **no verified open nested-focus defect** — Fixture D is *stronger* than the profile claimed. D1=4 now rests on the *real* gaps: **no vendor axe/a11y attestation** and **zero grid coverage** (both confirmed). Total holds at 4.18.
- **Hand-rolled D1 2.5, D3 2.5 (total 3.77→3.52)**: the "native platform helps materially" claim over-credits the platform — `<dialog>.showModal()` deliberately does *not* fully trap focus, `autofocus` is buggy in Chrome, and async-inserted focusables aren't picked up; the *hard* a11y (roving-tabindex×virtualization, activedescendant×virtualization, initial/async focus) gets zero platform uplift. D3 cut because a typed component API is *more* agent-legible than a contract-free ARIA sprawl in an agent-authored codebase.

No gate is capped (no candidate scores 1 on D1 or D2). The decision rests on the weighted totals plus the Eden-specific tradeoffs in §3.

---

## 2. RECOMMENDATION & REASONING

### Adopt Bits UI as the primary behavior layer; hand-roll only the grid.

Bits UI wins decisively on the weighted total (**4.18** vs 3.52 hand-rolled vs 3.13 Melt) and, more importantly, wins on the **two dimensions that actually decide this for Eden**: it passes both gates cleanly, and it is the **only candidate that ships three of the four hard patterns first-class** (Dialog/AlertDialog with `tabbable` focus-trap, full Menu/Menubar/ContextMenu with roving-tabindex + typeahead, and a real `⌘K` **Command** palette using the correct `aria-activedescendant`-on-input model). Melt next-gen ships *none* of the menu stack, *no* Command, and *no* table — its line is pre-1.0, single-maintainer, stalled ~3 months, at 6.5k weekly downloads. Hand-rolling wins theming/markup/bundle but pays for it entirely in the a11y dimension that ADR-0004 makes a ship-blocker, and in agent-regression risk that Eden's agent-authoring model makes a recurring tax.

**Why Bits over hand-rolled specifically** — the two are closest (4.18 vs 3.52), and the gap is exactly Eden's risk profile:
- **The hardest a11y machinery is already built and battle-tested.** Bits vendors a *coordinated LIFO layer stack* — insertion-ordered global escape/dismissible registries (`findLast` → only the topmost layer's Escape fires) plus reference-counted body-scroll-lock that only restores on the last release. This is the single hardest thing to get right in Fixture D, and hand-rolling it correctly *and proving it* is precisely where an AI agent silently ships a double-Escape or a scroll-lock leak. Buying it removes Eden's highest-risk hand-roll.
- **A typed component contract is more agent-legible than contract-free ARIA.** Eden's components are authored/extended *by agents*. `<Command.Item>`/`<Dialog.Title>` with typed props give an agent a constrained, autocompletable, Radix/shadcn-lineage surface it has seen thousands of times — versus re-deriving APG keyboard/ARIA/focus logic from scratch every time, where the failure mode (ARIA that compiles and passes axe but is wrong) is undetectable. This is why hand-rolled D3 drops to 2.5.

**Why hybrid, not pure Bits:** Bits ships **no grid/table**, and its internal roving-focus/arrow-nav primitives are **not exported**, so Fixture C is a *complete* APG hand-roll regardless of the layer chosen. The grid is therefore the one place hand-rolling is genuinely "least disadvantaged" (everyone hand-rolls it). The recommendation embraces that: **Bits for overlays/menus/palette + a hand-rolled `role="grid"` over `@tanstack/table-core` (data-ops only).** The wizard is composed from Bits `Tabs` + Eden runes (no candidate ships a stepper) — a thin shell, mostly Eden code, but with Bits supplying correct tablist semantics and roving tabindex for the step rail.

**Why not Melt at all (not even as the builder substrate):** The adversarially-corrected case against Melt is strong: D4=1.5 (three of four patterns unbuilt), D7=2 (stalled, pre-1.0, single-maintainer, 6.5k downloads), and the **corpus-hallucination trap** — agents will reach for the *classic* `@melt-ui/svelte` store/action API (165k downloads, ~25:1 dominance) which is structurally incompatible with the next-gen `new Combobox({...})` + `{@attach}` model. For an agent-authored codebase that is a daily failure mode. Critically, choosing Bits already *captures Melt's one architectural advantage* (Bits is a Radix-style port with the same clean attribute-spread seam) **without** Melt's coverage holes — and note the governance reality: **Bits and Melt share one maintainer (huntabyte/TGlide ecosystem)**, so "fall back to Melt" is not real bus-factor diversification.

### Key risks of this recommendation
1. **Single-maintainer SPOF (Bits, D7).** Bits is one maintainer (Huntabyte). Mitigation: Bits is MIT, 754k weekly downloads (the de-facto Svelte-5 headless standard, shadcn-svelte's foundation), `svelte ^5.33.0`-native, and — because Eden owns 100% of appearance — a fork or migration touches only behavior wiring, not visuals. The hand-rolled grid is *already* Eden-owned, de-risking the most complex surface from vendor fate.
2. **No vendor a11y attestation (Bits, the real D1 gap).** Bits ships no published axe/jest-axe conformance suite. ADR-0004 evidence must be **produced by Eden**, not cited from the vendor — which §4 makes the plan, and which is true of *every* candidate.
3. **v3 RFC churn (low).** An open Bits v3 RFC (#1856) proposes `Select.List`/`Combobox.List` restructuring — but it is narrowly scoped to Select/Combobox, has ~3 comments / no momentum / no timeline, and **does not touch `Command`** (Eden's palette). Demoted to a footnote: pin the major version; revisit on v3 ship.
4. **Virtualization is unsolved everywhere.** Bits Command/Combobox don't virtualize; Eden bolts on `@tanstack/svelte-virtual`, and the **activedescendant-must-be-realized-in-DOM** bug (and roving-tabindex-loses-focus-on-recycle for the grid) is a genuinely hard custom integration in *all three* candidates. This is unavoidable scope, not a Bits-specific defect.
5. **Portal/top-layer markup leak (minor, D5/D2).** Bits `Portal` relocates content out of Eden's DOM tree and floating components force a non-collapsible positioning wrapper — both can break **CSS-custom-property token inheritance that relies on DOM ancestry** (directly relevant to Eden's token engine). Mitigation in §3.

---

## 3. DECISIVE TRADEOFFS FOR EDEN

### Appearance stays 100% Eden's
- **Cosmetically: a clean pass (D2=5 for Bits).** Bits ships no CSS reset, no base stylesheet, no design-system assumptions — all hooks are `class` props + rich `data-*` (`data-state`, `data-highlighted`, `data-side`) + ARIA. Eden's CSS-custom-property tokens become the sole appearance source with zero purge. All three candidates pass this gate, so **D2 does not discriminate** — it is necessary, not decisive.
- **The real seam isn't color, it's markup/DOM-ancestry.** Bits' `Portal` (out-of-tree) and mandatory positioning wrappers, *and* the native top-layer that Melt/hand-rolled lean on, all sit **outside ancestor stacking/`overflow`/`transform` context**. A token system that inherits CSS custom properties down the DOM tree must be engineered so that **token definitions are scoped at or above the portal target** (e.g., define tokens on `:root`/a portal-host wrapper, not on a transient ancestor). This is the one place "100% Eden appearance" frays for *any* candidate and is a required design constraint, not a defect of the choice.

### LLM-authorability
- **Bits is the strongest of the three for agent authoring**, and this is the second-most-decisive factor after coverage. The compound-component anatomy (`Command.Root/Input/List/Group/Item`) is the dominant Radix/shadcn pattern an LLM has seen thousands of times; it is fully typed; there is one idiomatic shape per component. An agent scaffolds a dialog or palette correctly from memory.
- **The two real footguns to instrument away:** (1) the `child`-snippet render-delegation needs `{...props}` spread *and* a two-level wrapper spread for floating parts — omitting either silently breaks a11y/positioning; (2) implicit prop/`data-*`/handler merging is invisible to the agent. Both are exactly the "edits break invariants silently" class — so Eden must encode them as `project-go`-style PostToolUse lint rules + golden examples (see §4/§5), not rely on the compiler (which, per Geoff Rich, catches ~none of runtime ARIA/focus).
- **Hand-rolled is the worst here (D3=2.5):** no contract to anchor the agent; every palette/grid extension re-derives APG from scratch with no type or compiler safety net. Melt sits between, dragged down by the classic-API corpus-hallucination trap.

### The a11y burden (ADR-0004)
- **Bits minimizes Eden's residual a11y burden** for three of four patterns: the correct `aria-activedescendant` combobox model, roving-tabindex menus with typeahead, `aria-modal` dialogs with focus-return, and the LIFO layer stack are **already built** — Eden's job shrinks from "implement + prove" to "**prove**." That is the right division of labor when the proof obligation (§4) is non-negotiable.
- **The grid is the irreducible burden.** `role="grid"` (never `table`), roving-tabindex × virtualization (the focused cell unmounts on recycle), and `aria-rowindex`/`aria-colindex` math for virtualized rows are 100% Eden's in *every* candidate. This is Eden's single largest a11y liability and Bits contributes nothing reusable to it — which is *why* the recommendation hand-rolls it deliberately rather than pretending a library helps.
- **No candidate ships ADR-0004 evidence.** The conformance matrix must be Eden-generated regardless. The choice of Bits doesn't reduce the *evidence* obligation — it reduces the *implementation* surface that the evidence has to cover with novel code.

---

## 4. A11Y EVIDENCE-STORY PLAN (what ADR-0004 demands)

**Principle:** automated tooling covers only ~25–35% of a11y errors (WebAIM, via Geoff Rich) and the Svelte compiler catches ~none of runtime ARIA/focus. So the artifact is a **three-layer evidence stack per pattern**, and a cell is "accessible" only when all three are green and archived.

### Patterns to conformance-test (the APG contract, mapped to fixtures)

| APG pattern | Fixture | Source of behavior | Conformance focus |
|---|---|---|---|
| **Dialog (modal)** 1A | D, B(host) | Bits `Dialog`/`AlertDialog` | focus-trap wrap, focus-return-to-invoker, `aria-modal`+`aria-labelledby`/`describedby` actually wired, Escape |
| **Menu/Menubar** 1B | D | Bits `DropdownMenu`/`Menubar`/`ContextMenu` | roving tabindex (one tab stop), arrow/Home/End/Esc/Tab, `aria-haspopup`/`expanded`/`checked`, typeahead |
| **Combobox/Command** 1C | B | Bits `Command`+`Combobox` | `role=combobox`+`aria-activedescendant`, **DOM focus stays on input**, `aria-autocomplete="list"`, active option `scrollIntoView` **under virtualization** |
| **Grid** 1D | C | **Hand-rolled** + `@tanstack/table-core` | `role="grid"` not `table`, roving tabindex, full cell-nav keys, `aria-rowcount`/`colcount`+per-cell `aria-rowindex`/`colindex` virtualized, `aria-sort`, selection keys |
| **Nested/LIFO dismissal** 1A+1B | D | Bits layer stack | Escape dismisses **only topmost**, outside-click LIFO, reference-counted scroll-lock, per-layer focus-return |

### Tooling per layer

1. **Automated (axe-core via Playwright + `@axe-core/playwright`).** Run `axe` against each fixture in every state: closed, open, each wizard step, palette empty/loading/results, grid sorted/selected/edit-mode, and **each nesting depth** of Fixture D. Zero violations of `wcag2a`/`wcag2aa`/`best-practice`. Wire into the ADR-0020 testing-phase gate as an `integration`-dimension test on real Chromium **and a WebKit Playwright project** (the Tauri/WKWebView proxy).
2. **Behavioral / keyboard (Playwright key-driven assertions).** axe cannot see keyboard behavior. For each pattern, scripted key sequences assert the *outcome*: Tab-cycle stays inside the dialog and wraps; Escape closes only the top layer (assert the stack depth before/after); arrow keys move `aria-activedescendant` and the referenced node is **mounted + `scrollIntoView`'d**; grid arrows move the single `tabindex=0` cell and `aria-rowindex` tracks the *logical* row under virtual scroll; "Next" stays disabled until async validation resolves and focus lands on the first error. These are the rows automation otherwise misses.
3. **Manual screen-reader passes (the 25–35% gap).** A documented matrix run per release on **NVDA+Firefox, VoiceOver+Safari (= the WKWebView engine), JAWS+Chrome**. Priority targets are the known landmines: VoiceOver/Safari may *ignore* `aria-activedescendant`; NVDA flips to browse mode if it points outside the widget; grid rowindex announcements. Each pattern gets a pass/fail per SR/browser cell with notes.

### The artifact that proves a cell ships

A per-component **`a11y-evidence/<component>.md` conformance record**, generated and version-pinned, containing: (a) the **APG REQUIRED-row checklist** with PASS/PARTIAL/FAIL + the asserting test id; (b) the **axe run** output (0 violations) with commit SHA + Playwright project (Chromium **and** WebKit); (c) the **keyboard-assertion test ids** that prove the behavioral rows; (d) the **manual SR matrix** (NVDA/VO/JAWS × pass/fail/notes, dated); (e) **LLM-legibility note** — the golden authoring example + the lint rule that guards the merge footgun. **No component merges without a green record on all five.** This is wired as a Stop-hook/`phase-gate qa` blocker, mirroring ADR-0020's existing discipline.

---

## 5. CONFIRMING RUNTIME SPIKE (build-this-to-validate)

Once the TS/Svelte toolchain exists, build the **minimum that exercises every load-bearing claim** before committing the library to Bits. Keep it to two artifacts:

**Spike 1 — Focus-trapped nested Dialog + LIFO stack (validates the Bits thesis):**
Build Fixture D end-to-end on Bits: `Dialog` → field → `Popover` → `DropdownMenu` → menu-item opens a **second `Dialog`**. Style entirely with Eden CSS-custom-property tokens (incl. `::backdrop`), placing token definitions at/above the `Portal` host to prove DOM-ancestry inheritance survives portalling. Drive it with Playwright key-assertions for LIFO Escape, reference-counted scroll-lock, and per-layer focus-return — and run axe at each depth in **both Chromium and WebKit** projects.

**Spike 2 — ⌘K Command palette, grouped + virtualized + Eden scorer (validates the riskiest seam):**
Bits `Command` inside a `Dialog`, ~500 items, grouped (Recent/Actions/Navigation), `shouldFilter={false}` with **Eden's own fuzzy scorer** driving results, wrapped in `@tanstack/svelte-virtual`. This stresses the one genuinely hard integration: assert `role=combobox`+`aria-activedescendant`, that **the active option is realized in the DOM and `scrollIntoView`'d** as the window recycles, focus stays on the input, and the VoiceOver/Safari manual pass actually announces the active item. *(The grid — Fixture C — is explicitly out of spike scope because it's hand-rolled regardless; if appetite allows, a minimal `role="grid"` × roving-tabindex × virtualization slice de-risks the largest hand-roll, but it does not gate the Bits decision.)*

### Go / No-Go criteria
- **GO (commit to Bits-primary hybrid)** if: Spike 1 passes axe at every depth on Chromium **and WebKit** with correct LIFO Escape + scroll-lock refcount + per-layer focus-return; Eden tokens (incl. backdrop) render through `Portal` with no ancestry breakage; Spike 2 keeps `aria-activedescendant` pointed at a mounted, scrolled node under virtualization and the Eden scorer drives ranking; and the VoiceOver/Safari pass announces palette navigation. 
- **NO-GO / reconsider** if: WebKit (the WKWebView engine) shows a focus-trap or top-layer/portal defect Bits can't work around; the activedescendant×virtualization integration proves intractable within the spike; or token inheritance through `Portal` cannot be made clean. In that event, fall back to **hand-rolled** (next-highest at 3.52, and already Eden's plan for the grid) — *not* to Melt, whose coverage holes and corpus-hallucination trap make it the weakest fit for an agent-authored codebase.

---

### Verification log (re-checked at source 2026-06-14)
- **Melt `melt@0.44.0`**: `sideEffects` field **absent** (registry) — confirms the profile's "`None`/false-equivalent" tree-shaking claim is fabricated; D10 justification struck. Peer `svelte ^5.30.1`; deps incl. `focus-trap`, `runed`, `jest-axe@9`. Repo `melt-ui/next-gen`: 319★, **open_issues 33**, **`pushed_at` 2026-03-04** (≈3-month stall), MIT.
- **Bits UI `bits-ui@2.18.1`**: peer `svelte ^5.33.0` + `@internationalized/date`; deps incl. `tabbable@^6`, `@floating-ui/{core,dom}`, `runed`, `svelte-toolbelt`, `esm-env` — **no `@melt-ui/svelte` dependency** (confirms independent Radix-style port). Issues **#1307 CLOSED/completed 2025-03-31** and **#755 CLOSED/completed 2025-02-15** — both adversarial corrections confirmed; **no verified open nested-focus defect**.
- **Svelte**: current stable **5.56.x** line (registry `latest` = 5.56.3) — runes/`{@attach}` mature; supersedes the profiles' 5.55 figure.

(Deliverable is this message; no files written.)
