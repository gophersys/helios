#!/usr/bin/env bash
#
# libs/typescript/_ctl/lib.sh — the shared ctl library for every Eden TypeScript/Svelte
# library (ADR-0024 — the ADR-0020 analog for the UI track).
#
# HNS-1 (10 §5): the directory is `_ctl` (an internal helper, leading-underscore so Nx ignores
# it) and the FILE concept is "the ctl library" — hence `lib.sh`. The banned tokens
# `common`/`util`/`core` are deliberately NOT used here.
#
# This file is the ONE HOME (10 §9) for the SDLC phase-gate sequencer and the UI test-dimension
# verbs (ADR-0024 §3). Each per-lib ctl.sh is a THIN dispatcher that sets its metadata
# (leaf-or-not, coverage floor) and sources this file — verb bodies are defined exactly once,
# mirroring libs/go/_ctl/lib.sh's shape. project.json targets delegate here, so a consumer can
# `nx run <lib>:phase-gate` without reading source.
#
# Contract for the verbs (mirrors the Go contract):
#   - set -Eeuo pipefail + shellcheck-clean, house style.
#   - require_cmd the tool a verb needs, so a MISSING tool exits 127 (FAIL-NOT-SKIP, ADR-0024:
#     "absent tool = FAIL not skip"). In the devcontainer every tool is present, so an absence
#     here is a real gate failure, never a silent skip.
#   - tools run THROUGH BUN (`bun x <tool>`): the devcontainer's JS runtime is bun, so every verb
#     invokes tools via `bun x`. The LONE exception is the mutation lane (cmd_mutate), which runs
#     StrykerJS under the baked node (nvm) — see that verb's header for why.
#
# shellcheck shell=bash

set -Eeuo pipefail
IFS=$'\n\t'

# ── library metadata (set by the sourcing per-lib ctl.sh BEFORE `lib_main`) ─────────────────
# EDEN_LIB_NAME       — the slug, e.g. "scale" (defaults to the lib dir basename).
# EDEN_LIB_SCOPE      — the npm/code scope; always "@eden".
# EDEN_LIB_LEAF       — "true" for a pure leaf lib (no real substrate), "false" for substrate.
# EDEN_COVERAGE_FLOOR — per-package coverage FLOOR as an integer percent (80 leaf / 70 substrate).
# EDEN_HAS_SVELTE     — "true" if the lib ships *.svelte (wires svelte-check + the a11y lane).
# EDEN_MUTATION_FLOOR — the StrykerJS mutation-score FLOOR as an integer percent (the gremlins ≥0.75
#                       analog). 75 mirrors the Go leaf floor; a substrate/large-surface lib records
#                       a lower CURRENT baseline that RATCHETS toward 75 (the bench-baseline model:
#                       record the floor, never regress below it). A survived mutant on covered code
#                       is a real test gap — strengthen the test to kill it (ADR-0024 / rule 21).
: "${EDEN_LIB_NAME:=}"
: "${EDEN_LIB_SCOPE:=@eden}"
: "${EDEN_LIB_LEAF:=true}"
: "${EDEN_COVERAGE_FLOOR:=80}"
: "${EDEN_HAS_SVELTE:=false}"
: "${EDEN_MUTATION_FLOOR:=75}"

# PROJECT_ROOT is the per-lib directory; the sourcing ctl.sh exports it.
: "${PROJECT_ROOT:?lib.sh: PROJECT_ROOT must be set by the sourcing per-lib ctl.sh}"

# The exported-surface baseline for a UI library is the component/prop/event/slot public-API
# snapshot (the .d.ts surface) — breaking it is the cardinal sin (ADR-0024 §2), exactly as a
# `go doc -short` break is for Go. Lives once per lib at <lib>/.apibaseline.
API_BASELINE="${PROJECT_ROOT}/.apibaseline"

