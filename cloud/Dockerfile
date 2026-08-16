# syntax=docker/dockerfile:1.7
#
# hadolint global ignore=SC1071,DL4006,SC3040,DL3059
#
# SC1071/DL4006/SC3040 are disabled globally because the SHELL directive
# below switches to /usr/bin/zsh. hadolint's embedded shellcheck only
# supports sh/bash/dash/ksh and warns on every zsh RUN line. The `set -o
# pipefail` semantics hold in zsh as well; the warning is a tooling gap.
#
# DL3059 (consolidate consecutive RUNs) is disabled because the component
# calls below are one RUN per component ON PURPOSE: one tool group, one
# layer, one proof — a failed component names itself, and a version bump
# rebuilds exactly one layer. Consolidation is the defect here, not the fix.
#
# cloud — the reduced base + the CI fold (image-architecture §2.2, ledger #94).
#
# ONE image for dev and CI, byte for byte. In a devcontainer the runner, the
# claude CLI and cictl are inert files; a CI pod overrides the container
# command to /home/runner/run.sh. The deployment shape is chosen by the
# command, never by a different image.
#
# The KEEP set is base/Dockerfile's proven RUN blocks, copied faithfully.
# Deliberately NOT here (they move to category deltas or are dropped by
# decision): clang, cmake, the GTK/webkit/Tauri dev libs, the USB/BLE libs,
# Rust, terraform, AWS CLI, ansible + oci-cli, speedtest-cli, ncat, net-tools.
#
# Conventions:
#   - ARGs at the top, VALUE-LESS: every version arrives as --build-arg
#     generated from versions.env at the repository root — the ONE home for
#     every pin. The pin gate below fails the build naming any missing one.
#   - No hardcoded versions in RUN statements.
#   - Architecture-aware: every binary install resolves ARCH from
#     TARGETPLATFORM.
#   - Tool groups beyond the kept base blocks install through
#     _delta/components/*.sh — one file per group, versions via environment,
#     each ending in its own proof line.

# No --platform here: it pinned the userland to the BUILD host while buildx
# labelled the result with the TARGET, which is how a mislabelled arm64 image
# was published once. Plain FROM makes the userland follow the target.
FROM ubuntu:24.04

# Buildx-injected platform var. Declared so RUN layers can branch on arch.
ARG TARGETPLATFORM

# -------------------------------------------------------------------------
# Tool versions — value-less ARGs, fed from versions.env via generated
# --build-arg (versions_env_build_args in _ctl/lib.sh; the CI job generates
# the same list). The "latest LTS as of" comments live in versions.env, next
# to the values they date.
# -------------------------------------------------------------------------

# Shell.
ARG ZSH_VERSION
ARG OH_MY_ZSH_INSTALL_URL=https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh

# Node toolchain.
ARG NVM_VERSION
ARG NODE_VERSION
ARG NPM_VERSION
ARG BUN_VERSION

# Python.
ARG PYTHON_PACKAGE
ARG UV_VERSION

# Go + gate tools (ADR-0018 + ADR-0020).
ARG GO_VERSION
ARG GOFUMPT_VERSION
ARG GOLANGCI_LINT_VERSION
ARG GOVULNCHECK_VERSION
ARG GOSEC_VERSION
ARG HNSLINT_VERSION
ARG GREMLINS_VERSION
ARG BENCHSTAT_REF
ARG DELVE_VERSION

# Parsing + QA.
ARG YQ_VERSION
ARG HADOLINT_VERSION
ARG KUBECONFORM_VERSION
ARG GITLEAKS_VERSION

# Infra CLIs.
ARG KUBECTL_VERSION
ARG HELM_VERSION
ARG K9S_VERSION
ARG K3D_VERSION
ARG KIND_VERSION
ARG TAILSCALE_VERSION
ARG BW_VERSION
ARG GH_VERSION
ARG NATS_VERSION

# Docker cli-plugins (version + per-arch release digest).
ARG DOCKER_COMPOSE_VERSION
ARG DOCKER_COMPOSE_SHA256_X86_64
ARG DOCKER_COMPOSE_SHA256_AARCH64
ARG DOCKER_BUILDX_VERSION
ARG DOCKER_BUILDX_SHA256_AMD64
ARG DOCKER_BUILDX_SHA256_ARM64

# Protocols.
ARG BUF_VERSION
ARG GRPCURL_VERSION

# The CI fold.
ARG RUNNER_VERSION
ARG CICTL_VERSION
ARG CLAUDE_CODE_VERSION
ARG OMP_VERSION
ARG CODEX_VERSION

# Non-root dev user identity.
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

