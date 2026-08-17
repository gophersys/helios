#!/usr/bin/env bash
#
# _ctl/tests/egress-policy.test.sh — the build path's 2 egress rules.
#
# ============================================================================
# THE DEFECT THIS FILE EXISTS FOR
# ============================================================================
#
# The first build wave on arc-build (run 32050747682, 2026-08-17) failed 3
# times without a line of this repository's code being wrong, on 2 different
# properties of the path between a build container and the internet:
#
#   1. NESTED MTU. The dind daemon's bridge defaults to MTU 1500 inside a
#      flannel pod interface of MTU 1450. A container on that bridge
#      advertises an MSS the overlay cannot carry, the peer's full-size
#      packets are dropped silently, and the connection stalls until the peer
#      resets it. Whether a fetch survives depends on the PEER: ghcr.io,
#      docker.io and dl.k8s.io tolerated the mismatch, get.helm.sh (Azure)
#      reset it 3 of 3 times at the same ~126s offset. Proven by a controlled
#      probe on k3s-w-0: the same URL timed out from a bridge container at
#      MTU 1500 and succeeded at MTU 1400, and succeeded from the pod's own
#      namespace. The fix is that no bridge exists on the build path at all:
#      the builder container and its RUN steps share the pod's namespace,
#      whose MTU the CNI sizes.
#
#   2. BOOT-TIME REGISTRY DEPENDENCE. With no image named, buildx boots the
#      builder from docker.io/moby/buildkit:buildx-stable-1 — an unpinned tag
#      on a registry nothing else here uses, pulled before any line of ours
#      runs. Attempt 2 died on a 502 from auth.docker.io in exactly that pull.
#      The fix is BUILDKIT_REF: the same image mirrored into ghcr.io, pinned
#      by index digest, kept populated by .ci/mirror-buildkit.sh.
#
# Both fixes are 1-line-shaped and both would vanish silently in a refactor —
# a builder that lost `network=host` still builds, on every host that
# tolerates the mismatch, and fails only on the next Azure-shaped peer. That
# is the class this file pins: the TOKENS of the 2 rules, in the files that
# carry them, plus the retry posture of the 2 fetch helpers (weather exists
# even with both rules in place — the 502 above was real).
#
# Like platform-policy.test.sh, this file asserts LITERALS on purpose: a check
# that read the value out of the script it checks would agree with any value.
#
set -Eeuo pipefail
IFS=$'\n\t'

TEST_NAME="egress-policy"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$PROJECT_ROOT/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$PROJECT_ROOT/tests/harness.sh"

BUILDX_NODE="$REPO_ROOT/.ci/buildx-node.sh"
MIRROR="$REPO_ROOT/.ci/mirror-buildkit.sh"
FETCH="$REPO_ROOT/_build/fetch-verified.sh"
RESOLVER="$REPO_ROOT/_build/resolve-upstream.sh"
WORKFLOW="$REPO_ROOT/.github/workflows/build-and-push.yml"
PROVIDER_WORKFLOW="$REPO_ROOT/.ci/providers/github/build-and-push.yml"

# ----------------------------------------------------------------------------
# Rule 1: no bridge on the build path. Both halves, because each covers a
# namespace the other does not: network=host places the BUILDER container in
# the pod, --oci-worker-net=host places every RUN step in the builder's.
# ----------------------------------------------------------------------------

if grep -q -- '--driver-opt network=host' "$BUILDX_NODE"; then
  pass_check "buildx-node: the builder container shares the pod namespace (network=host)"
else
  fail_check "buildx-node: the builder container shares the pod namespace (network=host)" \
    "no '--driver-opt network=host' in ${BUILDX_NODE} — the builder is back on the dind bridge, MTU 1500 inside 1450"
fi

if grep -q -- "--buildkitd-flags '--oci-worker-net=host'" "$BUILDX_NODE"; then
  pass_check "buildx-node: RUN steps share the builder namespace (--oci-worker-net=host)"
else
  fail_check "buildx-node: RUN steps share the builder namespace (--oci-worker-net=host)" \
    "no --oci-worker-net=host in ${BUILDX_NODE} — every RUN fetch rides BuildKit's own bridge again"
fi

# ----------------------------------------------------------------------------
# Rule 2: the builder boots from OUR registry, pinned by digest, and only the
# mirror script may name the docker.io source.
# ----------------------------------------------------------------------------

# The ${} below must NOT expand: the assertion is that the script reads the
# library variable, not any particular value of it.
# shellcheck disable=SC2016
if grep -q -- '--driver-opt "image=${BUILDKIT_REF}"' "$BUILDX_NODE"; then
  pass_check "buildx-node: the builder boots from BUILDKIT_REF"
else
  fail_check "buildx-node: the builder boots from BUILDKIT_REF" \
    "no image= driver-opt reading BUILDKIT_REF in ${BUILDX_NODE} — the boot is back on docker.io's moving tag"
fi