# ── monorepo + workspace roots ──────────────────────────────────────────────────────────────
# libs/ is a git submodule, so the monorepo is the superproject working tree; fall back to the
# submodule toplevel (standalone clone) only if there is no superproject. The shared tooling
# config (tsconfig.base.json, eslint.config.base.mjs, vitest.config.base.ts) lives at the
# libs/typescript workspace level — PROJECT_ROOT's parent.
_eden_monorepo_root() {
  local sp
  sp="$(cd "$PROJECT_ROOT" && git rev-parse --show-superproject-working-tree 2>/dev/null)" || true
  if [[ -n "$sp" ]]; then printf '%s' "$sp"; return; fi
  cd "$PROJECT_ROOT" && git rev-parse --show-toplevel 2>/dev/null
}
EDEN_TS_WORKSPACE="${EDEN_TS_WORKSPACE:-$(cd "$PROJECT_ROOT/.." && pwd)}"

# ── logging (identical palette to the Go track for an auditable, uniform gate table) ────────
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

# ── tool gate (FAIL-NOT-SKIP, ADR-0024) ─────────────────────────────────────────────────────
# The JS runtime is bun; every tool runs via `bun x <tool>`. `require_cmd` proves bun resolves
# AND that the named tool package is installed under the workspace node_modules, so a MISSING
# tool exits 127 — the mechanical FAIL-NOT-SKIP rule. `bun x` itself is invoked from the
# workspace dir so it resolves the hoisted node_modules/.bin.
require_bun() {
  command -v bun >/dev/null 2>&1 || {
    log_error "missing required runtime: bun"
    log_dim   "  ADR-0024 FAIL-NOT-SKIP: bun is the devcontainer JS runtime; run inside ghcr.io/gophersys/base."
    exit 127
  }
}

# require_tool <bin-name> <node_modules-package> — the .bin must exist (proves install). We do
# NOT exec the .bin directly (its shebang is #!/usr/bin/env node and there is no node); presence
# of the .bin entry is the install proof, and the verb runs it through `bun x`.
require_tool() {
  local bin="$1" pkg="$2"
  require_bun
  if [[ ! -e "${EDEN_TS_WORKSPACE}/node_modules/.bin/${bin}" ]]; then
    log_error "missing required tool: ${bin} (package ${pkg})"
    log_dim   "  ADR-0024 FAIL-NOT-SKIP: in the devcontainer the UI toolchain is guaranteed present."
    log_dim   "  install at the workspace: (cd ${EDEN_TS_WORKSPACE} && bun install)"
    exit 127
  fi
}

# bunx <tool> <args...> — run a workspace tool through bun from the lib dir. bun resolves the
# hoisted node_modules/.bin and provides the node-compatible runtime the tool's shebang wants.
bunx() { ( cd "$PROJECT_ROOT" && bun x "$@" ); }

# ── (1) APPLICATION-LOGIC CORRECTNESS + the core authoring verbs ─────────────────────────────

# cmd_build — type-emit the library (tsc --build / emit declarations). The build IS the
# typecheck-with-emit: a leaf utility library's artifact is its .js + .d.ts surface.
cmd_build() {
  require_tool tsc typescript
  log_info "build: tsc -p tsconfig.json (emit .js + .d.ts)"
  bunx tsc -p tsconfig.json
  log_success "build: OK"
}

# cmd_typecheck — strict type-check with NO emit (the fast inner-loop gate). Adds svelte-check
# for libs that ship *.svelte.
cmd_typecheck() {
  require_tool tsc typescript
  log_info "typecheck: tsc --noEmit (the shared strict tsconfig.base.json)"
  bunx tsc -p tsconfig.json --noEmit
  if [[ "$EDEN_HAS_SVELTE" == "true" ]]; then
    require_tool svelte-check svelte-check
    log_info "typecheck: svelte-check (component diagnostics)"
    bunx svelte-check --tsconfig ./tsconfig.json
  fi
  log_success "typecheck: OK"
}

# cmd_lint — ESLint over the shared strict flat config (includes the HNS-1 name lint + the
# interface-design / error-handling rule analogs). The golangci-lint counterpart.
cmd_lint() {
  require_tool eslint eslint
  log_info "lint: eslint (shared strict flat config + HNS-1 name lint)"
  bunx eslint .
  log_success "lint: OK"
}

# The prettier target set: the lib's source + its own config files. dist/ build artifacts and
# node_modules are excluded by the workspace .prettierignore (pinned via --ignore-path so it is
# found from any CWD). The config is resolved by prettier walking up to the workspace .prettierrc.
_prettier() {
  local mode="$1" # --check | --write
  bunx prettier "$mode" \
    --ignore-path "${EDEN_TS_WORKSPACE}/.prettierignore" \
    'src/**/*.{ts,svelte}' '*.{json,mjs,ts}'
}

