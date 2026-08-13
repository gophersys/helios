#!/usr/bin/env bash
#
# libs/templates/_ctl/template.sh — the shared ctl library for every Eden application
# TEMPLATE (the app-side analogue of libs/go/_ctl/lib.sh, ADR-0023).
#
# HNS-1 (10 §5): the directory is `_ctl` (an internal helper, leading-underscore so Go and Nx
# ignore it) and the FILE concept is "the template ctl library" — hence `template.sh`. The banned
# token `common` is deliberately NOT used.
#
# This file is the ONE HOME for an application template's verb bodies + the SDLC phase-gate
# sequencer (ADR-0023). Each per-template `ctl.sh` becomes a thin dispatcher that sets its
# metadata (the template slug, the codegen sub-projects, the coverage floor) and sources this
# file, so the verb bodies are defined exactly once — "one concept, one home" (10 §9). It REUSES
# the ADR-0020 library pipeline shape (architecture → implementation → testing → qa) so an app
# template is engineered to the same bar as a library: no shortcuts, real substrates, the gate
# green before "done".
#
# Contract for the verbs (identical to lib.sh):
#   - set -Eeuo pipefail + shellcheck-clean, matching the house style.
#   - require_cmd the tool a verb needs, so a MISSING tool exits 127 (the FAIL-NOT-SKIP rule,
#     ADR-0020 §enforcement). In the devcontainer every tool is present, so an absence here is a
#     gate failure, never a silent skip.
#   - build/test/integration run WITH the workspace go.work (the unpublished v0.0.0 sibling
#     gophersys/libs/go/* modules only resolve there); the app's own go.mod carries NO
#     module-level replace.
#
# shellcheck shell=bash

set -Eeuo pipefail
IFS=$'\n\t'

# ── template metadata (set by the sourcing per-template ctl.sh BEFORE `template_main`) ───────
# EDEN_TEMPLATE_NAME    — the slug, e.g. "http-gateway" (defaults to the template dir basename).
# EDEN_COVERAGE_FLOOR   — per-package coverage FLOOR as an integer percent (an app is a leaf: 80).
# EDEN_INTEGRATION_CMDS — space-separated tools the integration lane requires (docker k3d kind …).
# EDEN_CODEGEN_PROJECTS — space-separated codegen sub-projects to delegate `generate` to
#                         (relative dirs that carry their own ctl.sh, e.g. "persistence clients/go").
: "${EDEN_TEMPLATE_NAME:=}"
: "${EDEN_COVERAGE_FLOOR:=80}"
: "${EDEN_INTEGRATION_CMDS:=docker}"
: "${EDEN_CODEGEN_PROJECTS:=}"

# PROJECT_ROOT is the per-template directory; the sourcing ctl.sh exports it.
: "${PROJECT_ROOT:?template.sh: PROJECT_ROOT must be set by the sourcing per-template ctl.sh}"

# The workspace go.work that pins the unpublished v0.0.0 sibling libraries lives at the MONOREPO
# root. libs/templates is a git submodule, so the monorepo is the superproject working tree;
# fall back to the submodule toplevel (standalone clone) only if there is no superproject.
_eden_monorepo_root() {
  local sp
  sp="$(cd "$PROJECT_ROOT" && git rev-parse --show-superproject-working-tree 2>/dev/null)" || true
  if [[ -n "$sp" ]]; then printf '%s' "$sp"; return; fi
  cd "$PROJECT_ROOT" && git rev-parse --show-toplevel 2>/dev/null
}
EDEN_GOWORK="${EDEN_GOWORK:-$(_eden_monorepo_root)/go.work}"
if [[ -f "$EDEN_GOWORK" ]]; then
  export GOWORK="${GOWORK:-$EDEN_GOWORK}"
fi

# The shared, strict golangci-lint config lives in the libs submodule root (ADR-0018 Layer 1) —
# one standard, no per-template copy.
EDEN_GOLANGCI_CONFIG="${EDEN_GOLANGCI_CONFIG:-$(_eden_monorepo_root)/libs/.golangci.yml}"

