#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────────
# Phase D Layer 3 — release-range runner-rebuild gate
# ───────────────────────────────────────────────────────────────────
#
# Called by /concord-release between pre-flight and version-bump.
#
# Purpose: refuse to cut a release that touches `libs/python/corekinect/`,
# `libs/protocols/mtib/`, or `tools/corectl/` UNLESS `test-runner` is in
# the Nx affected-projects set for the same range. If a release ships
# corekinect changes without rebuilding the runner image, the deployed
# runner pods drift from the platform — the v0.12.0->0.12.3 silent
# skew failure mode.
#
# ADDITIONALLY (contract #2): when `libs/protocols/mtib/` changes,
# `mtib-server` must ALSO be in the affected set — the edge server
# compiles the same gRPC stubs as the runner. A proto bump that rebuilds
# only the runner leaves the deployed mtib-server image stale, so the new
# RPCs return UNIMPLEMENTED ("Method not found!") at runtime — the
# HealthCheck/UartStream outage where every panel failed at step 1 with
# the hardware perfectly fine.
#
# Usage:
#   check-runner-affected.sh <last_tag> [<head_ref>]
#
# Env:
#   CONCORD_FORCE_NO_RUNNER_REBUILD=1   bypass the runner gate (loud-warn)
#   CONCORD_FORCE_NO_MTIB_REBUILD=1     bypass the mtib-server gate (loud-warn)
#   NX_AFFECTED_CMD=<cmd>               override nx command (tests)
#
# Exits:
#   0  — paths of interest not touched in range  (silent)
#   0  — paths touched AND test-runner is affected (info note)
#   0  — paths touched AND test-runner NOT affected, but
#        CONCORD_FORCE_NO_RUNNER_REBUILD=1 set (loud-warn)
#   1  — paths touched AND test-runner NOT affected (hard fail)
#   2  — usage / internal error
#
# ───────────────────────────────────────────────────────────────────
set -euo pipefail

# Colours mirror deploy/ctl.sh so the operator's terminal looks consistent.
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

err()  { echo -e "${RED}[runner-gate]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[runner-gate]${NC} $*"; }
info() { echo -e "${CYAN}[runner-gate]${NC} $*"; }
ok()   { echo -e "${GREEN}[runner-gate]${NC} $*"; }

usage() {
  cat <<EOF
Usage: check-runner-affected.sh <last_tag> [<head_ref>]

Refuse a release when libs/python/corekinect/, libs/protocols/mtib/, or
tools/corectl/ changed between <last_tag> and <head_ref> (default HEAD)
unless 'test-runner' is in the Nx affected-projects set.

Environment:
  CONCORD_FORCE_NO_RUNNER_REBUILD=1   bypass (loud warn)
  NX_AFFECTED_CMD                     override the nx invocation
                                      (default: 'nx show projects --affected')

See .claude/knowledge/deploy/runner.md (Layer 3) for the full design.
EOF
}

# ───────────────────────────────────────────────────────────────────
# Argument parsing
# ───────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  err "missing required argument: <last_tag>"
  echo "" >&2
  usage >&2
  exit 2
fi

LAST_TAG="$1"
HEAD_REF="${2:-HEAD}"

# ───────────────────────────────────────────────────────────────────
# Paths of interest — anything that the runner image bakes in.
# Keep in lockstep with deploy/runner/project.json `implicitDependencies`
# and deploy/runner/Dockerfile COPY lines.
# ───────────────────────────────────────────────────────────────────

PATHS_OF_INTEREST=(
  "libs/python/corekinect/"
  "libs/protocols/mtib/"
  "tools/corectl/"
)

# ───────────────────────────────────────────────────────────────────
# Step 1 — what changed between LAST_TAG and HEAD_REF?
# ───────────────────────────────────────────────────────────────────

if ! git rev-parse --verify "${LAST_TAG}" &>/dev/null; then
  err "last_tag '${LAST_TAG}' does not resolve to a git ref"
  exit 2
fi
if ! git rev-parse --verify "${HEAD_REF}" &>/dev/null; then
  err "head_ref '${HEAD_REF}' does not resolve to a git ref"
  exit 2