# cmd_format — prettier in CHECK mode for the gate (write mode is `fmt`). The gofumpt -l analog.
cmd_format() {
  require_tool prettier prettier
  log_info "format: prettier --check (src + config; dist excluded)"
  _prettier --check
  log_success "format: OK"
}

# cmd_fmt — prettier WRITE (the gofumpt -w analog; not part of the gate, an authoring verb).
cmd_fmt() {
  require_tool prettier prettier
  log_info "fmt: prettier --write (src + config)"
  _prettier --write
  log_success "fmt: OK"
}

# cmd_test — the unit + property + (where wired) component suite under vitest. The fast lane.
cmd_test() {
  require_tool vitest vitest
  log_info "test: vitest run (unit + fast-check property + fake conformance)"
  bunx vitest run
  log_success "test: OK"
}

# cmd_property — the fast-check property lane (rapid analog). fast-check is a vitest dependency
# exercised by the *.property.test.ts files; here we run the whole suite with the property
# files included (numRuns is set in-test). The `property` verb keeps the dimension nameable.
cmd_property() {
  require_tool vitest vitest
  log_info "property: vitest run (fast-check invariants — scale/round-trip/idempotency)"
  bunx vitest run
  log_success "property: OK"
}

# ── (8 / maintainability) COVERAGE FLOOR ─────────────────────────────────────────────────────
# Per-package FLOOR (80% leaf / 70% substrate, ADR-0020 §cover-floor). vitest v8 coverage with
# the per-lib thresholds set in vitest.config.ts; here we run with coverage and let the config's
# thresholds fail the run if a package dips below floor.
cmd_cover_floor() {
  require_tool vitest vitest
  log_info "cover-floor: vitest run --coverage (per-package FLOOR ${EDEN_COVERAGE_FLOOR}%)"
  bunx vitest run --coverage
  log_success "cover-floor: OK"
}

# ── (maintainability bundle) strict lint + typecheck + format + name lint + cohesion ──────────
cmd_maintainability() {
  log_info "maintainability: typecheck + strict eslint (incl. HNS-1 name lint) + prettier check + cohesion"
  cmd_typecheck
  cmd_lint
  cmd_format
  cmd_cohesion
  log_success "maintainability: OK"
}

# ── (apidiff) the exported-surface baseline — the CARDINAL SIN gate (ADR-0024 §2) ────────────
# The UI library's frozen surface is its public .d.ts snapshot (component/prop/event/slot for a
# component lib; the exported type/function signatures for a utility lib). We emit declarations
# to a temp dir and normalize them into a stable snapshot, then diff vs the frozen .apibaseline.
_emit_api_surface() {
  # Emit .d.ts only, concatenate the PUBLIC declaration surface into a normalized snapshot
  # (sorted, comment/whitespace-stripped) so the diff is order-stable and noise-free.
  require_tool tsc typescript
  local tmp; tmp="$(mktemp -d -t "${EDEN_LIB_NAME}-api.XXXXXX")"
  ( cd "$PROJECT_ROOT" && bun x tsc -p tsconfig.json \
      --declaration --emitDeclarationOnly --outDir "$tmp" --declarationMap false --sourceMap false ) >/dev/null
  # Normalize to the DECLARATION SURFACE ONLY (the real cardinal-sin signal): strip JSDoc block
  # comments (/** … */ and the ` * …` continuation lines), line comments, blank lines, import
  # lines, the sourceMappingURL pragma; collapse whitespace; sort for order-stability.
  find "$tmp" -name '*.d.ts' -print0 \
    | sort -z \
    | xargs -0 cat \
    | grep -vE '^\s*$|^\s*//|^//#|^\s*/?\*|^\s*/\*\*|^import |^export \{\}' \
    | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//' \
    | sort -u
  rm -rf "$tmp"
}

cmd_apidiff_record() {
  log_info "apidiff-record: freezing the exported .d.ts surface → .apibaseline"
  _emit_api_surface > "$API_BASELINE"
  log_success "apidiff-record: recorded $(wc -l < "$API_BASELINE" | tr -d ' ') surface line(s) → ${API_BASELINE##*/}"
}

