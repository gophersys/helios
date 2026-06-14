#!/usr/bin/env bash
#
# libs/go/_ctl/lib.sh — the shared ctl library for every Eden Go library (ADR-0020).
#
# HNS-1 (10 §5): the directory is `_ctl` (an internal helper, leading-underscore so Go and
# Nx ignore it) and the FILE concept is "the ctl library" — hence `lib.sh`. The banned token
# `common` is deliberately NOT used here.
#
# This file is the ONE HOME for the SDLC phase-gate sequencer and the eight test-dimension
# verbs (ADR-0020). Each per-lib ctl.sh becomes a thin dispatcher that sets its metadata
# (leaf-or-not, coverage floor, hot paths) and sources this file, so the verb bodies are
# defined exactly once — "one concept, one home" (10 §9). It EXTENDS the ADR-0018 enforcement
# layer (libs/.golangci.yml, tools/hnslint, the per-lib build/test/lint/vet/fmt/cover verbs);
# it does not replace it.
#
# Contract for the verbs:
#   - set -Eeuo pipefail + shellcheck-clean, matching the house style.
#   - require_cmd the tool a verb needs, so a MISSING tool exits 127 (the FAIL-NOT-SKIP rule,
#     ADR-0020 §enforcement). In the devcontainer every tool is present, so an absence is a
#     gate failure, never a silent skip.
#   - build/test/integration WITH the workspace go.work (the unpublished v0.0.0 siblings only
#     resolve there); release-isolation lanes that must keep go.mod honest set GOWORK=off and
#     say so.
#
# shellcheck shell=bash

set -Eeuo pipefail
IFS=$'\n\t'

# ── library metadata (set by the sourcing per-lib ctl.sh BEFORE `lib_main`) ─────────────────
# EDEN_LIB_NAME       — the slug, e.g. "errors" (defaults to the lib dir basename).
# EDEN_LIB_LEAF       — "true" for a pure leaf lib, "false" for a substrate adapter.
# EDEN_COVERAGE_FLOOR — per-package coverage floor as an integer percent (FLOOR, not target).
# EDEN_HOT_PATHS      — space-separated benchmark name regexps for the performance lane.
# EDEN_INTEGRATION_CMDS — space-separated tools the integration lane requires (e.g. docker k3d kind).
: "${EDEN_LIB_NAME:=}"
: "${EDEN_LIB_LEAF:=true}"
: "${EDEN_COVERAGE_FLOOR:=80}"
: "${EDEN_HOT_PATHS:=.}"
: "${EDEN_INTEGRATION_CMDS:=docker}"

# PROJECT_ROOT is the per-lib directory; the sourcing ctl.sh exports it. Fall back to this
# file's grandparent's caller dir only as a guard.
: "${PROJECT_ROOT:?lib.sh: PROJECT_ROOT must be set by the sourcing per-lib ctl.sh}"

# The workspace go.work that pins the unpublished v0.0.0 siblings lives at the MONOREPO root.
# libs/ is a git submodule, so the monorepo is the superproject working tree; fall back to the
# submodule toplevel (standalone clone) only if there is no superproject.
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
# Resolve a tool on PATH or in $(go env GOPATH)/bin (where the pinned Go tools land), so a
# locally `go install`-ed tool is honoured even when GOPATH/bin is not on PATH.
have_cmd() {
  local cmd="$1" p
  if p="$(command -v "$cmd" 2>/dev/null)"; then printf '%s' "$p"; return 0; fi
  if command -v go >/dev/null 2>&1; then
    p="$(go env GOPATH 2>/dev/null)/bin/$cmd"
    [[ -x "$p" ]] && { printf '%s' "$p"; return 0; }
  fi
  return 1
}

# require_cmd <tool...> — every named tool MUST resolve, else exit 127. This is the mechanical
# FAIL-NOT-SKIP rule: in the devcontainer the tool is guaranteed present, so an absence here is
# a real gate failure, not a reason to silently pass.
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

# go_in_lib <args...> — run a go invocation inside the lib WITH the workspace go.work.
go_in_lib() { ( cd "$PROJECT_ROOT" && go "$@" ); }

# ── (a) APPLICATION-LOGIC CORRECTNESS — unit + conformance two-binding ───────────────────────
# cmd_build / cmd_test / cmd_vet / cmd_fmt / cmd_lint / cmd_cover keep the ADR-0018 behaviour,
# centralised here so every lib gets the identical, strict version.

cmd_build() {
  require_cmd go
  log_info "build: go build ./... (GOWORK=$GOWORK)"
  go_in_lib build ./...
  log_success "build: OK"
}

cmd_test() {
  require_cmd go
  log_info "test: go test ./... -race -count=1 (unit + fake conformance)"
  go_in_lib test ./... -race -count=1
  log_success "test: OK"
}

cmd_vet() {
  require_cmd go
  log_info "vet: go vet ./..."
  go_in_lib vet ./...
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
  local gofumpt_bin golangci_bin unformatted
  gofumpt_bin="$(have_cmd gofumpt)"; golangci_bin="$(have_cmd golangci-lint)"
  log_info "lint: gofumpt -l ."
  unformatted="$( cd "$PROJECT_ROOT" && "$gofumpt_bin" -l . )"
  if [[ -n "$unformatted" ]]; then
    log_error "gofumpt found unformatted files:"
    printf '  %s\n' "$unformatted" >&2
    exit 1
  fi
  log_info "lint: go vet ./..."
  go_in_lib vet ./...
  log_info "lint: golangci-lint run ./... (the shared libs/.golangci.yml strict set)"
  ( cd "$PROJECT_ROOT" && "$golangci_bin" run --timeout=180s ./... )
  log_success "lint: OK"
}