# ── logging ─────────────────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  _LC_INFO=$'\033[0;36m'; _LC_OK=$'\033[0;32m'; _LC_WARN=$'\033[0;33m'
  _LC_ERR=$'\033[0;31m'; _LC_DIM=$'\033[2m'; _LC_RST=$'\033[0m'
else
  _LC_INFO=''; _LC_OK=''; _LC_WARN=''; _LC_ERR=''; _LC_DIM=''; _LC_RST=''
fi
log_info()    { printf '%s[info]%s  %s\n'  "$_LC_INFO" "$_LC_RST" "$*"; }
log_warn()    { printf '%s[warn]%s  %s\n'  "$_LC_WARN" "$_LC_RST" "$*" >&2; }
log_error()   { printf '%s[error]%s %s\n'  "$_LC_ERR"  "$_LC_RST" "$*" >&2; }
log_success() { printf '%s[ok]%s    %s\n'  "$_LC_OK"   "$_LC_RST" "$*"; }
log_dim()     { printf '%s%s%s\n'          "$_LC_DIM"  "$*" "$_LC_RST" >&2; }

# ── tool gate (FAIL-NOT-SKIP, ADR-0020) ─────────────────────────────────────────────────────
# Resolve a tool on PATH or in $(go env GOPATH)/bin (where the pinned Go tools land).
have_cmd() {
  local cmd="$1" p
  if p="$(command -v "$cmd" 2>/dev/null)"; then printf '%s' "$p"; return 0; fi
  if command -v go >/dev/null 2>&1; then
    p="$(go env GOPATH 2>/dev/null)/bin/$cmd"
    [[ -x "$p" ]] && { printf '%s' "$p"; return 0; }
  fi
  return 1
}

# require_cmd <tool...> — every named tool MUST resolve, else exit 127 (FAIL-NOT-SKIP). In the
# devcontainer the tool is guaranteed present, so an absence here is a real gate failure.
require_cmd() {
  local missing=() cmd
  for cmd in "$@"; do
    have_cmd "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    log_dim   "  ADR-0020 FAIL-NOT-SKIP: in the devcontainer these are guaranteed present; install them or run inside ghcr.io/gophersys/base."
    exit 127
  fi
}

# go_in_app <args...> — run a go invocation inside the template WITH the workspace go.work.
go_in_app() { ( cd "$PROJECT_ROOT" && go "$@" ); }

# ── (a) APPLICATION-LOGIC CORRECTNESS — build / test / vet / fmt / lint / cover ──────────────

cmd_build() {
  require_cmd go
  log_info "build: go build ./... (GOWORK=${GOWORK:-unset})"
  go_in_app build ./...
  log_success "build: OK"
}

cmd_test() {
  require_cmd go
  log_info "test: go test ./... -race -count=1 (handler + fake conformance)"
  go_in_app test ./... -race -count=1
  log_success "test: OK"
}

cmd_vet() {
  require_cmd go
  log_info "vet: go vet ./..."
  go_in_app vet ./...
  log_success "vet: OK"
}

cmd_fmt() {
  require_cmd gofumpt
  log_info "fmt: gofumpt -w ."
  ( cd "$PROJECT_ROOT" && "$(have_cmd gofumpt)" -w . )
  log_success "fmt: OK"
}