cmd_apidiff() {
  if [[ ! -f "$API_BASELINE" ]]; then
    log_error "no .apibaseline — record the frozen surface: ./ctl.sh apidiff-record"
    exit 1
  fi
  log_info "apidiff: diff exported .d.ts surface vs frozen .apibaseline (the cardinal-sin gate)"
  local current; current="$(mktemp -t "${EDEN_LIB_NAME}-api-cur.XXXXXX")"
  _emit_api_surface > "$current"
  if ! diff -u "$API_BASELINE" "$current"; then
    rm -f "$current"
    log_error "EXPORTED-SURFACE BREAK vs .apibaseline — the cardinal sin (ADR-0024 §2). Revise the contract + re-record, or fix the break."
    exit 1
  fi
  rm -f "$current"
  log_success "apidiff: exported surface unchanged"
}

# ── (9 / NOVEL) DESIGN-CORRECTNESS — the ADR-0024 ninth dimension ─────────────────────────────
# Aesthetics made computable: every color DERIVED (no hand-set hex → token-provenance lint);
# every fg/bg pair PASSES the contrast gate (mechanical, unrounded WCAG formula); every
# size/space comes from the SCALE FORMULA (asserted, not eyeballed); plus the a11y matrix for
# component libs. "Looks right" becomes a passing gate (ADR-0024 §3).
#
# STUB (this is the pipeline-standup deliverable): the verb is wired end-to-end and runs the
# two mechanical checks that need no @eden/theme yet — (a) the no-hand-set-hex token-provenance
# lint over non-test source, and (b) the design-correctness vitest lane (*.design.test.ts), where
# a lib asserts its scale/contrast values come from the research math. Full contrast-gate +
# axe a11y matrix land with @eden/theme (its design constraint per ADR-0024 §5).
cmd_design_correctness() {
  log_info "design-correctness: the ADR-0024 ninth dimension (math-is-source-of-truth)"

  # (a) token-provenance lint: NO hand-set hex literal in non-test source. Every color must be
  # DERIVED through the generative engine, never pasted. (A leaf utility lib has no colors, so
  # this is vacuously green for it; it is the load-bearing gate for @eden/theme and components.)
  #
  # The ONE exception is a designated SEED SOURCE: a brand seed (e.g. the founder's locked palette)
  # is by definition an external literal the engine ingests ONCE and derives everything from. Such a
  # file declares its intent with the `@eden-seed-source` provenance pragma in its header; the lint
  # exempts only those files (the Go-pipeline analog of exempting a test-require block). Authoring a
  # color as hex ANYWHERE else stays the cardinal sin — you cannot scatter hex, you must declare a
  # seed source. The exemption is auditable: grep the pragma to enumerate every hex crossing.
  log_info "design-correctness: no-hand-set-hex provenance lint (non-test source; @eden-seed-source exempt)"
  local hex_hits='' f
  while IFS= read -r -d '' f; do
    grep -qlE '@eden-seed-source' "$f" 2>/dev/null && continue   # a declared seed source — exempt
    local file_hits
    file_hits="$(grep -nE '#[0-9a-fA-F]{3,8}\b' "$f" 2>/dev/null || true)"
    [[ -n "$file_hits" ]] && hex_hits+="${f}:"$'\n'"${file_hits}"$'\n'
  done < <(find "$PROJECT_ROOT/src" \( -name '*.ts' -o -name '*.svelte' \) \
             ! -name '*.test.ts' ! -name '*.spec.ts' -print0 2>/dev/null)
  if [[ -n "$hex_hits" ]]; then
    log_error "hand-set hex literal(s) found — colors must be DERIVED via @eden/theme, never pasted (ADR-0024 §3):"
    printf '%s\n' "$hex_hits" >&2
    log_dim   "  (a legitimate brand-seed file declares the @eden-seed-source pragma to ingest external literals once)"
    exit 1
  fi
  log_success "design-correctness: provenance clean (no hand-set hex outside declared seed sources)"

  # (b) the design-correctness vitest lane: *.design.test.ts assert scale/contrast/size values
  # are produced by the research-math formula (asserted, not eyeballed). Skip-free: if the lib
  # has no design test it simply has no design assertions, but the lane itself always runs.
  require_tool vitest vitest
  log_info "design-correctness: vitest design lane (scale/contrast/size from the research math)"
  # --passWithNoTests so a lib legitimately without design assertions is not a false FAIL; a lib
  # WITH a *.design.test.ts (the reference lib has one) is fully exercised.
  bunx vitest run --passWithNoTests
  log_success "design-correctness: OK"
}

