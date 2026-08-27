#!/usr/bin/env bash
#
# libs/go/secrets/ctl.sh — control script for the Eden secrets library
# (the secret-reference / redaction pattern; leaf).
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
EDEN_LIB_NAME="secrets"
# The lib gained a REAL-substrate adapter (vaultadapter, ADR-0022 #1): its Vault backend resolves
# against a REAL hashicorp/vault container, proven by the //go:build integration lane — exactly the
# posture workspaceprovider adopted when it gained the docker adapter. So leaf=false: a substrate
# adapter's real behaviour is proven by integration (real Vault), NOT by mutation (gremlins runs the
# UNIT suite GOWORK=off, which cannot reach the real vault/api transport — every such mutant would
# vacuously LIVE). The pure value types (Reference/Secret/Mediator) stay heavily covered by the
# property (1000 rapid checks), canary, conformance, and unit lanes that still run on every gate.
EDEN_LIB_LEAF="false"
# 70% floor matches the substrate-adapter posture (workspaceprovider): the adapter's real logic
# (login/token-file/KV read) is exercised through the integration lane, included in the cover tags.
EDEN_COVERAGE_FLOOR="70"
EDEN_HOT_PATHS="."
# The Vault backend's real behaviour is leveraged through a REAL docker-run hashicorp/vault container
# (docker-out-of-docker); the integration lane requires the docker CLI.
EDEN_INTEGRATION_CMDS="go docker"
# The vaultadapter's parse/token/KV/mint real logic is exercised ONLY through the REAL-substrate
# //go:build integration lane, so the per-package coverage floor MUST measure that lane too (else the
# adapter package undercounts to its fake-only unit number). The engine's sanctioned per-lib override.
EDEN_COVER_TAGS="lifecycle load integration"
export EDEN_LIB_NAME EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HOT_PATHS EDEN_INTEGRATION_CMDS
export EDEN_COVER_TAGS

# shellcheck source=../_ctl/lib.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/lib.sh"

# -------- usage (drift-check anchor for libs/ctl.sh::cmd_validate) --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]   (secrets — leaf=${EDEN_LIB_LEAF}, coverage-floor=${EDEN_COVERAGE_FLOOR}%)

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