fi

touched_paths=$(git diff --name-only "${LAST_TAG}..${HEAD_REF}" -- "${PATHS_OF_INTEREST[@]}" 2>/dev/null || true)

if [[ -z "${touched_paths}" ]]; then
  # Nothing of interest changed — gate is a no-op.
  exit 0
fi

# Something touched. Continue to step 2.

# ───────────────────────────────────────────────────────────────────
# Step 2 — is test-runner in the Nx affected set for this range?
# ───────────────────────────────────────────────────────────────────

NX_CMD="${NX_AFFECTED_CMD:-nx show projects --affected --base=${LAST_TAG} --head=${HEAD_REF}}"

# Capture the affected list. We don't fail-on-error here because some
# CI environments call nx through a wrapper that prints headers we
# want to ignore; we just look for the project name in the output.
set +e
affected_output=$(${NX_CMD} 2>&1)
nx_exit=$?
set -e

# Detect total nx failure (e.g., submodule-mount issue where the
# devcontainer can't reach the parent .git/modules, or nx itself isn't
# on PATH because we're on the host). Distinct from "nx ran fine and
# test-runner wasn't in the output" — falling back to a hard fail in
# that case would be a false positive. Surface it explicitly and ask
# the operator to re-run from a context where nx can resolve the
# base..head diff.
if [[ ${nx_exit} -ne 0 ]] && echo "${affected_output}" | grep -qE "not a git repository|Command failed: git diff|fatal:|command not found|No such file|not recognized"; then
  warn "release-range runner-rebuild gate: nx-affected query failed to run."
  warn "  command: ${NX_CMD}"
  warn "  output:"
  echo "${affected_output}" | sed 's/^/    /' >&2
  warn ""
  warn "  This usually means you are running the gate from a context"
  warn "  where git/nx cannot resolve the ${LAST_TAG}..${HEAD_REF} range"
  warn "  (e.g., concord checked out as a submodule and the devcontainer"
  warn "  has no parent .git/modules mount). Re-run the gate from a"
  warn "  standalone concord clone, OR set NX_AFFECTED_CMD to a wrapper"
  warn "  that runs nx-affected against a context that can see the range."
  warn ""
  warn "  Treating as inconclusive — passing through so the release can"
  warn "  proceed, but the operator MUST verify test-runner rebuilds"
  warn "  during Phase 9/10 deploys. Look for 'Test runner' in cmd_build"
  warn "  output."
  exit 0
fi

if echo "${affected_output}" | grep -qx "test-runner"; then
  runner_affected=true
else
  runner_affected=false
fi

# mtib-server must ALSO rebuild when the mtib *protocol* changes — the
# edge server compiles the same gRPC stubs as the runner (contract #2).
# Skipping it is what caused the HealthCheck/UartStream UNIMPLEMENTED
# outage: a proto bump rebuilt the runner but left the deployed
# mtib-server image stale, so the new RPCs came back "Method not found!"
# and every panel failed at step 1 with the hardware perfectly fine.
if echo "${touched_paths}" | grep -q "^libs/protocols/mtib/"; then
  proto_touched=true
else
  proto_touched=false
fi
if echo "${affected_output}" | grep -qx "mtib-server"; then
  mtib_affected=true
else
  mtib_affected=false
fi

# ───────────────────────────────────────────────────────────────────
# Step 3 — decide
# ───────────────────────────────────────────────────────────────────

# Summarise touched projects (for log messages) — strip the trailing /
# from each path-of-interest and pick the highest-level prefix that
# matched. Cheap and deterministic.
summarise_touched() {
  local lines="$1"
  local seen=""
  while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    for p in "${PATHS_OF_INTEREST[@]}"; do
      if [[ "${line}" == ${p}* ]]; then
        local short="${p%/}"
        if [[ ",${seen}," != *",${short},"* ]]; then
          seen="${seen}${seen:+,}${short}"
        fi
      fi
    done
  done <<< "${lines}"
  echo "${seen}"
}

touched_summary=$(summarise_touched "${touched_paths}")

# test-runner must rebuild for ANY touched path; mtib-server must ALSO
# rebuild when the mtib protocol changed. Each requirement has its own
# escape hatch so an operator can override them independently.

