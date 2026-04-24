# syntax=docker/dockerfile:1.7
#
# hadolint global ignore=SC1071,DL4006,SC3040
#
# images/orchestrator — Ubuntu 24.04 thin orchestration image.
#
# Role: brain-level orchestration — Claude orchestrator session, mkdocs
# Material docs site, MCP servers, short-lived autonomous agents. Peer of
# `base` (not a derivative); the two carry different tool surfaces and
# are sized differently. Bundling would defeat both goals: dev work needs
# the 5 GB toolchain, cron nodes only need ~500 MB.
#
# What's IN:
#   - Python 3.12 + uv (all Python tooling lands here)
#   - Node 24 LTS + nvm + npm + corepack (MCP servers + claude CLI)
#   - Claude Code CLI (@anthropic-ai/claude-code via npm)
#   - Bitwarden CLI (secrets materialization)
#   - GitHub CLI
#   - Docker CLI client only (NO daemon — host socket via proxy at runtime)
#   - mkdocs Material + plugins (docs site)
#   - openai + voyageai (API-only LLM clients; no local weights)
#   - pyyaml + jsonschema (frontmatter + schema validation)
#   - jq/yq/ripgrep/fd/bat for corpus queries
#   - zsh + oh-my-zsh (default shell)
#
# Deliberately absent (route to a project devcontainer via socket-proxy):
#   - Go/Rust/Flutter/Android/Zephyr SDKs
#   - terraform/kubectl/helm/k9s/tailscale/ansible/oci-cli/aws-cli
#   - postgresql-client/sqlite3-cli/redis-cli (orchestrator is not a data-plane)
#   - desktop (GTK/webkit) and USB/BLE libraries
#
# Deferred (added when the RAG pipeline lands):
#   - sqlite-vec, tantivy, sentence-transformers, torch (CPU wheel)
#
# Conventions (identical to base):
#   - Every tool version is an ARG at the top with a "latest LTS as of" comment.
#   - No hardcoded versions in RUN statements.
#   - Multi-arch-aware: every binary install resolves ARCH from TARGETPLATFORM.
#   - oh-my-zsh default shell; SHELL switches to zsh after install.
#   - Non-root `dev` user (uid 1000). The ubuntu 24.04 default user is removed first.

FROM --platform=${BUILDPLATFORM:-linux/amd64} ubuntu:24.04

# Buildx-injected platform vars. Declared so RUN layers can branch on arch.
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# -------------------------------------------------------------------------
# Tool versions — all pinned ARGs. Every value below is the latest LTS or
# latest stable release as of 2026-04-24. Bump a value by editing the ARG;
# never hardcode a version in a RUN line.
# -------------------------------------------------------------------------

# Shell.
ARG ZSH_VERSION=5.9                                                    # latest LTS as of 2026-04-24
ARG OH_MY_ZSH_INSTALL_URL=https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh

# Node toolchain — nvm installs the pinned Node LTS, corepack enables yarn/pnpm.
ARG NVM_VERSION=0.40.4                                                 # latest LTS as of 2026-04-24
ARG NODE_VERSION=24.15.0                                               # latest LTS as of 2026-04-24 (Krypton)
ARG NPM_VERSION=11.3.0                                                 # latest LTS as of 2026-04-24

# Python — apt-provided 3.12 + uv for user-space packaging.
ARG PYTHON_PACKAGE=python3.12                                          # latest LTS as of 2026-04-24
ARG UV_VERSION=0.11.7                                                  # latest LTS as of 2026-04-24

# Auth + transport CLIs.
ARG BW_VERSION=2026.3.0                                                # latest LTS as of 2026-04-24
ARG GH_VERSION=2.90.0                                                  # latest LTS as of 2026-04-24

# Docker CLI client (no daemon — brain mounts a docker-socket-proxy).
ARG DOCKER_COMPOSE_VERSION=5.1.3                                       # latest LTS as of 2026-04-24

# Dev QA.
ARG HADOLINT_VERSION=2.14.0                                            # latest LTS as of 2026-04-24

# Claude Code CLI — npm package @anthropic-ai/claude-code.
ARG CLAUDE_CODE_VERSION=2.0.1                                          # latest as of 2026-04-24

# Python application stack (docs + schema validation + API LLM clients).
ARG MKDOCS_MATERIAL_VERSION=9.5.45                                     # latest as of 2026-04-24
ARG MKDOCS_MACROS_VERSION=1.3.7                                        # latest as of 2026-04-24
ARG PYMDOWN_EXTENSIONS_VERSION=10.14                                   # latest as of 2026-04-24
ARG PYYAML_VERSION=6.0.2                                               # latest as of 2026-04-24
ARG JSONSCHEMA_VERSION=4.23.0                                          # latest as of 2026-04-24
ARG VOYAGEAI_VERSION=0.3.2                                             # latest as of 2026-04-24
ARG OPENAI_VERSION=1.54.0                                              # latest as of 2026-04-24