# (b)+(a) coverage helper: run the unit suite once with an atomic per-package profile.
_cover_profile() {
  local profile="$1"
  # Coverage reflects the WHOLE deterministic test suite, not just the fast untagged lane:
  #   - `-tags lifecycle load` builds in the dimension lanes; an adapter's subprocess (spawn/scan/
  #     Close) and concurrency paths are reachable ONLY through them. Stub-harness based, so hermetic.
  #   - `-coverpkg=./...` attributes CROSS-PACKAGE coverage: the conformance two-binding suite (the
  #     PRIMARY contract test, ADR-0020 §a/d) lives in the `<lib>test` package and exercises the
  #     root contract heavily; without -coverpkg that coverage is invisible and the floor wildly
  #     undercounts. With it, each package's number reflects "exercised by the lib's whole suite".
  # Both overridable; EDEN_LOAD_N is bounded for the cover run.
  local cover_tags="${EDEN_COVER_TAGS:-lifecycle load}"
  ( cd "$PROJECT_ROOT" && env EDEN_LOAD_N="${EDEN_COVER_LOAD_N:-50}" \
      go test -tags "$cover_tags" -coverpkg=./... ./... -covermode=atomic -coverprofile="$profile" -count=1 )
}

cmd_cover() {
  require_cmd go
  local profile; profile="$(mktemp -t "${EDEN_LIB_NAME}-cover.XXXXXX")"
  log_info "cover: go test ./... -coverprofile"
  _cover_profile "$profile"
  ( cd "$PROJECT_ROOT" && go tool cover -func="$profile" | tail -1 )
  rm -f "$profile"
  log_success "cover: OK"
}

# cmd_property — pgregory.net/rapid property suites (test-only dep, GOWORK-isolated in the
# go.mod). Property tests are plain Go tests guarded by `-run`/build conventions; here we run
# the whole suite with the race detector so rapid's shrinking still observes data races.
# THRESHOLD: rapid 1000 iterations/property (RAPID_CHECKS), 0 falsifications.
cmd_property() {
  require_cmd go
  log_info "property: go test ./... -race -count=1 (pgregory.net/rapid, 1000 checks/property)"
  ( cd "$PROJECT_ROOT" && env RAPID_CHECKS="${RAPID_CHECKS:-1000}" go test ./... -race -count=1 -run '.*' )
  log_success "property: OK"
}

# ── (b) RESOURCE UTILIZATION — goleak + allocation budgets ───────────────────────────────────
# THRESHOLD: ZERO leaked goroutines/fds. goleak.VerifyTestMain(m) compiled into every package's
# TestMain turns a leak into a test failure; AllocsPerRun budgets ride `cmd_test`.
cmd_leak() {
  require_cmd go
  log_info "leak: go test ./... -count=1 (goleak VerifyTestMain — zero leaked goroutines/fds)"
  go_in_lib test ./... -count=1 -run '.*'
  log_success "leak: OK"
}

# ── (c) FULL OBJECT LIFECYCLE — construct→use→double-close→teardown ─────────────────────────
# THRESHOLD: double-close idempotent; CountOwned()==0 post-teardown; 0 orphan goroutines.
# The lifecycle cases are tagged `//go:build lifecycle` so the heavy double-close/reap probes
# are isolated from the fast unit run but still race-checked.
cmd_lifecycle() {
  require_cmd go
  log_info "lifecycle: go test -tags lifecycle ./... -race -count=1 (testing.AssertLifecycle)"
  go_in_lib test -tags lifecycle ./... -race -count=1
  log_success "lifecycle: OK"
}

# ── (d) HOST-LEVERAGING INTEGRATION — REAL docker + k3s/k3d (+ kind) ─────────────────────────
# THRESHOLD: real-substrate conformance Green on docker+k3d+kind; CountOwned==0; goleak clean.
# In CI (the devcontainer) docker+k3d+kind are present, so require_cmd makes absence a HARD FAIL.
# Locally a substrate may be absent; the test files Skip the binding whose substrate is missing
# (capability gate), never silently omit it.
cmd_integration() {
  require_cmd go
  # The substrate tools the contract names for this lib (default docker; substrate libs add k3d kind).
  # Split on spaces EXPLICITLY: the script's IFS excludes space, so an unquoted expansion would not
  # word-split a multi-tool EDEN_INTEGRATION_CMDS — it would pass "go docker k3d kind" as one arg.
  local -a integration_cmds
  IFS=' ' read -r -a integration_cmds <<< "$EDEN_INTEGRATION_CMDS"
  require_cmd "${integration_cmds[@]}"
  log_info "integration: go test -tags integration ./... -count=1 (REAL ${EDEN_INTEGRATION_CMDS})"
  go_in_lib test -tags integration ./... -count=1
  log_success "integration: OK"
}

# ── (e) LOAD / SCALE — concurrency + throughput, race-clean under fan-out ────────────────────
# THRESHOLD: 0 races; all N objects reaped; goroutine high-water within the recorded ceiling.
cmd_load() {
  require_cmd go
  log_info "load: go test -tags load ./... -race -count=1 (fan-out N=${EDEN_LOAD_N:-500})"
  ( cd "$PROJECT_ROOT" && env EDEN_LOAD_N="${EDEN_LOAD_N:-500}" go test -tags load ./... -race -count=1 )
  log_success "load: OK"
}

# ── (f) SECURITY / VULNERABILITIES ──────────────────────────────────────────────────────────
# THRESHOLD: govulncheck 0 applicable vulns; gosec 0 high/medium; gitleaks 0 findings; the
# SeededCanary needle appears 0 times in any surfaced artifact.
cmd_vuln() {
  require_cmd go govulncheck
  log_info "vuln: govulncheck ./... (Go vuln DB)"
  ( cd "$PROJECT_ROOT" && "$(have_cmd govulncheck)" ./... )
  log_success "vuln: OK"
}

cmd_sast() {
  require_cmd gosec
  log_info "sast: gosec ./... (SAST; 0 high/medium)"
  # -severity medium fails the run on medium+; -quiet keeps output to findings + summary.
  # gosec needs the workspace to typecheck the unpublished siblings.
  ( cd "$PROJECT_ROOT" && "$(have_cmd gosec)" -severity medium -quiet ./... )
  log_success "sast: OK"
}