runner_ok=false
if ${runner_affected}; then
  runner_ok=true
elif [[ "${CONCORD_FORCE_NO_RUNNER_REBUILD:-0}" == "1" ]]; then
  warn "═══════════════════════════════════════════════════════════════════"
  warn "  CONCORD_FORCE_NO_RUNNER_REBUILD=1 — bypassing runner-rebuild gate"
  warn "  Range ${LAST_TAG}..${HEAD_REF} touched: ${touched_summary}"
  warn "  test-runner is NOT in the Nx affected set. Runner pods will run"
  warn "  stale corekinect/protocols/corectl. Explicit override."
  warn "═══════════════════════════════════════════════════════════════════"
  runner_ok=true
fi

mtib_ok=true
if ${proto_touched} && ! ${mtib_affected}; then
  if [[ "${CONCORD_FORCE_NO_MTIB_REBUILD:-0}" == "1" ]]; then
    warn "═══════════════════════════════════════════════════════════════════"
    warn "  CONCORD_FORCE_NO_MTIB_REBUILD=1 — bypassing mtib-server-rebuild gate"
    warn "  libs/protocols/mtib/ changed but mtib-server is NOT in the Nx"
    warn "  affected set. Deployed edge servers will lack the new RPCs."
    warn "  Explicit override."
    warn "═══════════════════════════════════════════════════════════════════"
  else
    mtib_ok=false
  fi
fi

if ${runner_ok} && ${mtib_ok}; then
  ok "release-range proto/runner-rebuild gate: OK"
  info "  touched in range: ${touched_summary}"
  if ${runner_affected}; then
    info "  test-runner IS in the Nx affected set — the deploy will rebuild it."
  fi
  if ${proto_touched} && ${mtib_affected}; then
    info "  mtib-server IS in the Nx affected set — the proto change will rebuild the edge server."
  fi
  exit 0
fi

# ── One or both requirements unmet — fail with specific guidance. ────
if ! ${runner_ok}; then
  err "release-range runner-rebuild gate: FAIL"
  err "  paths touched in ${LAST_TAG}..${HEAD_REF}: ${touched_summary}"
  err "  test-runner is NOT in the Nx affected set."
  err ""
  err "  The runner Docker image bakes corekinect/protocols/corectl in at"
  err "  build time. A release that ships changes to those without"
  err "  rebuilding the runner image leaves deployed pods on the old code"
  err "  — the v0.12.0->0.12.3 silent-skew failure mode."
  err ""
  err "  Fix one of these BEFORE retrying the release:"
  err "    1. Ensure deploy/runner/project.json implicitDependencies"
  err "       covers corekinect, protocols, corectl (Phase D Layer 1)."
  err "    2. Confirm the Nx affected query is correct: ${NX_CMD}"
  err "    3. Intentional ship-without-rebuild (rare): set"
  err "         CONCORD_FORCE_NO_RUNNER_REBUILD=1"
fi
if ! ${mtib_ok}; then
  err "release-range mtib-server-rebuild gate: FAIL"
  err "  libs/protocols/mtib/ changed in ${LAST_TAG}..${HEAD_REF} but"
  err "  mtib-server is NOT in the Nx affected set."
  err ""
  err "  The mtib-server image compiles the SAME gRPC stubs as the runner."
  err "  Shipping a proto change without rebuilding AND redeploying"
  err "  mtib-server leaves the edge Verdins on a server missing the new"
  err "  RPCs — the HealthCheck/UartStream 'Method not found!' (UNIMPLEMENTED)"
  err "  outage where every panel failed at step 1 with the hardware fine."
  err ""
  err "  Fix BEFORE retrying the release:"
  err "    1. Confirm apps/edge/mtib-server/project.json implicitDependencies"
  err "       covers protocols (it should)."
  err "    2. Rebuild + push the arm64 image (nx run mtib-server:containerize"
  err "       -c production) AND redeploy the fixture MTIB deployments."
  err "    3. Intentional override (rare): set CONCORD_FORCE_NO_MTIB_REBUILD=1"
fi
exit 1
