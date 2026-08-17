# Fixture world for _ctl/tests/pin-mirroring.test.sh — the second home of the
# tree the writer is driven against.
#
# Nothing builds this file and it is not an image. It sits at base/Dockerfile
# under the fixture root because the writer finds a home by its repository
# path, and the test copies the whole tree to a temporary directory before it
# writes anything.
#
# The RUN line below is the reason the digest row exists: the bytes it fetches
# are compared against WRITERTOOL_SHA256_AMD64, so a version that moves without
# its digest dies at build time — which is why the writer has to move both, in
# both homes, in one edit.
FROM ubuntu:24.04

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
