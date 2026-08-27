# Counter-stimulus fixture for _ctl/tests/download-coverage.test.sh, the QUIET
# half of the helper-wiring rule.
#
# Nothing builds this file and it is not an image. The COPY that puts the
# fetcher into the image sits ABOVE the layer that calls it, which is the shape
# base/Dockerfile and cloud/Dockerfile have to hold. A detector that reports
# this file reports both real Dockerfiles too, and then the rule says nothing.
FROM ubuntu:24.04

ARG WIREDTOOL_VERSION=1.2.3
ARG WIREDTOOL_SHA256_AMD64=1111111111111111111111111111111111111111111111111111111111111111   # computed-at-pin: 2026-08-17

# The next 2 lines are prose and not instructions. They name
# /usr/local/lib/gophersys/fetch-verified.sh above the COPY on purpose, the way
# base/Dockerfile writes prose above its own: a reader that counted comment
# lines would find a first call above the COPY and report this file.
COPY _build/ /usr/local/lib/gophersys/

RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/wiredtool-v${WIREDTOOL_VERSION}.tar.gz" \
      /tmp/wiredtool.tar.gz "${WIREDTOOL_SHA256_AMD64}" WIREDTOOL_SHA256_AMD64