# ── (cohesion) DEAD-EXPORT + CROSS-LIB MATH DUPLICATION — one concept, one home (10 §9) ──────────
# The TS analog of the Go pipeline's `_cohesion_scan` + the two cross-lib duplication detectors. The
# TS track previously had NO cohesion dimension (audit: "a TS lib can re-derive another TS lib's
# entire generator and stay phase-gate-all GREEN"; "a fully dead exported type cluster sails through
# green"). The scan (a TS-compiler-API tool — `_ctl/cohesion-scan.mjs`, no new tooling dep) FAILS on:
#   (A) a non-index exported symbol reachable from NOWHERE (not on the barrel, no importer across the
#       TS libs) — the scale-dead-end / dead-contract class; and
#   (B) an exported math const/function in a downstream lib that DUPLICATES one already exported by a
#       foundation lib (@eden/scale) without CITING it — the theme-reimplements-scale class.
# Importer counting is necessarily whole-workspace, so the scan reads ALL libs but only FAILS on
# findings owned by THIS lib (`--lib ${EDEN_LIB_NAME}`), keeping the gate per-lib.
cmd_cohesion() {
  require_bun
  local scan="${EDEN_TS_WORKSPACE}/_ctl/cohesion-scan.mjs"
  if [[ ! -f "$scan" ]]; then
    log_error "missing cohesion scanner: ${scan}"
    exit 127
  fi
  log_info "cohesion: dead-export + cross-lib math-duplication scan (one concept, one home — 10 §9)"
  ( cd "$EDEN_TS_WORKSPACE" && bun "$scan" --lib "$EDEN_LIB_NAME" )
  log_success "cohesion: OK"
}

