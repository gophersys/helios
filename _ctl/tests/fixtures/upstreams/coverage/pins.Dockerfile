# Counter-stimulus fixture for _ctl/tests/upstream-coverage.test.sh — the
# Dockerfile-shaped half of the pin home pair.
#
# Nothing builds this file and it is not an image. It carries the 3 shapes a
# Dockerfile home holds, so the reader is watched on all 3:
#
#   a build parameter that pins no tool   TARGETPLATFORM, USERNAME, BASE_TAG
#   a version-shaped ARG with a value     COVERTOOL_VERSION (also in pins.env),
#                                         COVERSOLE_VERSION, COVERSOLE_CHANNEL
#   a digest row                          not a pin; download-coverage owns it
#
# A reader that counted USERNAME as a pin would demand an upstream row for
# `dev`, and the author would then write a row that answers nothing.
FROM ubuntu:24.04

ARG TARGETPLATFORM
ARG BASE_TAG=latest
ARG USERNAME=dev
ARG USER_UID=1000

ARG COVERTOOL_VERSION=1.0.0
ARG COVERTOOL_SHA256_AMD64=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa   # computed-at-pin: 2026-08-17

ARG COVERSOLE_VERSION=2.0.0
ARG COVERSOLE_CHANNEL=stable

RUN echo "${TARGETPLATFORM} ${BASE_TAG} ${USERNAME} ${USER_UID}" \
 && echo "${COVERTOOL_VERSION} ${COVERTOOL_SHA256_AMD64}" \
 && echo "${COVERSOLE_VERSION} ${COVERSOLE_CHANNEL}"