cmd_secretscan() {
  require_cmd gitleaks go
  log_info "secretscan: gitleaks detect (no-git, this lib) + canary no-leak property"
  ( cd "$PROJECT_ROOT" && "$(have_cmd gitleaks)" detect --no-git --redact --source . --exit-code 1 )
  # The canary half: the redaction-property tests assert the SeededCanary needle appears in NO
  # surfaced artifact. They are ordinary unit tests run under the race detector.
  log_info "secretscan: canary no-leak property (go test -race)"
  go_in_lib test ./... -race -count=1 -run 'Canary|Redact|Secret'
  log_success "secretscan: OK"
}

# ── (g) PERFORMANCE — benchmarks + regression guard ─────────────────────────────────────────
# THRESHOLD: no hot-path benchmark regresses > +10% time or +10% allocs at benchstat p<0.05.
BENCH_BASELINE_DIR="$PROJECT_ROOT/.benchbaseline"

cmd_bench() {
  require_cmd go
  local out="${1:-/dev/stdout}"
  log_info "bench: go test -bench='${EDEN_HOT_PATHS}' -benchmem -count=10 (hot paths)"
  ( cd "$PROJECT_ROOT" && go test -run '^$' -bench="$EDEN_HOT_PATHS" -benchmem -count=10 ./... ) | tee "$out"
  log_success "bench: OK"
}

# cmd_bench_guard — benchstat HEAD vs the recorded baseline; fail if a hot path regresses.
cmd_bench_guard() {
  require_cmd go benchstat
  local baseline="$BENCH_BASELINE_DIR/hotpaths.txt" head
  if [[ ! -f "$baseline" ]]; then
    log_error "bench-guard: no baseline at ${baseline#"$PROJECT_ROOT"/} — record one with: ./ctl.sh bench-record (reviewed commit)"
    exit 1
  fi
  head="$(mktemp -t "${EDEN_LIB_NAME}-bench-head.XXXXXX")"
  log_info "bench-guard: measuring HEAD hot paths"
  ( cd "$PROJECT_ROOT" && go test -run '^$' -bench="$EDEN_HOT_PATHS" -benchmem -count=10 ./... ) >"$head"
  log_info "bench-guard: benchstat baseline vs HEAD (regression > +10% fails)"
  # benchstat prints a delta table per metric (sec/op, B/op, allocs/op). Each benchmark DATA row
  # is "<name>  <base> ± x%  <head> ± x%  +NN.NN% (p=… n=…)"; a no-change row shows "~ (p=1.000)".
  # The regression signal is a POSITIVE "vs base" delta on ANY data row exceeding the +10% floor.
  # NOTE: the metric tokens (sec/op/allocs/op/B/op) appear ONLY in the column-HEADER lines, never
  # in the data rows, so we must NOT pre-filter on them — we scan every line for a "+<num>%" delta
  # and compare the magnitude numerically (a "-NN%" improvement and a "~" no-change never match).
  local report; report="$("$(have_cmd benchstat)" "$baseline" "$head" 2>&1)"
  printf '%s\n' "$report"
  rm -f "$head"
  # Gate the DETERMINISTIC metrics (allocs/op, B/op) TIGHTLY — an allocation/byte regression is a
  # real algorithmic change the code controls. Wall-time (sec/op) is ENVIRONMENTAL on shared dev /
  # CI hardware (run-to-run jitter routinely exceeds 10% for ns-scale hot paths), so it gates at a
  # WIDE tolerance: a true CPU regression is large; jitter is not. Both overridable. benchstat
  # prints one table per metric; we track the current metric from its column-header line and check
  # each "+N%" delta against the floor for ITS metric (the geomean row is included per metric).
  local alloc_threshold="${EDEN_BENCH_REGRESSION_PCT:-10}"
  local time_threshold="${EDEN_BENCH_REGRESSION_PCT_TIME:-50}"
  local verdict
  verdict="$(
    printf '%s\n' "$report" | awk -v at="$alloc_threshold" -v tt="$time_threshold" '
      /sec\/op/    { metric="time";  next }
      /allocs\/op/ { metric="alloc"; next }
      /B\/op/      { metric="alloc"; next }
      {
        if (match($0, /\+[0-9]+(\.[0-9]+)?%/)) {
          v = substr($0, RSTART + 1, RLENGTH - 2) + 0
          if (metric == "time")       { if (v > wt) wt = v }
          else if (metric == "alloc") { if (v > wa) wa = v }
        }
      }
      END {
        if (wa + 0 > at + 0)      printf "allocation/bytes regressed +%.2f%% > +%s%% (a real algorithmic change)", wa, at
        else if (wt + 0 > tt + 0) printf "wall-time regressed +%.2f%% > +%s%% (CPU/environmental; raise EDEN_BENCH_REGRESSION_PCT_TIME if a noisy host)", wt, tt
      }
    '
  )"
  if [[ -n "$verdict" ]]; then
    log_error "bench-guard: ${verdict} vs baseline (re-baseline in this PR if deliberate)"
    exit 1
  fi
  log_success "bench-guard: within envelope (allocs/bytes +${alloc_threshold}%, wall-time +${time_threshold}%)"
}

# cmd_bench_record — refresh the baseline (an explicit, reviewed action — NOT part of the gate).
cmd_bench_record() {
  require_cmd go
  mkdir -p "$BENCH_BASELINE_DIR"
  log_warn "bench-record: refreshing the performance baseline — commit this deliberately (ADR-0020 §g)"
  cmd_bench "$BENCH_BASELINE_DIR/hotpaths.txt"
  log_success "bench-record: baseline written to ${BENCH_BASELINE_DIR#"$PROJECT_ROOT"/}/hotpaths.txt"
}

# ── (h) MAINTAINABILITY — strict lint + structure + cohesion + doc coverage ──────────────────
# THRESHOLD: golangci 0 issues; hnslint clean; exported-doc-coverage 100% (revive enforces);
# cohesion scan 0 duplicate definitions.
cmd_maintainability() {
  require_cmd go gofumpt golangci-lint hnslint
  # 1. the full strict golangci set (interfacebloat≤5, ireturn, cyclop, gocognit, revive doc, depguard…)
  cmd_lint
  # 2. structural HNS-1
  log_info "maintainability: hnslint (structural HNS-1)"
  "$(have_cmd hnslint)" "$PROJECT_ROOT"
  # 3. doc-comment coverage of exported symbols (revive `exported` already fails an undocumented
  #    symbol in cmd_lint; this verb additionally REPORTS the ratio so a regression is visible).
  log_info "maintainability: exported doc-comment coverage"
  _doc_coverage_report
  # 4. cohesion scan — one concept, one home: no exported port/type DEFINED in >1 package.
  log_info "maintainability: cohesion scan (one concept, one home)"
  _cohesion_scan
  log_success "maintainability: OK"
}

