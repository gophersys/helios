#!/usr/bin/env bash
#
# libs/go/edenhttp/ctl.sh — control script for the Eden edenhttp library (the reusable HTTP spine:
# the 6-stage handler pipeline + uniform envelope + SSE writer/stream + dev-JWT identity/grants, and
# the natssse JetStream→SSE bridge; ADR-0022 #3).
#
# Thin dispatcher (ADR-0020): the verb BODIES live once in libs/go/_ctl/lib.sh
# ("one concept, one home", 10 §9). This file sets the per-lib metadata and sources the shared
# library. project.json targets delegate here.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT

# -------- per-lib metadata (ADR-0020) --------
EDEN_LIB_NAME="edenhttp"
# edenhttp carries a REAL-substrate adapter sub-package (natssse): its JetStream→SSE bridge is proven
# against a REAL embedded nats-server with JetStream AND a real nats:latest container
# (docker-out-of-docker), exactly the natsbus posture. So leaf=false: the bridge's real behaviour is
# proven by the //go:build integration lane (real NATS), NOT by mutation (gremlins runs the UNIT
# suite GOWORK=off, which cannot reach the real NATS transport — every such mutant would vacuously
# LIVE, a blind gate). The pure spine (pipeline, envelope, SSE framing, grant grammar, dev-JWT
# verify) stays heavily covered by the property (1000 rapid checks), conformance, lifecycle, load
# and unit lanes that still run on every gate.
EDEN_LIB_LEAF="false"
# 70% floor matches the substrate-adapter posture (agentruntime/secrets/workspaceprovider): the
# bridge's real logic (open-consumer / replay-by-seq / heartbeat / reap) is exercised through the
# integration lane, included in the cover tags below.
EDEN_COVERAGE_FLOOR="70"
EDEN_HOT_PATHS="."
# The natssse bridge's real behaviour is leveraged through a REAL embedded nats-server (fast lanes)
# AND a REAL docker-run nats:latest container (the integration lane), so the integration lane
# requires the docker CLI (docker-out-of-docker).
EDEN_INTEGRATION_CMDS="go docker"
# The natssse open-consumer/replay/heartbeat/reap real logic is exercised through the
# //go:build integration lane (real embedded server + real container), so the per-package coverage
# floor MUST measure that lane too (else the bridge package undercounts to its unit-only number).
EDEN_COVER_TAGS="lifecycle load integration"
export EDEN_LIB_NAME EDEN_LIB_LEAF EDEN_COVERAGE_FLOOR EDEN_HOT_PATHS EDEN_INTEGRATION_CMDS
export EDEN_COVER_TAGS

# shellcheck source=../_ctl/lib.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../_ctl/lib.sh"

# -------- usage (drift-check anchor for libs/ctl.sh::cmd_validate) --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]   (edenhttp — leaf=false, coverage-floor=${EDEN_COVERAGE_FLOOR}%)

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
  integration      REAL nats-server/JetStream (embedded + container) SSE-bridge suite
  load             fan-out concurrency, race-clean under N
  vuln             govulncheck — 0 applicable vulnerabilities
  sast             gosec — 0 high/medium findings
  secretscan       gitleaks + the SeededCanary no-leak property
  bench            Hot-path benchmarks (-benchmem -count=10)
  bench-guard      benchstat HEAD vs baseline — no >+10% regression
  bench-record     Refresh the performance baseline (reviewed action)
  maintainability  Strict lint + hnslint + doc coverage + cohesion scan
  mutate           gremlins mutation score (skipped on substrate adapters)
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
