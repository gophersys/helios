# CLAUDE.md

This is the **Eden** monorepo — an agentic-engineering platform, currently in the
architecture/bootstrap phase (no production code yet; the kernel is the first build target).

## Read before acting

- `docs/architecture/README.md` — the canonical doc set: reading order, epistemic legend
  (✅🔶⚠️🧩), source registry, Eden-level invariants E1–E7, cohesion contract (one concept, one
  home — cite, never redefine).
- `docs/README.md` — the documentation scheme (ADR-0010): where any new document belongs and how
  it is named.
- `docs/architecture/09-build-execution-plan.md` — current workstreams and milestones.

## Hard rules

- **Naming:** the system is Eden; never introduce a `helios` identifier (invariant E7). Full
  naming per HNS-1 (10 §5): `configuration` not `config`, `kubernetes` not `k8s`,
  `dependencies` not `deps`; `util`/`common`/`core` are banned outright.
- **Decisions:** settled rulings live in `docs/architecture/adr/` — do not re-litigate them.
  Unruled forks go in `docs/architecture/open-decisions.md`, not in prose.
- **Docs:** new documents follow the four-class scheme (canonical spec / research note /
  directory README / attic). Lowercase kebab-case filenames; specs carry a status header and
  epistemic tags. Superseded docs move to `docs/attic/`, never deleted.
- **Pipeline vocabulary:** "phase" = a step of the 10-phase SDLC pipeline; "stage" = the
  environment axis (development/test/staging/production). Never mix them.
- **Commits:** Conventional Commits; **no AI/LLM attribution lines** (ratified in ADR-0010 —
  omit Co-Authored-By trailers). **Always push after committing** (standing directive,
  2026-06-12: never lose data — save and push).
- **Go:** floor 1.26; everything that can be Go is Go (ADR-0003). UI is Svelte 5 (ADR-0004).
- `poc/` is donor material: reference freely, but code enters `main` only through gates
  (ADR-0009 D). Do not modify PoC artifacts in place.
- Generated artifacts (e.g. `docs/architecture/eden-architecture.html`) are never edited by
  hand — regenerate via `node docs/tools/render-html.mjs`.
- **Subagents/workflows always run on the Opus model** (standing directive, 2026-06-12 — usage
  economics; the main loop orchestrates, Opus executes).

## Workspace facts

- Nx + yarn 4 workspace; `bash .ci/ctl.sh affected-check` is the canonical PR gate (no-ops until
  `yarn install`).
- `libs/`, `infrastructure/`, `.devcontainer/` are git submodules — separate repos, separate
  commits.
- Nx Cloud is disabled in `nx.json` (ratified in ADR-0010); keep it that way.

## Go enforcement (ADR-0018)

- **Git hooks (one-time setup):** the tracked hooks live in `.githooks/`. Point git at them:
  `git config core.hooksPath .githooks`. `pre-commit` runs gofumpt + golangci-lint (per touched
  module) + hnslint (per touched `libs/go/<lib>`) on the staged Go; `pre-push` adds `go test -race`
  per touched module. Bypass with `--no-verify` only in emergencies — CI re-runs the identical gate.
- **AI authoring (Layer 2):** the `project-go` Claude Code plugin (`libs/plugins/project-go/`,
  registered in `libs/.claude-plugin/marketplace.json`) injects `libs/.claude/rules/` at session
  start, lints every `*.go` edit (PostToolUse), and gates `git commit`/`push` (PreToolUse). Install:
  `claude plugin marketplace add ./libs && claude plugin install project-go@eden-libs`.
- **`hnslint`** (structural HNS-1) is `tools/hnslint`; install with
  `(cd tools/hnslint && GOWORK=off go install ./cmd/hnslint)`. The shared linter config is
  `libs/.golangci.yml`.
