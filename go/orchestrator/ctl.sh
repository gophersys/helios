#!/usr/bin/env bash
#
# libs/go/orchestrator/ctl.sh — control script for the Eden orchestrator library
# (the orchestration substrate; integration on real docker+k3d+kind).
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
EDEN_LIB_NAME="orchestrator"
EDEN_LIB_LEAF="false"
EDEN_COVERAGE_FLOOR="70"
EDEN_HOT_PATHS="."
EDEN_INTEGRATION_CMDS="go docker k3d kind"
# The reconcile spine's concurrency/convergence/admission/release invariants are exercised most
# heavily by the tagged dimension lanes (lifecycle's Pool double-close + drain, load's fan-out
# Spawn/Stop race, integration's many-agent concurrent churn over the REAL agentsession +
# workspaceprovider seams), so the per-package coverage floor MUST measure those lanes too — the
# same substrate-lib override workspaceprovider uses (cmd_cover reads EDEN_COVER_TAGS). Raise
# tests, never lower the floor.
EDEN_COVER_TAGS="lifecycle load integration"
# `go test -timeout` PER PACKAGE on the substrate lanes — NOT a ceiling on the lane, which spins a
# real cluster and is bounded only by the CI job's own timeout. Same 25m as workspaceprovider, and
# for the same reason: this lib declares `k3d kind` and the reconcile spine's integration lane
# drives the REAL agentsession + workspaceprovider seams, so it inherits that lib's cluster cost.
# The number is ~1.4x the planner's ~18-20 min CI estimate for that lib; it is not a measurement of
# this one.
EDEN_SUBSTRATE_TIMEOUT="25m"
export EDEN_LIB_NAME EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HOT_PATHS EDEN_INTEGRATION_CMDS
export EDEN_COVER_TAGS EDEN_SUBSTRATE_TIMEOUT

# shellcheck source=../_ctl/lib.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/lib.sh"

# -------- usage (drift-check anchor for libs/ctl.sh::cmd_validate) --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]   (orchestrator — leaf=false, coverage-floor=${EDEN_COVERAGE_FLOOR}%)

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
