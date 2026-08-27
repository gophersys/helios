#!/usr/bin/env bash
#
# libs/go/forge/ctl.sh — control script for the Eden forge library (the remote
# source-code-forge connector; the GitHub REST adapter owns the forge management API).
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
EDEN_LIB_NAME="forge"
EDEN_LIB_LEAF="true"
EDEN_COVERAGE_FLOOR="80"
EDEN_HOT_PATHS="./githubadapter"
# The forge integration lane talks to the REAL github.com REST API over a real
# *http.Client, gated by a throwaway PAT (EDEN_FORGE_GITHUB_TOKEN) + owner
# (EDEN_FORGE_GITHUB_OWNER). Its substrate is the network, not docker/k3d — so the
# integration command requirement is `go` only; the live gating is the env + the
# `integration` build tag (the suite Skips, never fails, when the PAT is absent).
EDEN_INTEGRATION_CMDS="go"
export EDEN_LIB_NAME EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HOT_PATHS EDEN_INTEGRATION_CMDS

# shellcheck source=../_ctl/lib.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/lib.sh"

# -------- usage (drift-check anchor for libs/ctl.sh::cmd_validate) --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]   (forge — leaf=true, coverage-floor=${EDEN_COVERAGE_FLOOR}%)

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
  integration      REAL github.com REST API (PAT-gated; creates+deletes a throwaway repo)
  load             fan-out concurrency, race-clean under N
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