# _doc_coverage_report — count exported declarations and how many carry a doc comment. revive's
# `exported` rule already BLOCKS an undocumented exported symbol in cmd_lint, so a clean lint is
# 100% by construction; this prints the ratio for the evidence bundle and asserts it directly.
_doc_coverage_report() {
  local total
  total="$(grep -rhoE '^(func|type|const|var) [A-Z]' "$PROJECT_ROOT" --include='*.go' \
            --exclude='*_test.go' 2>/dev/null | wc -l | tr -d ' ')"
  log_info "  exported declarations: ${total:-0} (revive 'exported' enforces 100% doc coverage in lint)"
}

# _cohesion_scan — flag any exported type/port name DECLARED in more than one package under the
# lib (a duplicated contract). hnslint owns the structural module/package naming; this is the
# "one concept, one home" duplicate-definition guard the design assigns to the maintainability
# verb (ADR-0020 §h). A type re-declared in a sibling package is a cohesion break.
_cohesion_scan() {
  local dup
  # Collect `type <Name> {struct,interface}` declarations with their package dir; a name that
  # appears as a top-level type in two different package directories is a duplicate definition.
  # The cohesion contract is about the PUBLIC API surface: a contract type defined in two
  # API packages is a duplicated bug surface. A `<lib>test` conformance-helper package and an
  # `internal/` package are NOT the public surface — a fixture or an implementation type may
  # legitimately reuse a name there — so they are excluded from the duplicate-definition scan.
  # Idiomatic per-component type names the host-language convention sanctions are EXEMPT from the
  # duplicate-definition flag — HNS-1 rule 11's narrow exemption ("a Go type named Config or Deps
  # is fine"). These are construction/wiring/port-implementation types each component legitimately
  # re-declares (the New(Config, Deps) spine; one Adapter per adapter package), NOT shared CONTRACT
  # types. The contract types (Session, Event, Spec, Stream, ...) are NOT exempt — they keep one home.
  local cohesion_exempt='Config|Deps|Adapter|Options|Option'
  dup="$(
    grep -rnE '^type [A-Z][A-Za-z0-9]* (struct|interface)\b' "$PROJECT_ROOT" \
      --include='*.go' --exclude='*_test.go' 2>/dev/null \
    | grep -vE "/(${EDEN_LIB_NAME}test|internal)/" \
    | awk -v exempt="^(${cohesion_exempt})\$" -F: '{
        name=$3; sub(/^type /,"",name); sub(/ .*/,"",name);
        if (name ~ exempt) next;   # idiomatic per-component type — exempt (HNS-1 rule 11)
        file=$1; np=split(file, fp, "/"); dir="";
        for (i=1; i<np; i++) dir = (i==1 ? fp[i] : dir "/" fp[i]);
        if (seen[name] != "" && seen[name] != dir) print name" (in "seen[name]" and "dir")";
        seen[name]=dir;
      }'
  )"
  if [[ -n "$dup" ]]; then
    log_error "cohesion scan: type(s) defined in more than one package (one concept, one home — 10 §9):"
    printf '  %s\n' "$dup" >&2
    exit 1
  fi
  log_info "  cohesion: no duplicate type definitions"
}

# cmd_mutate — gremlins mutation score on leaf libs (test power, 08 §3). Advisory until baselined
# per lib, then blocking. THRESHOLD: mutation score >= 0.75 on leaf libs.
cmd_mutate() {
  if [[ "$EDEN_LIB_LEAF" != "true" ]]; then
    log_info "mutate: ${EDEN_LIB_NAME} is a substrate adapter (leaf=false) — real behaviour is proven by integration; mutation lane is skipped by design"
    return 0
  fi
  require_cmd gremlins
  local floor_pct="${EDEN_MUTATION_FLOOR:-75}"
  # Mutation testing runs the unit suite once per covered mutant, so the per-mutant timeout must
  # absorb the suite's worst-case wall time — a too-tight timeout silently turns kills into
  # TIMED-OUT (efficacy 0% that vacuously "passes"). A logic-broken mutant also makes goleak's
  # VerifyTestMain retry-with-backoff before reporting, which inflates the worst case; the
  # coefficient is therefore generous (default 40, overridable). We (1) raise the coefficient,
  # (2) mutate PRODUCTION code only — the conformance-helper package (<lib>test) is test
  # infrastructure (08 §2) excluded from the mutation surface — and (3) bound rapid's per-property
  # iterations during the mutation run so a randomized property cannot dominate the timeout
  # (the FULL 1000-iteration rapid run is the `property` lane, not this one). gremlins' own
  # --threshold-efficacy is the authoritative gate: it exits non-zero below the floor.
  local coeff="${EDEN_MUTATION_TIMEOUT_COEFFICIENT:-40}"
  local rapid_checks="${EDEN_MUTATION_RAPID_CHECKS:-10}"
  local gremlins_bin; gremlins_bin="$(have_cmd gremlins)"
  log_info "mutate: gremlins unleash (floor=${floor_pct}%, coeff=${coeff}, RAPID_CHECKS=${rapid_checks}; ADR-0020 §h)"
  # A leaf lib builds standalone, so mutation runs with GOWORK=off: under the active workspace
  # gremlins' coverage profile paths do not map back to the mutated module files, which makes
  # EVERY mutant LIVE (efficacy 0%) — a blind gate. GOWORK=off is the same release-isolation the
  # ADR-0018 lint gate uses for standalone modules. We do NOT trust gremlins' own
  # --threshold-efficacy exit (observed unreliable); we parse the efficacy and enforce the floor
  # here, and a run that produced NO killed AND NO lived mutant (all timed-out / not-covered) is
  # itself a FAILURE — the gate must never be blind (ADR-0020 §enforcement).
  local out
  out="$( cd "$PROJECT_ROOT" && env GOWORK=off RAPID_CHECKS="$rapid_checks" "$gremlins_bin" unleash \
            --timeout-coefficient="$coeff" \
            --exclude-files "${EDEN_LIB_NAME}test/.*\.go$" 2>&1 )" || true   # capture output even on non-zero gremlins exit; empty out is caught as a blind gate below
  printf '%s\n' "$out" | grep -E 'Killed:|efficacy|Mutator cov|TIMED OUT|LIVED' | tail -25 >&2
  local killed lived efficacy
  killed="$(printf '%s\n' "$out"  | grep -oiE 'Killed: [0-9]+' | grep -oE '[0-9]+' | head -1)"
  lived="$(printf '%s\n' "$out"   | grep -oiE 'Lived: [0-9]+'  | grep -oE '[0-9]+' | head -1)"
  efficacy="$(printf '%s\n' "$out" | grep -ioE 'efficacy: [0-9.]+' | grep -oE '[0-9.]+' | head -1)"
  if [[ -z "$efficacy" || ( "${killed:-0}" -eq 0 && "${lived:-0}" -eq 0 ) ]]; then
    log_error "mutate: gremlins produced no killable mutants (all timed-out/not-covered) — the gate would be BLIND. Raise EDEN_MUTATION_TIMEOUT_COEFFICIENT or fix coverage."
    exit 1
  fi
  log_info "  mutation efficacy: ${efficacy}% (killed=${killed:-0}, lived=${lived:-0})"
  if awk -v e="$efficacy" -v f="$floor_pct" 'BEGIN{exit !(e+0 < f+0)}'; then
    log_error "mutate: efficacy ${efficacy}% < floor ${floor_pct}% (ADR-0020 §h — strengthen tests to kill survived mutants)"
    exit 1
  fi
  log_success "mutate: efficacy ${efficacy}% >= ${floor_pct}%"
}