# yq binary.
ARG YQ_VERSION=4.44.3                                                  # latest LTS as of 2026-04-24

# Non-root dev user identity.
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

# -------------------------------------------------------------------------
# Base env — set once.
# -------------------------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    GOPHERSYS_DEVCONTAINER=orchestrator

# -------------------------------------------------------------------------
# apt layer — minimal orchestration tooling. Intentionally a subset of
# base: no desktop/USB/BLE/infra/data-client libraries.
# -------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      apt-transport-https \
      bash-completion \
      bat \
      build-essential \
      ca-certificates \
      curl \
      fd-find \
      git \
      gnupg \
      htop \
      httpie \
      iputils-ping \
      jq \
      less \
      libssl-dev \
      locales \
      lsb-release \
      make \
      net-tools \
      openssh-client \
      pkg-config \
      python3-pip \
      "${PYTHON_PACKAGE}" \
      "${PYTHON_PACKAGE}-dev" \
      "${PYTHON_PACKAGE}-venv" \
      ripgrep \
      shellcheck \
      software-properties-common \
      sudo \
      tmux \
      tzdata \
      unzip \
      util-linux \
      vim \
      wget \
      xz-utils \
      "zsh=${ZSH_VERSION}*" \
 && locale-gen C.UTF-8 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Debian renames fd-find/batcat; provide the names the ecosystem expects.
RUN ln -sf /usr/bin/fdfind /usr/local/bin/fd \
 && ln -sf /usr/bin/batcat /usr/local/bin/bat

# -------------------------------------------------------------------------
# Remove default `ubuntu` uid 1000 user (24.04 ships with it now); create
# `dev` at uid 1000 so bind mounts line up with the host user.
# -------------------------------------------------------------------------
RUN if id ubuntu >/dev/null 2>&1; then userdel --remove ubuntu 2>/dev/null || userdel ubuntu; fi \
 && if getent group ubuntu >/dev/null 2>&1; then groupdel ubuntu || true; fi \
 && groupadd --gid "${USER_GID}" "${USERNAME}" \
 && useradd --uid "${USER_UID}" --gid "${USER_GID}" --create-home --shell /usr/bin/zsh "${USERNAME}" \
 && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
 && chmod 0440 "/etc/sudoers.d/${USERNAME}" \
 && mkdir -p /workspace \
 && chown -R "${USERNAME}:${USERNAME}" /workspace "/home/${USERNAME}"

# -------------------------------------------------------------------------
# oh-my-zsh for the dev user, then switch SHELL to zsh for later layers.
# Move SHELL to bash with pipefail for the curl | sh install; ubuntu
# 24.04's /bin/sh is dash and does not support `set -o pipefail`.
# -------------------------------------------------------------------------
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER ${USERNAME}
RUN curl -fsSL "${OH_MY_ZSH_INSTALL_URL}" | sh -s -- --unattended --keep-zshrc \
 && touch "/home/${USERNAME}/.zshrc"

SHELL ["/usr/bin/zsh", "-o", "pipefail", "-c"]

# -------------------------------------------------------------------------
# yq binary — Mike Farah's release, multi-arch. Installed under
# /home/dev/.local/bin to stay out of /usr.
# -------------------------------------------------------------------------
RUN mkdir -p "/home/${USERNAME}/.local/bin" \
 && case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${ARCH}" \
      -o "/home/${USERNAME}/.local/bin/yq" \
 && chmod +x "/home/${USERNAME}/.local/bin/yq"
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# -------------------------------------------------------------------------
# nvm + Node LTS + corepack. The nvm installer refuses to run under zsh
# so we override $SHELL and invoke the whole block under bash.
# -------------------------------------------------------------------------
ENV NVM_DIR=/home/${USERNAME}/.nvm
RUN unset ZSH_VERSION; SHELL=/bin/bash bash -c "unset ZSH_VERSION; set -euo pipefail; \
      mkdir -p \"\${NVM_DIR}\"; \
      curl -fsSL \"https://raw.githubusercontent.com/nvm-sh/nvm/v${NVM_VERSION}/install.sh\" | PROFILE=/dev/null bash; \
      . \"\${NVM_DIR}/nvm.sh\"; \
      nvm install \"${NODE_VERSION}\"; \
      nvm alias default \"${NODE_VERSION}\"; \
      npm install -g \"npm@${NPM_VERSION}\"; \
      corepack enable; \
      corepack prepare yarn@stable --activate; \
      corepack prepare pnpm@latest --activate"

# -------------------------------------------------------------------------
# Claude Code CLI — npm-installed globally into the dev user's nvm prefix.
# -------------------------------------------------------------------------
RUN unset ZSH_VERSION; SHELL=/bin/bash bash -c "unset ZSH_VERSION; set -euo pipefail; \
      . \"\${NVM_DIR}/nvm.sh\"; \
      npm install -g \"@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}\""
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# -------------------------------------------------------------------------
# uv — Python package manager. Installed via the official installer to
# /home/dev/.local/bin.
# -------------------------------------------------------------------------
RUN curl -fsSL "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh \
 && "/home/${USERNAME}/.local/bin/uv" --version

