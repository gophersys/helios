# The `+ runner` layer.
#
# Adds the GitHub Actions runner to ANY of this repo's dev images and changes
# nothing else. One Dockerfile serves every parent: `BASE_IMAGE` selects which.
#
#   docker build --build-arg BASE_IMAGE=ghcr.io/gophersys/base:<sha>   -t base-runner   runner/
#   docker build --build-arg BASE_IMAGE=ghcr.io/gophersys/zephyr:<sha> -t zephyr-runner runner/
#
# WHY THIS EXISTS
# The CI pool runs this as the runner *container image* rather than pulling a
# toolchain per job with `container:`. A `container:` image is pulled inside the
# pod's dind daemon and dies with the pod — measured at 5m17s per job for an
# image this size. As the pod image it is pulled by the kubelet, which caches
# per node, so only the first job on a node pays. It also means the private
# packages are pulled with one in-cluster imagePullSecret instead of a
# per-(package, repository) grant that GitHub only exposes in its UI.
#
# The dev image and the CI image therefore differ by exactly one layer, and that
# layer contains no toolchain. Nothing a workflow can observe differs between them.
#
# See gophersys/infrastructure docs/ci-substrate.md for the full interface.
#
# hadolint global ignore=DL3008
ARG BASE_IMAGE=ghcr.io/gophersys/base:latest
FROM ${BASE_IMAGE}

ARG RUNNER_VERSION=2.336.0                                             # latest release as of 2026-08-10
ARG CLAUDE_CODE_VERSION=2.1.212                                        # MUST match eden harnesses/versions.env
ARG CICTL_VERSION=v0.1.0                                               # gophersys/cictl, first standalone release
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
ARG TARGETPLATFORM

# Root by design, and it is the whole reason this layer exists. The runner sits
# beside a privileged dind sidecar, so an unprivileged runner was never a
# boundary, and running as `dev` produced 3 classes of permission defect in 1
# day. run.sh also refuses to start as root unless RUNNER_ALLOW_RUNASROOT is
# set, which this image sets. The dev images keep the `dev` user, because a
# developer bind-mounts a repository into those.
# hadolint ignore=DL3002
USER root

# The runner is a .NET application: libicu is a hard runtime dependency and its
# soname is pinned to the Ubuntu release (24.04 -> libicu74). The rest are what
# `bin/installdependencies.sh` would pull in; installing them explicitly keeps
# the layer reproducible and avoids running that script under QEMU.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libicu74 \
      libkrb5-3 \
      liblttng-ust1t64 \
 && rm -rf /var/lib/apt/lists/*

# The runner lives at /home/runner because that is where the ARC chart mounts
# `work` (/home/runner/_work) and `dind-externals` (/home/runner/externals).
# Keeping the stock layout means the pod spec needs no special-casing. The
# process still runs as ${USERNAME}, so HOME stays /home/${USERNAME} and every
# toolchain installed there (Go, nvm, cargo) resolves exactly as it does in dev.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p /home/runner \
 && curl -fsSL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${ARCH}-${RUNNER_VERSION}.tar.gz" \
      -o /tmp/runner.tar.gz \
 && tar -xzf /tmp/runner.tar.gz -C /home/runner \
 && rm -f /tmp/runner.tar.gz \
 && mkdir -p /home/runner/_work
# No chown. This image runs as ROOT — see the note below — so every path under
# /home/runner is already writable by the process that uses it.

# cictl — the CI contract tool. It lives HERE and not in `base` because the image
# that needs a tool is the image that gets it: cictl generates and drift-checks
# workflows, which is a CI concern, and `base` stays a development environment.
#
# CGO_ENABLED=0 is required, not tidy: an arm64 layer builds under QEMU with an
# x86 toolchain, and a cgo build there hands arm64 assembly to an x86 assembler.
# cictl is pure Go, so a static binary is both buildable and the better artifact.
#
# gophersys/cictl is public precisely so this needs no credential.
RUN CGO_ENABLED=0 GOTOOLCHAIN=local GOBIN=/usr/local/bin \
      go install "github.com/gophersys/cictl/cmd/cictl@${CICTL_VERSION}" \
 && chmod 0755 /usr/local/bin/cictl \
 && cictl help >/dev/null \
 && rm -rf /root/go /root/.cache/go-build

# The Claude CLI, for the pull request review agent.
#
# It is HERE and not in `base` for the same reason cictl is: the image that needs
# a tool is the image that gets it, and this is a CI concern.
#
# THE PIN HAS A SECOND HOME, AND THAT IS A COST.
# ADR-0021 says the harness pin lives once, in eden `harnesses/versions.env`. This
# image cannot read that file: it is built from the .devcontainer repository,
# which stands alone. So the version is repeated here and the 2 MUST move
# together. Recorded in gophersys/infrastructure docs/debt-register.md.
#
# The install is verified in the same layer. A silent failure here would surface
# much later, as "missing required tool: claude" in a review job.
# pipefail, so a failed curl cannot be hidden by the bash that follows it. Without
# it, a 404 or a dropped connection sends an EMPTY script into bash, which exits 0
# and leaves the image with no claude at all. The verification below would still
# catch it, but the pipe must not lie in the first place.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_CODE_VERSION}" \
 && ln -sfn /root/.local/bin/claude /usr/local/bin/claude \
 && installed="$(claude --version 2>/dev/null || true)" \
 && case "$installed" in \
      *"${CLAUDE_CODE_VERSION}"*) : ;; \
      *) echo "FATAL: claude reports '${installed}', expected ${CLAUDE_CODE_VERSION}"; exit 1 ;; \
    esac

# THIS IMAGE RUNS AS ROOT, DELIBERATELY.
#
# The dev images keep the unprivileged `dev` user, because a developer bind-mounts
# a repository into them and the files must belong to the host user. A CI runner
# has no bind mount and no interactive user, so that reason does not apply.
#
# What running as `dev` DID cost: 3 classes of defect in one day, each of which
# reached a published image and was only found by a real job failing.
#   - /home/runner owned by root while the process ran as dev, so the runner could
#     not write .runner or .credentials at registration;
#   - the process outside gid 123, so it could not reach the dind socket;
#   - node installed under /home/dev via nvm and absent from PATH for any other user.
#
# What it BOUGHT: nothing. The pod runs a privileged dind sidecar, so a job can
# already `docker run --privileged -v /:/host` and take the node. An unprivileged
# runner container beside a privileged daemon is not a boundary.
#
# Reintroduce a non-root runner when the dind sidecar is gone, and not before.
# Recorded in gophersys/infrastructure docs/debt-register.md.

# Identifies the image to anything that inspects it, the same way the dev images
# do. `-runner` is appended so a job can tell CI from an interactive session.
ENV GOPHERSYS_DEVCONTAINER_RUNNER=true \
    RUNNER_MANUALLY_TRAP_SIG=1 \
    ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=1 \
    RUNNER_ALLOW_RUNASROOT=1
# RUNNER_ALLOW_RUNASROOT is REQUIRED because this image runs as root. Without it
# run.sh prints "Must not run interactively with sudo" and exits 1 in under a
# second, and ARC replaces the pod in a loop with no job ever starting. The
# variable belongs in the image: the image is what decided to run as root.

WORKDIR /home/runner
# No ENTRYPOINT/CMD: the ARC scale set supplies `command: ["/home/runner/run.sh"]`.