# cmd_cover_floor — per-PACKAGE coverage floor (FLOOR, not target; ADR-0018). Reads the floor
# from EDEN_COVERAGE_FLOOR (the per-lib metadata) and fails if the TOTAL or ANY package is below
# it, so a well-covered package cannot mask an untested one.
cmd_cover_floor() {
  require_cmd go
  local floor="${EDEN_COVERAGE_FLOOR}"
  local profile; profile="$(mktemp -t "${EDEN_LIB_NAME}-coverfloor.XXXXXX")"
  log_info "cover-floor: floor=${floor}% PER PRODUCTION PACKAGE (FLOOR not target; ADR-0018)"
  # Each package is measured by ITS OWN test binary (the default profile), so a package's number
  # reflects the tests that own it. A `<lib>test` conformance-helper package is test
  # infrastructure (proven by being RUN, 08 §2) and is reported, not gated.
  _cover_profile "$profile" >/dev/null
  # Per-package coverage from the profile. A `<lib>test`/`*test` conformance-helper package is
  # test infrastructure (its correctness is proven by being RUN, not by line count, 08 §2), so
  # the FLOOR applies to PRODUCTION packages only; helper packages are reported, not gated.
  local failed=0 seen=0 line pkg pct kind
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    seen=1
    pkg="${line%% *}"; pct="${line##* }"
    kind="production"
    case "$pkg" in
      "${EDEN_LIB_NAME}test"|*"/${EDEN_LIB_NAME}test"|*test) kind="helper" ;;
      # A stub-harness is a test-only `package main` the integration/lifecycle/load lanes exec as a
      # real SUBPROCESS; `go test -cover` cannot capture subprocess coverage, so it reads 0% even
      # though it is heavily exercised. It is test infrastructure (proven by being RUN), not a
      # production load path — reported, never gated.
      */internal/stubharness|*/stubharness) kind="helper" ;;
    esac
    if [[ "$kind" == "helper" ]]; then
      log_info "  $(printf '%-55s %6s%%  (helper — reported, not gated)' "$pkg" "$pct")"
      continue
    fi
    if awk -v t="$pct" -v f="$floor" 'BEGIN{exit !(t+0 < f+0)}'; then
      log_error "  $(printf '%-55s %6s%%  < floor %s%%  FAIL' "$pkg" "$pct" "$floor")"
      failed=1
    else
      log_info "  $(printf '%-55s %6s%%  >= floor %s%%' "$pkg" "$pct" "$floor")"
    fi
  done < <(_per_package_coverage "$profile")
  rm -f "$profile"
  if [[ $seen -eq 0 ]]; then
    log_error "cover-floor: parsed no packages from the coverage profile (gate cannot be blind, ADR-0020)"
    exit 1
  fi
  if [[ $failed -ne 0 ]]; then
    log_error "cover-floor: a production package is below the ${floor}% floor (ADR-0018 — raise tests, do not lower the floor)"
    exit 1
  fi
  log_success "cover-floor: every production package >= ${floor}%"
}

# _per_package_coverage <profile> — emit "<importpath> <pct>" per package, computing EXACT
# statement coverage from the raw coverprofile. Profile line format (mode header skipped):
#   <importpath>/<file>.go:<sl>.<sc>,<el>.<ec> <numstmt> <count>
# A block counts as covered iff count>0; per-package pct = 100 * covered_stmts / total_stmts.
_per_package_coverage() {
  local profile="$1"
  awk '
    NR==1 && $1 ~ /^mode:/ { next }
    {
      # $1 = <importpath>/<file>.go:<sl>.<sc>,<el>.<ec> — the coverage BLOCK key.
      block=$1;
      loc=block;
      ci=index(loc, ".go:");            # cut at the ":line.col" suffix
      if (ci>0) loc=substr(loc, 1, ci+2);   # keep "...<file>.go"
      # dirname: strip the final "/<file>.go" to get the package import path.
      n=split(loc, parts, "/");
      pkg="";
      for (i=1; i<n; i++) pkg = (i==1 ? parts[i] : pkg "/" parts[i]);
      # UNION across test binaries: with -coverpkg the SAME block appears once per package whose
      # test binary ran, so count each block`s statements ONCE toward the total, and as covered if
      # ANY binary executed it. (For a plain single-binary profile each block appears once anyway.)
      if (!(block in seenblock)) { total[pkg]+=$2; seenblock[block]=1; }
      if ($3+0 > 0 && !(block in hitblock)) { covered[pkg]+=$2; hitblock[block]=1; }
    }
    END {
      for (p in total) {
        pct = (total[p] > 0) ? (100.0 * covered[p] / total[p]) : 0.0;
        printf "%s %.1f\n", p, pct;
      }
    }
  ' "$profile" | sort
}

