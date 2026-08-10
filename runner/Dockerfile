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
ARG USERNAME=dev
ARG TARGETPLATFORM

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
 && mkdir -p /home/runner/_work \
 && chown -R "${USERNAME}:${USERNAME}" /home/runner
# NOTE: no --version smoke here — the runner binary is cross-arch and fails under
# QEMU. `.ci/smoke.sh` verifies it on a native runner after the push.

# Identifies the image to anything that inspects it, the same way the dev images
# do. `-runner` is appended so a job can tell CI from an interactive session.
ENV GOPHERSYS_DEVCONTAINER_RUNNER=true \
    RUNNER_MANUALLY_TRAP_SIG=1 \
    ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=1

USER ${USERNAME}
WORKDIR /home/runner
# No ENTRYPOINT/CMD: the ARC scale set supplies `command: ["/home/runner/run.sh"]`.
