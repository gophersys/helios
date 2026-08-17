# Counter-stimulus fixture for _ctl/tests/pin-mirroring.test.sh — the QUIET
# half of the mirroring rule, in the Dockerfile shape.
#
# Nothing builds this file and it is not an image. It declares the same 2 pins
# agreeing.env declares, at the same 2 values, so the rule must be silent over
# the pair.
FROM ubuntu:24.04

ARG TARGETPLATFORM
ARG USERNAME=dev

ARG MIRRORTOOL_VERSION=1.4.2                                           # latest LTS as of 2026-08-17
ARG MIRRORTOOL_SHA256_AMD64=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb   # computed-at-pin: 2026-08-17

ARG MIRRORPLAIN_VERSION=3.0.0                                          # installed by `go install`, so it carries no digest row

RUN echo "${TARGETPLATFORM} ${USERNAME}" \
 && echo "${MIRRORTOOL_VERSION} ${MIRRORTOOL_SHA256_AMD64} ${MIRRORPLAIN_VERSION}"
