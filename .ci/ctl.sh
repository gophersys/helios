#!/usr/bin/env bash
#
# monorepo/.ci/ctl.sh — baseline CI for every project created from the
# gophersys/template monorepo scaffold.
#
# Verbs run `nx run-many` or `nx affected` over the whole monorepo. When
# nx isn't yet installed (fresh scaffold), the verbs fall through to a
# no-op with an informational message so the workflow doesn't explode on
# day one.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
function log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }

function require_cmd() {
  local missing=()
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    exit 127
  fi
}

function on_exit() {
  local rc=$?
  return "$rc"
}
trap on_exit EXIT

# Base commit for `nx affected`. Defaults to origin/main. A first-push or force-push delivers
# github.event.before as the all-zeros SHA (and a misconfigured caller may pass ""), which would
# make every `nx affected` git call fail — fold both to HEAD~1 (the previous commit), the honest
# minimal base for a push event.
NX_BASE="${NX_BASE:-origin/main}"
if [[ -z "$NX_BASE" || "$NX_BASE" == "0000000000000000000000000000000000000000" ]]; then
  NX_BASE="HEAD~1"
fi

# NOTE: the frontend's `e2e` nx target (Playwright over a real dev-serve) is deliberately in NO CI
# lane yet — it needs a browser-capable runner + a playwright install step; wire it into the
# substrate lane once that lane is proven green on arc-org. Until then e2e runs via
# `apps/frontend/ctl.sh e2e` locally (a documented gap, not an accidental one).

