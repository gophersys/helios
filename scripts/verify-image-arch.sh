#!/usr/bin/env bash
# Assert that every variant of a multi-arch image really IS the architecture that
# its manifest declares.
#
# Usage: bash scripts/verify-image-arch.sh <image-ref> [required-platforms]
#   e.g. bash scripts/verify-image-arch.sh ghcr.io/gophersys/base:e0c6bc5
#        bash scripts/verify-image-arch.sh ghcr.io/gophersys/base-runner:x linux/amd64
#
# required-platforms is a comma-separated list, and it defaults to the
# devcontainer policy of linux/amd64,linux/arm64. An image that narrows the list
# states its own, as base-runner does: it is amd64 only, by a measured decision.
#
# WHY THIS EXISTS (D42)
# The manifest declares a platform. Nothing verified the CONTENT. The published
# linux/arm64 base image turned out to be an amd64 Ubuntu userland carrying
# aarch64 Go binaries, and it shipped that way against a policy that
# .claude/rules/00-identity.md calls non-negotiable. An arm64 Mac pulled an
# emulated amd64 userland whose gate tools were a different architecture.
#
# A label is a claim. This runs the image and reads 3 independent facts:
#   uname -m                      the kernel-visible machine of the userland
#   dpkg --print-architecture     what apt installed into it
#   the ELF machine byte          what the compiled binaries actually are
#
# All 3 must agree with each other AND with the declared platform. Two of them
# agreeing is what hid this defect: uname and dpkg agreed, and the binaries did
# not.
set -Eeuo pipefail
IFS=$'\n\t'

IMAGE="${1:-}"
# The variants that MUST be published. The first version of this script checked
# only the variants that existed, so an image with no arm64 entry at all passed:
# zephyr-devbox publishes amd64 only, against a policy the identity rules call
# non-negotiable, and this script called it PASS. A check that cannot see an
# absence is the same defect it was written to catch.
REQUIRED_PLATFORMS="${2:-linux/amd64,linux/arm64}"
# A Go binary that every gophersys image carries. It is the ELF probe.
PROBE_BINARY="${PROBE_BINARY:-gofumpt}"

red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }

[ -n "$IMAGE" ] || { echo "usage: bash scripts/verify-image-arch.sh <image-ref>" >&2; exit 2; }
for c in docker jq; do
  command -v "$c" >/dev/null 2>&1 || { echo "missing required tool: $c" >&2; exit 127; }
done

echo "verifying ${IMAGE}: every required variant is present, and each IS the architecture it claims"
echo "  required: ${REQUIRED_PLATFORMS}"

# Attestation entries carry platform unknown/unknown. They hold no userland, so
# there is nothing to run and nothing to check. Skipping them is not a silent
# skip: they are not image variants.
platforms="$(docker manifest inspect "$IMAGE" 2>/dev/null \
  | jq -r '(.manifests // [])[] | select(.platform.os != "unknown") | "\(.platform.os)/\(.platform.architecture)"' \
  | sort -u)"

if [ -z "$platforms" ]; then
  echo "  $(red FAIL) no image variants found in the manifest of ${IMAGE}" >&2
  echo "  a single-platform image has no manifest list; this check needs one" >&2
  exit 1
fi

fail=0

# An absent variant first. It is invisible to every per-variant check below.
# IFS is newline+tab here, so a space-separated expansion does NOT split. The
# first version relied on it and produced 1 word holding the whole list, which
# then matched nothing: an image carrying BOTH variants was reported as carrying
# neither. Split on the comma explicitly.
for want in $(printf '%s' "$REQUIRED_PLATFORMS" | tr ',' '\n'); do
  if ! printf '%s\n' "$platforms" | grep -qx "$want"; then
    printf '  %s %s publishes no %s variant, and the policy requires it\n' "$(red FAIL)" "$IMAGE" "$want" >&2
    fail=1
  fi
done

for platform in $platforms; do
  arch="${platform#*/}"
  # What each fact must read for this declared platform.
  case "$arch" in
    amd64) want_uname="x86_64";  want_dpkg="amd64"; want_elf="3e00" ;;
    arm64) want_uname="aarch64"; want_dpkg="arm64"; want_elf="b700" ;;
    *)     echo "  $(red FAIL) unknown architecture in manifest: $arch" >&2; fail=1; continue ;;
  esac

  # One container run collects all 3 facts. The ELF machine is bytes 18-19 of the
  # header, little-endian: 3e00 is x86-64 and b700 is aarch64.
  out="$(docker run --rm --platform "$platform" "$IMAGE" bash -lc '
    set -u
    printf "%s\n" "$(uname -m)"
    printf "%s\n" "$(dpkg --print-architecture 2>/dev/null || echo none)"
    b="$(command -v '"$PROBE_BINARY"' 2>/dev/null || true)"
    if [ -n "$b" ]; then printf "%s\n" "$(od -An -tx1 -j18 -N2 "$b" | tr -d " ")"; else printf "none\n"; fi
  ' 2>/dev/null)" || { echo "  $(red FAIL) ${platform}: the image would not run" >&2; fail=1; continue; }

  got_uname="$(printf '%s' "$out" | sed -n 1p)"
  got_dpkg="$(printf '%s' "$out" | sed -n 2p)"
  got_elf="$(printf '%s' "$out" | sed -n 3p)"

  if [ "$got_elf" = "none" ]; then
    echo "  $(red FAIL) ${platform}: ${PROBE_BINARY} is not in the image, so the binaries cannot be checked" >&2
    fail=1
    continue
  fi

  bad=""
  [ "$got_uname" = "$want_uname" ] || bad="${bad} uname=${got_uname}(want ${want_uname})"
  [ "$got_dpkg" = "$want_dpkg" ]   || bad="${bad} dpkg=${got_dpkg}(want ${want_dpkg})"
  [ "$got_elf" = "$want_elf" ]     || bad="${bad} ${PROBE_BINARY}-elf=${got_elf}(want ${want_elf})"

  if [ -n "$bad" ]; then
    printf '  %s %s declares %s but holds:%s\n' "$(red FAIL)" "$IMAGE" "$platform" "$bad" >&2
    fail=1
  else
    printf '  %s %-14s uname=%s dpkg=%s %s=%s\n' "$(grn PASS)" "$platform" \
      "$got_uname" "$got_dpkg" "$PROBE_BINARY" "$arch"
  fi
done

if [ "$fail" -eq 0 ]; then
  printf '\n  %s every variant of %s is the architecture it declares\n' "$(grn PASS)" "$IMAGE"
  exit 0
fi
printf '\n  %s %s ships at least 1 variant that is not what its manifest says\n' "$(red FAIL)" "$IMAGE" >&2
printf '  see docs/debt-register.md D42\n' >&2
exit 1
