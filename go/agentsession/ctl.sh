#!/usr/bin/env bash
#
# libs/go/agentsession/ctl.sh — control script for the Eden agentsession library
# (the agent-session substrate; load lane for fan-out REQ-0022).
#
# Thin dispatcher (ADR-0020): the verb BODIES live once in libs/go/_ctl/lib.sh
# ("one concept, one home", 10 §9). This file sets the per-lib metadata and sources
# the shared library. project.json targets delegate here.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT

# -------- per-lib metadata (ADR-0020) --------
EDEN_LIB_NAME="agentsession"
EDEN_LIB_LEAF="false"
EDEN_COVERAGE_FLOOR="70"
EDEN_HOT_PATHS="."
EDEN_INTEGRATION_CMDS="go docker k3d kind"
# The harness lane (opt-in; NOT run in libs CI — it runs in eden's harness-conformance at PR-2,
# which holds the vendor credentials and the pinned harnesses, ADR-0021 one-home). require_cmd
# names the binaries, require_env names the credentials — each a FAIL-NOT-SKIP, never a t.Skip.
EDEN_HARNESS_CMDS="claude omp"
EDEN_HARNESS_CREDENTIALS="CLAUDEADAPTER_LIVE_TOKEN OPENROUTER_API_KEY"
export EDEN_LIB_NAME EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HOT_PATHS EDEN_INTEGRATION_CMDS
export EDEN_HARNESS_CMDS EDEN_HARNESS_CREDENTIALS

# shellcheck source=../_ctl/lib.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/lib.sh"

# -------- usage (drift-check anchor for libs/ctl.sh::cmd_validate) --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]   (agentsession — leaf=false, coverage-floor=${EDEN_COVERAGE_FLOOR}%)

Commands:
  build            Compile the library (go build ./...)
  test             Unit + fake conformance with the race detector
  lint             gofumpt + go vet + golangci-lint (shared strict set)
  vet              go vet ./...
  fmt              gofumpt -w .
  cover            Tests with coverage; print the total
  property         pgregory.net/rapid property suites
  leak             goleak — zero leaked goroutines/fds
  lifecycle        construct-use-double-close-teardown conformance
  integration      REAL docker + k3s/k3d (+ kind) substrate suite
  load             fan-out concurrency, race-clean under N
  harness          REAL vendor harnesses + models (opt-in; FAIL-NOT-SKIP; NOT run in libs CI)
  vuln             govulncheck — 0 applicable vulnerabilities
  sast             gosec — 0 high/medium findings
  secretscan       gitleaks + the SeededCanary no-leak property
  bench            Hot-path benchmarks (-benchmem -count=10)
  bench-guard      benchstat HEAD vs baseline — no >+10% regression
  bench-record     Refresh the performance baseline (reviewed action)
  maintainability  Strict lint + hnslint + doc coverage + cohesion scan
  mutate           gremlins mutation score (>= 0.75 on leaf libs)
  cover-floor      Per-package coverage FLOOR
  apidiff          Diff the exported surface vs the frozen .apibaseline
  apidiff-record   Record the frozen surface (architecture gate / revision)
  phase-gate       <architecture|implementation|testing|qa|all>
  help             Show this message
EOF
}

case "${1:-help}" in
  help|"") usage ;;
  *)       lib_main "$@" ;;
esac
