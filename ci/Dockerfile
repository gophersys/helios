# CI image for gophersys/research-ui — browser and fonts baked in, so a missing
# tool is a HARD FAIL at build time, never a per-job install (ADR-0020
# posture).
#
# CHILD of ghcr.io/gophersys/base (house convention: base -> domain children;
# eden's flutter/zephyr are the siblings). The base carries shells and
# languages for humans — its node (nvm) and uv are profile-homed under the
# `dev` user — while CI jobs here run as root, so the tools the gates call
# are installed root-wide below and proven before the image can tag.
#
# Browser: google-chrome-stable from Google's own apt repo — ubuntu's
# chromium is a snap stub, and the playwright CDN times out from the fleet's
# docker-build egress (proven in run 31750517561 — all three azureedge
# mirrors, 30s each). Chrome ships amd64 only, so this image is amd64 only;
# an arm64 devcontainer host runs it under emulation.
#
# The devcontainer (.devcontainer/Dockerfile) builds FROM this image, so dev
# and CI cannot drift.
#
# Published as ghcr.io/gophersys/research-ui-ci by .github/workflows/build-ci-image.yml,
# which pre-pulls the private base with GHCR_PULL_TOKEN — a cross-repo
# package; GITHUB_TOKEN's packages:read covers only this repo's own packages
# (eden lesson L3).
ARG BASE_TAG=latest
FROM ghcr.io/gophersys/base:${BASE_TAG}

USER root
ENV DEBIAN_FRONTEND=noninteractive

# google-chrome-stable via Google's apt repo (amd64 only)
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
      | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update -q \
    && apt-get install -y -q --no-install-recommends \
      google-chrome-stable fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/google-chrome-stable /usr/local/bin/ui-chromium
ENV UI_CHROME=/usr/local/bin/ui-chromium
# Gates stream their verdicts: without this, python block-buffers when piped
# and uv mutes progress on non-tty, so a slow CI step is indistinguishable
# from a hung one (proven in run 31761167311 — 9.5 silent minutes read as a
# stall and got cancelled).
ENV PYTHONUNBUFFERED=1

# node 22 root-wide (base's node is nvm/profile-homed under `dev`; gates run as root)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y -q nodejs && rm -rf /var/lib/apt/lists/*

# uv root-wide (base's uv lives in /home/dev/.local/bin)
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# prove the critical tools before this image can ever be tagged
RUN ui-chromium --version && uv --version && node --version && python3 --version