# ── (mutation) StrykerJS MUTATION LANE — the gremlins ≥0.75 analog (ADR-0024 Stage-3) ────────────
# A survived mutant on covered code is a real test gap (rule 21 §h). StrykerJS mutates the lib's
# non-test src and re-runs the vitest suite per mutant; the run FAILS if the mutation score dips
# below ${EDEN_MUTATION_FLOOR}% (Stryker's `break` threshold). 75 mirrors the Go leaf floor; a
# substrate/large-surface lib records a lower CURRENT baseline that ratchets toward 75.
#
# RUNTIME — the ONE verb that runs under node, not bun. The mutation lane is a DEV-GATE, not the
# runtime: StrykerJS forks worker processes and drives vitest under worker_threads, which the
# devcontainer's bun does not fully implement. So `mutate` runs StrykerJS under the BAKED node
# (installed via nvm — NODE_VERSION 24.x), the one dev-gate tool that uses node; the @eden runtime
# and every OTHER verb still dogfood bun. We activate the nvm node inside the verb and invoke
# Stryker the ordinary node way (`node node_modules/@stryker-mutator/core/bin/stryker.js`). Under
# real node, peer-dep resolution Just Works, so the vitest-runner plugin is named by its plain
# specifier `@stryker-mutator/vitest-runner` (Stryker resolves it via normal node_modules) — no
# `.bun` store path, no bun-compat patches, no captureStackTrace shim.
#
# We use Stryker's DEFAULT sandbox EXCEPT we keep `inPlace:true`: each lib's vitest.config.ts
# imports `../vitest.config.base.js` (a path that escapes the lib dir up to the workspace root),
# and Stryker's sandbox copies only the lib subtree, so a sandbox copy cannot resolve that parent
# import. `inPlace` mutates the real files in a clean git tree and Stryker restores them after each
# mutant; the gate also clears `.stryker-tmp` on exit.
cmd_mutate() {
  require_tool stryker @stryker-mutator/core
  require_tool vitest vitest

  # Activate the baked node (nvm). This is the ONE verb that runs under node, not bun — see header.
  # FAIL-NOT-SKIP: if node is unavailable, exit 127 (the gate records REQUIRED-BUT-ABSENT).
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck disable=SC1091
  if [[ -s "${NVM_DIR}/nvm.sh" ]]; then . "${NVM_DIR}/nvm.sh"; nvm use --silent node >/dev/null 2>&1 || nvm use --silent 24 >/dev/null 2>&1 || true; fi
  if ! command -v node >/dev/null 2>&1; then
    log_error "missing required runtime: node (the mutation lane runs StrykerJS under the baked nvm node)"
    log_dim   "  ADR-0024 FAIL-NOT-SKIP: node is baked via nvm in ghcr.io/gophersys/base (NODE_VERSION 24.x)."
    exit 127
  fi
  log_dim "mutate: StrykerJS under node $(node --version) (the dev-gate node; the runtime stays bun)"

  local ws="$EDEN_TS_WORKSPACE"
  local core_bin="${ws}/node_modules/@stryker-mutator/core/bin/stryker.js"
  if [[ ! -f "$core_bin" ]]; then log_error "missing Stryker core bin: ${core_bin}"; exit 127; fi

  # The mutate target set: every non-test src module except the pure re-export barrel index.ts.
  # (Mirrors the cover-floor include/exclude — the barrel has no logic to mutate.)
  local mutate_json
  if [[ -f "${PROJECT_ROOT}/src/index.ts" ]] && [[ "$(find "${PROJECT_ROOT}/src" -maxdepth 1 -name '*.ts' ! -name '*.test.ts' ! -name '*.spec.ts' | wc -l | tr -d ' ')" == "1" ]]; then
    # single-module leaf (e.g. scale): all logic lives in index.ts, so mutate it.
    mutate_json='["src/index.ts"]'
  else
    mutate_json='["src/**/*.ts","!src/index.ts","!src/**/*.test.ts","!src/**/*.property.test.ts","!src/**/*.design.test.ts","!src/**/*.spec.ts"]'
  fi

  # Normal node_modules resolution: the vitest-runner plugin is named by its plain specifier and
  # Stryker resolves it (with its peer @stryker-mutator/api co-resolved) through node — no store path.
  local cfg; cfg="$(mktemp -t "${EDEN_LIB_NAME}-stryker.XXXXXX.json")"
  cat > "$cfg" <<JSON
{
  "packageManager": "npm",
  "testRunner": "vitest",
  "plugins": ["@stryker-mutator/vitest-runner"],
  "vitest": { "configFile": "vitest.config.ts" },
  "mutate": ${mutate_json},
  "reporters": ["clear-text"],
  "coverageAnalysis": "perTest",
  "concurrency": 4,
  "checkers": [],
  "inPlace": true,
  "tempDirName": ".stryker-tmp",
  "cleanTempDir": true,
  "thresholds": { "high": 90, "low": 80, "break": ${EDEN_MUTATION_FLOOR} }
}
JSON

  log_info "mutate: StrykerJS over ${EDEN_LIB_SCOPE}/${EDEN_LIB_NAME} src (break FLOOR ${EDEN_MUTATION_FLOOR}% — the gremlins ≥0.75 analog)"
  local rc=0
  ( cd "$PROJECT_ROOT" && node "$core_bin" run "$cfg" ) || rc=$?

  rm -f "$cfg"
  rm -rf "${PROJECT_ROOT}/.stryker-tmp"

  if [[ $rc -ne 0 ]]; then
    log_error "mutate: mutation score below FLOOR ${EDEN_MUTATION_FLOOR}% (or the run failed) — a survived mutant on covered code is a real test gap (rule 21 §h). Strengthen the test to kill it."
    return 1
  fi
  log_success "mutate: OK (mutation score ≥ ${EDEN_MUTATION_FLOOR}%)"
}

# ── the SDLC phase-gate sequencer (ADR-0024 — mirrors libs/go/_ctl/lib.sh) ────────────────────
# `phase-gate <architecture|implementation|testing|qa|all>` — the mechanical gate per SDLC phase.
# Each gate runs EVERY dimension, prints a per-dimension PASS/FAIL/REQUIRED-BUT-ABSENT table, and
# exits non-zero on ANY failure (a blind gate is visible, never silent). "phase" = the SDLC step,
# NEVER the environment "stage" (CLAUDE.md vocabulary rule).

