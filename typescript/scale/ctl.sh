#!/usr/bin/env bash
#
# libs/typescript/scale/ctl.sh — control script for @eden/scale (the modular scale generator;
# the reference LEAF library proving the ADR-0024 TS/Svelte pipeline).
#
# Thin dispatcher (ADR-0024, mirrors libs/go/<lib>/ctl.sh): the verb BODIES live once in
# libs/typescript/_ctl/lib.sh ("one concept, one home", 10 §9). This file sets the per-lib
# metadata and sources the shared library. project.json targets delegate here, so a consumer can
# invoke `nx run scale:phase-gate` without reading source.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT

# -------- per-lib metadata (ADR-0024) --------
EDEN_LIB_NAME="scale"            # the slug → @eden/scale
EDEN_LIB_SCOPE="@eden"
EDEN_LIB_LEAF="true"             # pure dependency-free leaf utility
EDEN_COVERAGE_FLOOR="80"         # leaf-lib FLOOR (ADR-0020); a FLOOR, not a target
EDEN_HAS_SVELTE="false"          # no components — pure math, so no svelte-check / a11y lane
EDEN_MUTATION_FLOOR="75"         # StrykerJS break FLOOR — the gremlins ≥0.75 leaf floor (scale: 77.78%)
export EDEN_LIB_NAME EDEN_LIB_SCOPE EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HAS_SVELTE EDEN_MUTATION_FLOOR

# shellcheck source=../_ctl/lib.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/lib.sh"

# -------- usage (the verb names below MUST match this lib's project.json targets) --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]   (@eden/scale — leaf, coverage-floor=${EDEN_COVERAGE_FLOOR}%)

Commands:
  build              Emit the library (.js + .d.ts) via tsc
  typecheck          Strict tsc --noEmit
  lint               eslint over the shared strict flat config (+ HNS-1 name lint)
  format             prettier --check
  fmt                prettier --write
  test               vitest run (unit + property + design)
  property           fast-check invariant suites
  cover-floor        per-package coverage FLOOR
  maintainability    typecheck + strict eslint + format check + cohesion
  cohesion           dead-export + cross-lib math-duplication scan (one concept, one home)
  mutate             StrykerJS mutation lane (break FLOOR ${EDEN_MUTATION_FLOOR}% — the gremlins ≥0.75 analog)
  design-correctness the ninth dimension — math-is-source-of-truth
  apidiff            diff the exported .d.ts surface vs the frozen .apibaseline
  apidiff-record     record the frozen surface (architecture gate / revision)
  phase-gate         <architecture|implementation|testing|qa|all>
  help               Show this message
EOF
}

case "${1:-help}" in
  help|"") usage ;;
  *)       lib_main "$@" ;;
esac
