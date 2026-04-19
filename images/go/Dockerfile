# syntax=docker/dockerfile:1.7
#
# images/go — Go toolchain on top of images/base.
#
# Installed from the official go.dev tarball (not apt) so the version is
# current and controlled by a single ARG, and there is no dependency on
# Ubuntu's packaging cadence.
FROM ghcr.io/gophersys/base:latest

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="Go toolchain from go.dev official tarball"

USER root

ARG GO_VERSION=1.23.4
ARG GO_SHA256=6924efde5de86fe277676e929c1ea681abd1eb45f63d565b46ff17fa8a09092d

ENV GOROOT=/usr/local/go \
    GOPATH=/home/dev/go \
    PATH=/usr/local/go/bin:/home/dev/go/bin:${PATH}

RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tar.gz \
 && echo "${GO_SHA256}  /tmp/go.tar.gz" | sha256sum -c - \
 && tar -C /usr/local -xzf /tmp/go.tar.gz \
 && rm /tmp/go.tar.gz \
 && mkdir -p "${GOPATH}/bin" "${GOPATH}/src" "${GOPATH}/pkg" \
 && chown -R dev:dev "${GOPATH}" \
 && go version

USER dev
WORKDIR /home/dev
