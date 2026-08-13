# CI image for gophersys/dense-ui — the browser-and-fonts toolchain baked in,
# so a missing tool is a HARD FAIL at build time, never a per-job install
# (ADR-0020 posture, same as ghcr.io/gophersys/base).
#
# The devcontainer (.devcontainer/Dockerfile) builds FROM this image, so dev
# and CI cannot drift: what developers reproduce failures in IS the CI env.
#
# Published as ghcr.io/gophersys/dense-ui-ci by .github/workflows/build-ci-image.yml.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -q && apt-get install -y -q --no-install-recommends \
      ca-certificates curl git python3 python3-venv unzip zip \
      fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# node 22 (nodesource) — the demo modules are gate-checked with node
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y -q nodejs && rm -rf /var/lib/apt/lists/*

# uv — the python toolchain runner
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# chromium via playwright AT BUILD TIME (ubuntu's apt chromium is a snap stub);
# --with-deps pulls the shared libs. The binary path is pinned into ENV so the
# probe's find_chrome() needs no discovery in CI.
RUN npx -y playwright@1.49 install --with-deps chromium \
    && chrome_bin="$(find /root/.cache/ms-playwright -name chrome -type f | head -1)" \
    && test -n "$chrome_bin" \
    && ln -s "$chrome_bin" /usr/local/bin/densui-chromium
ENV DENSUI_CHROME=/usr/local/bin/densui-chromium

# prove the critical tools before this image can ever be tagged
RUN /usr/local/bin/densui-chromium --version && uv --version && node --version && python3 --version
