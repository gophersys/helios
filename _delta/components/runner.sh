#!/usr/bin/env bash
#
# _delta/components/runner.sh — the CI fold: the GitHub Actions runner, its
# .NET runtime dependencies, and cictl. Pinned by RUNNER_VERSION and
# CICTL_VERSION.
#
# Runs inside a Dockerfile RUN, as root. In a devcontainer these are inert
# files; a CI pod overrides the container command to /home/runner/run.sh, so
# the deployment shape is chosen by the command and never by a different image.
#
# Two facts carried over from the retiring runner/Dockerfile:
#   - RUNNER_ALLOW_RUNASROOT=1 is REQUIRED for a pod that runs as root; it is
#     ENV, so the Dockerfile sets it (a script cannot set ENV).
#   - /home/runner is where the ARC chart mounts `work` (/home/runner/_work)
#     and `dind-externals` (/home/runner/externals), so the stock layout stays.
#
# Ownership differs from runner/Dockerfile ON PURPOSE, and the reason is the
# fold: that image ran as root, so it needed no chown. This image defaults to
# the `dev` user (it is a devcontainer first), and an ARC pod that keeps the
# image default runs the runner as `dev` — so /home/runner is chowned to dev.
# Root-running pods lose nothing (root writes anywhere), and
# RUNNER_ALLOW_RUNASROOT=1 keeps that path open. The runner writes .runner and
# .credentials into /home/runner at registration; the first runner build
# shipped that directory unwritable and every pod failed to start.
#
# The .NET runtime deps: libicu's soname is pinned to the Ubuntu release
# (24.04 -> libicu74). Installing them explicitly keeps the layer reproducible
# instead of running bin/installdependencies.sh.
#
# cictl: CGO_ENABLED=0 for a static, cross-buildable binary; the go caches this
# install writes are removed in the SAME script — the cache-clean discipline of
# the retiring runner/Dockerfile cictl layer (its line 87), which is the origin
# of the 1.6 GB gate-tools fix.
#
# Idempotent: apt re-install is a no-op, the tar overwrites, go install
# overwrites.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${RUNNER_VERSION:?RUNNER_VERSION is not in versions.env}"
: "${CICTL_VERSION:?CICTL_VERSION is not in versions.env}"
: "${TARGETPLATFORM:?TARGETPLATFORM is not set (docker buildx injects it)}"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  libicu74 \
  libkrb5-3 \
  liblttng-ust1t64
apt-get clean
rm -rf /var/lib/apt/lists/*

case "${TARGETPLATFORM}" in
  linux/amd64) ARCH=x64 ;;
  linux/arm64) ARCH=arm64 ;;
  *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;;
esac

mkdir -p /home/runner
curl -fsSL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${ARCH}-${RUNNER_VERSION}.tar.gz" \
  -o /tmp/runner.tar.gz
tar -xzf /tmp/runner.tar.gz -C /home/runner
rm -f /tmp/runner.tar.gz
mkdir -p /home/runner/_work

# cictl — the CI contract tool, public precisely so this needs no credential.
# GOMODCACHE/GOCACHE are pinned under /root EXPLICITLY: the image-wide ENV
# sets GOPATH=/home/dev/go, so a bare root-run `go install` would write its
# module cache into ${GOPATH}/pkg/mod — the exact directory the cloud smoke
# asserts absent. Pinning them makes the rm below remove what was written.
CGO_ENABLED=0 GOTOOLCHAIN=local GOBIN=/usr/local/bin \
  GOMODCACHE=/root/go/pkg/mod GOCACHE=/root/.cache/go-build \
  go install "github.com/gophersys/cictl/cmd/cictl@${CICTL_VERSION}"
chmod 0755 /usr/local/bin/cictl
rm -rf /root/go /root/.cache/go-build

# Proof. It runs BEFORE the chown below, and that order is the fix for a
# defect the first cloud build shipped: Runner.Listener creates
# /home/runner/_diag for its own trace log on EVERY invocation, this proof
# runs as root, and with the chown already done the proof re-rooted _diag
# inside the dev-owned tree. A pod running as the image default user then
# died writing its first trace line — invisible in that build's CI run only
# because its smoke failed at the size gate before the container checks ran.
test -x /home/runner/run.sh
/home/runner/bin/Runner.Listener --version
cictl help >/dev/null

# The proof's own trace log does not ship; the chown then owns EVERYTHING
# under /home/runner to dev, so nothing root-owned can hide in the tree a
# dev-running pod must write into.
rm -rf /home/runner/_diag
chown -R dev:dev /home/runner
echo "runner + cictl: ok"