cmd_lint() {
  require_cmd go gofumpt golangci-lint
  local gofumpt_bin golangci_bin unformatted golangci_rc
  gofumpt_bin="$(have_cmd gofumpt)"; golangci_bin="$(have_cmd golangci-lint)"
  log_info "lint: gofumpt -l ."
  unformatted="$( cd "$PROJECT_ROOT" && "$gofumpt_bin" -l . )"
  if [[ -n "$unformatted" ]]; then
    log_error "gofumpt found unformatted files:"
    printf '  %s\n' "$unformatted" >&2
    exit 1
  fi
  log_info "lint: go vet ./..."
  go_in_app vet ./... || { log_error "go vet reported problems"; exit 1; }
  log_info "lint: golangci-lint run --config $EDEN_GOLANGCI_CONFIG ./... (the shared strict set)"
  # golangci-lint 2.x: 0 clean, 1 findings, anything else the RUN failed (a lost file
  # lock, an invalid config, a panic, an OOM kill). Reporting every non-zero exit as
  # findings sent readers hunting for lint output that was never produced, so the
  # message branches on the code and always names it.
  #
  # The cd reports ITSELF rather than riding `cd … &&`: a failed cd exits the subshell
  # with 1, which the arms below now DEFINE as "findings", so an unreadable PROJECT_ROOT
  # would print the exact lie this branch exists to delete. 120 is outside golangci-lint's
  # documented range (0-7) and outside the shell's exec failures (126/127), so no real run
  # can land on that arm.
  golangci_rc=0
  (
    cd "$PROJECT_ROOT" || { log_error "cannot enter $PROJECT_ROOT — golangci-lint never ran"; exit 120; }
    "$golangci_bin" run --timeout=180s --config "$EDEN_GOLANGCI_CONFIG" ./...
  ) || golangci_rc=$?
  case "$golangci_rc" in
    0)   ;;
    1)   log_error "golangci-lint found issues"; exit 1 ;;
    120) exit 1 ;;  # the cd already named itself
    *)   log_error "golangci-lint failed to run (exit $golangci_rc) — a run failure, not a lint finding"; exit 1 ;;
  esac
  log_success "lint: OK"
}

cmd_cover() {
  require_cmd go
  log_info "cover: go test ./... -coverprofile"
  local profile
  profile="$(mktemp -t "${EDEN_TEMPLATE_NAME:-template}-cover.XXXXXX")"
  go_in_app test ./... -covermode=atomic -coverprofile="$profile"
  ( cd "$PROJECT_ROOT" && go tool cover -func="$profile" | tail -1 )
  rm -f "$profile"
  log_success "cover: OK"
}

# ── (b) CODEGEN — go-first OpenAPI emit + sqlc persistence + the OpenAPI test client ──────────
# OD-16-openapi is resolved GO-FIRST-EMIT (ADR-0023): the five-file route packages' Go types are the
# authoring surface, and contract/openapi.yaml is EMITTED from them by EDEN_OPENAPI_EMITTER. The
# regen chain is openapi (emit the contract) → persistence (sqlc) → clients/go (oapi-codegen the test
# client from the just-emitted contract), so `generate` refreshes the whole generated surface in the
# right order. Each codegen sub-project keeps its own ctl.sh; `generate` orchestrates them.

# EDEN_OPENAPI_EMITTER — the `go run` target of the go-first contract emitter (relative to the
# template root). When set, `openapi`/`verify-openapi` run it and `generate` emits the contract
# FIRST; unset → the template is hand-authored spec-first (the contract is committed, not emitted).
: "${EDEN_OPENAPI_EMITTER:=}"
# EDEN_OPENAPI_CONTRACT — the contract path the emitter writes and the client reads.
: "${EDEN_OPENAPI_CONTRACT:=contract/openapi.yaml}"
# EDEN_CLIENT_PROJECT — the codegen sub-project that runs oapi-codegen over the contract (the typed
# Go test client). `gen-client` delegates to its ctl.sh generate.
: "${EDEN_CLIENT_PROJECT:=clients/go}"

# openapi — EMIT contract/openapi.yaml from the Go route types (go-first-emit). The route packages
# are the source of truth; the YAML is their projection.
cmd_openapi() {
  if [[ -z "$EDEN_OPENAPI_EMITTER" ]]; then
    log_warn "openapi: no EDEN_OPENAPI_EMITTER declared — this template is spec-first (the contract is hand-authored)"
    return 0
  fi
  require_cmd go
  log_info "openapi: emit $EDEN_OPENAPI_CONTRACT from the route types ($EDEN_OPENAPI_EMITTER)"
  go_in_app run "$EDEN_OPENAPI_EMITTER" -mode emit -out "$EDEN_OPENAPI_CONTRACT"
  log_success "openapi: OK"
}