buildkit_ref_line="$(grep -E '^export BUILDKIT_REF=' "$PROJECT_ROOT/lib.sh" || true)"
if [[ "$buildkit_ref_line" =~ ^export\ BUILDKIT_REF=\"ghcr\.io/gophersys/buildkit:[^@\"]+@sha256:[0-9a-f]{64}\"$ ]]; then
  pass_check "lib.sh: BUILDKIT_REF names ghcr.io and carries a full index digest"
else
  fail_check "lib.sh: BUILDKIT_REF names ghcr.io and carries a full index digest" \
    "got: ${buildkit_ref_line:-<no BUILDKIT_REF row>}"
fi

upstream_ref_line="$(grep -E '^export BUILDKIT_UPSTREAM_REF=' "$PROJECT_ROOT/lib.sh" || true)"
ref_digest="${buildkit_ref_line##*@}"
upstream_digest="${upstream_ref_line##*@}"
if [[ -n "$ref_digest" && "$ref_digest" == "$upstream_digest" ]]; then
  pass_check "lib.sh: the mirror and its upstream pin the SAME digest"
else
  fail_check "lib.sh: the mirror and its upstream pin the SAME digest" \
    "mirror:   ${ref_digest:-<none>}" \
    "upstream: ${upstream_digest:-<none>} — a copy of one digest verified against another cannot succeed"
fi

# Comment lines may SAY docker.io — the header explains why it left — so the
# rule reads code lines only.
if grep -v '^[[:space:]]*#' "$BUILDX_NODE" | grep -q 'docker\.io'; then
  fail_check "buildx-node: no docker.io on the boot path" \
    "$(grep -v '^[[:space:]]*#' "$BUILDX_NODE" | grep -n 'docker\.io')"
else
  pass_check "buildx-node: no docker.io on the boot path"
fi

if grep -q 'BUILDKIT_UPSTREAM_REF' "$MIRROR"; then
  pass_check "mirror-buildkit: the cold-path copy reads BUILDKIT_UPSTREAM_REF"
else
  fail_check "mirror-buildkit: the cold-path copy reads BUILDKIT_UPSTREAM_REF" \
    "the mirror script no longer reads the upstream pin, so the cold path copies nothing anybody declared"
fi

# ----------------------------------------------------------------------------
# The workflow wiring: in every build job, the registry login comes first, the
# mirror step second, the builder third. The builder pulls a PRIVATE ghcr
# package, so a builder step above the login boots anonymously and is refused;
# a mirror step below the builder populates the registry after the boot needed
# it. The order is asserted per job by line position, in both copies —
# platform-policy.test.sh already holds the 2 copies byte-identical, and this
# file still checks both so a red here names the file that actually broke.
# ----------------------------------------------------------------------------

for wf in "$WORKFLOW" "$PROVIDER_WORKFLOW"; do
  wf_name="$(basename "$(dirname "$wf")")/$(basename "$wf")"
  login_lines="$(grep -n 'uses: docker/login-action@v3' "$wf" | cut -d: -f1)"
  mirror_lines="$(grep -n 'run: bash .ci/mirror-buildkit.sh' "$wf" | cut -d: -f1)"
  buildx_lines="$(grep -n 'run: bash .ci/buildx-node.sh' "$wf" | cut -d: -f1)"
  n_login="$(printf '%s\n' "$login_lines" | grep -c . || true)"
  n_mirror="$(printf '%s\n' "$mirror_lines" | grep -c . || true)"
  n_buildx="$(printf '%s\n' "$buildx_lines" | grep -c . || true)"

  if [[ "$n_login" -eq 5 && "$n_mirror" -eq 5 && "$n_buildx" -eq 5 ]]; then
    pass_check "${wf_name}: all 5 build jobs carry login + mirror + builder"
  else
    fail_check "${wf_name}: all 5 build jobs carry login + mirror + builder" \
      "login=${n_login} mirror=${n_mirror} buildx=${n_buildx} — a job is missing a step, and its builder boots unauthenticated or unmirrored"
    continue
  fi

  order_ok=1
  for i in 1 2 3 4 5; do
    l="$(printf '%s\n' "$login_lines" | sed -n "${i}p")"
    m="$(printf '%s\n' "$mirror_lines" | sed -n "${i}p")"
    b="$(printf '%s\n' "$buildx_lines" | sed -n "${i}p")"
    if [[ "$l" -ge "$m" || "$m" -ge "$b" ]]; then
      order_ok=0
      fail_check "${wf_name}: job ${i} orders login -> mirror -> builder" \
        "login@${l} mirror@${m} builder@${b}"
    fi
  done
  if [[ "$order_ok" -eq 1 ]]; then
    pass_check "${wf_name}: every job orders login -> mirror -> builder"
  fi
done

# ----------------------------------------------------------------------------
# The retry posture of the 2 fetch helpers. --retry-all-errors is the token
# that matters: without it curl's retry set skips a mid-transfer reset, which
# is the failure this path actually produces. The digest comparison in
# fetch-verified.sh is what keeps a retry from ever changing WHICH bytes
# install, so widening the retry set is safe there by construction.
# ----------------------------------------------------------------------------

fetch_curl="$(grep -c -- '--retry-all-errors' "$FETCH" || true)"
if [[ "$fetch_curl" -ge 1 ]]; then
  pass_check "fetch-verified: the fetch retries on any transient failure"
else
  fail_check "fetch-verified: the fetch retries on any transient failure" \
    "no --retry-all-errors in ${FETCH} — one reset kills a 40-minute build again"
fi

# The invocation spelling, not the word: a comment or an error message that
# SAYS curl must not count as a fetch site.
resolver_curl_total="$(grep -cE 'curl -fsSL' "$RESOLVER" || true)"
resolver_curl_retrying="$(grep -E 'curl -fsSL' "$RESOLVER" | grep -c -- '--retry-all-errors' || true)"
if [[ "$resolver_curl_total" -ge 1 && "$resolver_curl_total" -eq "$resolver_curl_retrying" ]]; then
  pass_check "resolve-upstream: every curl invocation retries (${resolver_curl_retrying}/${resolver_curl_total})"
else
  fail_check "resolve-upstream: every curl invocation retries" \
    "${resolver_curl_retrying} of ${resolver_curl_total} curl invocations carry --retry-all-errors — the ones that do not are the Monday failures"
fi

test_summary "$TEST_NAME"
