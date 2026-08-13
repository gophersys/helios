#!/usr/bin/env bash
#
# libs/go/workspaceprovider/ctl.sh — control script for the Eden workspaceprovider library
# (the F1 workspace substrate; integration on real docker+k3d+kind).
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
EDEN_LIB_NAME="workspaceprovider"
EDEN_LIB_LEAF="false"
EDEN_COVERAGE_FLOOR="70"
EDEN_HOT_PATHS="."
EDEN_INTEGRATION_CMDS="go docker k3d kind"
# The docker/kubernetes adapters' real logic (Create/Run/Exec/Files/credential injection) is
# exercised ONLY through the REAL-substrate `//go:build integration` lane, so the per-package
# coverage floor MUST measure that lane too — otherwise the adapter packages undercount to ~5%.
# This is the engine's sanctioned per-lib override (cmd_cover reads EDEN_COVER_TAGS); a substrate
# lib needs `integration` in the cover tag set.
EDEN_COVER_TAGS="lifecycle load integration"
# `go test -timeout` PER PACKAGE on the substrate lanes — NOT a ceiling on the lane, which stands
# up one k3d or kind cluster per test across several packages and is bounded only by the CI job's
# own timeout. The shared default is Go's own 10m, and kubernetesadapter does not fit in it: the
# planner measured that package at 601.3s isolated / 544.1s in-lane against the 600.0s wall — a coin
# flip at 91-100% of a budget nobody chose, which is why it read as flake. 25m is ~1.4x the ~18-20
# min the planner estimates for CI hardware, which measured ~2x that host.
#
# RE-DERIVE THE SECONDS — the whole justification for 25m is those numbers, so here is what makes
# them again, verbatim:
#
#     cd go/workspaceprovider && ./ctl.sh integration          # in-lane: every package
#     cd go/workspaceprovider && GOWORK=off go test -tags integration -count=1 -v \
#         -timeout=25m ./kubernetesadapter                     # isolated: the one package
#
# It needs a REAL k3d AND a real kind on the host — the lane stands up one cluster per test. It will
# NOT reproduce inside ghcr.io/gophersys/base on an arm64 machine: the image is amd64-only, neither
# substrate is reachable under it, and QEMU seconds would be meaningless anyway. `-v` (which the
# shared integration lane now passes) prints each test's own elapsed time, so a re-derivation
# attributes the wall per test rather than reporting one number.
#
# Measured 2026-08-13, natively, on the arm64 macOS dev host. If a re-run disagrees, the 25m is what
# should move — not this comment.
EDEN_SUBSTRATE_TIMEOUT="25m"
export EDEN_LIB_NAME EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HOT_PATHS EDEN_INTEGRATION_CMDS
export EDEN_COVER_TAGS EDEN_SUBSTRATE_TIMEOUT

# shellcheck source=../_ctl/lib.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/lib.sh"

# -------- usage (drift-check anchor for libs/ctl.sh::cmd_validate) --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]   (workspaceprovider — leaf=false, coverage-floor=${EDEN_COVERAGE_FLOOR}%)

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
