# syntax=docker/dockerfile:1.7
#
# hadolint global ignore=SC1071,DL4006,SC3040
#
# SC1071/DL4006/SC3040 are disabled globally because the SHELL directive
# below switches to /usr/bin/zsh. hadolint's embedded shellcheck only
# supports sh/bash/dash/ksh and warns on every zsh RUN line. The `set -o
# pipefail` semantics hold in zsh as well; the warning is a tooling gap.
#
# images/base — Ubuntu 24.04 LTS IDP base image.
#
# Single "pick up and work" image for the brain ecosystem: shells, languages
# (Node, Python, Go, Rust), infra CLIs (kubectl/helm/terraform/tailscale/gh),
# desktop/Tauri system libs, USB/BLE system libs, and the data/parsing tools
# every consuming project reaches for. Child images (flutter, zephyr) add
# domain-specific toolchains on top.
#
# Conventions enforced by this Dockerfile:
#   - Every tool version is an ARG at the top with a "latest LTS as of" comment.
#   - No hardcoded versions in RUN statements — always reference an ARG.
#   - Multi-arch-aware: every binary install resolves ARCH from TARGETPLATFORM.
#   - oh-my-zsh is the default shell; SHELL switches to zsh after install so
#     later RUN layers run under zsh.
#   - Non-root `dev` user (uid 1000). The ubuntu 24.04 default `ubuntu` user
#     at uid 1000 is removed first.

FROM --platform=${BUILDPLATFORM:-linux/amd64} ubuntu:24.04

# Buildx-injected platform vars. Declared so RUN layers can branch on arch.
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# -------------------------------------------------------------------------
# Tool versions — all pinned ARGs. Every value below is the latest LTS or
# latest stable release as of 2026-04-19. Bump a value by editing the ARG;
# never hardcode a version in a RUN line.
# -------------------------------------------------------------------------

# Shell — zsh via apt, oh-my-zsh via the official installer URL.
ARG ZSH_VERSION=5.9                                                    # latest LTS as of 2026-04-19
ARG OH_MY_ZSH_INSTALL_URL=https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh

# Node toolchain — nvm installs the pinned Node LTS, corepack enables yarn.
ARG NVM_VERSION=0.40.4                                                 # latest LTS as of 2026-04-19
ARG NODE_VERSION=24.15.0                                               # latest LTS as of 2026-04-19 (Krypton)
ARG NPM_VERSION=11.3.0                                                 # latest LTS as of 2026-04-19

# Python — apt-provided 3.12 + uv for user-space package mgmt.
ARG PYTHON_PACKAGE=python3.12                                          # latest LTS as of 2026-04-19
ARG UV_VERSION=0.11.7                                                  # latest LTS as of 2026-04-19

# Go — official tarball.
ARG GO_VERSION=1.26.2                                                  # latest LTS as of 2026-04-19

# Rust — rustup channel, not a pinned version.
ARG RUST_CHANNEL=stable                                                # latest LTS as of 2026-04-19

# Infra CLIs.
ARG TERRAFORM_VERSION=1.14.8                                           # latest LTS as of 2026-04-19
ARG KUBECTL_VERSION=1.35.4                                             # latest LTS as of 2026-04-19
ARG HELM_VERSION=4.1.4                                                 # latest LTS as of 2026-04-19
ARG ANSIBLE_VERSION=13.5.0                                             # latest LTS as of 2026-04-19
ARG TAILSCALE_VERSION=1.96.4                                           # latest LTS as of 2026-04-19
ARG BW_VERSION=2026.3.0                                                # latest LTS as of 2026-04-19
ARG GH_VERSION=2.90.0                                                  # latest LTS as of 2026-04-19
ARG K9S_VERSION=0.50.18                                                # latest LTS as of 2026-04-19
ARG DOCKER_COMPOSE_VERSION=5.1.3                                       # latest LTS as of 2026-04-19
ARG NATS_VERSION=0.3.2                                                 # latest LTS as of 2026-04-19

# Dev QA.
ARG HADOLINT_VERSION=2.14.0                                            # latest LTS as of 2026-04-19

# Non-root dev user identity.
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

# -------------------------------------------------------------------------
# Base env — set once. locale is handled alongside the apt layer below.
# -------------------------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    GOPHERSYS_DEVCONTAINER=base