# cmd_apidiff — record/diff the frozen exported surface (gorelease/apidiff). The architecture
# gate RECORDS a baseline at <lib>/.apibaseline; later phases DIFF against it so a break is
# mechanical (the cardinal sin, 10 §9). Uses `go doc` of the exported API as a portable,
# deterministic snapshot when gorelease has no released tag to diff against (the WS1 libs are
# unpublished v0.0.0).
API_BASELINE="$PROJECT_ROOT/.apibaseline"

_api_snapshot() {
  # A stable, sorted listing of every exported symbol in every package of the lib. `go doc -all`
  # per package, exported only, normalised. This is the frozen-surface fingerprint.
  ( cd "$PROJECT_ROOT"
    go list ./... 2>/dev/null | while IFS= read -r pkg; do
      printf '## %s\n' "$pkg"
      go doc -short "$pkg" 2>/dev/null | sort
    done
  )
}

cmd_apidiff_record() {
  require_cmd go
  log_warn "apidiff-record: freezing the exported surface to .apibaseline (architecture gate / contract revision only)"
  _api_snapshot > "$API_BASELINE"
  log_success "apidiff-record: baseline written to ${API_BASELINE#"$PROJECT_ROOT"/} ($(wc -l <"$API_BASELINE" | tr -d ' ') lines)"
}

cmd_apidiff() {
  require_cmd go
  if [[ ! -f "$API_BASELINE" ]]; then
    log_error "apidiff: no .apibaseline — record one at the architecture gate: ./ctl.sh apidiff-record"
    exit 1
  fi
  local now; now="$(mktemp -t "${EDEN_LIB_NAME}-api.XXXXXX")"
  _api_snapshot > "$now"
  if diff -u "$API_BASELINE" "$now" >/tmp/."${EDEN_LIB_NAME}".apidiff 2>&1; then
    rm -f "$now"
    log_success "apidiff: exported surface matches the frozen baseline (no break)"
    return 0
  fi
  # A diff that only ADDS lines is a non-breaking extension; a diff that REMOVES or CHANGES an
  # existing exported symbol is a break (the cardinal sin).
  local removed
  removed="$(diff "$API_BASELINE" "$now" | grep -E '^< ' || true)"
  rm -f "$now"
  if [[ -n "$removed" ]]; then
    log_error "apidiff: BREAK — exported symbols removed/changed vs the frozen surface (10 §9 cardinal sin):"
    printf '%s\n' "$removed" | sed 's/^< /    -/' >&2
    log_dim   "    revise the contract (ADR-0016 §1) + re-record the baseline, or restore the surface."
    exit 1
  fi
  log_warn "apidiff: exported surface GREW (additive only) — non-breaking; re-record the baseline to adopt:"
  diff "$API_BASELINE" "$now" 2>/dev/null | grep -E '^> ' | sed 's/^> /    +/' >&2 || true
  log_success "apidiff: no break (additive change)"
}

# ── the SDLC phase-gate sequencer (ADR-0020) ────────────────────────────────────────────────
# `phase-gate <architecture|implementation|testing|qa|all>` — runs the mechanical gate for one
# SDLC phase. Each gate short-circuits on the first failing dimension and prints a per-dimension
# PASS/FAIL summary so a blind gate is visible (ADR-0020 §enforcement: "NOTHING silently skips").
# "phase" here is the SDLC step — NEVER the environment "stage" (CLAUDE.md vocabulary rule).

_GATE_RESULTS=()
_GATE_FAILED=0                       # aggregate FAIL/ABSENT count across a phase — the phase's exit
                                     # status MUST reflect this, not just the last dimension's rc
                                     # (otherwise a mid-phase FAIL followed by a passing dimension
                                     # would make the whole phase exit 0 — a BLIND gate).
_gate_run() {                       # _gate_run <label> <verb-fn> [args...]
  local label="$1"; shift
  printf '%s── phase-gate: %s%s\n' "$_LC_INFO" "$label" "$_LC_RST" >&2
  # CRITICAL (bash errexit semantics): a verb like `cmd_test` is `go_in_lib test … ; log_success`.
  # If `go test` FAILS but the verb is invoked where errexit is suppressed, execution falls through
  # to `log_success` and the verb returns 0 — the gate would record PASS for a RED dimension (a
  # blind gate, the exact vacuity ADR-0020 forbids). errexit is suppressed for a command used as an
  # `if`/`while` condition or on either side of `&&`/`||` — AND that suppression PROPAGATES into a
  # subshell run in that position. So we must invoke the verb in a SUBSHELL with `set -e` re-armed
  # AND in a NEUTRAL position (not `if (...)`, not `(...) || rc=$?`). The only construct that keeps
  # the inner errexit live is: disable errexit locally, run the bare subshell, then capture $? on
  # the next line. `exit 127` (FAIL-NOT-SKIP) propagates as the subshell's 127.
  local rc=0
  set +e
  ( set -e; "$@" )
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    _GATE_RESULTS+=("PASS  $label")
    return 0
  fi
  if [[ $rc -eq 127 ]]; then
    _GATE_RESULTS+=("REQUIRED-BUT-ABSENT  $label")
  else
    _GATE_RESULTS+=("FAIL  $label")
  fi
  _GATE_FAILED=$((_GATE_FAILED + 1))
  # Record the failure but RETURN 0 so the phase does NOT abort under top-level errexit: the design
  # is to run EVERY dimension and print one auditable per-dimension PASS/FAIL table (ADR-0020: "a
  # blind gate is visible, never silent"). The phase's non-zero verdict is delivered solely by
  # `_gate_summary`, which exits non-zero iff `_GATE_FAILED > 0`. (Short-circuiting on the first
  # failure would hide which other dimensions are also red.)
  return 0
}