# -------------------------------------------------------------------------
# The pin gate. Every version above must have arrived from versions.env; an
# absent pin would otherwise expand to the empty string and surface much
# later as a mangled download URL. FAIL-NOT-SKIP: the build stops HERE and
# the message names the variable.
# -------------------------------------------------------------------------
RUN : "${ZSH_VERSION:?not in versions.env}" \
 && : "${NVM_VERSION:?not in versions.env}" \
 && : "${NODE_VERSION:?not in versions.env}" \
 && : "${NPM_VERSION:?not in versions.env}" \
 && : "${BUN_VERSION:?not in versions.env}" \
 && : "${PYTHON_PACKAGE:?not in versions.env}" \
 && : "${UV_VERSION:?not in versions.env}" \
 && : "${GO_VERSION:?not in versions.env}" \
 && : "${GOFUMPT_VERSION:?not in versions.env}" \
 && : "${GOLANGCI_LINT_VERSION:?not in versions.env}" \
 && : "${GOVULNCHECK_VERSION:?not in versions.env}" \
 && : "${GOSEC_VERSION:?not in versions.env}" \
 && : "${HNSLINT_VERSION:?not in versions.env}" \
 && : "${GREMLINS_VERSION:?not in versions.env}" \
 && : "${BENCHSTAT_REF:?not in versions.env}" \
 && : "${DELVE_VERSION:?not in versions.env}" \
 && : "${YQ_VERSION:?not in versions.env}" \
 && : "${HADOLINT_VERSION:?not in versions.env}" \
 && : "${KUBECONFORM_VERSION:?not in versions.env}" \
 && : "${GITLEAKS_VERSION:?not in versions.env}" \
 && : "${KUBECTL_VERSION:?not in versions.env}" \
 && : "${HELM_VERSION:?not in versions.env}" \
 && : "${K9S_VERSION:?not in versions.env}" \
 && : "${K3D_VERSION:?not in versions.env}" \
 && : "${KIND_VERSION:?not in versions.env}" \
 && : "${TAILSCALE_VERSION:?not in versions.env}" \
 && : "${BW_VERSION:?not in versions.env}" \
 && : "${GH_VERSION:?not in versions.env}" \
 && : "${NATS_VERSION:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_VERSION:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_SHA256_X86_64:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_SHA256_AARCH64:?not in versions.env}" \
 && : "${DOCKER_BUILDX_VERSION:?not in versions.env}" \
 && : "${DOCKER_BUILDX_SHA256_AMD64:?not in versions.env}" \
 && : "${DOCKER_BUILDX_SHA256_ARM64:?not in versions.env}" \
 && : "${BUF_VERSION:?not in versions.env}" \
 && : "${GRPCURL_VERSION:?not in versions.env}" \
 && : "${RUNNER_VERSION:?not in versions.env}" \
 && : "${CICTL_VERSION:?not in versions.env}" \
 && : "${CLAUDE_CODE_VERSION:?not in versions.env}" \
 && : "${OMP_VERSION:?not in versions.env}" \
 && : "${CODEX_VERSION:?not in versions.env}"

# -------------------------------------------------------------------------
# Base env — set once. locale is handled alongside the apt layer below.
# -------------------------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    GOPHERSYS_DEVCONTAINER=cloud

# -------------------------------------------------------------------------
# apt layer 1 — system, networking, parsing, QA. base/Dockerfile's layer
# minus the moved and dropped groups: no clang, no cmake, no desktop libs,
# no USB/BLE libs, no db clients (component), no comfort TUIs (component),
# no ncat/net-tools/speedtest-cli (dropped for good).
# -------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      apt-transport-https \
      bash-completion \
      build-essential \
      ca-certificates \
      curl \
      dirmngr \
      fd-find \
      gettext \
      git \
      gnupg \
      iputils-ping \
      jq \
      less \
      libssl-dev \
      locales \
      lsb-release \
      make \
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

# Debian renames the binary; provide the name the ecosystem expects. (bat's
# symlink lives in the comforts component, next to its install.)
RUN ln -sf /usr/bin/fdfind /usr/local/bin/fd

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

# yq — multi-arch binary from Mike Farah's releases. Installed under
# /home/dev/.local/bin to stay out of /usr.
RUN mkdir -p "/home/${USERNAME}/.local/bin" \
 && case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${ARCH}" \
      -o "/home/${USERNAME}/.local/bin/yq" \
 && chmod +x "/home/${USERNAME}/.local/bin/yq"

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

