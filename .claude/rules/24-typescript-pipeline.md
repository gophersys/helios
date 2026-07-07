# Rule — TypeScript library pipeline: cohesion + mutation teeth (ADR-0024)

> The UI-track analog of rules 20 (library-pipeline) and 21 (test-taxonomy). Enforced mechanically by
> `bash ./ctl.sh phase-gate <phase>` per `@eden/*` TypeScript lib (shared verbs in
> `libs/typescript/_ctl/lib.sh`), re-run identically in CI. Tooling runs through **bun** (the
> devcontainer JS runtime; verbs invoke tools via `bun x`). The **lone exception is the mutation
> lane** (`./ctl.sh mutate`), which runs StrykerJS under the baked **node** (installed via nvm) — see
> §2. "phase" = the SDLC step, never the environment "stage".

The four phases and the cardinal sin are identical to the Go track: **architecture → implementation
→ testing → qa**, each with a mechanical gate; the frozen `.apibaseline` (the public `.d.ts` surface)
is the cardinal sin — an exported-surface break aborts the gate, and a deliberate additive/neutral
change re-records it via `./ctl.sh apidiff-record`. The **ninth dimension is design-correctness**
(math-is-source-of-truth: provenance + the scale/contrast/proportion assertions). This rule documents
the two **Stage-3 ENFORCE** dimensions the TS track previously lacked vs the Go track — the
`gremlins ≥ 0.75` and `one-concept-one-home` analogs.

## (1) Cohesion — dead-export + cross-lib math duplication (`./ctl.sh cohesion`)

One concept, one home (10 §9). The scan (`libs/typescript/_ctl/cohesion-scan.mjs`, a TypeScript
**compiler-API** tool — no new dependency) reads the WHOLE TS workspace (importer counting is
necessarily cross-lib) and FAILS the gate on either class, scoped to the lib under gate:

- **Dead export.** An exported symbol declared in a NON-index module that is reachable from nowhere:
  neither re-exported by its own lib's public barrel (`src/index.ts`) NOR imported by any module
  across the TS libs. This is the **scale-dead-end / dead-contract** class. **Fix:** re-export it from
  `index.ts` (make it public API) or DELETE it. A barrel-published symbol is the lib's frozen public
  surface and is exempt — do not gate public-but-not-yet-consumed types here (that is what the
  `.apibaseline` freezes).
- **Cross-lib math duplication.** An exported math const/function in a downstream `@eden` lib whose
  identifier collides with one already exported by a **foundation** lib (a lib others depend on —
  e.g. `@eden/scale`), UNLESS the downstream lib IMPORTS that identifier from the foundation. This is
  the **theme-reimplements-scale** class. **The modular-scale generator (`stepAt`/`modularScale`) and
  the ratio/base seeds (`INTERVAL_RATIO`, `DEFAULT_TYPE_RATIO`, `DEFAULT_BASE_PX`) live ONCE in
  `@eden/scale`; `@eden/theme` CITES them (`import { stepAt } from '@eden/scale'`), never re-derives
  the formula or the table.** A cited re-export or a foundation import is fine; a locally re-declared
  same-named const/function is the FAIL.

`cohesion` runs inside `maintainability` and as its own qa-gate dimension. It is non-vacuous: a
planted unused non-index export, or a planted local re-derivation of a foundation export, fails it.

## (2) Mutation — StrykerJS (`./ctl.sh mutate`), the gremlins ≥ 0.75 analog

A survived mutant on covered code is a **real test gap** (rule 21 §h). StrykerJS mutates the lib's
non-test `src` (every module except the pure re-export barrel `index.ts`) and re-runs the vitest
suite per mutant. The run FAILS if the mutation score dips below the per-lib **`EDEN_MUTATION_FLOOR`**
(Stryker's `break` threshold). **`75` mirrors the Go leaf floor (gremlins ≥ 0.75)**; a
substrate/large-surface lib records a lower CURRENT baseline that **ratchets** toward 75 — the
bench-baseline model: pin the floor, never regress below it, raise it as test gaps close. Set the
floor per-lib in the dispatcher `ctl.sh` (`EDEN_MUTATION_FLOOR=...`), not in shared `lib.sh`. Today
(the four-lib roster this rule governs): `@eden/scale` = 75 (score 77.78%), `@eden/theme` = 65
(score 66.24%; ratchets toward 75 as the generative-surface gaps in findings idx 60-67 close),
`@eden/primitives` = 75, `@eden/visualization` = 75. `mutate` is a qa-gate dimension.

**When a mutant survives, strengthen the TEST to kill it — never lower the floor to pass.** Lowering
`EDEN_MUTATION_FLOOR` is a recorded, reviewed re-baseline (like bench/apidiff), only ever DOWNWARD as
a deliberate documented exception, and the standing direction is to ratchet it UP.

### The mutation lane runs under node (the one dev-gate verb that does)

The mutation lane runs StrykerJS under the **baked node** (installed via nvm in `ghcr.io/gophersys/base`,
`NODE_VERSION` 24.x) — the one dev-gate tool that uses node; the **runtime and every other verb still
dogfood bun**. Mutation testing is a **dev-gate, not the runtime**: StrykerJS forks worker processes
and drives vitest through `worker_threads`, which the devcontainer's bun does not fully implement, so
running it under node is the clean substrate rather than forcing it through bun.

The `mutate` verb (in `libs/typescript/_ctl/lib.sh`) activates the nvm node inside the verb (sourcing
`nvm.sh`; **FAIL-NOT-SKIP** — exit 127 if node is unavailable), then invokes Stryker the ordinary node
way: `node node_modules/@stryker-mutator/core/bin/stryker.js run <config>`. Under real node, peer-dep
resolution Just Works, so the vitest-runner plugin is named by its **plain specifier**
`@stryker-mutator/vitest-runner` (normal `node_modules` resolution) — **no bun patches, no preload
shim, no `.bun` store path, no `node`→bun PATH shim**. `require_tool` still asserts the Stryker package
is installed. The verb keeps `inPlace:true`: each lib's `vitest.config.ts` imports
`../vitest.config.base.js` (a path escaping the lib dir to the workspace root), and Stryker's
sandbox copies only the lib subtree, so a sandbox copy cannot resolve that parent import; `inPlace`
mutates the real files in a clean git tree and Stryker restores them on exit (the verb also clears
`.stryker-tmp`).

If a Stryker/vitest/node upgrade changes this surface, re-verify by running `./ctl.sh mutate` over
`@eden/scale` (the reference leaf) and confirming a planted weak test drops the score below floor.
