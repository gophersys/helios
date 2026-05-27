# Concord Generic Test Runner
#
# Downloads product-specific test packages from MinIO at startup.
# The test code is NOT baked in — it's downloaded at runtime based
# on the TEST_PACKAGE_VERSION env var. One image serves all products.
#
# Contains:
#   - Python 3.10 + pytest + grpcio
#   - corekinect framework (test, hardware, cloud, protocols)
#   - corectl CLI
#   - nRF Command Line Tools (nrfjprog + J-Link)
#
# Build:
#   npx nx build test-runner -c staging
#
# Push:
#   npx nx push test-runner -c staging

FROM ubuntu:22.04

# ─────────────────────────────────────────────────────────────────────────────
# System Dependencies
# ─────────────────────────────────────────────────────────────────────────────

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    iputils-ping \
    curl \
    ca-certificates \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────────────────
# nRF Command Line Tools (nrfjprog + J-Link)
# ─────────────────────────────────────────────────────────────────────────────

ARG NRF_CLI_VERSION=10.24.2

RUN apt-get update && apt-get install -y --no-install-recommends libusb-1.0-0 && \
    ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
      NRF_CLI_DEB="nrf-command-line-tools_${NRF_CLI_VERSION}_amd64.deb"; \
    else \
      NRF_CLI_DEB="nrf-command-line-tools_${NRF_CLI_VERSION}_arm64.deb"; \
    fi && \
    curl -o nrf-cli-tools.deb "https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/desktop-software/nrf-command-line-tools/sw/versions-10-x-x/10-24-2/${NRF_CLI_DEB}" && \
    apt-get install -y ./nrf-cli-tools.deb && \
    rm nrf-cli-tools.deb && \
    # Install bundled J-Link driver
    JLINK_DEB=$(find /opt/nrf-command-line-tools/share/ -name 'JLink_Linux_*.deb' | head -1) && \
    if [ -n "$JLINK_DEB" ]; then apt-get install -y "$JLINK_DEB" --fix-broken || true; fi && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────────────────
# Python Dependencies (framework + test deps, cached layer)
# ─────────────────────────────────────────────────────────────────────────────

WORKDIR /app

COPY deploy/runner/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# corekinect Framework + Protocols
# ─────────────────────────────────────────────────────────────────────────────

ARG CACHE_BUST=0

COPY libs/protocols/mtib /libs/protocols/mtib
COPY libs/python /libs/python

ENV PYTHONPATH="/app:/libs:/libs/python:/libs/protocols"

# ─────────────────────────────────────────────────────────────────────────────
# corectl CLI
# ─────────────────────────────────────────────────────────────────────────────

COPY tools/corectl /tmp/corectl
RUN pip3 install --no-cache-dir /tmp/corectl && rm -rf /tmp/corectl

# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint: download test package → install deps → run tests
# ─────────────────────────────────────────────────────────────────────────────

COPY deploy/runner/entrypoint.sh /app/entrypoint.sh
COPY deploy/runner/check_framework_constraint.py /app/check_framework_constraint.py
RUN chmod +x /app/entrypoint.sh /app/check_framework_constraint.py

# ─────────────────────────────────────────────────────────────────────────────
# Build Metadata
# ─────────────────────────────────────────────────────────────────────────────

ARG APP_VERSION=0.0.0
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_TIME=unknown
ARG ENVIRONMENT=development
# Phase D Layer 2 — corekinect tree SHA baked at build time. The
# `_check_runner_corekinect_freshness` gate in deploy/ctl.sh reads this
# env var from `docker image inspect` and refuses to deploy if it
# diverges from the workspace's libs/python/corekinect/ HEAD.
ARG COREKINECT_GIT_SHA=unknown

ENV APP_VERSION=${APP_VERSION}
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}
ENV BUILD_TIME=${BUILD_TIME}
ENV ENVIRONMENT=${ENVIRONMENT}
ENV COREKINECT_GIT_SHA=${COREKINECT_GIT_SHA}

# Human-readable build info file. Also readable by the runner entrypoint
# at runtime so we can correlate a pod to its source SHA without docker
# inspect access.
RUN printf 'app_version=%s\ngit_commit=%s\ngit_branch=%s\nbuild_time=%s\nenvironment=%s\ncorekinect_git_sha=%s\n' \
      "${APP_VERSION}" "${GIT_COMMIT}" "${GIT_BRANCH}" "${BUILD_TIME}" "${ENVIRONMENT}" "${COREKINECT_GIT_SHA}" \
      > /etc/concord-runner-build-info

# ─────────────────────────────────────────────────────────────────────────────
# Runtime defaults
# ─────────────────────────────────────────────────────────────────────────────

ENV STAGE=fuota
ENV ARTIFACTS_DIR=/var/log/validation

ENTRYPOINT ["/app/entrypoint.sh"]