# Go gate tools (ADR-0018 + ADR-0020), installed as the dev user into
# ${GOPATH}/bin so every gate verb resolves its tool (FAIL-NOT-SKIP).
# CGO_ENABLED=0 inline: the tools are pure Go, and the gate's `go test -race`
# still gets cgo from build-essential.
#
# THE CACHE CLEANUP IS THE POINT OF THIS LAYER. base/Dockerfile's copy of it
# measured 2.06 GB, of which ~1.6 GB was the module and build cache the RUN
# never removed — the 7 binaries are ~200 MB. `go clean` handles the
# read-only module tree; the rm afterwards mops what remains.
USER ${USERNAME}
RUN CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install mvdan.cc/gofumpt@v${GOFUMPT_VERSION} \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install "github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v${GOLANGCI_LINT_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install "golang.org/x/vuln/cmd/govulncheck@v${GOVULNCHECK_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install "github.com/securego/gosec/v2/cmd/gosec@v${GOSEC_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install "github.com/go-gremlins/gremlins/cmd/gremlins@v${GREMLINS_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install "golang.org/x/perf/cmd/benchstat@${BENCHSTAT_REF}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install "github.com/gophersys/hnslint/cmd/hnslint@v${HNSLINT_VERSION}" \
 && go clean -modcache \
 && go clean -cache \
 && rm -rf "${GOPATH}/pkg/mod" "/home/${USERNAME}/.cache/go-build"
USER root

# -------------------------------------------------------------------------
# Infra CLIs. Each is TARGETPLATFORM-aware — base/Dockerfile's blocks,
# copied faithfully. terraform, AWS and ansible/oci are NOT here: dropped by
# decision, their ready components sit in _delta/components/.
# -------------------------------------------------------------------------
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" -o /usr/local/bin/kubectl \
 && chmod +x /usr/local/bin/kubectl

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" -o /tmp/helm.tgz \
 && tar -C /tmp -xzf /tmp/helm.tgz \
 && mv "/tmp/linux-${ARCH}/helm" /usr/local/bin/helm \
 && rm -rf /tmp/helm.tgz "/tmp/linux-${ARCH}"

# k3d — the default local Kubernetes substrate for the ADR-0020
# integration/load lanes (k3s-in-docker; single static binary).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/k3d-io/k3d/releases/download/v${K3D_VERSION}/k3d-linux-${ARCH}" -o /usr/local/bin/k3d \
 && chmod +x /usr/local/bin/k3d

# kind — the second Kubernetes substrate target.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/kubernetes-sigs/kind/releases/download/v${KIND_VERSION}/kind-linux-${ARCH}" -o /usr/local/bin/kind \
 && chmod +x /usr/local/bin/kind

# gitleaks — the secret-scan tool for the ADR-0020 security dimension.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${ARCH}.tar.gz" -o /tmp/gitleaks.tgz \
 && tar -C /tmp -xzf /tmp/gitleaks.tgz gitleaks \
 && mv /tmp/gitleaks /usr/local/bin/gitleaks \
 && rm /tmp/gitleaks.tgz

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" -o /tmp/gh.tgz \
 && tar -C /tmp -xzf /tmp/gh.tgz \
 && mv "/tmp/gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh \
 && rm -rf /tmp/gh.tgz "/tmp/gh_${GH_VERSION}_linux_${ARCH}"

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

# hadolint — single binary; asset names are lowercase "linux" as of 2.14.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) HADOLINT_ASSET="hadolint-linux-x86_64" ;; \
      linux/arm64) HADOLINT_ASSET="hadolint-linux-arm64" ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/${HADOLINT_ASSET}" \
      -o /usr/local/bin/hadolint \
 && chmod +x /usr/local/bin/hadolint

# kubeconform — Kubernetes manifest schema validation.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      linux/arm64) ARCH=arm64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-${ARCH}.tar.gz" \
      -o /tmp/kubeconform.tar.gz \
 && tar -xzf /tmp/kubeconform.tar.gz -C /usr/local/bin kubeconform \
 && chmod +x /usr/local/bin/kubeconform \
 && rm -f /tmp/kubeconform.tar.gz

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

# Bun — JavaScript runtime for the Oh My Pi (`omp`) harness. Installed to
# /usr/local/bin so it is on PATH for every shell and user.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x64 ;; \
      linux/arm64) ARCH=aarch64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-${ARCH}.zip" -o /tmp/bun.zip \
 && unzip -q /tmp/bun.zip -d /tmp/bun \
 && mv "/tmp/bun/bun-linux-${ARCH}/bun" /usr/local/bin/bun \
 && chmod +x /usr/local/bin/bun \
 && rm -rf /tmp/bun /tmp/bun.zip

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
      linux/amd64) ARCH=x86_64;  SHA256="${DOCKER_COMPOSE_SHA256_X86_64}" ;; \
      linux/arm64) ARCH=aarch64; SHA256="${DOCKER_COMPOSE_SHA256_AARCH64}" ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && curl -fsSL "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose \
 && echo "${SHA256}  /usr/local/lib/docker/cli-plugins/docker-compose" | sha256sum -c - \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Convenience: path shims for zsh so interactive logins see all of the
