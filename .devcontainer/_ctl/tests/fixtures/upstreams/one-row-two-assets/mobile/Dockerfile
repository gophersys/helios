# Fixture world for _ctl/tests/resolve-upstream.test.sh — the governed file that
# is WRONG, in the exact way the real tree is 1 edit away from being wrong.
#
# Nothing builds this file and it is not an image. It is named mobile/Dockerfile
# because that is where the live seed sits: in the real repository the Android
# cmdline-tools download runs under a `linux/amd64) : ;;` guard arm and answers
# for ANDROID_CMDLINE_TOOLS_SHA256_NOARCH — 1 arm, 1 row, 1 asset, correct. The
# day somebody adds an arm64 arm to that RUN without splitting the row, it
# becomes this file: 2 arms, 2 different assets, and 1 row that can attest only
# one of them.
#
# The 2 arms share the URL TEMPLATE and differ only in what they assign ARCH,
# which is why the identity of an asset is the url with the arm resolved into
# it. Keyed on the row alone the second record is a duplicate and is dropped
# silently, and the writer is then satisfied by a set it half resolved: the
# aarch64 leg installs bytes that no digest row answers for, and the build says
# nothing because the digest it compares is the x86_64 one.
FROM ubuntu:24.04

ARG TARGETPLATFORM
ARG STUBONEROW_VERSION
ARG STUBONEROW_SHA256_NOARCH

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x86_64; SHA256="${STUBONEROW_SHA256_NOARCH}"; SHA256_PIN=STUBONEROW_SHA256_NOARCH ;; \
      linux/arm64) ARCH=aarch64; SHA256="${STUBONEROW_SHA256_NOARCH}"; SHA256_PIN=STUBONEROW_SHA256_NOARCH ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/stubowner/stubonerow/releases/download/v${STUBONEROW_VERSION}/stubonerow-${STUBONEROW_VERSION}-linux-${ARCH}.tar.gz" \
      /tmp/stubonerow.tar.gz "${SHA256}" "${SHA256_PIN}"
