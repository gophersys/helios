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
# a builder that lost the pod namespace still builds, on every host that
# tolerates the mismatch, and fails only on the next Azure-shaped peer. That
# is the class this file pins: the TOKENS of the 2 rules, in the files that
# carry them, plus the retry posture of the 2 fetch helpers (weather exists
# even with both rules in place — the 502 above was real).
#
# Like platform-policy.test.sh, this file asserts LITERALS on purpose: a check
# that read the value out of the script it checks would agree with any value.
#
# ============================================================================
# THE 3 TOKENS MOVED WHEN THE DRIVER DID. THE INVARIANTS DID NOT
# ============================================================================
#
# .ci/buildx-node.sh made a `docker-container` builder and appended the mini
# with `--driver remote`. buildx refuses a builder whose nodes disagree on the
# driver, so the local node is a `remote` node now too: a standalone buildkitd
# container the script starts itself. Every one of these 3 rules survived that
# rewrite, spelled differently, because each one is a property of the BUILD and
# not of a driver:
#
#   was                                      is
#   --driver-opt network=host                --network host       (docker run)
#   --buildkitd-flags '--oci-worker-net=host' --oci-worker-net=host (daemon argv)
#   --driver-opt "image=${BUILDKIT_REF}"     "$BUILDKIT_REF"      (the image run)
#
# All 3 now live in ONE `docker run` command, so the detectors below read that
# command rather than the file. That is deliberate and it is the property the
# old greps had by accident: the implementer of the rewrite was explicitly
# unwilling to satisfy a file-wide grep with a comment, and a file-wide grep is
# exactly what a comment can satisfy. This file must not ask for less.
#
# Reading the COMMAND also buys a rule a grep could not state at all: whether a
# flag is in docker's options or in the daemon's argv. `--oci-worker-net=host`
# BEFORE the image is an argument docker rejects; after it, it is the flag
# buildkitd reads. The reader below tells the 2 apart by position.
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
# The reader the 3 buildx-node rules share.
#
# docker_run_arguments <file> — the argv of every `docker run` command in the
# file, 1 argument per line, as
#
#   <position>|<argument>
#
# where <position> is:
#   option   an argument DOCKER reads   (before the image)
#   image    the image the run starts   (the first argument that is not a flag)
#   daemon   an argument the started PROCESS reads (after the image)
#
# It drops comment lines BEFORE joining, which is what makes a comment unable
# to satisfy any rule below — the old file-wide greps could be satisfied by
# one, and the implementer of the driver rewrite refused to do that. It reads
# the continuation block of the command and stops at the line that does not end
# in a backslash, so a `docker run` elsewhere in the file is a separate block
# and a token outside every block is invisible here.
#
# A trailing redirection is stripped, so `--oci-worker-net=host >/dev/null`
# reads as the flag it is.
#
# THE ONE ASSUMPTION, stated because it can be violated: docker's own order,
# `docker run [OPTIONS] IMAGE [COMMAND] [ARG...]`, plus this repository's
# 1-argument-per-continuation-line style. A flag whose VALUE slid onto its own
# line would be read as the image — and that does not fail silently, because
# the image is asserted to be exactly "$BUILDKIT_REF" and the reader would name
# whatever it found instead.
# ----------------------------------------------------------------------------
function docker_run_arguments() {
  local file="$1"
  awk '
    function emit(argument) {
      sub(/[[:space:]]*[0-9]*>.*$/, "", argument)
      sub(/[[:space:]]+$/, "", argument)
      if (argument == "") { return }
      if (!seen_image && argument !~ /^-/) {
        seen_image = 1
        printf "image|%s\n", argument
        return
      }
      printf "%s|%s\n", (seen_image ? "daemon" : "option"), argument
    }
    {
      line = $0
      if (line ~ /^[[:space:]]*#/) { next }
      sub(/[[:space:]]+$/, "", line)
      continues = (line ~ /\\$/)
      sub(/\\$/, "", line)
      sub(/^[[:space:]]+/, "", line)
      sub(/[[:space:]]+$/, "", line)

      if (!inside) {
        if (line ~ /^docker[[:space:]]+run([[:space:]]|$)/) {
          inside = 1
          seen_image = 0
          sub(/^docker[[:space:]]+run[[:space:]]*/, "", line)
          emit(line)
        }
      } else {
        emit(line)
      }
      if (inside && !continues) { inside = 0 }
    }
  ' "$file"
}

RUN_ARGUMENTS="$(docker_run_arguments "$BUILDX_NODE")"
RUN_IMAGES="$(printf '%s\n' "$RUN_ARGUMENTS" | awk -F'|' '$1 == "image" { print $2 }')"
RUN_IMAGE_COUNT="$(printf '%s\n' "$RUN_IMAGES" | grep -c . || true)"

# THE LIVENESS CLAUSE. Without it a rewrite that removed the `docker run`
# altogether would leave 3 checks failing for a reason none of them can state,
# and a reader would look for a missing flag in a command that is not there.
if [[ "$RUN_IMAGE_COUNT" -eq 1 ]]; then
  pass_check "buildx-node: the reader finds exactly 1 docker run command to judge"
else
  fail_check "buildx-node: the reader finds exactly 1 docker run command to judge" \
    "found ${RUN_IMAGE_COUNT} in ${BUILDX_NODE}, want 1 — the local buildkitd container" \
    "the 3 rules below all read that command, so any other count makes them report" \
    "the absence of a flag rather than the absence of the command" \
    "arguments read:" "${RUN_ARGUMENTS:-<none>}"
fi

# ----------------------------------------------------------------------------
# Rule 1: no bridge on the build path. Both halves, because each covers a
# namespace the other does not: --network host places the BUILDKITD container
# in the pod's, --oci-worker-net=host places every RUN step in buildkitd's.
# ----------------------------------------------------------------------------

# An OPTION of docker run, so it is asserted at that position: `--network host`
# after the image would be an argument handed to buildkitd, which would refuse
# it, and the container would never reach the pod's namespace.
if printf '%s\n' "$RUN_ARGUMENTS" | grep -qxF -- 'option|--network host'; then
  pass_check "buildx-node: the local buildkitd shares the pod namespace (--network host)"
else
  fail_check "buildx-node: the local buildkitd shares the pod namespace (--network host)" \
    "no '--network host' among the docker run OPTIONS in ${BUILDX_NODE}" \
    "the buildkitd container is back on the dind bridge, MTU 1500 inside 1450," \
    "and the loopback endpoint the builder dials is no longer the pod's" \
    "arguments read:" "${RUN_ARGUMENTS:-<none>}"
fi

# A DAEMON argument, because this is buildkitd's own flag. It arrived through
# --buildkitd-flags while the driver was docker-container; it is passed
# directly now, and the position is the whole difference between the daemon
# reading it and docker rejecting it.
if printf '%s\n' "$RUN_ARGUMENTS" | grep -qxF -- 'daemon|--oci-worker-net=host'; then
  pass_check "buildx-node: RUN steps share the builder namespace (--oci-worker-net=host in the daemon argv)"
else
  fail_check "buildx-node: RUN steps share the builder namespace (--oci-worker-net=host in the daemon argv)" \
    "no '--oci-worker-net=host' AFTER the image in the docker run of ${BUILDX_NODE}" \
    "every RUN fetch rides BuildKit's own bridge again — and a copy of the flag" \
    "among docker's own options would not be read by the daemon at all" \
    "arguments read:" "${RUN_ARGUMENTS:-<none>}"
fi

# ----------------------------------------------------------------------------
# Rule 2: the builder boots from OUR registry, pinned by digest, and only the
# mirror script may name the docker.io source.
# ----------------------------------------------------------------------------

# The ${} / $ below must NOT expand: the assertion is that the script reads the
# library variable, not any particular value of it. The mechanism moved — the
# image was a driver-opt and is the image the run starts — and the invariant is
# unchanged, so the check keeps its name.
# shellcheck disable=SC2016
if [[ "$RUN_IMAGES" == '"$BUILDKIT_REF"' ]]; then
  pass_check "buildx-node: the builder boots from BUILDKIT_REF"
else
  # shellcheck disable=SC2016
  fail_check "buildx-node: the builder boots from BUILDKIT_REF" \
    'want the docker run to start the image "$BUILDKIT_REF"' \
    "got:  ${RUN_IMAGES:-<the docker run names no image>}" \
    "the boot is back on a ref this repository does not pin — with no image named" \
    "buildx pulls docker.io/moby/buildkit:buildx-stable-1, and a 502 from" \
    "auth.docker.io killed a build attempt in exactly that pull"
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
  # `|| true` on every read: under pipefail a no-match grep kills this file
  # BEFORE its summary — proven live when the actions moved to sha pins and
  # this very check's literal stopped matching. The pattern matches the
  # ACTION at any ref, because the pin rule in workflow-yaml.test.sh owns
  # which refs are legal; this file owns only the ORDER.
  login_lines="$(grep -n 'uses: docker/login-action@' "$wf" | cut -d: -f1 || true)"
  mirror_lines="$(grep -n 'run: bash .ci/mirror-buildkit.sh' "$wf" | cut -d: -f1 || true)"
  buildx_lines="$(grep -n 'run: bash .ci/buildx-node.sh' "$wf" | cut -d: -f1 || true)"
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

# The INVOCATION line, never the file: the rationale comment beside the curl
# says --retry-all-errors too, and a check that greps the file passes on the
# comment after the code loses the flag — proven by breaking it on 2026-08-17.
fetch_curl_total="$(grep -cE 'curl -fsSL' "$FETCH" || true)"
fetch_curl_retrying="$(grep -E 'curl -fsSL' "$FETCH" | grep -c -- '--retry-all-errors' || true)"
if [[ "$fetch_curl_total" -ge 1 && "$fetch_curl_total" -eq "$fetch_curl_retrying" ]]; then
  pass_check "fetch-verified: the fetch retries on any transient failure (${fetch_curl_retrying}/${fetch_curl_total})"
else
  fail_check "fetch-verified: the fetch retries on any transient failure" \
    "${fetch_curl_retrying} of ${fetch_curl_total} curl invocations carry --retry-all-errors — one reset kills a 40-minute build again"
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
