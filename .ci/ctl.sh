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
# and never a submodule's test fixture.
#
# THE ASYMMETRY THIS GATE EXISTS FOR. A fixture project file inside a submodule is invisible to BOTH
# repositories' gates. The submodule builds no nx graph of its own — `.devcontainer`'s `cmd_validate`
# runs `jq empty` over such a file and reads no field of it — so its CI cannot see the name. Eden
# never sees the file at all until its POINTER MOVES. So the first thing in the estate able to
# observe a collision is a submodule pointer bump, the worst possible place for it: gophersys/eden#14
# carried 847 commits and zero TypeScript and died at `NX Failed to process project graph`, because
# `.devcontainer` had grown a SECOND `first`/`second` fixture pair in `40edaaf`.
#
# IT JUDGES BY PROJECT ROOT, NOT BY NAME, and that is the whole design. An earlier draft read each
# fixture `project.json`, guessed the 1 or 2 names nx might give it, and asked whether those names
# were in the graph. An adversarial refutation broke it twice in one sitting: a fixture whose
# `project.json` carries no `name` but whose sibling `package.json` does is named by neither guess
# and passed clean; and a fixture with NO `project.json` at all — a bare `package.json` +
# `tsconfig.json`, which `@nx/js/typescript` infers — was never even looked for. Reading the ROOT of
# every project nx actually built inverts that: whatever mechanism nx used to infer a project,
# present or future, its root is still a path, and a path under a submodule fixture directory is
# still wrong. There is no name to guess and no inference path to enumerate.
#
# IT BINDS ON A TREE WITH NO FIXTURES. `.nxignore` is checked for COVERAGE first, so deleting or
# mangling that file is RED even at pointers carrying no fixture at all. Without that clause the
# gate asserted nothing on exactly the run used to justify merging it — the whole file could be
# removed and the verdict was byte-identical.
function cmd_graph_guard() {
  require_cmd jq find
  # FAIL-NOT-SKIP. The sibling verbs in this file warn and return 0 when nx is absent, because they
  # are RUNNERS and a fresh scaffold has no nx. This is a GATE, and a gate that cannot run is a
  # failure, never a pass.
  if ! has_nx; then
    log_error "graph-guard: nx is not available, so this gate cannot run — that is a FAILURE, never a skip"
    return 1
  fi

  # The submodule trees this verb judges. Eden's OWN tree is deliberately not among them: a duplicate
  # project name that eden itself commits is caught by eden's own gate on the very pull request that
  # adds it, so it needs no structural exclusion. The submodules are the blind spot.
  local -a submodule_roots=(".devcontainer" "libs" "infrastructure")
  # The directory vocabulary. This list is deliberately WIDER than the directory names spelled in
  # .nxignore: `_fixtures` and `test-fixtures` have no patterns of their own, so a fixture placed in
  # one reaches the graph and is caught HERE, as a red gate rather than as a quiet hole.
  local fixture_dir_re='(fixtures?|__fixtures__|_fixtures|test-fixtures|testdata)'
  # The 3 file types that DEFINE an nx project in this workspace. nx.json enables
  # @nx/js/typescript, so package.json + tsconfig*.json infer a project exactly as project.json
  # declares one. .nxignore must cover all 3 for every directory name it spells.
  local -a project_files=("project.json" "package.json" "tsconfig*.json")
  local -a ignored_dirs=("fixture" "fixtures" "__fixtures__" "testdata")

  # LIVENESS 1 — every tree this gate judges must be CHECKED OUT, not merely present.
  # `[[ -d ]]` is NOT that test and reading it as one was a defect: `git submodule init` without
  # `update`, and a plain `git clone` with no `--recursive`, both leave the mount point as an EMPTY
  # DIRECTORY. It exists, so a `-d` test passes, while 39 of the 49 projects are simply not there —
  # and every assertion below then passes having read nothing of the tree it exists to read. An
  # initialised submodule always carries a `.git` entry (a gitfile in a superproject checkout, a
  # directory in a standalone clone), so that is what is tested.
  local root
  local -a absent=()
  for root in "${submodule_roots[@]}"; do
    if [[ ! -d "$REPO_ROOT/$root" ]]; then
      absent+=("$root (no such directory)")
    elif [[ ! -e "$REPO_ROOT/$root/.git" ]]; then
      absent+=("$root (present but NOT checked out — no .git entry)")
    fi
  done
  if [[ ${#absent[@]} -gt 0 ]]; then
    log_error "graph-guard: submodule tree(s) not usable:"
    for root in "${absent[@]}"; do log_error "  $root"; done
    log_error "graph-guard: run 'git submodule update --init --recursive' — an uninitialised submodule makes this gate read nothing and report OK"
    return 1
  fi

  # ── 1. .nxignore COVERAGE ────────────────────────────────────────────────────────────────────
  # Derived here rather than read from the file, so the file is judged against this verb and never
  # against itself. This is the clause that binds when the fixture set is empty.
  local nxignore="$REPO_ROOT/.nxignore"
  if [[ ! -f "$nxignore" ]]; then
    log_error "graph-guard: .nxignore is absent — a submodule's fixtures would be globbed into eden's graph"
    return 1
  fi
  local dir pf want
  local -a uncovered=()
  for root in "${submodule_roots[@]}"; do
    for dir in "${ignored_dirs[@]}"; do
      for pf in "${project_files[@]}"; do
        want="$root/**/$dir/**/$pf"
        grep -qxF -- "$want" "$nxignore" || uncovered+=("$want")
      done
    done
  done
  if [[ ${#uncovered[@]} -gt 0 ]]; then
    log_error "graph-guard: .nxignore is missing ${#uncovered[@]} required pattern(s):"
    for want in "${uncovered[@]}"; do log_error "  $want"; done
    return 1
  fi
  log_info "graph-guard: .nxignore covers all $(( ${#submodule_roots[@]} * ${#ignored_dirs[@]} * ${#project_files[@]} )) required patterns"

  # ── 2a. THE GRAPH RESOLVES — asserted with `nx show projects`, NOT with `nx graph` ────────────
  # THESE TWO COMMANDS DISAGREE, and picking the wrong one made this clause a lie.
  # Measured on this workspace against `.devcontainer` 404e83a, which declares `first` and `second`
  # twice each — the exact defect that blocked gophersys/eden#14:
  #
  #     nx show projects   -> rc=1, "Failed to process project graph ... defined in multiple
  #                           locations", naming both pairs
  #     nx graph --file    -> rc=0, silently DEDUPLICATED to 56 nodes, `first` and `second` present
  #
  # So a build assertion written on `nx graph` tolerates the very collision this gate exists to
  # catch, and which of the two same-named projects survives is nx's discovery order. The strict
  # command is what decides; `nx graph` is used below only to READ roots out of a graph already
  # proven to resolve.
  log_info "graph-guard: resolving the nx project graph"
  local work_dir
  work_dir="$(mktemp -d -t graph-guard.XXXXXX)"
  local show_err="$work_dir/show.err"
  local show_out show_rc=0
  # STDERR IS KEPT OUT OF $show_out DELIBERATELY. Every non-blank line of it is counted as a project
  # name below, and the count is compared against the graph's. Folding stderr in with `2>&1` made one
  # incidental line a FALSE RED on a healthy tree — measured: under `npx`, `nx show projects 2>&1`
  # yields 51 lines against 49 real projects, the 2 extra being `npm notice` banners. That path is
  # live: `nx_cmd`'s third branch runs `yarn nx` with no `--silent`, whatever the comment above it
  # claims. Diagnostics still reach the operator; they just never become project names.
  show_out="$( (cd "$REPO_ROOT" && nx_cmd show projects) 2>"$show_err" )" || show_rc=$?
  if [[ $show_rc -ne 0 ]]; then
    log_error "graph-guard: the nx project graph does not resolve (nx show projects exited $show_rc)"
    printf '%s\n' "$show_out" >&2
    cat "$show_err" >&2 || true
    rm -rf "$work_dir"
    return 1
  fi
  local -a project_names=()
  mapfile -t project_names < <(printf '%s\n' "$show_out" | grep -vE '^\s*$' || true)
  # LIVENESS 2 — a graph of zero projects satisfies every assertion below for the wrong reason.
  if [[ ${#project_names[@]} -eq 0 ]]; then
    log_error "graph-guard: the graph resolved but holds ZERO projects — nothing here judged anything"
    rm -rf "$work_dir"
    return 1
  fi

  # ── 2b. THE ROOTS ────────────────────────────────────────────────────────────────────────────
  # `nx graph --file` is the only reader that carries each project's ROOT; `show projects` carries
  # names alone.
  local graph_file graph_err
  # The graph goes in the SAME temp directory as the stderr capture above, so this verb owns exactly
  # one path in /tmp and removes it on every exit. `nx graph --file` refuses a name not ending in
  # .json or .html, so an earlier spelling was `"$(mktemp -t X.XXXXXX)".json` — which leaves mktemp's
  # own extension-less file behind and writes beside it. Three runs left four files in /tmp.
  graph_file="$work_dir/graph.json"
  if ! graph_err="$( (cd "$REPO_ROOT" && nx_cmd graph --file="$graph_file") 2>&1 )"; then
    log_error "graph-guard: 'nx graph --file' failed after the graph had already resolved"
    printf '%s\n' "$graph_err" >&2
    rm -rf "$work_dir"
    return 1
  fi
  # The shape is asserted before it is trusted. `jq -r .[]` over an OBJECT silently pretty-prints
  # its values into lines that read like project names, so a wrong shape has to fail HERE.
  if ! jq -e 'type=="object" and (.graph.nodes|type=="object")' "$graph_file" >/dev/null 2>&1; then
    log_error "graph-guard: 'nx graph --file' did not produce a graph with an object at .graph.nodes"
    head -c 400 "$graph_file" >&2 || true
    rm -rf "$work_dir"
    return 1
  fi
  local -a roots=()
  mapfile -t roots < <(jq -r '.graph.nodes | to_entries[] | "\(.key)\t\(.value.data.root // "")"' "$graph_file")
  rm -rf "$work_dir"
  # The two readers must agree on how many projects there are. They disagree exactly when `nx graph`
  # has deduplicated a name collision that `show projects` would have refused, so this is the second
  # line of defence on 2a rather than a tidiness check.
  if [[ ${#roots[@]} -ne ${#project_names[@]} ]]; then
    log_error "graph-guard: the 2 graph readers disagree — 'show projects' reports ${#project_names[@]} project(s), 'graph --file' reports ${#roots[@]}"
    log_error "graph-guard: that gap is what a deduplicated name collision looks like"
    return 1
  fi
  log_info "graph-guard: the graph resolves and holds ${#roots[@]} project(s)"

  # ── 3. NO PROJECT IS ROOTED IN A SUBMODULE FIXTURE TREE ──────────────────────────────────────
  local line name prj_root sm
  local -a leaked=()
  for line in "${roots[@]}"; do
    name="${line%%$'\t'*}"
    prj_root="${line#*$'\t'}"
    [[ -n "$prj_root" ]] || continue
    for sm in "${submodule_roots[@]}"; do
      [[ "$prj_root" == "$sm/"* ]] || continue
      if printf '%s' "$prj_root" | grep -qE "/${fixture_dir_re}(/|\$)"; then
        leaked+=("$prj_root -> '$name'")
      fi
    done
  done

  if [[ ${#leaked[@]} -gt 0 ]]; then
    log_error "graph-guard: ${#leaked[@]} submodule fixture project(s) reached eden's graph:"
    for line in "${leaked[@]}"; do log_error "  $line"; done
    log_error "graph-guard: a submodule's test fixtures are never eden's projects — widen .nxignore to cover them"
    return 1
  fi

  # Reported for the reader, and never used as the pass condition: an empty fixture set is a real
  # state of the tree (eden main carries none), not a reason to weaken clause 1.
  #
  # The wording is deliberately narrow. An earlier line said "all excluded", which claimed more than
  # the count can support: this `find` sees only the file NAMES this verb knows about, so a fixture
  # that becomes a project by some other means is outside the number and "all" was a promise about
  # files nobody had enumerated. Clause 3 is what actually holds the property, over ROOTS, and it
  # says so on its own line.
  local fixture_count=0
  local -a fixture_dirs_abs=()
  for root in "${submodule_roots[@]}"; do fixture_dirs_abs+=("$REPO_ROOT/$root"); done
  fixture_count="$(find "${fixture_dirs_abs[@]}" -type f \( -name project.json -o -name package.json -o -name 'tsconfig*.json' \) 2>/dev/null \
    | grep -cE "/${fixture_dir_re}/" || true)"
  log_success "graph-guard: OK — ${#roots[@]} project(s) resolved, 0 rooted in a submodule fixture tree"
  log_info "graph-guard: ${fixture_count} project-shaped file(s) sit under a submodule fixture directory and produced no project"
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
