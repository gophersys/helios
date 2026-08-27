# Counter-stimulus fixture for _ctl/tests/download-coverage.test.sh, the LOUD
# half of the helper-wiring rule: the COPY is MISSING.
#
# Nothing builds this file and it is not an image. It is the exact shape the
# verifier produced out of cloud/Dockerfile by deleting 1 line: every download
# still names its digest, every digest still lives beside its version, every
# static check of this rule stays green — and the first fetch layer dies with
# "/usr/local/lib/gophersys/fetch-verified.sh: not found", after the merge.
#
# The comment above writes the helper path on purpose. The reader drops comment
# lines before it looks, so a rule satisfied by a sentence would show up here.
FROM ubuntu:24.04

ARG UNWIREDTOOL_VERSION=7.8.9
ARG UNWIREDTOOL_SHA256_AMD64=3333333333333333333333333333333333333333333333333333333333333333   # computed-at-pin: 2026-08-17

RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/unwiredtool-v${UNWIREDTOOL_VERSION}.tar.gz" \
      /tmp/unwiredtool.tar.gz "${UNWIREDTOOL_SHA256_AMD64}" UNWIREDTOOL_SHA256_AMD64