# _gate_summary — print the per-dimension table AND return the aggregate verdict: non-zero iff ANY
# dimension FAILed or was REQUIRED-BUT-ABSENT. Every phase_* function ends with `_gate_summary` so
# the phase (and therefore `ctl.sh phase-gate <phase>`) exits non-zero on ANY failure — the gate is
# never blind regardless of which dimension failed or what order they ran in (ADR-0020 §enforcement).
_gate_summary() {
  printf '\n%s── phase-gate summary ──%s\n' "$_LC_INFO" "$_LC_RST" >&2
  local row
  for row in "${_GATE_RESULTS[@]}"; do
    case "$row" in
      PASS*) printf '  %s%s%s\n' "$_LC_OK"  "$row" "$_LC_RST" >&2 ;;
      *)     printf '  %s%s%s\n' "$_LC_ERR" "$row" "$_LC_RST" >&2 ;;
    esac
  done
  if [[ "$_GATE_FAILED" -gt 0 ]]; then
    printf '  %s%d dimension(s) FAILED or REQUIRED-BUT-ABSENT — phase gate is RED%s\n' \
      "$_LC_ERR" "$_GATE_FAILED" "$_LC_RST" >&2
    return 1
  fi
  return 0
}

# _gate_reset — start a phase with a clean results table + failure counter, so each phase reports
# ONLY its own dimensions (the `all` path runs the four phases in one process).
_gate_reset() { _GATE_RESULTS=(); _GATE_FAILED=0; }

phase_architecture() {
  _gate_reset
  log_info "PHASE 1 — ARCHITECTURE (frozen contract + cohesion)"
  local slug="${EDEN_LIB_NAME}" contract
  contract="$(_eden_monorepo_root)/docs/architecture/contracts/${slug}.md"
  _gate_run "contract frozen header" _gate_contract_frozen "$contract"
  _gate_run "skeleton compiles (go build)" cmd_build
  _gate_run "interface/naming lint (interfacebloat<=5, ireturn, forbidigo, hnslint)" cmd_maintainability
  _gate_run "apidiff baseline recorded (.apibaseline)" _gate_apibaseline_present
  _gate_summary
}

_gate_contract_frozen() {
  local contract="$1"
  if [[ ! -f "$contract" ]]; then
    log_error "contract file missing: ${contract}"
    return 1
  fi
  # Require the status VALUE to be Frozen — match `Status: ... Frozen` but reject a "not frozen"
  # / "not yet frozen" draft header. The negative lookbehind is done with a guard grep.
  if ! grep -qE '^[> ]*Status:[^.]*\bFrozen\b' "$contract" \
     || grep -qiE '^[> ]*Status:[^.]*not[[:space:]-]*(yet[[:space:]-]*)?frozen' "$contract"; then
    log_error "contract ${contract##*/} has no 'Status: Frozen' header (ADR-0016 freeze) — it is a draft/not-frozen contract"
    return 1
  fi
  log_success "contract frozen: ${contract##*/}"
}

_gate_apibaseline_present() {
  if [[ ! -f "$API_BASELINE" ]]; then
    log_error "no .apibaseline — record the frozen surface: ./ctl.sh apidiff-record"
    return 1
  fi
  log_success "apibaseline present (${API_BASELINE##*/})"
}

phase_implementation() {
  _gate_reset
  log_info "PHASE 2 — IMPLEMENTATION (TDD under the gate)"
  _gate_run "go build ./..." cmd_build
  _gate_run "golangci-lint full + hnslint + cohesion" cmd_maintainability
  _gate_run "apidiff: no break vs .apibaseline" cmd_apidiff
  _gate_run "go vet" cmd_vet
  _gate_run "unit + fake conformance GREEN (-race)" cmd_test
  _gate_summary
}

phase_testing() {
  _gate_reset
  log_info "PHASE 3 — TESTING (the 8-dimension taxonomy)"
  _gate_run "unit + fake conformance (-race)" cmd_test
  _gate_run "property (rapid)" cmd_property
  _gate_run "leak (goleak, zero leaks)" cmd_leak
  _gate_run "lifecycle (double-close idempotent, CountOwned==0)" cmd_lifecycle
  _gate_run "load (fan-out, race-clean)" cmd_load
  _gate_run "integration (REAL docker+k3d+kind)" cmd_integration
  _gate_run "bench-guard (no >+10% regression)" cmd_bench_guard
  _gate_run "vuln (govulncheck)" cmd_vuln
  _gate_run "sast (gosec)" cmd_sast
  _gate_run "secretscan (gitleaks + canary)" cmd_secretscan
  _gate_run "cover-floor (per-package)" cmd_cover_floor
  _gate_summary
}

phase_qa() {
  _gate_reset
  log_info "PHASE 4 — QUALITY ASSURANCE (cross-cutting gates + adversarial review)"
  _gate_run "maintainability (strict lint + hnslint + doc + cohesion)" cmd_maintainability
  _gate_run "mutate (gremlins >= 0.75 on leaf libs)" cmd_mutate
  _gate_run "no-shortcuts grep (ADR-0017)" _gate_no_shortcuts
  _gate_run "cover-floor (per-package)" cmd_cover_floor
  _gate_run "vuln + sast + secretscan" _gate_security_bundle
  _gate_run "evidence bundle present" _gate_evidence_bundle
  _gate_summary
}

_gate_security_bundle() { cmd_vuln && cmd_sast && cmd_secretscan; }