# -------------------------------------------------------------------------
# apt layer 1 — system, networking, parsing, QA, data clients, desktop libs,
# USB/BLE libs. One apt-get update + install + rm in the same RUN to keep
# the layer reproducible and lean.
# -------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      apt-transport-https \
      bash-completion \
      bat \
      bluez \
      btop \
      build-essential \
      ca-certificates \
      clang \
      cmake \
      curl \
      dirmngr \
      fd-find \
      gettext \
      git \
      gnupg \
      htop \
      httpie \
      iputils-ping \
      jq \
      less \
      libayatana-appindicator3-dev \
      libbluetooth-dev \
      libgtk-3-dev \
      librsvg2-dev \
      libssl-dev \
      libudev-dev \
      libusb-1.0-0-dev \
      libwebkit2gtk-4.1-dev \
      locales \
      lsb-release \
      make \
      ncat \
      net-tools \
      openssh-client \
      pkg-config \
      postgresql-client \
      python3-pip \
      "${PYTHON_PACKAGE}" \
      "${PYTHON_PACKAGE}-dev" \
      "${PYTHON_PACKAGE}-venv" \
      redis-tools \
      ripgrep \
      shellcheck \
      software-properties-common \
      speedtest-cli \
      sqlite3 \
      sudo \
      tmux \
      tzdata \
      unzip \
      usbutils \
      util-linux \
      vim \
      wget \
      xz-utils \
      "zsh=${ZSH_VERSION}*" \
 && locale-gen C.UTF-8 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Debian renames some binaries; provide the names the ecosystem expects.
RUN ln -sf /usr/bin/fdfind /usr/local/bin/fd \
 && ln -sf /usr/bin/batcat /usr/local/bin/bat

# -------------------------------------------------------------------------
# Remove the default `ubuntu` uid 1000 user (24.04 ships with it now), then
# create `dev` at uid 1000 so bind mounts line up with the typical host user.
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
# oh-my-zsh for the `dev` user, then switch SHELL to zsh for every
# subsequent RUN layer. We first move SHELL to bash with -o pipefail so the
# curl | sh pipeline is safe (ubuntu 24.04's /bin/sh is dash, which does
# not support `set -o pipefail`). Then we switch to zsh for the remaining
# language-toolchain layers.
# -------------------------------------------------------------------------
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER ${USERNAME}
RUN curl -fsSL "${OH_MY_ZSH_INSTALL_URL}" | sh -s -- --unattended --keep-zshrc \
 && touch "/home/${USERNAME}/.zshrc"

SHELL ["/usr/bin/zsh", "-o", "pipefail", "-c"]

# -------------------------------------------------------------------------
# Language toolchains — installed into the dev user's home so nothing
# requires root at runtime.
# -------------------------------------------------------------------------

# yq — multi-arch binary from Mike Farah's releases. Pinned to match the jq
# ecosystem; installed under /home/dev/.local/bin to stay out of /usr.
ARG YQ_VERSION=4.44.3                                                  # latest LTS as of 2026-04-19
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

# nvm + Node LTS + corepack (yarn, pnpm). The nvm installer inspects $SHELL
# and refuses to run when it sees zsh, so we override $SHELL for this RUN
# and invoke the whole block under bash.
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

# uv — Python package manager. Installed via the official installer to the
# dev user's ~/.local/bin.
RUN curl -fsSL "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh \
 && "/home/${USERNAME}/.local/bin/uv" --version

# Go — official tarball, TARGETPLATFORM-aware. Installed under /home/dev/go
# so /usr is not touched.
ENV GOROOT=/home/${USERNAME}/go-sdk \
    GOPATH=/home/${USERNAME}/go \
    PATH=/home/${USERNAME}/go-sdk/bin:/home/${USERNAME}/go/bin:/home/${USERNAME}/.local/bin:${PATH}
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p "${GOROOT}" "${GOPATH}/bin" \
 && curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" -o /tmp/go.tgz \
 && tar -C "${GOROOT}" --strip-components=1 -xzf /tmp/go.tgz \
 && rm /tmp/go.tgz
# NOTE: no go version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Rust — rustup pinned to the declared channel. `rustup-init -y` is idempotent.
ENV CARGO_HOME=/home/${USERNAME}/.cargo \
    RUSTUP_HOME=/home/${USERNAME}/.rustup \
    PATH=/home/${USERNAME}/.cargo/bin:${PATH}
RUN curl -fsSL https://sh.rustup.rs -o /tmp/rustup-init.sh \
 && sh /tmp/rustup-init.sh -y --default-toolchain "${RUST_CHANNEL}" --profile minimal \
 && rm /tmp/rustup-init.sh \
 && rustup component add rustfmt clippy
# NOTE: no rustc/cargo --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# -------------------------------------------------------------------------
# Infra CLIs. Each is TARGETPLATFORM-aware. Binary downloads are placed in
# /home/dev/.local/bin; the dev user already owns it.
# -------------------------------------------------------------------------
USER root
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip" -o /tmp/tf.zip \
 && unzip -q /tmp/tf.zip -d /usr/local/bin \
 && rm /tmp/tf.zip
# NOTE: no terraform version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" -o /usr/local/bin/kubectl \
 && chmod +x /usr/local/bin/kubectl
# NOTE: no kubectl version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" -o /tmp/helm.tgz \
 && tar -C /tmp -xzf /tmp/helm.tgz \
 && mv "/tmp/linux-${ARCH}/helm" /usr/local/bin/helm \
 && rm -rf /tmp/helm.tgz "/tmp/linux-${ARCH}"
