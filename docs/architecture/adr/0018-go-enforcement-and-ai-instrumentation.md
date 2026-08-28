# ADR-0018: Go library enforcement toolchain + AI-instrumented authoring

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo (intake C25)

> **Note (2026-08-11) — `hnslint` moved. The decision below does not change.** The Layer-1 list
> names `tools/hnslint`, which was its home in this monorepo. `hnslint` is now the public
> repository `gophersys/hnslint`, and `.devcontainer/base/Dockerfile` installs it pinned by
> `HNSLINT_VERSION`. This monorepo holds no copy. To change the check, cut a release there and
> raise the pin. The reason for the move is in `gophersys/infrastructure`
> `docs/debt-register.md` D39: no image carried the tool, so `gophersys/libs` could not gate.

## Context

The core Go libraries are Eden's crown-jewel asset (C25): if they are stale, non-uniform, or
carry weak interfaces, everything built on them inherits the rot. ADR-0017 added a post-wave
*review* — agent judgment after the fact. C25 demands more: the standard must be **mechanically
enforced** so non-conformant code cannot be committed, and **AI-instrumented** so the rules shape
generation at authoring time, not only at the gate. 10 §9 specified this three-layer model
(neutral principles → per-ecosystem rendering → tooling enforcement); it was never built. The
`cfgtest` naming break that passed Wave 3A's prompt guidance is the proof that guidance without
teeth is porous: a `forbidigo` rule rejects `cfgtest` the instant it is written.

This ADR is the build spec for that enforcement layer. It is **knowledge ≠ enforcement** (P7)
applied to the libraries themselves.

## Decision

### Layer 1 — Deterministic gates (the teeth)

A single shared configuration in the `gophersys/libs` submodule, inherited by every `libs/go/<lib>`,
run by `ctl.sh` verbs, by git hooks, and re-run in CI (defense in depth — client hooks are
bypassable, the server gate is not):

- **`gofumpt`** — stricter-than-gofmt formatting; zero tolerance.
- **`go vet`** — correctness.
- **`golangci-lint` v2** with a curated, strict `libs/.golangci.yml`. Load-bearing linters and the
  canon rule each enforces:
  - `interfacebloat` (max **5** methods) — the ≤5-method interface rule (10 §9).
  - `ireturn` — accept interfaces, return concrete (10 §9).
  - `errcheck`, `wrapcheck`, `errorlint`, `err113`, `errname`, `nilerr`, `nilnil` — no swallowed
    errors; wrapping with `%w` and `errors.AsType` inspection (the `errors` contract; "no
    shortcuts", C24).
  - `forbidigo` — the **HNS-1 banned-token gate**: reject `cfg`/`config`, `deps`, `k8s`, `mgmt`,
    `obsv`/`o11y`, `golang`, `util`/`utils`/`common`/`core`/`misc` as identifiers (10 §5).
  - `depguard` — **import boundaries (P1/E1)**: leaf libraries import stdlib only; a vendor SDK may
    be imported only inside an adapter package; no cross-pattern back-imports.
  - `revive` (exported-symbol doc comments, naming, receiver consistency), `staticcheck`,
    `gosimple`, `unused`, `ineffassign`, `gocritic`.
  - `cyclop`/`gocognit` (complexity bounds), `exhaustive` (enum-switch completeness),
    `testpackage`, `tparallel`, `paralleltest`, `thelper` (test hygiene), `gochecknoinits`,
    `predeclared`, `misspell`, `godot`.
- **`govulncheck`** — dependency vulnerability scan.
- **Exported-surface breaking-change gate** (`gorelease`/`apidiff`): diff the exported API against
  the last released tag; a break without a major-version bump fails — breaking a published
  interface is the cardinal sin (10 §9). Advisory locally, blocking in CI.
- **`go test -race -cover`** with a coverage **floor** (not a ceiling); ADR-0017's true-coverage
  bar (conformance + integration + E2E) is the real standard — coverage % is necessary, not
  sufficient.
- **`gremlins`** (mutation testing) where cheap — test-power (08 §3), at least the leaf libraries.
- **`hnslint`** (a small `tools/hnslint` Go analyzer): the **structural** HNS-1 check `forbidigo`
  cannot do — module path is `github.com/gophersys/libs/go/<slug>`, package name is the
  separator-free lowercase rendering of the slug, directory is the slug (10 §5).

### Layer 2 — AI-instrumented authoring (the guidance, P7)

A `project-go` Claude Code plugin in the `gophersys/libs` submodule (`libs/plugins/project-go/`,
neutral principles in `libs/.claude/rules/` — 10 §9 layer A), so any agent developing from this
repo is constrained at edit time:

- **`SessionStart` hook** — inject the active library's frozen contract + the naming/interface/error
  rules + "you are implementing a frozen contract; deviations are forbidden."
- **`PostToolUse` hook** on `Edit`/`Write` of `*.go` — run `golangci-lint` (fast path) + `hnslint`
  on the touched file and return findings to the agent for self-correction **before it proceeds**.
  This is the inner-loop enforcement that would have caught `cfgtest` immediately.
- **`PreToolUse` hook** on `git commit`/`push` — run the full Layer-1 gate suite; block on failure.
- A `skills/api-design/SKILL.md` rendering the interface-design rules for Go.

CLAUDE.md points at the plugin and the gate verbs.

### Sequencing

The enforcement layer is **Wave 3A.5**, built and committed immediately after Wave 3A's libraries
land and before Wave 3B. It is then run **mechanically against the Wave 3A libraries** (the
review wave consumes its findings rather than re-deriving them by eye), 3A is conformed, and
**every wave from 3B develops under it from birth** — the standing answer to C25.

## Consequences

- Wave 3A libraries are retroactively conformed; this is honest (enforcement postdates them) and
  bounded (one conform pass). From 3B, conformance is by construction.
- The review wave (ADR-0017) gains a deterministic substrate: its true-coverage and cohesion
  lanes start from linter output, freeing agent judgment for what linters cannot express
  (interface *taste*, architectural cohesion, real-substrate test adequacy).
- 08 (testing) and 10 §9 are amended on next touch to reference this ADR as the realized toolchain.
- CI must install the toolchain (pinned versions via the Go `tool` directive where possible);
  release builds run `GOWORK=off` so a stray workspace never masks a missing published version
  (10 §6.1) — the transient observed during the 3A build is exactly that isolation working.
- Self-hosting payoff: because Eden's own build agents develop from this repo under these hooks,
  generated libraries are conformant by construction and the gate guarantees it where construction
  drifts — the same safety property the platform will sell its users.