function has_nx() {
  # Check, in order: global nx, node_modules/.bin (npm/yarn classic), Yarn
  # 4 PnP (needs `yarn nx` to resolve via .pnp.cjs).
  if command -v nx >/dev/null 2>&1; then return 0; fi
  if [[ -x "$REPO_ROOT/node_modules/.bin/nx" ]]; then return 0; fi
  if [[ -f "$REPO_ROOT/.pnp.cjs" ]] && command -v yarn >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

function nx_cmd() {
  if command -v nx >/dev/null 2>&1; then
    nx "$@"
  elif [[ -x "$REPO_ROOT/node_modules/.bin/nx" ]]; then
    "$REPO_ROOT/node_modules/.bin/nx" "$@"
  else
    # Yarn 4 PnP: `yarn nx` resolves via .pnp.cjs. --silent suppresses
    # yarn's own banner lines so nx output stays clean.
    (cd "$REPO_ROOT" && yarn nx "$@")
  fi
}

function cmd_validate() {
  log_info "validate: shellcheck .ci/ctl.sh"
  require_cmd shellcheck jq
  shellcheck "$PROJECT_ROOT/ctl.sh"

  if has_nx; then
    log_info "validate: nx run-many -t validate"
    (cd "$REPO_ROOT" && nx_cmd run-many -t validate --output-style=stream) || return 1
  else
    log_warn "nx not available; project-level validate skipped"
  fi
  log_success "validate: OK"
}

function cmd_build_all() {
  if ! has_nx; then
    log_warn "nx not available; build-all is a no-op"
    return 0
  fi
  (cd "$REPO_ROOT" && nx_cmd run-many -t build --output-style=stream)
}

function cmd_test_all() {
  if ! has_nx; then
    log_warn "nx not available; test-all is a no-op"
    return 0
  fi
  (cd "$REPO_ROOT" && nx_cmd run-many -t test --output-style=stream)
}

function cmd_lint_all() {
  if ! has_nx; then
    log_warn "nx not available; lint-all is a no-op"
    return 0
  fi
  (cd "$REPO_ROOT" && nx_cmd run-many -t lint --output-style=stream)
}

function cmd_typecheck_all() {
  if ! has_nx; then
    log_warn "nx not available; typecheck-all is a no-op"
    return 0
  fi
  (cd "$REPO_ROOT" && nx_cmd run-many -t typecheck --output-style=stream)
}

function cmd_affected_build() {
  if ! has_nx; then log_warn "nx not available; affected-build is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected -t build --base="$NX_BASE" --output-style=stream)
}

function cmd_affected_test() {
  if ! has_nx; then log_warn "nx not available; affected-test is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected -t test --base="$NX_BASE" --output-style=stream)
}

function cmd_affected_check() {
  if ! has_nx; then log_warn "nx not available; affected-check is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected -t lint,typecheck,test --base="$NX_BASE" --output-style=stream)
}

# cmd_affected_gate — the ADR-0020 full-taxonomy PR gate. Runs the eight test dimensions as Nx
# targets over the affected projects. This runs INSIDE ghcr.io/gophersys/base (the on-pr.yml
# container) where docker+k3d+kind+all linters are present, so integration/load/security run for
# real and a missing tool is a HARD FAIL (each ctl.sh verb require_cmds its tool → exit 127).
# Split lane membership lives in on-pr.yml (fast vs substrate jobs); this verb is the union a
# single job can invoke.
function cmd_affected_gate() {
  if ! has_nx; then log_warn "nx not available; affected-gate is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected \
     -t lint,typecheck,test,leak,property,lifecycle,integration,load,vuln,sast,secretscan,bench-guard,cover-floor,maintainability,mutate \
     --base="$NX_BASE" --output-style=stream)
}

# cmd_affected_gate_fast — the minutes-long subset (no real-substrate lanes): lint/typecheck/test/
# leak/property/maintainability/vuln/sast/secretscan. Used by the `fast` GitHub job. `property`
# (pgregory.net/rapid, `go test -race`, no build tags) is hermetic — it belongs here so the local
# phase-gate's application-logic-correctness dimension is also enforced in CI. cover-floor + mutate
# are NOT here: cover-floor for a substrate lib is computed WITH the integration tag
# (EDEN_COVER_TAGS="lifecycle load integration") so it needs the real docker+k3d host, and mutate is
# time-heavy — both live in the substrate lane below.
function cmd_affected_gate_fast() {
  if ! has_nx; then log_warn "nx not available; affected-gate-fast is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected \
     -t lint,typecheck,test,leak,property,maintainability,vuln,sast,secretscan \
     --base="$NX_BASE" --output-style=stream)
}

# cmd_graph_guard — eden's project graph holds EDEN's projects and its submodules' REAL projects,
# and never a test fixture's stand-in project.json.
#
# THE ASYMMETRY THIS GATE EXISTS FOR. A fixture project.json inside a submodule is invisible to
# BOTH repositories' gates. The submodule builds no nx graph of its own — `.devcontainer`'s
# `cmd_validate` runs `jq empty` over such a file and reads no field of it — so its CI cannot see
# the name. Eden never sees the file at all until its POINTER MOVES. So the first thing in the
# estate able to observe a collision is a submodule pointer bump, which is the worst possible
# place for it: gophersys/eden#14 carried 787 commits and zero TypeScript, and died at
# `NX Failed to process project graph` because `.devcontainer` had grown a SECOND `first`/`second`
# fixture pair (`40edaaf`). The bump SURFACED that defect and could not have caused it.
#
# `.nxignore` is the structural fix — a submodule's fixtures are never eden's projects, so eden
# stops globbing them into its graph. This verb is that file's HOLDER. A glob that silently
# stopped matching would restore the whole defect class with nothing going red, which is the
# FAIL-NOT-SKIP failure in its purest form: a check that is believed and did not run.
#
# It reports rather than assumes. An empty fixture set is a MEASUREMENT of the tree at the current
# pointers (eden `main` carries none today — every fixture project.json entered `.devcontainer` in
# the range #14 bumps over), not a skipped check — and the two liveness clauses below are what
# keep the difference honest.
function cmd_graph_guard() {
  require_cmd jq find
  # FAIL-NOT-SKIP. The sibling verbs in this file warn and return 0 when nx is absent, because they
  # are RUNNERS and a fresh scaffold has no nx. This is a GATE, and a gate that cannot run is a
  # failure, never a pass.
  if ! has_nx; then
    log_error "graph-guard: nx is not available, so this gate cannot run — that is a FAILURE, never a skip"
    return 1
  fi

  # The submodule trees this verb judges. Eden's OWN tree is deliberately not among them: a
  # duplicate project name that eden itself commits is caught by eden's own gate on the very pull
  # request that adds it, so it needs no structural exclusion. The submodules are the blind spot.
  local -a submodule_roots=(".devcontainer" "libs" "infrastructure")

  # LIVENESS 1 — every tree this gate judges must be ON DISK. With the submodules uninitialised the
  # search below matches nothing, and the guard would report a clean graph having read no file of
  # the tree it exists to read. That green is the one this clause makes impossible.
  local root
  local -a absent=()
  for root in "${submodule_roots[@]}"; do
    [[ -d "$REPO_ROOT/$root" ]] || absent+=("$root")
  done
  if [[ ${#absent[@]} -gt 0 ]]; then
    log_error "graph-guard: submodule tree(s) absent: ${absent[*]}"
    log_error "graph-guard: run 'git submodule update --init --recursive' — an uninitialised submodule makes this gate read nothing and report OK"
    return 1
  fi

  # The graph itself. This is BLOCKER-1's symptom directly: nx refuses to BUILD a graph that holds
  # two projects of one name, and every affected lane dies with it before selecting a single task.
  log_info "graph-guard: building the nx project graph"
  local graph_json
  if ! graph_json="$(cd "$REPO_ROOT" && nx_cmd show projects --json 2>&1)"; then
    log_error "graph-guard: the nx project graph does not build"
    printf '%s\n' "$graph_json" >&2
    return 1
  fi
  local -a graph_names=()
  if ! mapfile -t graph_names < <(printf '%s' "$graph_json" | jq -r '.[]' 2>/dev/null); then
    log_error "graph-guard: 'nx show projects --json' did not return a JSON array"
    printf '%s\n' "$graph_json" >&2
    return 1
  fi
  # LIVENESS 2 — a graph of zero projects would satisfy every assertion below for the wrong reason.
  if [[ ${#graph_names[@]} -eq 0 ]]; then
    log_error "graph-guard: the graph built but holds ZERO projects — nothing here judged anything"
    return 1
  fi
  log_info "graph-guard: the graph builds and holds ${#graph_names[@]} project(s)"

  # Every project.json living under a fixture tree of a submodule. `find` walks the real directories
  # rather than reading a listing, so a fixture directory added tomorrow is covered the day it is
  # added. `|| true` guards grep's no-match exit under `pipefail`, which is a legitimate result here
  # and not an error.
  local -a fixture_roots=()
  for root in "${submodule_roots[@]}"; do fixture_roots+=("$REPO_ROOT/$root"); done
  local -a fixture_files=()
  mapfile -t fixture_files < <(
    find "${fixture_roots[@]}" -type f -name project.json 2>/dev/null \
      | grep -E '/(fixtures?|testdata)/' || true
  )

  if [[ ${#fixture_files[@]} -eq 0 ]]; then
    log_success "graph-guard: OK — no submodule fixture project.json exists at these pointers, and the graph builds"
    return 0
  fi

  # A fixture project may reach the graph under either of two names: the one it DECLARES, and the
  # basename of its directory, which is what nx infers when a project.json declares none. Both are
  # asserted, because `.nxignore` removes the FILE and therefore must remove both.
  local -a leaked=()
  local file rel name dirname_candidate candidate
  for file in "${fixture_files[@]}"; do
    rel="${file#"$REPO_ROOT"/}"
    name="$(jq -r '.name // empty' "$file" 2>/dev/null || true)"
    dirname_candidate="$(basename "$(dirname "$file")")"
    for candidate in "$name" "$dirname_candidate"; do
      [[ -n "$candidate" ]] || continue
      if printf '%s\n' "${graph_names[@]}" | grep -qxF -- "$candidate"; then
        leaked+=("$rel -> '$candidate'")
      fi
    done
  done

  if [[ ${#leaked[@]} -gt 0 ]]; then
    log_error "graph-guard: ${#leaked[@]} submodule fixture project(s) reached eden's graph:"
    for rel in "${leaked[@]}"; do log_error "  $rel"; done
    log_error "graph-guard: a submodule's test fixtures are never eden's projects — widen .nxignore to cover them"
    return 1
  fi

  log_success "graph-guard: OK — ${#fixture_files[@]} submodule fixture project.json found, 0 in the graph of ${#graph_names[@]}"
}

# cmd_affected_gate_substrate — the careful-orchestration lanes on the real docker+k3d host:
# integration/load/lifecycle/bench-guard, plus cover-floor and mutate. cover-floor lives here (not in
# the fast lane) because a substrate lib's coverage profile is built with the integration tag
# (EDEN_COVER_TAGS="lifecycle load integration"), which requires the real docker+k3d+postgres host; a
# leaf lib's hermetic cover run is harmless on this host too. mutate (gremlins on Go leaf libs,
# StrykerJS on TS libs) is time-heavy, so it rides the careful lane. Together these close the gap
# between CI and the local `phase-gate qa` 8-dimension taxonomy (ADR-0020).
function cmd_affected_gate_substrate() {
  if ! has_nx; then log_warn "nx not available; affected-gate-substrate is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected \
     -t integration,load,lifecycle,bench-guard,cover-floor,mutate \
     --base="$NX_BASE" --output-style=stream)
}

# cmd_lib_gate <lib> — run the full per-lib SDLC sequence (phase-gate all: architecture →
# implementation → testing → qa, short-circuiting on first failure) for one library.
function cmd_lib_gate() {
  local lib="${1:-}"
  if [[ -z "$lib" ]]; then log_error "usage: lib-gate <lib>"; return 2; fi
  local lib_dir="$REPO_ROOT/libs/go/$lib"
  if [[ ! -f "$lib_dir/ctl.sh" ]]; then log_error "no such lib: libs/go/$lib"; return 2; fi
  log_info "lib-gate: libs/go/$lib → phase-gate all (1→4)"
  (cd "$lib_dir" && bash ./ctl.sh phase-gate all)
}

function cmd_release_check() {
  require_cmd git
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
    log_error "working tree dirty"
    git -C "$REPO_ROOT" status --short >&2
    return 1
  fi
  local branch
  branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
  if [[ "$branch" != "main" ]]; then
    log_error "not on main (on '$branch')"
    return 1
  fi
  git -C "$REPO_ROOT" fetch --quiet origin
  local head remote
  head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  remote="$(git -C "$REPO_ROOT" rev-parse origin/main)"
  if [[ "$head" != "$remote" ]]; then
    log_error "main ($head) != origin/main ($remote)"
    return 1
  fi
  log_success "release-check: ready"
}

function usage() {
  cat <<EOF
Usage: bash .ci/ctl.sh <command> [args]

Commands:
  validate        shellcheck + nx run-many -t validate
  build-all       nx run-many -t build
  test-all        nx run-many -t test
  lint-all        nx run-many -t lint
  typecheck-all   nx run-many -t typecheck
  affected-build  nx affected -t build (base=\${NX_BASE:-origin/main})
  affected-test   nx affected -t test
  affected-check  nx affected -t lint,typecheck,test (canonical PR gate)
  affected-gate   nx affected -t <full ADR-0020 taxonomy> (lint..maintainability)
  graph-guard     the nx graph builds, and holds no submodule test-fixture project
  affected-gate-fast       the minutes subset (no real-substrate lanes)
  affected-gate-substrate  integration/load/lifecycle on the real docker+k3d host
  lib-gate <lib>  per-lib SDLC sequence: ctl.sh phase-gate all (1→4)
  release-check   preflight: clean, on main, up to date with origin
  help            Show this message
EOF
}

function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    validate)        cmd_validate        "$@" ;;
    build-all)       cmd_build_all       "$@" ;;
    test-all)        cmd_test_all        "$@" ;;
    lint-all)        cmd_lint_all        "$@" ;;
    typecheck-all)   cmd_typecheck_all   "$@" ;;
    affected-build)  cmd_affected_build  "$@" ;;
    affected-test)   cmd_affected_test   "$@" ;;
    affected-check)  cmd_affected_check  "$@" ;;
    affected-gate)             cmd_affected_gate           "$@" ;;
    graph-guard)               cmd_graph_guard             "$@" ;;
    affected-gate-fast)        cmd_affected_gate_fast      "$@" ;;
    affected-gate-substrate)   cmd_affected_gate_substrate "$@" ;;
    lib-gate)                  cmd_lib_gate                "$@" ;;
    release-check)   cmd_release_check   "$@" ;;
    help|"")         usage ;;
    *) log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
