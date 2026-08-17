# Counter-stimulus fixture for _ctl/tests/download-coverage.test.sh, the LOUD
# half of the same-home rule.
#
# Nothing builds this file and it is not an image. It carries 1 instance of
# every way a digest pin can be wrong while the build still looks fine, and
# each name is chosen so no one is a substring of another.
FROM ubuntu:24.04

# HOMELESS. Referenced below, declared in no home at all. The reference expands
# to the empty string and the helper is handed nothing to compare against.
ARG HOMELESS_VERSION=1.0.0

# NO EVIDENCE. 64 hex, declared beside its version, and nothing on the line
# says where the value came from. A digest with no provenance is a number a
# reviewer has to take on faith.
ARG NOEVIDENCE_VERSION=2.0.0
ARG NOEVIDENCE_SHA256_AMD64=dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd

# SHORT. 63 characters. A truncated digest reads as correct in a diff and dies
# at build time, after the merge — the same defect UBUNTU_BASE_REF has a length
# check for.
ARG SHORTHEX_VERSION=3.0.0
ARG SHORTHEX_SHA256_AMD64=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee   # computed-at-pin: 2026-08-17

# LEGACY VOCABULARY. _X86_64 is the older of the 2 arch spellings this change
# replaces. One vocabulary or a reader has to know 2, and the second one is
# where a pin hides.
ARG LEGACY_VERSION=4.0.0
ARG LEGACY_SHA256_X86_64=ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff   # computed-at-pin: 2026-08-17

# NO VERSION PIN. A digest whose <TOOL>_VERSION exists in no home pins the
# bytes of a release nothing names, so a bump cannot find it.
ARG ORPHANDIGEST_SHA256_AMD64=0000000000000000000000000000000000000000000000000000000000000000   # computed-at-pin: 2026-08-17

RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/homeless-v${HOMELESS_VERSION}.tar.gz" \
      /tmp/homeless.tar.gz "${HOMELESS_SHA256_AMD64}" HOMELESS_SHA256_AMD64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/noevidence-v${NOEVIDENCE_VERSION}.tar.gz" \
      /tmp/noevidence.tar.gz "${NOEVIDENCE_SHA256_AMD64}" NOEVIDENCE_SHA256_AMD64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/shorthex-v${SHORTHEX_VERSION}.tar.gz" \
      /tmp/shorthex.tar.gz "${SHORTHEX_SHA256_AMD64}" SHORTHEX_SHA256_AMD64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/legacy-v${LEGACY_VERSION}.tar.gz" \
      /tmp/legacy.tar.gz "${LEGACY_SHA256_X86_64}" LEGACY_SHA256_X86_64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/orphandigest.tar.gz" \
      /tmp/orphandigest.tar.gz "${ORPHANDIGEST_SHA256_AMD64}" ORPHANDIGEST_SHA256_AMD64
