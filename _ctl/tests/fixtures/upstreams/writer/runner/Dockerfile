# Fixture world for _ctl/tests/runner-residue-mirroring.test.sh — the second
# home of the tree the writer is driven against.
#
# Nothing builds this file and it is not an image. It sits at runner/Dockerfile
# under the fixture root because the writer finds a home by its repository
# path, and runner/Dockerfile is the one Dockerfile of PIN_VALUE_HOMES that
# still shares pins with versions.env. The test copies the whole tree to a
# temporary directory before it writes anything.
#
# It was base/Dockerfile until 2026-08-17. base went value-less when the 2 pin
# mechanisms collapsed onto versions.env, so it declares nothing for a writer to
# rewrite and it left PIN_VALUE_HOMES. This file moved with the rule.
#
# The RUN line below is the reason the digest row exists: the bytes it fetches
# are compared against WRITERTOOL_SHA256_AMD64, so a version that moves without
# its digest dies at build time — which is why the writer has to move both, in
# both homes, in one edit.
ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

ARG TARGETPLATFORM
ARG USERNAME=dev

ARG WRITERTOOL_VERSION=1.4.2                                           # latest LTS as of 2026-08-17
ARG WRITERTOOL_SHA256_AMD64=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb   # computed-at-pin: 2026-08-17

ARG WRITERPLAIN_VERSION=3.0.0                                          # latest LTS as of 2026-08-17
ARG UNTOUCHED_VERSION=9.9.9                                            # latest LTS as of 2026-08-17

RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/writertool/v${WRITERTOOL_VERSION}/writertool-linux-amd64.tar.gz" \
      /tmp/writertool.tar.gz "${WRITERTOOL_SHA256_AMD64}" WRITERTOOL_SHA256_AMD64 \
 && echo "${TARGETPLATFORM} ${USERNAME} ${WRITERPLAIN_VERSION} ${UNTOUCHED_VERSION}"
