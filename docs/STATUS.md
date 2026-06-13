# Eden build STATUS — autonomous manager loop

> Living working-state for the self-paced manager loop (set up 2026-06-12 while Mateo is away).
> This is my memory across loop iterations. Mateo: read this first when you're back.

## Goal (definition of done)

1. Every `libs/go/` library implemented from its frozen contract; gates green (gofmt, vet,
   `go test -race`); uniform per 10 §6.1; conformance suites pass.
2. Substrate/integration libraries have REAL integration tests (docker daemon + k3d cluster,
   never mocks) that pass.
3. Apps in place: `apps/frontend` (chat + document workspace) + the backend agent-session
   service, wired to the `agentsession` contract. Chat UI: server-triggered sequence-numbered
   events, full telemetry taxonomy, lossless start/stop/resume, drill-down to any session —
   built + tested with a FAKE harness adapter end-to-end. Real claude-code adapter wired but its
   authenticated run is **gated on Mateo's `setup-token`** (I cannot mint it).
4. Playwright forced-CRUD E2E lane green (create through UI → destroy through UI before exit;
   nested creation covered).
5. Every implementation wave followed by the mandatory ADR-0017 review-and-architecture wave
   (cohesion + true-coverage + adversarial), findings fixed before proceeding.
6. Working tree clean; HTMLs regenerated; no scratch; servers killed; libs submodule pushed +
   pointer bumped; eden pushed.

## Current state (updated each milestone)

- **Wave 3A** (in progress, workflow wf_f87fddaa-ba8): leaf libs scaffolded
  (errors ✅green, dependencies ✅green, configuration ⚠️ test build break — see Next actions);
  three new contracts drafted (workspaceprovider, gitrepository, orchestrator); go.work +
  dependent libs (testing, secrets, observability) + verify phase still ahead.
- Done earlier: docs (00–12 + ADRs 0001–0017), document system + validator, frontend v0 (document
  workspace, Eden visual identity C21), agentsession contract, REQ-0001..0024.

## Next actions (my detailed plan — survives loop iterations)

When Wave 3A completes:
1. **Triage** — run gates myself (`go vet`, `go test -race` over libs/go, `gofmt -l`). Fix the
   known `configuration` break: `conformance_test.go` references undefined `cfgtest.Run` /
   `cfgtest.NewParser`; `cfgtest` is a banned abbreviation → must be `configurationtest`. Triage
   the verify agent's other deviations. Dispatch an Opus fixer for anything non-trivial.
   (NOTE: a transient workspace build inconsistency was observed mid-wave — dependent libs'
   go.mod requiring errors@v0.0.0 while being written; clears when 3A finishes; `GOWORK=off`
   isolates. Confirm the whole workspace builds clean post-3A.)
2. **Commit** — commit the six libraries into the `gophersys/libs` submodule, push it; bump the
   submodule pointer in eden; push eden (the three new contract drafts; go.work is gitignored).
3. **Wave 3A.5 — ENFORCEMENT (ADR-0018, C25): build the enforcement layer before the review.**
   Toolchain is already installed (golangci-lint, gofumpt, govulncheck, gorelease, staticcheck).
   Build: the shared `libs/.golangci.yml` (curated strict config — interfacebloat=5, ireturn,
   errcheck/wrapcheck/errorlint, forbidigo banned-token gate, depguard import boundaries, revive,
   etc.); `tools/hnslint` (structural HNS-1 check); the breaking-change gate (gorelease); wire all
   into each library's `ctl.sh` + a tracked `.githooks/` (pre-commit/pre-push) + `.ci/`; build the
   `libs/plugins/project-go` Claude Code plugin (SessionStart contract+rules injection, PostToolUse
   per-file lint, PreToolUse commit gate) + `libs/.claude/rules/`. Run it mechanically against the
   3A libraries and **conform them** (this is where `cfgtest` and friends get caught for real).
4. **Review wave** (ADR-0017, all agents Opus) — now consumes the linter output as its substrate:
   architecture cohesion vs contracts + 10 §6.1; true-coverage audit (flag mock-only/no-shortcut
   violations; list which libs owe real docker/k3d integration tests); adversarial correctness.
   Fix findings.
5. **Verify** green again (gates + enforcement clean); update this STATUS.
6. **Wave 3B (develops UNDER enforcement from birth)** — substrate adapters (docker + k3d, real
   integration tests), git operations, orchestrator v0, agent-session backend service, chat UI,
   Playwright forced-CRUD E2E. Then its review wave. Then verify.
7. Final cleanup + DONE check → push a notification to Mateo.

## Blockers / needs-Mateo

- **setup-token** (REQ-0021): the real claude-code authenticated agent run needs Mateo to run
  `claude setup-token` once interactively. I build and test the full path with a FAKE harness
  adapter; the real adapter is wired but its live run waits for the token. NOT a loop-stopper.

## Cleanup ledger

- Render toolchain lives at `/tmp/eden-render/node_modules` (marked, mermaid, jsdom) — used by
  `docs/tools/*.mjs` via `NODE_PATH`. Consolidate into repo `node_modules` via root `yarn install`
  once safe (deferred while the frontend's install is in flight). Tracked so it's not forgotten.
