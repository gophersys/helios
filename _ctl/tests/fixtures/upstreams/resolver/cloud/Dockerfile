# Fixture world for _ctl/tests/resolve-upstream.test.sh — the PER-PLATFORM
# governed file of a miniature repository.
#
# Nothing builds this file and it is not an image. Its neighbour base/Dockerfile
# is the 1-arm world: 1 `linux/amd64)` arm, 1 asset per pin, 1 `_SHA256_AMD64`
# row. That world cannot express the defect this file exists for — a pin whose
# digest rows are PER PLATFORM, where a reader that stops at the first arm
# computes 1 digest for a set of 2 and leaves the sibling on the digest of the
# release the pin is being bumped away from.
#
# The 3 shapes below are the 3 a governed file can have, and each takes its own
# pin so a case can name it:
#
#   STUBDUAL     2 arms. The asset spelling is the upstream's own and the ROW
#                spelling is the platform vocabulary: the arm64 arm fetches an
#                `aarch64` asset and answers for STUBDUAL_SHA256_ARM64. That is
#                the whole reason a row is never named after the asset.
#   STUBSHARED   2 arms, spelled `amd64`/`arm64` — the OTHER spelling of the
#                same 2 platforms, so this fixture world holds both. It is
#                fetched a second time, at the SAME url and for the SAME rows,
#                by _delta/components/stubshared.sh: the k9s and buildx shape,
#                where base and a component install one tool.
#   STUBNOARCH   no case at all. 1 asset serves every platform, so the fetch
#                spells its pin literally and the row is `_SHA256_NOARCH`. A
#                reader that consulted the sanctioned platform set instead of
#                the arms THAT EXIST would demand an arm64 asset from it.
#
# Each arm stays on ONE line, which is the rule the reader in _ctl/lib.sh
# depends on: an arm broken across lines reads as an arm that assigns nothing.
FROM ubuntu:24.04

ARG TARGETPLATFORM
ARG STUBDUAL_VERSION
ARG STUBDUAL_SHA256_AMD64
ARG STUBDUAL_SHA256_ARM64
ARG STUBSHARED_VERSION
ARG STUBSHARED_SHA256_AMD64
ARG STUBSHARED_SHA256_ARM64
ARG STUBNOARCH_VERSION
ARG STUBNOARCH_SHA256_NOARCH

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x86_64; SHA256="${STUBDUAL_SHA256_AMD64}"; SHA256_PIN=STUBDUAL_SHA256_AMD64 ;; \
      linux/arm64) ARCH=aarch64; SHA256="${STUBDUAL_SHA256_ARM64}"; SHA256_PIN=STUBDUAL_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/stubowner/stubdual/releases/download/v${STUBDUAL_VERSION}/stubdual-${STUBDUAL_VERSION}-linux-${ARCH}.tar.gz" \
      /tmp/stubdual.tar.gz "${SHA256}" "${SHA256_PIN}"

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${STUBSHARED_SHA256_AMD64}"; SHA256_PIN=STUBSHARED_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${STUBSHARED_SHA256_ARM64}"; SHA256_PIN=STUBSHARED_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/stubowner/stubshared/releases/download/v${STUBSHARED_VERSION}/stubshared_Linux_${ARCH}.tar.gz" \
      /tmp/stubshared.tar.gz "${SHA256}" "${SHA256_PIN}"

RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/stubowner/stubnoarch/releases/download/v${STUBNOARCH_VERSION}/stubnoarch-${STUBNOARCH_VERSION}-any.tar.gz" \
      /tmp/stubnoarch.tar.gz "${STUBNOARCH_SHA256_NOARCH}" STUBNOARCH_SHA256_NOARCH