# verify-openapi — re-emit and fail if contract/openapi.yaml drifts from the route types (the
# go-first drift gate: the routes changed but the contract was not regenerated).
cmd_verify_openapi() {
  if [[ -z "$EDEN_OPENAPI_EMITTER" ]]; then
    log_warn "verify-openapi: no EDEN_OPENAPI_EMITTER declared — spec-first template, nothing to verify"
    return 0
  fi
  require_cmd go
  log_info "verify-openapi: $EDEN_OPENAPI_CONTRACT is up to date with the route types"
  go_in_app run "$EDEN_OPENAPI_EMITTER" -mode verify -out "$EDEN_OPENAPI_CONTRACT"
  log_success "verify-openapi: OK"
}

# gen-client — run oapi-codegen (via the client sub-project) to emit the typed Go client FROM the
# contract. The integration lane drives the running handlers through this client.
cmd_gen_client() {
  local dir="$PROJECT_ROOT/$EDEN_CLIENT_PROJECT"
  if [[ ! -x "$dir/ctl.sh" ]]; then
    log_error "gen-client: client sub-project '$EDEN_CLIENT_PROJECT' has no executable ctl.sh at $dir"
    exit 1
  fi
  require_cmd oapi-codegen
  log_info "gen-client: → $EDEN_CLIENT_PROJECT (oapi-codegen the typed client from $EDEN_OPENAPI_CONTRACT)"
  ( cd "$dir" && bash ./ctl.sh generate )
  log_success "gen-client: OK"
}

cmd_generate() {
  # Go-first regen order: emit the contract FROM the routes, then the data layer (sqlc), then the
  # client FROM the just-emitted contract.
  cmd_openapi
  if [[ -z "$EDEN_CODEGEN_PROJECTS" ]]; then
    log_warn "generate: no EDEN_CODEGEN_PROJECTS declared — only the contract was emitted"
    return 0
  fi
  # Word-split EDEN_CODEGEN_PROJECTS on spaces into an array — the file-scoped IFS=$'\n\t'
  # excludes the space, so a bare `for sub in $EDEN_CODEGEN_PROJECTS` would NOT split
  # "persistence clients/go" into its two sub-projects. Read with an explicit IFS=' ' (the same
  # idiom cmd_integration uses for EDEN_INTEGRATION_CMDS) so each sub-project is iterated.
  local codegen_projects
  IFS=' ' read -r -a codegen_projects <<< "$EDEN_CODEGEN_PROJECTS"
  local sub
  for sub in "${codegen_projects[@]}"; do
    local dir="$PROJECT_ROOT/$sub"
    if [[ ! -x "$dir/ctl.sh" ]]; then
      log_error "generate: codegen sub-project '$sub' has no executable ctl.sh at $dir"
      exit 1
    fi
    log_info "generate: → $sub (bash ./ctl.sh generate)"
    ( cd "$dir" && bash ./ctl.sh generate )
  done
  log_success "generate: OK"
}

# ── (d) HOST-LEVERAGING INTEGRATION — the //go:build integration lane, REAL substrate ────────
# REAL postgres (sqlc/pgx) + the deploy substrate; never mocked (ADR-0016 §2). The lane requires
# EDEN_INTEGRATION_CMDS (docker for the ephemeral postgres; k3d/kind when the deploy path is
# exercised) — an absent tool is a gate FAILURE (exit 127), not a skip.
cmd_integration() {
  # Word-split a multi-tool EDEN_INTEGRATION_CMDS into separate require_cmd args (an array, so
  # "docker k3d kind" is three tools, not one) — the same idiom lib.sh uses.
  local integration_cmds
  IFS=' ' read -r -a integration_cmds <<< "$EDEN_INTEGRATION_CMDS"
  require_cmd go "${integration_cmds[@]}"
  log_info "integration: go test -tags integration ./... -race -count=1 (REAL postgres + deploy substrate)"
  go_in_app test -tags integration ./... -race -count=1
  log_success "integration: OK"
}

