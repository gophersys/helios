# Counter-stimulus fixture for _ctl/tests/download-coverage.test.sh — the shape
# the 2-platform set introduced.
#
# Nothing builds this file and it is not an image. It exists because the reader
# in that test learned to follow a case arm's LOCALS, and a capability no
# fixture exercises is a capability nobody has watched work. Every other fixture
# here spells its digest literally in the fetch command, so all of them pass
# against a reader that ignores locals entirely.
#
# 7 fetches, 6 different answers. The names are chosen so no one is a substring
# of another, because the assertions match on the name.
FROM ubuntu:24.04

ARG ARMTOOL_VERSION=1.0.0
ARG ARMTOOL_SHA256_AMD64=1111111111111111111111111111111111111111111111111111111111111111
ARG ARMTOOL_SHA256_ARM64=2222222222222222222222222222222222222222222222222222222222222222
ARG ONLYARM_VERSION=7.0.0
ARG ONLYARM_SHA256_ARM64=7777777777777777777777777777777777777777777777777777777777777777
ARG LITERALTOOL_VERSION=2.0.0
ARG LITERALTOOL_SHA256_NOARCH=3333333333333333333333333333333333333333333333333333333333333333
ARG FOOLTOOL_VERSION=3.0.0
ARG ORPHANTOOL_VERSION=4.0.0
ARG PAIRA_VERSION=5.0.0
ARG PAIRA_SHA256_AMD64=5555555555555555555555555555555555555555555555555555555555555555
ARG PAIRB_VERSION=6.0.0
ARG PAIRB_SHA256_AMD64=6666666666666666666666666666666666666666666666666666666666666666

# 1. THE NEW SHAPE, and the one the reader had to learn. The arm chooses the
# digest and the fetch spells the LOCAL, so the pin name is nowhere in the
# fetch command. Read as `verified` with the digest ARMTOOL_SHA256_AMD64.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${ARMTOOL_SHA256_AMD64}"; SHA256_PIN=ARMTOOL_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${ARMTOOL_SHA256_ARM64}"; SHA256_PIN=ARMTOOL_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/armtool-v${ARMTOOL_VERSION}-linux-${ARCH}.tar.gz" \
      /tmp/armtool.tar.gz "${SHA256}" "${SHA256_PIN}"

# 2. THE ASSIGNMENT THAT MUST NOT FOOL IT. The arm assigns a bare hex string
# rather than a ${<TOOL>_SHA256_<ARCH>} token, so no pin answers for this
# download and no home can be checked. A general assignment-follower would call
# it verified; this one must leave it `helper-without-digest`.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; FOOLTOOL_SHA256=4444444444444444444444444444444444444444444444444444444444444444 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/fooltool-v${FOOLTOOL_VERSION}-linux-${ARCH}.tar.gz" \
      /tmp/fooltool.tar.gz "${FOOLTOOL_SHA256}" FOOLTOOL_PIN

# 3. THE OLD SHAPE STILL READS. A download whose asset serves every platform
# has nothing to choose, so it keeps naming its pin in the fetch itself.
RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/literaltool-v${LITERALTOOL_VERSION}.tar.gz" \
      /tmp/literaltool.tar.gz "${LITERALTOOL_SHA256_NOARCH}" LITERALTOOL_SHA256_NOARCH

# 4. THE SCOPE RESETS AT THE RUN. This layer spells ${SHA256} and sets it
# nowhere, so at build time the helper would compare against the empty string.
# A reader that let layer 1's local leak forward would report this as verified
# BY ARMTOOL's digest — a download answered by a pin that has nothing to do
# with it, which is worse than an unanswered one because it looks answered.
RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/orphantool-v${ORPHANTOOL_VERSION}.tar.gz" \
      /tmp/orphantool.tar.gz "${SHA256}" ORPHANTOOL_PIN

# 5. ONE ARM, TWO TOOLS — the shape _delta/components/protocols.sh really has,
# and the reason the locals carry the tool's name there. Each fetch must be
# answered by ITS OWN pin. A reader that resolved only the first digest-shaped
# local in the arm, or that kept 1 "digest of this layer", would hand PAIRA's
# digest to PAIRB and report full coverage while the build compared the wrong
# bytes — and every rule in the test would then be green over a real defect.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; PAIRA_SHA256="${PAIRA_SHA256_AMD64}"; PAIRA_PIN=PAIRA_SHA256_AMD64; PAIRB_SHA256="${PAIRB_SHA256_AMD64}"; PAIRB_PIN=PAIRB_SHA256_AMD64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/paira-v${PAIRA_VERSION}.tar.gz" \
      /tmp/paira.tar.gz "${PAIRA_SHA256}" "${PAIRA_PIN}" \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/pairb-v${PAIRB_VERSION}.tar.gz" \
      /tmp/pairb.tar.gz "${PAIRB_SHA256}" "${PAIRB_PIN}"

# 6. THE ARM THAT IS NOT THE FIRST ONE. This download exists on linux/arm64 and
# on no other platform, so the amd64 arm refuses and only the arm64 arm assigns
# the digest. It IS a verified download — on the one platform that reaches it —
# and a reader that collects locals from `linux/amd64)` arms alone finds no
# assignment, reports `helper-without-digest`, and hands this file a red that
# names a defect nobody committed.
#
# The mirror of it ships in the real tree with the arms the other way round:
# mobile's Android cmdline-tools RUN opens `linux/amd64) : ;;` — a guard arm
# that assigns NOTHING — so the amd64-only reader is empty-handed there too. Any
# arm may be the one that answers, which is why the reader takes them all.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) echo "onlyarm publishes no amd64 asset"; exit 1 ;; \
      linux/arm64) ARCH=arm64; SHA256="${ONLYARM_SHA256_ARM64}"; SHA256_PIN=ONLYARM_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/onlyarm-v${ONLYARM_VERSION}-linux-${ARCH}.tar.gz" \
      /tmp/onlyarm.tar.gz "${SHA256}" "${SHA256_PIN}"