# NOTE: no helm version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/derailed/k9s/releases/download/v${K9S_VERSION}/k9s_Linux_${ARCH}.tar.gz" -o /tmp/k9s.tgz \
 && tar -C /tmp -xzf /tmp/k9s.tgz k9s \
 && mv /tmp/k9s /usr/local/bin/k9s \
 && rm /tmp/k9s.tgz
# NOTE: no k9s version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" -o /tmp/gh.tgz \
 && tar -C /tmp -xzf /tmp/gh.tgz \
 && mv "/tmp/gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh \
 && rm -rf /tmp/gh.tgz "/tmp/gh_${GH_VERSION}_linux_${ARCH}"
# NOTE: no gh --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Tailscale — the static binary bundle is TARGETPLATFORM-aware.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://pkgs.tailscale.com/stable/tailscale_${TAILSCALE_VERSION}_${ARCH}.tgz" -o /tmp/ts.tgz \
 && tar -C /tmp -xzf /tmp/ts.tgz \
 && mv "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}/tailscale" /usr/local/bin/tailscale \
 && mv "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}/tailscaled" /usr/local/bin/tailscaled \
 && rm -rf /tmp/ts.tgz "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}"
# NOTE: no tailscale version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Bitwarden CLI — native binary zip (no Node runtime required). amd64 has
# no arch suffix in the upstream asset name; arm64 has "-arm64-".
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) BW_ASSET="bw-oss-linux-${BW_VERSION}.zip" ;; \
      linux/arm64) BW_ASSET="bw-oss-linux-arm64-${BW_VERSION}.zip" ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/bitwarden/clients/releases/download/cli-v${BW_VERSION}/${BW_ASSET}" -o /tmp/bw.zip \
 && unzip -q /tmp/bw.zip -d /usr/local/bin \
 && chmod +x /usr/local/bin/bw \
 && rm /tmp/bw.zip
# NOTE: no bw --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# hadolint — single binary. As of v2.14.0 upstream ships both linux-x86_64 and
# linux-arm64 releases; asset names switched to lowercase "linux" between 2.12
# and 2.14. Install on both arches.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) HADOLINT_ASSET="hadolint-linux-x86_64" ;; \
      linux/arm64) HADOLINT_ASSET="hadolint-linux-arm64" ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/${HADOLINT_ASSET}" \
      -o /usr/local/bin/hadolint \
 && chmod +x /usr/local/bin/hadolint
# NOTE: no hadolint --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# NATS CLI — single binary zip, TARGETPLATFORM-aware.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/nats-io/natscli/releases/download/v${NATS_VERSION}/nats-${NATS_VERSION}-linux-${ARCH}.zip" -o /tmp/nats.zip \
 && unzip -q /tmp/nats.zip -d /tmp/nats \
 && mv "/tmp/nats/nats-${NATS_VERSION}-linux-${ARCH}/nats" /usr/local/bin/nats \
 && rm -rf /tmp/nats /tmp/nats.zip
# NOTE: no nats --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Docker Engine CLI + compose plugin from the official apt repo. The CLI is
# all we ship — dev boxes mount the host socket.
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

# docker-compose standalone binary pinned to DOCKER_COMPOSE_VERSION so we are
# independent of whatever compose-plugin version apt has at build time.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x86_64 ;; \
      linux/arm64) ARCH=aarch64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && curl -fsSL "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
# NOTE: no docker compose version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Ansible — install via pipx into the dev user's home so we never collide
# with the system python. Same pattern for ansible-core itself.
USER ${USERNAME}
# hadolint ignore=DL3013
RUN "/home/${USERNAME}/.local/bin/uv" tool install --python "${PYTHON_PACKAGE}" "ansible==${ANSIBLE_VERSION}" \
 && "/home/${USERNAME}/.local/bin/uv" tool run ansible --version

# Convenience: path shims for zsh so interactive logins see all of the
# installed toolchains without per-user config. Written to /etc/zsh/zshenv
# so every zsh (interactive or not) picks it up.
USER root
RUN { \
      echo '# Set by gophersys/base Dockerfile.'; \
      echo 'export PATH=/home/dev/.local/bin:/home/dev/.cargo/bin:/home/dev/go-sdk/bin:/home/dev/go/bin:/usr/local/lib/docker/cli-plugins:${PATH}'; \
      echo 'export GOROOT=/home/dev/go-sdk'; \
      echo 'export GOPATH=/home/dev/go'; \
      echo 'export NVM_DIR=/home/dev/.nvm'; \
      echo '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"'; \
    } >> /etc/zsh/zshenv

# -------------------------------------------------------------------------
# Final image identity.
# -------------------------------------------------------------------------
LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys IDP base: Ubuntu 24.04 + shells/langs/infra/desktop/USB-BLE toolchain"
LABEL org.opencontainers.image.licenses="MIT"

USER ${USERNAME}
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