_GATE_RESULTS=()
_GATE_FAILED=0
_gate_run() {                       # _gate_run <label> <verb-fn> [args...]
  local label="$1"; shift
  printf '%s── phase-gate: %s%s\n' "$_LC_INFO" "$label" "$_LC_RST" >&2
  # errexit semantics (see the Go lib.sh's long note): invoke the verb in a SUBSHELL with `set -e`
  # re-armed, capture $? on the NEXT line so the inner errexit stays live and a RED dimension is
  # never recorded PASS. `exit 127` (FAIL-NOT-SKIP) propagates as 127.
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
  return 0
}

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

_gate_reset() { _GATE_RESULTS=(); _GATE_FAILED=0; }

# PHASE 1 — ARCHITECTURE: frozen contract + skeleton typechecks + name/interface lint + the
# frozen .apibaseline (the component/prop/event/slot surface) is recorded.
phase_architecture() {
  _gate_reset
  log_info "PHASE 1 — ARCHITECTURE (frozen contract + cohesion + frozen exported surface)"
  _gate_run "skeleton typechecks (tsc --noEmit)" cmd_typecheck
  _gate_run "interface/naming lint (HNS-1 name lint, strict eslint)" cmd_lint
  _gate_run "apibaseline recorded (.apibaseline — the frozen .d.ts surface)" _gate_apibaseline_present
  _gate_summary
}

_gate_apibaseline_present() {
  if [[ ! -f "$API_BASELINE" ]]; then
    log_error "no .apibaseline — record the frozen surface: ./ctl.sh apidiff-record"
    return 1
  fi
  log_success "apibaseline present (${API_BASELINE##*/})"
}

# PHASE 2 — IMPLEMENTATION: build + maintainability + apidiff-no-break + the fast test lane GREEN.
phase_implementation() {
  _gate_reset
  log_info "PHASE 2 — IMPLEMENTATION (TDD under the gate)"
  _gate_run "build (tsc emit .js + .d.ts)" cmd_build
  _gate_run "maintainability (typecheck + strict eslint + prettier check)" cmd_maintainability
  _gate_run "apidiff: no break vs .apibaseline (the cardinal-sin gate)" cmd_apidiff
  _gate_run "unit + fake conformance GREEN (vitest)" cmd_test
  _gate_summary
}

# PHASE 3 — TESTING: the UI test taxonomy (ADR-0024 §3). The dimensions that need no real
# substrate / no @eden/theme run fully here; the substrate lanes (integration/load via Playwright)
# and the contrast/axe lanes are wired and REQUIRED for component libs, applied per-lib.
phase_testing() {
  _gate_reset
  log_info "PHASE 3 — TESTING (the UI test taxonomy)"
  _gate_run "unit + fake conformance (vitest)" cmd_test
  _gate_run "property (fast-check invariants)" cmd_property
  _gate_run "cover-floor (per-package vitest istanbul FLOOR)" cmd_cover_floor
  _gate_run "design-correctness (the ninth dimension — math-is-source-of-truth)" cmd_design_correctness
  _gate_summary
}

# PHASE 4 — QA: cross-cutting gates + no-shortcuts + cohesion + mutation + the frozen-surface
# evidence. The mutation lane (StrykerJS) + the cohesion scan (dead-export + cross-lib math
# duplication) are the Stage-3 ENFORCE teeth — the gremlins-≥0.75 + one-concept-one-home analogs the
# TS track previously lacked (mirrors the Go qa gate's `mutate` + `maintainability` cohesion).
phase_qa() {
  _gate_reset
  log_info "PHASE 4 — QUALITY ASSURANCE (cross-cutting gates + cohesion + mutation + adversarial review)"
  _gate_run "maintainability (strict lint + typecheck + name lint + format + cohesion)" cmd_maintainability
  _gate_run "cohesion (dead-export + cross-lib math-duplication — one concept, one home)" cmd_cohesion
  _gate_run "design-correctness (the ninth dimension)" cmd_design_correctness
  _gate_run "no-shortcuts grep (ADR-0017)" _gate_no_shortcuts
  _gate_run "cover-floor (per-package FLOOR)" cmd_cover_floor
  _gate_run "mutate (StrykerJS — break FLOOR ${EDEN_MUTATION_FLOOR}%, the gremlins ≥0.75 analog)" cmd_mutate
  _gate_run "apidiff: no break vs .apibaseline" cmd_apidiff
  _gate_run "evidence bundle present (.apibaseline frozen surface)" _gate_evidence_bundle
  _gate_summary
}