# -------------------------------------------------------------------------
# Python application stack — installed via `uv tool install` into isolated
# venvs so mkdocs, the docs-site build, and API clients never collide
# with arbitrary project deps. Every dep is arch-neutral (pure Python);
# no compilation under QEMU.
# -------------------------------------------------------------------------
# `uv tool install` creates an isolated venv per tool. Library imports
# (pyyaml, jsonschema) go into a shared workspace venv at /home/dev/.venv
# so scripts can activate one env for general library use.
# hadolint ignore=DL3013
RUN "/home/${USERNAME}/.local/bin/uv" tool install --python "${PYTHON_PACKAGE}" \
      --with "mkdocs-macros-plugin==${MKDOCS_MACROS_VERSION}" \
      --with "pymdown-extensions==${PYMDOWN_EXTENSIONS_VERSION}" \
      "mkdocs-material==${MKDOCS_MATERIAL_VERSION}" \
 && "/home/${USERNAME}/.local/bin/uv" tool install --python "${PYTHON_PACKAGE}" \
      "voyageai==${VOYAGEAI_VERSION}" \
 && "/home/${USERNAME}/.local/bin/uv" tool install --python "${PYTHON_PACKAGE}" \
      "openai==${OPENAI_VERSION}" \
 && "/home/${USERNAME}/.local/bin/uv" venv --python "${PYTHON_PACKAGE}" "/home/${USERNAME}/.venv" \
 && "/home/${USERNAME}/.local/bin/uv" pip install --python "/home/${USERNAME}/.venv/bin/python" \
      "pyyaml==${PYYAML_VERSION}" \
      "jsonschema==${JSONSCHEMA_VERSION}"
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# -------------------------------------------------------------------------
# Infra / transport CLIs — root-installed under /usr/local/bin.
# -------------------------------------------------------------------------
USER root

# gh CLI — multi-arch.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" -o /tmp/gh.tgz \
 && tar -C /tmp -xzf /tmp/gh.tgz \
 && mv "/tmp/gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh \
 && rm -rf /tmp/gh.tgz "/tmp/gh_${GH_VERSION}_linux_${ARCH}"
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Bitwarden CLI — native binary zip. amd64 has no arch suffix in the
# upstream asset name; arm64 has "-arm64-".
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) BW_ASSET="bw-oss-linux-${BW_VERSION}.zip" ;; \
      linux/arm64) BW_ASSET="bw-oss-linux-arm64-${BW_VERSION}.zip" ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/bitwarden/clients/releases/download/cli-v${BW_VERSION}/${BW_ASSET}" -o /tmp/bw.zip \
 && unzip -q /tmp/bw.zip -d /usr/local/bin \
 && chmod +x /usr/local/bin/bw \
 && rm /tmp/bw.zip
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# hadolint — single binary.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) HADOLINT_ASSET="hadolint-linux-x86_64" ;; \
      linux/arm64) HADOLINT_ASSET="hadolint-linux-arm64" ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/${HADOLINT_ASSET}" \
      -o /usr/local/bin/hadolint \
 && chmod +x /usr/local/bin/hadolint
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Docker Engine CLI — client only. The orchestrator mounts a
# docker-socket-proxy (not the raw host socket) to launch project-scoped
# work inside project devcontainers.
# hadolint ignore=DL3008,DL3009,DL4006
RUN install -m 0755 -d /etc/apt/keyrings \
 && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
 && chmod a+r /etc/apt/keyrings/docker.asc \
 && . /etc/os-release \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
      > /etc/apt/sources.list.d/docker.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends docker-ce-cli \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# docker-compose plugin — pinned binary; independent of whatever
# compose-plugin version apt carries at build time.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x86_64 ;; \
      linux/arm64) ARCH=aarch64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && curl -fsSL "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# -------------------------------------------------------------------------
# PATH shims in /etc/zsh/zshenv so every zsh sees the installed toolchains
# without per-user config.
# -------------------------------------------------------------------------
RUN { \
      echo '# Set by gophersys/orchestrator Dockerfile.'; \
      echo 'export PATH=/home/dev/.local/bin:/home/dev/.venv/bin:/usr/local/lib/docker/cli-plugins:${PATH}'; \
      echo 'export NVM_DIR=/home/dev/.nvm'; \
      echo '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"'; \
      echo 'export UV_PROJECT_ENVIRONMENT=/home/dev/.venv'; \
    } >> /etc/zsh/zshenv

# -------------------------------------------------------------------------
# Final image identity.
# -------------------------------------------------------------------------
LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys orchestrator: Ubuntu 24.04 thin image for brain-level orchestration (Claude, mkdocs, agents)"
LABEL org.opencontainers.image.licenses="MIT"

USER ${USERNAME}
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
