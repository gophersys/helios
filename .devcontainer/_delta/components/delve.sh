#!/usr/bin/env bash
#
# _delta/components/delve.sh — the Go debugger, pinned by DELVE_VERSION.
#
# Runs inside a Dockerfile RUN, as root, after the Go toolchain layer: the
# image-wide ENV PATH carries the Go SDK, so `go` resolves. GOBIN is
# /usr/local/bin so `dlv` is on PATH for every user and shell. The caches this
# install writes under /root are removed in the SAME script — the cache
# discipline the gate-tools layer applies (the 1.6 GB lesson).
#
# CGO_ENABLED=0: delve is pure Go on linux, and a static binary needs no
# toolchain match on a cross build. Idempotent: go install overwrites.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${DELVE_VERSION:?DELVE_VERSION is not in versions.env}"

# GOMODCACHE/GOCACHE are pinned under /root EXPLICITLY: the image-wide ENV
# sets GOPATH=/home/dev/go, so a bare root-run `go install` would write its
# module cache into ${GOPATH}/pkg/mod — the exact directory the cloud smoke
# asserts absent (the 1.6 GB fix). Pinning the caches makes the rm below
# remove what was actually written.
CGO_ENABLED=0 GOTOOLCHAIN=local GOWORK=off GOFLAGS=-mod=mod GOBIN=/usr/local/bin \
  GOMODCACHE=/root/go/pkg/mod GOCACHE=/root/.cache/go-build \
  go install "github.com/go-delve/delve/cmd/dlv@v${DELVE_VERSION}"
chmod 0755 /usr/local/bin/dlv
rm -rf /root/go /root/.cache/go-build

# Proof.
dlv version