# installed toolchains without per-user config. No cargo path: Rust moved to
# the category deltas that need it.
RUN { \
      echo '# Set by gophersys/cloud Dockerfile.'; \
      echo 'export PATH=/home/dev/.local/bin:/home/dev/go-sdk/bin:/home/dev/go/bin:/usr/local/lib/docker/cli-plugins:${PATH}'; \
      echo 'export GOROOT=/home/dev/go-sdk'; \
      echo 'export GOPATH=/home/dev/go'; \
      echo 'export NVM_DIR=/home/dev/.nvm'; \
      echo '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"'; \
    } >> /etc/zsh/zshenv

# Node on PATH for every user and every shell — ENV, not a sourced profile,
# so nothing has to lie about having verified it.
ENV PATH="/home/${USERNAME}/.nvm/versions/node/v${NODE_VERSION}/bin:${PATH}"

# -------------------------------------------------------------------------
# The component mechanism. Each script installs ONE tool group, reads its
# pins from the environment (the ARGs above are environment inside a RUN),
# asserts them present, and ends in its own proof line. The build context is
# the repository root, so _delta/ resolves.
# -------------------------------------------------------------------------
COPY _delta/components/ /opt/delta/components/

# One RUN per component ON PURPOSE: one tool group, one layer, one proof —
# a failed component names itself, and a version bump rebuilds one layer.
# Every version a component uses is an ARG above, threaded through the
# environment.

# Data clients: psql, redis-cli, sqlite3.
RUN bash /opt/delta/components/db-clients.sh

# k9s, pinned by K9S_VERSION.
RUN K9S_VERSION="${K9S_VERSION}" bash /opt/delta/components/k9s.sh

# Comforts kept by the census: bat, htop, btop, httpie.
RUN bash /opt/delta/components/comforts.sh

# The Go debugger, pinned by DELVE_VERSION.
RUN DELVE_VERSION="${DELVE_VERSION}" bash /opt/delta/components/delve.sh

# buf + grpcurl, pinned by BUF_VERSION / GRPCURL_VERSION.
RUN BUF_VERSION="${BUF_VERSION}" GRPCURL_VERSION="${GRPCURL_VERSION}" bash /opt/delta/components/protocols.sh

# The docker buildx cli-plugin — closes the measured base-runner gap.
# The prefix names the component's FULL pin contract. The ARGs reach the
# script through the RUN environment either way (the pin gate above runs on
# exactly that mechanism); the prefix is the call site documenting its
# component, and an understated one misleads.
RUN DOCKER_BUILDX_VERSION="${DOCKER_BUILDX_VERSION}" DOCKER_BUILDX_SHA256_AMD64="${DOCKER_BUILDX_SHA256_AMD64}" \
    DOCKER_BUILDX_SHA256_ARM64="${DOCKER_BUILDX_SHA256_ARM64}" bash /opt/delta/components/buildx.sh

# The CI fold: Actions runner + .NET deps + cictl.
RUN RUNNER_VERSION="${RUNNER_VERSION}" CICTL_VERSION="${CICTL_VERSION}" bash /opt/delta/components/runner.sh

# The harness bake runs as the dev user: claude lands in ~/.local/bin and the
# npm globals in the nvm prefix, both dev-owned and both on the ENV PATH.
USER ${USERNAME}
RUN CLAUDE_CODE_VERSION="${CLAUDE_CODE_VERSION}" OMP_VERSION="${OMP_VERSION}" CODEX_VERSION="${CODEX_VERSION}" \
    bash /opt/delta/components/agents.sh
USER root

# The scripts have done their work; the image does not ship them.
RUN rm -rf /opt/delta

# The runner semantics, carried from the retiring runner/Dockerfile.
# RUNNER_ALLOW_RUNASROOT: without it a pod that runs as root prints "Must not
# run interactively with sudo" and exits 1 in under a second, and ARC replaces
# the pod in a loop with no job ever starting. Inert in a devcontainer.
ENV RUNNER_MANUALLY_TRAP_SIG=1 \
    ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=1 \
    RUNNER_ALLOW_RUNASROOT=1

# -------------------------------------------------------------------------
# Final image identity. The default shape is the devcontainer: USER dev,
# CMD zsh. A CI pod overrides the command to /home/runner/run.sh — the
# command chooses the shape, never a different image.
# -------------------------------------------------------------------------
LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys cloud: the reduced IDP base + the CI fold (runner, claude, cictl, harnesses)"
LABEL org.opencontainers.image.licenses="MIT"

USER ${USERNAME}
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
