# Counter-stimulus fixture for _ctl/tests/download-coverage.test.sh, the QUIET
# half of the same-home rule.
#
# Nothing builds this file and it is not an image. Every digest below is
# declared beside its version in this same file, is 64 lowercase hex, and
# carries 1 of the 2 evidence comments. A detector that reports anything here
# reports every correct pin in the repository, which is as useless as a
# detector that reports nothing.
FROM ubuntu:24.04

ARG GOODTOOL_VERSION=1.2.3
ARG GOODTOOL_SHA256_AMD64=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa   # computed-at-pin: 2026-08-17

ARG SCRIPTTOOL_VERSION=2.0.0
ARG SCRIPTTOOL_SHA256_NOARCH=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb   # upstream-published: https://example.invalid/scripttool/checksums.txt

# The dual-home half. home-other.env declares the same 2 names; PAIRTOOL agrees
# there and GOODTOOL does not, so the equality detector has 1 of each to read.
ARG PAIRTOOL_VERSION=9.9.9
ARG PAIRTOOL_SHA256_AMD64=cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc   # computed-at-pin: 2026-08-17

RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/goodtool-v${GOODTOOL_VERSION}.tar.gz" \
      /tmp/goodtool.tar.gz "${GOODTOOL_SHA256_AMD64}" GOODTOOL_SHA256_AMD64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/scripttool-v${SCRIPTTOOL_VERSION}/install.sh" \
      /tmp/scripttool.sh "${SCRIPTTOOL_SHA256_NOARCH}" SCRIPTTOOL_SHA256_NOARCH \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/pairtool-v${PAIRTOOL_VERSION}.tar.gz" \
      /tmp/pairtool.tar.gz "${PAIRTOOL_SHA256_AMD64}" PAIRTOOL_SHA256_AMD64
