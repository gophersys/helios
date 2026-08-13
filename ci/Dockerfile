# CI image for gophersys/dense-ui — browser and fonts baked in, so a missing
# tool is a HARD FAIL at build time, never a per-job install (ADR-0020
# posture, same as ghcr.io/gophersys/base).
#
# debian, not ubuntu: debian's chromium is a real package; ubuntu's is a snap
# stub, and the playwright CDN times out from the fleet's docker-build egress
# (proven in run 31750517561 — all three azureedge mirrors, 30s each).
#
# The devcontainer (.devcontainer/Dockerfile) builds FROM this image, so dev
# and CI cannot drift.
#
# Published as ghcr.io/gophersys/dense-ui-ci by .github/workflows/build-ci-image.yml.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -q && apt-get install -y -q --no-install-recommends \
      ca-certificates curl git python3 python3-venv unzip zip \
      chromium fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/chromium /usr/local/bin/densui-chromium
ENV DENSUI_CHROME=/usr/local/bin/densui-chromium

# node 22 (nodesource) — the demo modules are gate-checked with node
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y -q nodejs && rm -rf /var/lib/apt/lists/*

# uv — the python toolchain runner
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# prove the critical tools before this image can ever be tagged
RUN densui-chromium --version && uv --version && node --version && python3 --version