# ── (h) MAINTAINABILITY — strict lint + hnslint (structural HNS-1) ───────────────────────────
cmd_maintainability() {
  require_cmd hnslint
  cmd_lint
  log_info "maintainability: hnslint (structural HNS-1)"
  # hnslint's whole interface is `hnslint <dir> [dir...]` — a DIRECTORY, never a Go package
  # pattern. `./...` was answered with "./...: not a directory" and exit 1, so this step had
  # never inspected a single file. It is invoked the way the one home invokes it
  # (go/_ctl/lib.sh cmd_maintainability): the tool, then $PROJECT_ROOT.
  "$(have_cmd hnslint)" "$PROJECT_ROOT"
  log_success "maintainability: OK"
}

# ── (f) SECURITY — govulncheck + gosec + gitleaks ────────────────────────────────────────────
cmd_vuln() {
  require_cmd govulncheck
  log_info "vuln: govulncheck ./..."
  ( cd "$PROJECT_ROOT" && "$(have_cmd govulncheck)" ./... )
  log_success "vuln: OK"
}

cmd_sast() {
  require_cmd gosec
  log_info "sast: gosec ./..."
  ( cd "$PROJECT_ROOT" && "$(have_cmd gosec)" -quiet ./... )
  log_success "sast: OK"
}

cmd_secretscan() {
  require_cmd gitleaks
  log_info "secretscan: gitleaks detect"
  ( cd "$PROJECT_ROOT" && "$(have_cmd gitleaks)" detect --no-git --redact --source . )
  log_success "secretscan: OK"
}

# ── the SDLC phase-gate sequencer (ADR-0023, mirrors ADR-0020) ───────────────────────────────
# `phase-gate <architecture|implementation|testing|qa|all>` runs the mechanical gate for one
# phase (or all four 1→4, short-circuiting). Each gate prints a per-step PASS/FAIL so a blind gate
# is visible, never silent. The app-template phases parallel the library phases:
#   architecture   — the contract is frozen: openapi.yaml present + the skeleton compiles.
#   implementation — build + lint + vet + fake conformance GREEN; codegen up to date.
#   testing        — unit + the integration lane on REAL substrate.
#   qa             — cross-cutting gates (vuln/sast/secretscan) + maintainability + no-shortcuts.

# _GATE_FAILED counts the FAILED dimensions of the phase in flight. The phase's exit status is
# taken from this counter, never from the last dimension's rc: every dimension runs so the table
# is complete, so a mid-phase FAIL followed by a passing dimension must still be RED.
_GATE_FAILED=0
_gate_reset() { _GATE_FAILED=0; }

_gate_run() {
  local label="$1"; shift
  printf '%s── phase-gate step: %s%s\n' "$_LC_INFO" "$label" "$_LC_RST" >&2
  # CRITICAL (bash errexit semantics) — the trap go/_ctl/lib.sh:1007-1020 already names and
  # fixes, in the one home this file was the second copy of. A verb like `cmd_build` is
  # `go_in_app build ./… ; log_success`, so its failure is carried ONLY by errexit. errexit is
  # suppressed for a command used as an `if`/`while` condition or on either side of `&&`/`||`,
  # and bash pushes that suppression INTO a subshell run in that position and into the functions
  # the subshell calls — the re-armed `set -Eeuo pipefail` inside the parentheses does NOT
  # restore it. So `if ( set -Eeuo pipefail; "$@" ); then` ran every verb through to
  # `log_success` and recorded PASS for a RED dimension. The only construct that keeps the inner
  # errexit live is: disable errexit locally, run the BARE subshell in a NEUTRAL position, then
  # read `$?` on the next line. `exit 127` (FAIL-NOT-SKIP) propagates as the subshell's 127.
  #
  # The caller's errexit setting is RESTORED rather than hard-set, because this function delivers
  # its verdict through its return status: a caller that reads that status must have errexit off
  # (see _gate_step), and a blind `set -e` here would abort the phase on its first red dimension
  # and hide every dimension after it.
  local shell_flags="$-" rc=0
  set +e
  ( set -e; "$@" )
  rc=$?
  case "$shell_flags" in *e*) set -e ;; esac
  if [[ "$rc" -eq 0 ]]; then
    printf 'PASS\t%s\n' "$label"
    return 0
  fi
  printf 'FAIL\t%s\n' "$label"
  return "$rc"
}