# _gate_no_shortcuts — the ADR-0017 no-shortcuts grep recast for TS: no stub-as-implementation,
# no swallowed error, no TODO/FIXME on a load path. Scans NON-TEST source.
_gate_no_shortcuts() {
  log_info "no-shortcuts: scanning non-test source (ADR-0017: no stub/throw-unimplemented/TODO)"
  local hits=0 out
  out="$(grep -rnE "throw new Error\(['\"](unimplemented|not implemented|TODO)" "$PROJECT_ROOT/src" \
          --include='*.ts' --include='*.svelte' --exclude='*.test.ts' --exclude='*.spec.ts' 2>/dev/null || true)"
  [[ -n "$out" ]] && { log_error "stub throw found:"; printf '%s\n' "$out" >&2; hits=1; }
  out="$(grep -rnE '//\s*(TODO|FIXME)\b' "$PROJECT_ROOT/src" \
          --include='*.ts' --include='*.svelte' --exclude='*.test.ts' --exclude='*.spec.ts' 2>/dev/null || true)"
  [[ -n "$out" ]] && { log_error "TODO/FIXME in non-test source (load path must be complete):"; printf '%s\n' "$out" >&2; hits=1; }
  if [[ $hits -ne 0 ]]; then return 1; fi
  log_success "no-shortcuts: clean"
}

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

  ${EDEN_LIB_SCOPE}/${EDEN_LIB_NAME}: leaf=${EDEN_LIB_LEAF} coverage-floor=${EDEN_COVERAGE_FLOOR}% svelte=${EDEN_HAS_SVELTE}

Authoring verbs:
  build              Emit the library (.js + .d.ts) via tsc
  typecheck          Strict tsc --noEmit (+ svelte-check for component libs)
  lint               eslint over the shared strict flat config (+ HNS-1 name lint)
  format             prettier --check (the gate); fmt to write
  fmt                prettier --write
  test               vitest run (unit + property + fake conformance)

ADR-0024 test-taxonomy verbs:
  property           fast-check invariant suites
  cover-floor        per-package coverage FLOOR
  maintainability    typecheck + strict eslint + format check + cohesion
  cohesion           dead-export + cross-lib math-duplication scan (one concept, one home)
  mutate             StrykerJS mutation lane (break FLOOR ${EDEN_MUTATION_FLOOR}% — the gremlins ≥0.75 analog)
  design-correctness the ninth dimension — math-is-source-of-truth (provenance + design lane)
  apidiff            diff the exported .d.ts surface vs the frozen .apibaseline (cardinal sin)
  apidiff-record     record the frozen surface (architecture gate / contract revision)

ADR-0024 SDLC sequencer:
  phase-gate         <architecture|implementation|testing|qa|all> — the mechanical gate
  help               Show this message
EOF
}

lib_main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)               cmd_build               "$@" ;;
    typecheck)           cmd_typecheck           "$@" ;;
    lint)                cmd_lint                "$@" ;;
    format)              cmd_format              "$@" ;;
    fmt)                 cmd_fmt                 "$@" ;;
    test)                cmd_test                "$@" ;;
    property)            cmd_property            "$@" ;;
    cover-floor)         cmd_cover_floor         "$@" ;;
    maintainability)     cmd_maintainability     "$@" ;;
    cohesion)            cmd_cohesion            "$@" ;;
    mutate)              cmd_mutate              "$@" ;;
    design-correctness)  cmd_design_correctness  "$@" ;;
    apidiff)             cmd_apidiff             "$@" ;;
    apidiff-record)      cmd_apidiff_record      "$@" ;;
    phase-gate)          cmd_phase_gate          "$@" ;;
    help|"")             lib_usage ;;
    *) log_error "unknown command: '$cmd'"; lib_usage; exit 1 ;;
  esac
}