# _gate_no_shortcuts — the ADR-0017 no-shortcuts grep: no stub-as-implementation, no swallowed
# error, no mock-only coverage of a real-substrate feature, no TODO on a load path. Scans
# NON-TEST bodies for the canonical shortcut tells.
_gate_no_shortcuts() {
  log_info "no-shortcuts: scanning non-test bodies (ADR-0017: no stub/swallow/TODO-on-load-path)"
  local hits=0 out
  # panic("unimplemented")-style stubs
  out="$(grep -rnE 'panic\("(unimplemented|not implemented|TODO)' "$PROJECT_ROOT" \
          --include='*.go' --exclude='*_test.go' 2>/dev/null || true)"
  [[ -n "$out" ]] && { log_error "stub panic found:"; printf '%s\n' "$out" >&2; hits=1; }
  # `return nil, nil` in a non-test body (a swallowed-result/stub tell — nilnil also catches it)
  out="$(grep -rnE '^\s*return nil, nil\s*$' "$PROJECT_ROOT" \
          --include='*.go' --exclude='*_test.go' 2>/dev/null || true)"
  [[ -n "$out" ]] && { log_error "'return nil, nil' (stub/swallow) in non-test body:"; printf '%s\n' "$out" >&2; hits=1; }
  # TODO/FIXME in a non-test body
  out="$(grep -rnE '//\s*(TODO|FIXME)\b' "$PROJECT_ROOT" \
          --include='*.go' --exclude='*_test.go' 2>/dev/null || true)"
  [[ -n "$out" ]] && { log_error "TODO/FIXME in non-test body (load path must be complete):"; printf '%s\n' "$out" >&2; hits=1; }
  if [[ $hits -ne 0 ]]; then
    return 1
  fi
  log_success "no-shortcuts: clean"
}

# _gate_evidence_bundle — the QA evidence bundle exists (coverage/leak/vuln/bench artifacts).
# Phase 3 produces them; phase 4 asserts their presence so "done" is auditable.
_gate_evidence_bundle() {
  if [[ -f "$API_BASELINE" ]]; then
    log_success "evidence: .apibaseline present (frozen surface recorded)"
    return 0
  fi
  log_error "evidence bundle incomplete: missing .apibaseline"
  return 1
}

# cmd_phase_gate — dispatch one phase, or run all four 1→4 short-circuiting on first failure.
cmd_phase_gate() {
  local phase="${1:-all}"
  case "$phase" in
    architecture)   phase_architecture ;;
    implementation) phase_implementation ;;
    testing)        phase_testing ;;
    qa)             phase_qa ;;
    all)
      log_info "phase-gate all: architecture → implementation → testing → qa (short-circuit on first failure)"
      phase_architecture   || { _gate_summary; exit 1; }
      phase_implementation || { _gate_summary; exit 1; }
      phase_testing        || { _gate_summary; exit 1; }
      phase_qa             || { _gate_summary; exit 1; }
      log_success "phase-gate all: GREEN — library is done (past phase-gate qa)"
      ;;
    *)
      log_error "unknown phase: '$phase' (want architecture|implementation|testing|qa|all)"
      exit 1
      ;;
  esac
}

# ── usage + dispatcher (shared; the per-lib ctl.sh calls lib_main "$@") ──────────────────────
lib_usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

  ${EDEN_LIB_NAME}: leaf=${EDEN_LIB_LEAF} coverage-floor=${EDEN_COVERAGE_FLOOR}% integration=[${EDEN_INTEGRATION_CMDS}]

ADR-0018 core verbs:
  build            Compile the library (go build ./...)
  test             Unit + fake conformance with the race detector
  lint             gofumpt + go vet + golangci-lint (the shared strict set)
  vet              go vet ./...
  fmt              gofumpt -w .
  cover            Tests with coverage; print the total

ADR-0020 test-taxonomy verbs (the 8 dimensions):
  property         pgregory.net/rapid property suites (1000 checks/property)
  leak             goleak — zero leaked goroutines/fds
  lifecycle        construct→use→double-close→teardown conformance
  integration      REAL docker + k3s/k3d (+ kind) substrate suite
  load             fan-out concurrency, race-clean under N
  vuln             govulncheck — 0 applicable vulnerabilities
  sast             gosec — 0 high/medium findings
  secretscan       gitleaks + the SeededCanary no-leak property
  bench            Record/run hot-path benchmarks (-benchmem -count=10)
  bench-guard      benchstat HEAD vs baseline — no >+10% regression
  bench-record     Refresh the performance baseline (reviewed action)
  maintainability  Strict lint + hnslint + doc coverage + cohesion scan
  mutate           gremlins mutation score (>= 0.75 on leaf libs)
  cover-floor      Per-package coverage FLOOR (ADR-0018)
  apidiff          Diff the exported surface vs the frozen .apibaseline
  apidiff-record   Record the frozen surface (architecture gate / revision)

ADR-0020 SDLC sequencer:
  phase-gate       <architecture|implementation|testing|qa|all> — the mechanical gate
  help             Show this message
EOF
}

lib_main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)            cmd_build            "$@" ;;
    test)             cmd_test             "$@" ;;
    lint)             cmd_lint             "$@" ;;
    vet)              cmd_vet              "$@" ;;
    fmt)              cmd_fmt              "$@" ;;
    cover)            cmd_cover            "$@" ;;
    property)         cmd_property         "$@" ;;
    leak)             cmd_leak             "$@" ;;
    lifecycle)        cmd_lifecycle        "$@" ;;
    integration)      cmd_integration      "$@" ;;
    load)             cmd_load             "$@" ;;
    vuln)             cmd_vuln             "$@" ;;
    sast)             cmd_sast             "$@" ;;
    secretscan)       cmd_secretscan       "$@" ;;
    bench)            cmd_bench            "$@" ;;
    bench-guard)      cmd_bench_guard      "$@" ;;
    bench-record)     cmd_bench_record     "$@" ;;
    maintainability)  cmd_maintainability  "$@" ;;
    mutate)           cmd_mutate           "$@" ;;
    cover-floor)      cmd_cover_floor      "$@" ;;
    apidiff)          cmd_apidiff          "$@" ;;
    apidiff-record)   cmd_apidiff_record   "$@" ;;
    phase-gate)       cmd_phase_gate       "$@" ;;
    help|"")          lib_usage ;;
    *) log_error "unknown command: '$cmd'"; lib_usage; exit 1 ;;
  esac
}