# _gate_step <label> <verb-fn> [args...] — run one dimension and TALLY its verdict, so the phase
# runs every dimension and still exits non-zero. `_gate_run` is called in a NEUTRAL position with
# errexit disabled around it: a `_gate_run … || rc=1` here re-suppresses errexit, and bash carries
# that suppression all the way down into the verb subshell above — which is the defect, restated
# one level up. Phases run with errexit on, so it is restored unconditionally.
_gate_step() {
  local rc=0
  set +e
  _gate_run "$@"
  rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    _GATE_FAILED=$((_GATE_FAILED + 1))
  fi
}

_gate_architecture() {
  _gate_reset
  log_info "phase-gate architecture: frozen contract + compiling skeleton"
  _gate_step "openapi-contract-present" _assert_openapi_present
  _gate_step "skeleton-compiles" cmd_build
  # Go-first-emit (OD-16-openapi): the committed contract must match the route types. A drift means
  # the routes changed but the contract was not re-emitted — the architecture is not frozen-coherent.
  _gate_step "openapi-no-drift" cmd_verify_openapi
  _gate_summary "architecture"
}

_gate_implementation() {
  _gate_reset
  log_info "phase-gate implementation: build + lint + vet + fake conformance"
  _gate_step "build" cmd_build
  _gate_step "vet" cmd_vet
  _gate_step "lint" cmd_lint
  _gate_step "test" cmd_test
  _gate_summary "implementation"
}

_gate_testing() {
  _gate_reset
  log_info "phase-gate testing: unit + REAL-substrate integration"
  _gate_step "test" cmd_test
  _gate_step "integration" cmd_integration
  _gate_step "cover" cmd_cover
  _gate_summary "testing"
}

_gate_qa() {
  _gate_reset
  log_info "phase-gate qa: security + maintainability + no-shortcuts"
  _gate_step "vuln" cmd_vuln
  _gate_step "sast" cmd_sast
  _gate_step "secretscan" cmd_secretscan
  _gate_step "maintainability" cmd_maintainability
  _gate_step "no-shortcuts" _assert_no_shortcuts
  _gate_summary "qa"
}

# _assert_openapi_present — the architecture gate's frozen-contract check: contract/openapi.yaml
# MUST exist (OpenAPI-first, ADR-0023). A missing contract aborts the gate.
_assert_openapi_present() {
  if [[ ! -f "$PROJECT_ROOT/contract/openapi.yaml" ]]; then
    log_error "architecture: contract/openapi.yaml is missing (OpenAPI-first — the contract is the architecture)"
    return 1
  fi
  log_success "architecture: contract/openapi.yaml present"
}

# _assert_no_shortcuts — the qa gate's no-shortcuts grep (ADR-0017): no stub-as-implementation /
# swallowed error / TODO-FIXME on a non-test load path. The skeleton's COMPILING stubs carry a
# `// SKELETON:` marker on the intent comment, never a forbidden tell, so a generated app fails
# this the instant a real route is half-built.
_assert_no_shortcuts() {
  require_cmd rg
  local hits rg_bin
  rg_bin="$(have_cmd rg)"
  # rg exits 1 on no-match (the clean case), so tolerate a non-zero exit; a real match populates hits.
  hits="$(
    cd "$PROJECT_ROOT"
    "$rg_bin" -n --glob '!*_test.go' --glob '!**/generated/**' \
      -e 'panic\("unimplemented"\)' -e 'TODO' -e 'FIXME' -- internal cmd 2>/dev/null
  )" || true
  if [[ -n "$hits" ]]; then
    log_error "no-shortcuts: forbidden tells on a non-test body (ADR-0017):"
    printf '  %s\n' "$hits" >&2
    return 1
  fi
  log_success "no-shortcuts: clean"
}

