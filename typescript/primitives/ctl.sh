#!/usr/bin/env bash
#
# libs/typescript/primitives/ctl.sh — control script for @eden/primitives (the Eden component
# primitives: accessible Svelte 5 components GENERATED FROM the @eden/theme tokens, on the bits-ui
# behavior layer — RD-16/OD-1). The FIRST component lib proving the ADR-0024 design-correctness +
# a11y-evidence dimensions end-to-end through a real bits-ui/Svelte component.
#
# Thin dispatcher (ADR-0024, mirrors libs/typescript/{scale,theme}/ctl.sh and libs/go/<lib>/ctl.sh):
# the verb BODIES live once in libs/typescript/_ctl/lib.sh ("one concept, one home", 10 §9). This
# file sets the per-lib metadata and sources the shared library. project.json targets delegate here,
# so a consumer can invoke `nx run primitives:phase-gate` without reading source.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT

# -------- per-lib metadata (ADR-0024) --------
EDEN_LIB_NAME="primitives"       # the slug → @eden/primitives
EDEN_LIB_SCOPE="@eden"
EDEN_LIB_LEAF="true"             # the token-derivation math is a pure leaf (no real server substrate);
                                 # the "real substrate" here is the REAL BROWSER (Playwright+axe lane).
EDEN_COVERAGE_FLOOR="80"         # leaf-lib FLOOR (ADR-0020) over the token-derivation math; a FLOOR.
EDEN_HAS_SVELTE="true"           # ships *.svelte → wires svelte-check + the Playwright a11y lane.
# StrykerJS break FLOOR. The mutated surface is the token-derivation math (button/tokens.ts); the
# *.svelte templates are NOT mutated (markup bound to derived vars, like a barrel). 75 mirrors the
# Go leaf floor (gremlins ≥0.75); the derivation math is small + fully asserted, so it holds 75.
EDEN_MUTATION_FLOOR="75"
export EDEN_LIB_NAME EDEN_LIB_SCOPE EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HAS_SVELTE EDEN_MUTATION_FLOOR

# shellcheck source=../_ctl/lib.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/lib.sh"

# -------- usage (the verb names below MUST match this lib's project.json targets) --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]   (@eden/primitives — component lib, coverage-floor=${EDEN_COVERAGE_FLOOR}%, svelte=true)

Commands:
  build              Emit the library (.js + .d.ts) via tsc (+ svelte component sources)
  typecheck          Strict tsc --noEmit + svelte-check (component diagnostics)
  lint               eslint over the shared strict flat config (+ HNS-1 name lint, svelte plugin)
  format             prettier --check
  fmt                prettier --write
  test               vitest run (unit + property + design + component render)
  property           fast-check invariant suites
  cover-floor        per-package coverage FLOOR
  maintainability    typecheck + strict eslint + format check + cohesion
  cohesion           dead-export + cross-lib math-duplication scan (one concept, one home)
  mutate             StrykerJS mutation lane (break FLOOR ${EDEN_MUTATION_FLOOR}% — the gremlins ≥0.75 analog)
  design-correctness the ninth dimension — math-is-source-of-truth + contrast/hit-target/scale gate
  a11y               the A11Y-EVIDENCE lane — axe on Chromium AND WebKit + keyboard (Playwright)
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
