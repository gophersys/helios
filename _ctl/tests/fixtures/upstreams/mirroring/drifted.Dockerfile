# Counter-stimulus fixture for _ctl/tests/pin-mirroring.test.sh — the LOUD half
# of the mirroring rule.
#
# Nothing builds this file and it is not an image. It is agreeing.Dockerfile
# with ONE home of ONE pin left behind: MIRRORTOOL_VERSION reads 1.4.1 while
# agreeing.env reads 1.4.2.
#
# That is the shape of the real defect. A pin with 2 homes is bumped by editing
# 2 lines in 2 files, so a bump that edits 1 of them publishes 2 different
# toolchains under 1 commit — the cloud family gets the new version and the base
# family goes on shipping the old one, and the diff of the pull request looks
# like a bump.
#
# MIRRORPLAIN_VERSION still agrees. The detector has to report the one and stay
# quiet about the other, in the SAME read: a detector that reports the whole
# file once it finds a defect names 2 pins where 1 moved.
FROM ubuntu:24.04

ARG TARGETPLATFORM
ARG USERNAME=dev

ARG MIRRORTOOL_VERSION=1.4.1                                           # LEFT BEHIND on purpose
ARG MIRRORTOOL_SHA256_AMD64=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb   # computed-at-pin: 2026-08-17

ARG MIRRORPLAIN_VERSION=3.0.0                                          # agrees with agreeing.env

RUN echo "${TARGETPLATFORM} ${USERNAME}" \
 && echo "${MIRRORTOOL_VERSION} ${MIRRORTOOL_SHA256_AMD64} ${MIRRORPLAIN_VERSION}"