# _gate_summary <phase> — the phase's verdict, read from the counter rather than from a list of
# rc arguments. The old signature took the rows, and `_gate_architecture` filled them with
# `rows+=("$?") || rc=1` — an append always succeeds, so `rc` was never set and that phase was
# GREEN whatever its dimensions did. A counter has no such silent arm.
_gate_summary() {
  local phase="$1"
  if [[ "$_GATE_FAILED" -eq 0 ]]; then
    log_success "phase-gate $phase: GREEN"
    return 0
  fi
  log_error "phase-gate $phase: RED — $_GATE_FAILED dimension(s) FAILED or REQUIRED-BUT-ABSENT"
  return 1
}

cmd_phase_gate() {
  local phase="${1:-all}"
  case "$phase" in
    architecture)   _gate_architecture ;;
    implementation) _gate_implementation ;;
    testing)        _gate_testing ;;
    qa)             _gate_qa ;;
    all)
      log_info "phase-gate all: architecture → implementation → testing → qa (short-circuit on first failure)"
      # Each phase runs in a NEUTRAL position with errexit disabled around it, for the reason
      # _gate_run states: `_gate_architecture || return 1` suppresses errexit for the whole
      # phase, and bash carries that suppression down into every verb subshell — the `all` path
      # would then report GREEN over exactly the reds the per-phase paths catch.
      local step rc=0
      for step in _gate_architecture _gate_implementation _gate_testing _gate_qa; do
        set +e
        "$step"
        rc=$?
        set -e
        if [[ "$rc" -ne 0 ]]; then
          return 1
        fi
      done
      log_success "phase-gate all: GREEN — the application is done (past phase-gate qa)"
      ;;
    *) log_error "unknown phase: '$phase' (architecture|implementation|testing|qa|all)"; exit 1 ;;
  esac
}

# ── usage + dispatcher (shared; the per-template ctl.sh calls template_main "$@") ─────────────
template_usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

  ${EDEN_TEMPLATE_NAME}: coverage-floor=${EDEN_COVERAGE_FLOOR}% integration=[${EDEN_INTEGRATION_CMDS}]

Core verbs:
  build            Compile the application (go build ./...)
  test             Unit + fake conformance with the race detector
  lint             gofumpt + go vet + golangci-lint (the shared strict set)
  vet              go vet ./...
  fmt              gofumpt -w .
  cover            Tests with coverage; print the total

Codegen (go-first-emit — ADR-0023, OD-16-openapi=go-first-emit):
  openapi          EMIT contract/openapi.yaml from the Go route types
  verify-openapi   re-emit and fail if the contract drifts from the route types
  gen-client       oapi-codegen the typed Go test client from the contract
  generate         openapi + sqlc persistence + gen-client (the full regen chain)

Test taxonomy:
  integration      REAL postgres (sqlc/pgx) + deploy substrate suite
  vuln             govulncheck — 0 applicable vulnerabilities
  sast             gosec — 0 high/medium findings
  secretscan       gitleaks
  maintainability  strict lint + hnslint (structural HNS-1)

SDLC sequencer:
  phase-gate       <architecture|implementation|testing|qa|all> — the mechanical gate
  help             Show this message
EOF
}

template_main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)            cmd_build           "$@" ;;
    test)             cmd_test            "$@" ;;
    lint)             cmd_lint            "$@" ;;
    vet)              cmd_vet             "$@" ;;
    fmt)              cmd_fmt             "$@" ;;
    cover)            cmd_cover           "$@" ;;
    generate)         cmd_generate        "$@" ;;
    openapi)          cmd_openapi         "$@" ;;
    verify-openapi)   cmd_verify_openapi  "$@" ;;
    gen-client)       cmd_gen_client      "$@" ;;
    integration)      cmd_integration     "$@" ;;
    vuln)             cmd_vuln            "$@" ;;
    sast)             cmd_sast            "$@" ;;
    secretscan)       cmd_secretscan      "$@" ;;
    maintainability)  cmd_maintainability "$@" ;;
    phase-gate)       cmd_phase_gate      "$@" ;;
    help|"")          template_usage ;;
    *) log_error "unknown command: '$cmd'"; template_usage; exit 1 ;;
  esac
}
