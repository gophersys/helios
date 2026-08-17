# Counter-stimulus fixture for _ctl/tests/download-coverage.test.sh, the LOUD
# half of the helper-wiring rule: the COPY is PRESENT and it is too late.
#
# Nothing builds this file and it is not an image. A reader that only asks
# "does the file carry the COPY" passes this Dockerfile, and the build still
# dies at the RUN above the COPY, because a layer runs against the filesystem
# the layers ABOVE it left. Presence is not wiring; order is.
FROM ubuntu:24.04

ARG LATETOOL_VERSION=4.5.6
ARG LATETOOL_SHA256_AMD64=2222222222222222222222222222222222222222222222222222222222222222   # computed-at-pin: 2026-08-17

RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/latetool-v${LATETOOL_VERSION}.tar.gz" \
      /tmp/latetool.tar.gz "${LATETOOL_SHA256_AMD64}" LATETOOL_SHA256_AMD64

COPY _build/ /usr/local/lib/gophersys/
