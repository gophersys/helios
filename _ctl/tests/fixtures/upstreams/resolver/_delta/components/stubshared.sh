#!/usr/bin/env bash
#
# Fixture world for _ctl/tests/resolve-upstream.test.sh — the SECOND governed
# file that fetches STUBSHARED, at the SAME url and for the SAME 2 rows as
# cloud/Dockerfile.
#
# Nothing runs this file and no image COPYs it. It is here because the real
# repository has this shape twice: k9s and docker buildx are each fetched by
# base/Dockerfile AND by a component under _delta/, at one url. A resolver that
# read every governed file and did not deduplicate would digest identical bytes
# a second time for each arm — 4 downloads where 2 answer, every Monday, out of
# the budget the weekly's timeout is made of.
#
# A row is deduplicated and never a url: 2 rows fetching 1 url is what a _NOARCH
# asset inside an armed RUN would be, and both of those rows have to move.
#
# The case arm shape is the one _delta/components/k9s.sh writes: 1 case for the
# whole file, each arm on 1 line, and the fetch reading ${SHA256} and
# ${SHA256_PIN} out of the arm that ran.
set -Eeuo pipefail
IFS=$'\n\t'

: "${STUBSHARED_VERSION:?STUBSHARED_VERSION is not in versions.env}"
: "${STUBSHARED_SHA256_AMD64:?STUBSHARED_SHA256_AMD64 is not in versions.env}"
: "${STUBSHARED_SHA256_ARM64:?STUBSHARED_SHA256_ARM64 is not in versions.env}"
: "${TARGETPLATFORM:?TARGETPLATFORM is not set (docker buildx injects it)}"

case "${TARGETPLATFORM}" in
  linux/amd64) ARCH=amd64; SHA256="${STUBSHARED_SHA256_AMD64}"; SHA256_PIN=STUBSHARED_SHA256_AMD64 ;;
  linux/arm64) ARCH=arm64; SHA256="${STUBSHARED_SHA256_ARM64}"; SHA256_PIN=STUBSHARED_SHA256_ARM64 ;;
  *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;;
esac

/usr/local/lib/gophersys/fetch-verified.sh \
  "https://github.com/stubowner/stubshared/releases/download/v${STUBSHARED_VERSION}/stubshared_Linux_${ARCH}.tar.gz" \
  /tmp/stubshared.tar.gz "${SHA256}" "${SHA256_PIN}"
