# NOTE: no `# syntax=` directive, deliberately. It made every cold builder
# pull the dockerfile frontend from docker.io — the LAST Docker Hub
# dependency on the build path, and a 502 from auth.docker.io killed a
# build through it (run 2026-08-18). The builder's own built-in frontend
# (BuildKit v0.32) supersedes dockerfile:1.7, and no feature here needs
# the external one.
#
# hadolint global ignore=SC1071,DL4006,SC3040
#
# SC1071/DL4006/SC3040 are disabled globally because the SHELL directive
# below switches to /usr/bin/zsh. hadolint's embedded shellcheck only
# supports sh/bash/dash/ksh and warns on every zsh RUN line. The `set -o
# pipefail` semantics hold in zsh as well; the warning is a tooling gap.
#
# base — Ubuntu 24.04 LTS IDP base image.
#
# Single "pick up and work" image for the brain ecosystem: shells, languages
# (Node, Python, Go, Rust), infra CLIs (kubectl/helm/tailscale/gh),
# desktop/Tauri system libs, USB/BLE system libs, and the data/parsing tools
# every consuming project reaches for. Child images (flutter, embedded) add
# domain-specific toolchains on top.
#
# Conventions enforced by this Dockerfile:
#   - ARGs at the top, VALUE-LESS: every version arrives as --build-arg
#     generated from versions.env at the repository root — the ONE home for
#     every pin. The pin gate below fails the build naming any missing one.
#   - No hardcoded versions in RUN statements — always reference an ARG.
#   - Architecture-aware: every binary install resolves ARCH from TARGETPLATFORM.
#   - oh-my-zsh is the default shell; SHELL switches to zsh after install so
#     later RUN layers run under zsh.
#   - Non-root `dev` user (uid 1000). The ubuntu 24.04 default `ubuntu` user
#     at uid 1000 is removed first.

# The base OS at a DIGEST, never at the moving tag: the commit decides the
# image. Value-less like every other pin — the digest arrives as a generated
# --build-arg from versions.env, its ONE home; it used to be spelled here as
# well, and 2 homes for 1 digest is what a test had to hold together. This ARG
# is declared above the FROM because a FROM can interpolate only an ARG declared
# before it — below it the expansion is empty, the FROM becomes `ubuntu:24.04@`,
# and the build dies in the publish job. versions.env carries the INDEX digest,
# so buildx still chooses the manifest for the platform it builds.
ARG UBUNTU_BASE_REF

# No --platform here. It pinned the userland to the BUILD host's architecture
# while buildx labelled the result with the TARGET platform, which is how the
# published linux/arm64 image came to be an amd64 Ubuntu userland carrying
# aarch64 Go binaries. Plain FROM makes the userland follow the target.
FROM ubuntu:24.04@${UBUNTU_BASE_REF}

# Buildx-injected platform var. Declared so RUN layers can branch on arch.
ARG TARGETPLATFORM

# -------------------------------------------------------------------------
# Tool versions — value-less ARGs, fed from versions.env via generated
# --build-arg (versions_env_build_args in _ctl/lib.sh; the CI job generates
# the same list). The "latest LTS as of" comments live in versions.env, next
# to the values they date.
# -------------------------------------------------------------------------

# Shell — zsh via apt, oh-my-zsh via the official installer URL.
ARG ZSH_VERSION
ARG OH_MY_ZSH_INSTALL_URL=https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh

# Node toolchain — nvm installs the pinned Node LTS, corepack enables yarn and pnpm.
#
# The nvm digest covers the INSTALLER SCRIPT only. node itself is fetched by that
# script, and node's own download is out of scope of this change. _NOARCH says the
# 1 asset serves every platform.
ARG NVM_VERSION
ARG NVM_SHA256_NOARCH
ARG NODE_VERSION
ARG NPM_VERSION
ARG PNPM_VERSION

# Bun — the JavaScript runtime the Oh My Pi (`omp`) harness requires (its CLI shebang is
# `#!/usr/bin/env bun`, engines.bun >= 1.3.14). Baked into the base image because spawned
# agent pods dogfood this same image family and must run `omp` without a network install.
ARG BUN_VERSION
ARG BUN_SHA256_AMD64
ARG BUN_SHA256_ARM64

# Python — apt-provided 3.12 + uv for user-space package mgmt.
#
# The uv digest covers the INSTALLER SCRIPT only, for the reason the nvm row gives:
# the uv binary is fetched by that script.
ARG PYTHON_PACKAGE
ARG UV_VERSION
ARG UV_SHA256_NOARCH

# Go — official tarball. Matches the workspace `go.work` toolchain directive so the agent-pod
# image bakes it rather than auto-downloading the toolchain on first `go` invocation per pod.
ARG GO_VERSION
ARG GO_SHA256_AMD64
ARG GO_SHA256_ARM64

# Rust — rustup channel, not a pinned version.
ARG RUST_CHANNEL

# Infra CLIs.
#
# Every binary download here is compared against the digest declared beside its
# version. The 2 rows move together in versions.env: a version bump whose digest
# is not bumped with it FAILS at that RUN line, naming the pin.
ARG KUBECTL_VERSION
ARG KUBECTL_SHA256_AMD64
ARG KUBECTL_SHA256_ARM64
ARG HELM_VERSION
ARG HELM_SHA256_AMD64
ARG HELM_SHA256_ARM64
ARG ANSIBLE_VERSION
ARG ANSIBLE_CORE_VERSION
ARG TAILSCALE_VERSION
ARG TAILSCALE_SHA256_AMD64
ARG TAILSCALE_SHA256_ARM64
ARG BW_VERSION
ARG BW_SHA256_AMD64
ARG BW_SHA256_ARM64
ARG GH_VERSION
ARG GH_SHA256_AMD64
ARG GH_SHA256_ARM64
ARG K9S_VERSION
ARG K9S_SHA256_AMD64
ARG K9S_SHA256_ARM64
ARG NATS_VERSION
ARG NATS_SHA256_AMD64
ARG NATS_SHA256_ARM64
ARG OCI_CLI_VERSION

# The 2 docker cli-plugins. They arrive as release binaries and not as apt
# packages, so nothing but the digest says the bytes are the ones upstream
# published. This pair is why the digest name states the PLATFORM and never the
# upstream asset spelling: linux/amd64 is x86_64 to compose and amd64 to buildx,
# linux/arm64 is aarch64 to compose and arm64 to buildx, so the asset spelling
# gives 2 vocabularies per arch. 1 vocabulary covers every digest here. The arm
# is what carries the asset spelling, and each arm names the row of its own
# platform.
ARG DOCKER_COMPOSE_VERSION
ARG DOCKER_COMPOSE_SHA256_AMD64
ARG DOCKER_COMPOSE_SHA256_ARM64
ARG DOCKER_BUILDX_VERSION
ARG DOCKER_BUILDX_SHA256_AMD64
ARG DOCKER_BUILDX_SHA256_ARM64

# Parsing + QA. yq was declared beside its own RUN block, 240 lines below, and
# it is here now because the pin gate can only check what is declared above it.
ARG YQ_VERSION
ARG YQ_SHA256_AMD64
ARG YQ_SHA256_ARM64
ARG HADOLINT_VERSION
ARG HADOLINT_SHA256_AMD64
ARG HADOLINT_SHA256_ARM64
ARG KUBECONFORM_VERSION
ARG KUBECONFORM_SHA256_AMD64
ARG KUBECONFORM_SHA256_ARM64

# Local Kubernetes substrates for the ADR-0020 host-leveraging integration/load lanes.
ARG K3D_VERSION
ARG K3D_SHA256_AMD64
ARG K3D_SHA256_ARM64
ARG KIND_VERSION
ARG KIND_SHA256_AMD64
ARG KIND_SHA256_ARM64

# Go gate tools (ADR-0018 + ADR-0020), installed via `go install ...@vX.Y.Z`. Pinned by ARG so
# the no-hardcoded-version-in-RUN rule holds and a bump is a one-line edit. These make every
# gate dimension runnable inside the image, so an absent tool is impossible (FAIL-NOT-SKIP).
ARG GOFUMPT_VERSION
ARG GOLANGCI_LINT_VERSION
ARG GOVULNCHECK_VERSION
ARG GOSEC_VERSION
ARG HNSLINT_VERSION
ARG GREMLINS_VERSION
# golang.org/x/perf has no semver tags; @latest is the canonical install form (no version digits,
# so it does not trip the no-hardcoded-version-in-RUN grep) — refreshed when the toolchain bumps.
ARG BENCHSTAT_REF
ARG GITLEAKS_VERSION
ARG GITLEAKS_SHA256_AMD64
ARG GITLEAKS_SHA256_ARM64

# Non-root dev user identity. These 3 are build parameters and not pins: no
# upstream publishes a uid, so they keep their values here.
#
# THE ARG IS READ BY THE PARSER AND NOT BY A SHELL. Every use of ${USERNAME}
# below is an ENV, a USER or a RUN that runs BEFORE the SHELL switches to zsh,
# and that is now a rule the gate holds rather than a habit: zsh auto-sets
# USERNAME to the effective user, so a ${USERNAME} in a RUN under zsh reads the
# layer's uid and never this value. `zsh_username_run_references` in ctl.sh
# fails `validate` naming the file and the line (ledger #105). The 9 RUN uses
# that stood below the switch are the literal `dev` now.
#
# DL3064's secret-name heuristic fires on 'USERNAME'. This is a username
# LITERAL, not a credential.
# hadolint ignore=DL3064
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

# -------------------------------------------------------------------------
# The pin gate. Every version above must have arrived from versions.env; an
# absent pin would otherwise expand to the empty string and surface much
# later as a mangled download URL. FAIL-NOT-SKIP: the build stops HERE and
# the message names the variable.
#
# UBUNTU_BASE_REF is not in the list: the FROM consumes it before this line
# runs, and an absent value fails there with `ubuntu:24.04@`.
# -------------------------------------------------------------------------
RUN : "${ZSH_VERSION:?not in versions.env}" \
 && : "${NVM_VERSION:?not in versions.env}" \
 && : "${NVM_SHA256_NOARCH:?not in versions.env}" \
 && : "${NODE_VERSION:?not in versions.env}" \
 && : "${NPM_VERSION:?not in versions.env}" \
 && : "${PNPM_VERSION:?not in versions.env}" \
 && : "${BUN_VERSION:?not in versions.env}" \
 && : "${BUN_SHA256_AMD64:?not in versions.env}" \
 && : "${BUN_SHA256_ARM64:?not in versions.env}" \
 && : "${PYTHON_PACKAGE:?not in versions.env}" \
 && : "${UV_VERSION:?not in versions.env}" \
 && : "${UV_SHA256_NOARCH:?not in versions.env}" \
 && : "${GO_VERSION:?not in versions.env}" \
 && : "${GO_SHA256_AMD64:?not in versions.env}" \
 && : "${GO_SHA256_ARM64:?not in versions.env}" \
 && : "${RUST_CHANNEL:?not in versions.env}" \
 && : "${KUBECTL_VERSION:?not in versions.env}" \
 && : "${KUBECTL_SHA256_AMD64:?not in versions.env}" \
 && : "${KUBECTL_SHA256_ARM64:?not in versions.env}" \
 && : "${HELM_VERSION:?not in versions.env}" \
 && : "${HELM_SHA256_AMD64:?not in versions.env}" \
 && : "${HELM_SHA256_ARM64:?not in versions.env}" \
 && : "${ANSIBLE_VERSION:?not in versions.env}" \
 && : "${ANSIBLE_CORE_VERSION:?not in versions.env}" \
 && : "${TAILSCALE_VERSION:?not in versions.env}" \
 && : "${TAILSCALE_SHA256_AMD64:?not in versions.env}" \
 && : "${TAILSCALE_SHA256_ARM64:?not in versions.env}" \
 && : "${BW_VERSION:?not in versions.env}" \
 && : "${BW_SHA256_AMD64:?not in versions.env}" \
 && : "${BW_SHA256_ARM64:?not in versions.env}" \
 && : "${GH_VERSION:?not in versions.env}" \
 && : "${GH_SHA256_AMD64:?not in versions.env}" \
 && : "${GH_SHA256_ARM64:?not in versions.env}" \
 && : "${K9S_VERSION:?not in versions.env}" \
 && : "${K9S_SHA256_AMD64:?not in versions.env}" \
 && : "${K9S_SHA256_ARM64:?not in versions.env}" \
 && : "${NATS_VERSION:?not in versions.env}" \
 && : "${NATS_SHA256_AMD64:?not in versions.env}" \
 && : "${NATS_SHA256_ARM64:?not in versions.env}" \
 && : "${OCI_CLI_VERSION:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_VERSION:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_SHA256_AMD64:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_SHA256_ARM64:?not in versions.env}" \
 && : "${DOCKER_BUILDX_VERSION:?not in versions.env}" \
 && : "${DOCKER_BUILDX_SHA256_AMD64:?not in versions.env}" \
 && : "${DOCKER_BUILDX_SHA256_ARM64:?not in versions.env}" \
 && : "${YQ_VERSION:?not in versions.env}" \
 && : "${YQ_SHA256_AMD64:?not in versions.env}" \
 && : "${YQ_SHA256_ARM64:?not in versions.env}" \
 && : "${HADOLINT_VERSION:?not in versions.env}" \
 && : "${HADOLINT_SHA256_AMD64:?not in versions.env}" \
 && : "${HADOLINT_SHA256_ARM64:?not in versions.env}" \
 && : "${KUBECONFORM_VERSION:?not in versions.env}" \
 && : "${KUBECONFORM_SHA256_AMD64:?not in versions.env}" \
 && : "${KUBECONFORM_SHA256_ARM64:?not in versions.env}" \
 && : "${K3D_VERSION:?not in versions.env}" \
 && : "${K3D_SHA256_AMD64:?not in versions.env}" \
 && : "${K3D_SHA256_ARM64:?not in versions.env}" \
 && : "${KIND_VERSION:?not in versions.env}" \
 && : "${KIND_SHA256_AMD64:?not in versions.env}" \
 && : "${KIND_SHA256_ARM64:?not in versions.env}" \
 && : "${GOFUMPT_VERSION:?not in versions.env}" \
 && : "${GOLANGCI_LINT_VERSION:?not in versions.env}" \
 && : "${GOVULNCHECK_VERSION:?not in versions.env}" \
 && : "${GOSEC_VERSION:?not in versions.env}" \
 && : "${HNSLINT_VERSION:?not in versions.env}" \
 && : "${GREMLINS_VERSION:?not in versions.env}" \
 && : "${BENCHSTAT_REF:?not in versions.env}" \
 && : "${GITLEAKS_VERSION:?not in versions.env}" \
 && : "${GITLEAKS_SHA256_AMD64:?not in versions.env}" \
 && : "${GITLEAKS_SHA256_ARM64:?not in versions.env}"

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
# The verified fetcher, above every download layer that uses it. flutter and
# embedded inherit it through their FROM and add no COPY of their own — the
# body of a verb lives 1 time, and this is that rule applied to the
# fetch-and-compare body.
#
# Editing the helper therefore rebuilds this image from here down. It changes
# rarely, and the alternative — a copy per image — is the defect.
#
# The build context is the repository root, not base/. base/ctl.sh and the
# base job of .github/workflows/build-and-push.yml both say so.
# -------------------------------------------------------------------------
COPY _build/ /usr/local/lib/gophersys/

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
# ecosystem; installed under /home/dev/.local/bin to stay out of /usr. Its 2
# ARGs are in the block at the top, with every other pin.
RUN mkdir -p "/home/dev/.local/bin" \
 && case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${YQ_SHA256_AMD64}"; SHA256_PIN=YQ_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${YQ_SHA256_ARM64}"; SHA256_PIN=YQ_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${ARCH}" \
      "/home/dev/.local/bin/yq" \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x "/home/dev/.local/bin/yq"
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# nvm + Node LTS + corepack (yarn, pnpm). The nvm installer inspects $SHELL
# and refuses to run when it sees zsh, so we override $SHELL for this RUN
# and invoke the whole block under bash.
#
# pnpm takes the PIN and not `@latest`: `@latest` made the image content change
# with no diff at all — two builds a day apart baked 11.21.0 and 11.22.0.
ENV NVM_DIR=/home/${USERNAME}/.nvm
RUN unset ZSH_VERSION; SHELL=/bin/bash bash -c "unset ZSH_VERSION; set -euo pipefail; \
      mkdir -p \"\${NVM_DIR}\"; \
      /usr/local/lib/gophersys/fetch-verified.sh \"https://raw.githubusercontent.com/nvm-sh/nvm/v${NVM_VERSION}/install.sh\" /tmp/nvm-install.sh \"${NVM_SHA256_NOARCH}\" NVM_SHA256_NOARCH; \
      PROFILE=/dev/null bash /tmp/nvm-install.sh; \
      rm -f /tmp/nvm-install.sh; \
      . \"\${NVM_DIR}/nvm.sh\"; \
      nvm install \"${NODE_VERSION}\"; \
      nvm alias default \"${NODE_VERSION}\"; \
      npm install -g \"npm@${NPM_VERSION}\"; \
      corepack enable; \
      corepack prepare yarn@stable --activate; \
      corepack prepare pnpm@${PNPM_VERSION} --activate"

# uv — Python package manager. Installed via the official installer to the
# dev user's ~/.local/bin.
RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://astral.sh/uv/${UV_VERSION}/install.sh" /tmp/uv-install.sh \
      "${UV_SHA256_NOARCH}" UV_SHA256_NOARCH \
 && sh /tmp/uv-install.sh \
 && rm -f /tmp/uv-install.sh \
 && "/home/dev/.local/bin/uv" --version

# Go — official tarball, TARGETPLATFORM-aware. Installed under /home/dev/go
# so /usr is not touched.
ENV GOROOT=/home/${USERNAME}/go-sdk \
    GOPATH=/home/${USERNAME}/go \
    PATH=/home/${USERNAME}/go-sdk/bin:/home/${USERNAME}/go/bin:/home/${USERNAME}/.local/bin:${PATH}
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${GO_SHA256_AMD64}"; SHA256_PIN=GO_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${GO_SHA256_ARM64}"; SHA256_PIN=GO_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p "${GOROOT}" "${GOPATH}/bin" \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" /tmp/go.tgz \
      "${SHA256}" "${SHA256_PIN}" \
 && tar -C "${GOROOT}" --strip-components=1 -xzf /tmp/go.tgz \
 && rm /tmp/go.tgz
# NOTE: no go version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Go gate tools (ADR-0018 + ADR-0020). Installed as the dev user into ${GOPATH}/bin so every
# `ctl.sh` gate verb resolves its tool and an absent tool is impossible (FAIL-NOT-SKIP). Pinned
# by ARG (no hardcoded version in the RUN line). GOFLAGS=-mod=mod + GOWORK=off install in
# isolation. golangci-lint v2 is installed from its module so the version matches libs/.golangci.yml.
# CGO_ENABLED=0 is INLINE (not a persistent ENV — the gate's `go test -race` needs CGO): these
# tools are all pure-Go, and disabling cgo skips the gcc/assembler path that fails on the arm64
# QEMU cross-build (`gcc_arm64.S: no such instruction: blr`).
#
# THE CACHE CLEANUP IS PART OF THIS LAYER, and it has to be: a later RUN that
# removed the cache would leave every byte of it in this layer's diff. cloud
# measured the same layer at 2.06 GB, of which ~1.6 GB was the module and build
# cache — the 7 binaries are ~200 MB. `go clean` handles the read-only module
# tree; the rm afterwards mops what remains. The cache also carried the vendored
# gosec rule sources that the nightly scan reads as CRITICAL secret findings
# (rules/hardcoded_credentials.go is a regex, not a credential).
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
 && rm -rf "${GOPATH}/pkg/mod" "/home/dev/.cache/go-build"
# NOTE: no --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test
USER root

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
# terraform is NOT installed here. _delta/components/terraform.sh states it was
# dropped from every image by decision (image-architecture §2.3), and this block
# was the one place that contradicted it — so base, flutter, zephyr,
# zephyr-devbox and base-runner all shipped it and all inherited its CVE. The
# pin stays in versions.env as the ready component; the delta is 1 line away.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${KUBECTL_SHA256_AMD64}"; SHA256_PIN=KUBECTL_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${KUBECTL_SHA256_ARM64}"; SHA256_PIN=KUBECTL_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" /usr/local/bin/kubectl \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/bin/kubectl
# NOTE: no kubectl version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${HELM_SHA256_AMD64}"; SHA256_PIN=HELM_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${HELM_SHA256_ARM64}"; SHA256_PIN=HELM_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" /tmp/helm.tgz \
      "${SHA256}" "${SHA256_PIN}" \
 && tar -C /tmp -xzf /tmp/helm.tgz \
 && mv "/tmp/linux-${ARCH}/helm" /usr/local/bin/helm \
 && rm -rf /tmp/helm.tgz "/tmp/linux-${ARCH}"
# NOTE: no helm version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${K9S_SHA256_AMD64}"; SHA256_PIN=K9S_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${K9S_SHA256_ARM64}"; SHA256_PIN=K9S_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/derailed/k9s/releases/download/v${K9S_VERSION}/k9s_Linux_${ARCH}.tar.gz" /tmp/k9s.tgz \
      "${SHA256}" "${SHA256_PIN}" \
 && tar -C /tmp -xzf /tmp/k9s.tgz k9s \
 && mv /tmp/k9s /usr/local/bin/k9s \
 && rm /tmp/k9s.tgz
# NOTE: no k9s version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# k3d — the default local Kubernetes substrate for the ADR-0020 integration/load lanes
# (k3s-in-docker; single static binary, TARGETPLATFORM-aware).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${K3D_SHA256_AMD64}"; SHA256_PIN=K3D_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${K3D_SHA256_ARM64}"; SHA256_PIN=K3D_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/k3d-io/k3d/releases/download/v${K3D_VERSION}/k3d-linux-${ARCH}" /usr/local/bin/k3d \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/bin/k3d
# NOTE: no k3d version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# kind — the second Kubernetes substrate target (Kubernetes-in-docker; static binary).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${KIND_SHA256_AMD64}"; SHA256_PIN=KIND_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${KIND_SHA256_ARM64}"; SHA256_PIN=KIND_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/kubernetes-sigs/kind/releases/download/v${KIND_VERSION}/kind-linux-${ARCH}" /usr/local/bin/kind \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/bin/kind
# NOTE: no kind version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# gitleaks — the secret-scan tool for the ADR-0020 security dimension (single binary release).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x64; SHA256="${GITLEAKS_SHA256_AMD64}"; SHA256_PIN=GITLEAKS_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${GITLEAKS_SHA256_ARM64}"; SHA256_PIN=GITLEAKS_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${ARCH}.tar.gz" /tmp/gitleaks.tgz \
      "${SHA256}" "${SHA256_PIN}" \
 && tar -C /tmp -xzf /tmp/gitleaks.tgz gitleaks \
 && mv /tmp/gitleaks /usr/local/bin/gitleaks \
 && rm /tmp/gitleaks.tgz
# NOTE: no gitleaks version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${GH_SHA256_AMD64}"; SHA256_PIN=GH_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${GH_SHA256_ARM64}"; SHA256_PIN=GH_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" /tmp/gh.tgz \
      "${SHA256}" "${SHA256_PIN}" \
 && tar -C /tmp -xzf /tmp/gh.tgz \
 && mv "/tmp/gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh \
 && rm -rf /tmp/gh.tgz "/tmp/gh_${GH_VERSION}_linux_${ARCH}"
# NOTE: no gh --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Tailscale — the static binary bundle is TARGETPLATFORM-aware.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${TAILSCALE_SHA256_AMD64}"; SHA256_PIN=TAILSCALE_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${TAILSCALE_SHA256_ARM64}"; SHA256_PIN=TAILSCALE_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://pkgs.tailscale.com/stable/tailscale_${TAILSCALE_VERSION}_${ARCH}.tgz" /tmp/ts.tgz \
      "${SHA256}" "${SHA256_PIN}" \
 && tar -C /tmp -xzf /tmp/ts.tgz \
 && mv "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}/tailscale" /usr/local/bin/tailscale \
 && mv "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}/tailscaled" /usr/local/bin/tailscaled \
 && rm -rf /tmp/ts.tgz "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}"
# NOTE: no tailscale version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Bitwarden CLI — native binary zip (no Node runtime required). amd64 has
# no arch suffix in the upstream asset name; arm64 has "-arm64-".
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) BW_ASSET="bw-oss-linux-${BW_VERSION}.zip"; SHA256="${BW_SHA256_AMD64}"; SHA256_PIN=BW_SHA256_AMD64 ;; \
      linux/arm64) BW_ASSET="bw-oss-linux-arm64-${BW_VERSION}.zip"; SHA256="${BW_SHA256_ARM64}"; SHA256_PIN=BW_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/bitwarden/clients/releases/download/cli-v${BW_VERSION}/${BW_ASSET}" /tmp/bw.zip \
      "${SHA256}" "${SHA256_PIN}" \
 && unzip -q /tmp/bw.zip -d /usr/local/bin \
 && chmod +x /usr/local/bin/bw \
 && rm /tmp/bw.zip
# NOTE: no bw --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# hadolint — single binary. Asset names switched to lowercase "linux" between
# 2.12 and 2.14.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) HADOLINT_ASSET="hadolint-linux-x86_64"; SHA256="${HADOLINT_SHA256_AMD64}"; SHA256_PIN=HADOLINT_SHA256_AMD64 ;; \
      linux/arm64) HADOLINT_ASSET="hadolint-linux-arm64"; SHA256="${HADOLINT_SHA256_ARM64}"; SHA256_PIN=HADOLINT_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/${HADOLINT_ASSET}" \
      /usr/local/bin/hadolint \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/bin/hadolint
# NOTE: no hadolint --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# kubeconform — Kubernetes manifest schema validation. Single binary tarball,
# TARGETPLATFORM-aware. Needed by every repo that validates manifests in CI;
# baking it here is what lets those jobs drop their no-sudo download step.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${KUBECONFORM_SHA256_AMD64}"; SHA256_PIN=KUBECONFORM_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${KUBECONFORM_SHA256_ARM64}"; SHA256_PIN=KUBECONFORM_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-${ARCH}.tar.gz" \
      /tmp/kubeconform.tar.gz \
      "${SHA256}" "${SHA256_PIN}" \
 && tar -xzf /tmp/kubeconform.tar.gz -C /usr/local/bin kubeconform \
 && chmod +x /usr/local/bin/kubeconform \
 && rm -f /tmp/kubeconform.tar.gz
# NOTE: no kubeconform -v smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# NATS CLI — single binary zip, TARGETPLATFORM-aware.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${NATS_SHA256_AMD64}"; SHA256_PIN=NATS_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${NATS_SHA256_ARM64}"; SHA256_PIN=NATS_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/nats-io/natscli/releases/download/v${NATS_VERSION}/nats-${NATS_VERSION}-linux-${ARCH}.zip" /tmp/nats.zip \
      "${SHA256}" "${SHA256_PIN}" \
 && unzip -q /tmp/nats.zip -d /tmp/nats \
 && mv "/tmp/nats/nats-${NATS_VERSION}-linux-${ARCH}/nats" /usr/local/bin/nats \
 && rm -rf /tmp/nats /tmp/nats.zip
# NOTE: no nats --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Bun — JavaScript runtime for the Oh My Pi (`omp`) harness. Single static binary zip.
# Installed to /usr/local/bin so it is on PATH for every shell and user (the dev user's
# npm-global `omp` shebang resolves `bun` here).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x64; SHA256="${BUN_SHA256_AMD64}"; SHA256_PIN=BUN_SHA256_AMD64 ;; \
      linux/arm64) ARCH=aarch64; SHA256="${BUN_SHA256_ARM64}"; SHA256_PIN=BUN_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-${ARCH}.zip" /tmp/bun.zip \
      "${SHA256}" "${SHA256_PIN}" \
 && unzip -q /tmp/bun.zip -d /tmp/bun \
 && mv "/tmp/bun/bun-linux-${ARCH}/bun" /usr/local/bin/bun \
 && chmod +x /usr/local/bin/bun \
 && rm -rf /tmp/bun /tmp/bun.zip
# NOTE: no bun --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

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
      linux/amd64) ARCH=x86_64; SHA256="${DOCKER_COMPOSE_SHA256_AMD64}"; SHA256_PIN=DOCKER_COMPOSE_SHA256_AMD64 ;; \
      linux/arm64) ARCH=aarch64; SHA256="${DOCKER_COMPOSE_SHA256_ARM64}"; SHA256_PIN=DOCKER_COMPOSE_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
      /usr/local/lib/docker/cli-plugins/docker-compose \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
# NOTE: no docker compose version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# docker buildx plugin, fetched as a release binary for the same reason compose
# is: the apt package version is whatever the repo holds at build time, and the
# pin has to be the ARG. The runner image is the CLIENT of the remote arm64
# builder — a job dials the builder over SSH and drives `docker buildx build`
# from inside this image — so the plugin belongs here and not in the job.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${DOCKER_BUILDX_SHA256_AMD64}"; SHA256_PIN=DOCKER_BUILDX_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${DOCKER_BUILDX_SHA256_ARM64}"; SHA256_PIN=DOCKER_BUILDX_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/docker/buildx/releases/download/v${DOCKER_BUILDX_VERSION}/buildx-v${DOCKER_BUILDX_VERSION}.linux-${ARCH}" \
      /usr/local/lib/docker/cli-plugins/docker-buildx \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
# NOTE: no docker buildx version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# The AWS CLI is NOT installed here. _delta/components/aws.sh states it was
# dropped from every image by decision (image-architecture §2.3 — only
# arm-builder EC2 operations touched AWS, and arm-builder is decommissioned),
# and versions.env files AWS_CLI_VERSION under "ready components, consumed by NO
# image today". This block was the one place that contradicted both, exactly as
# the terraform block did. The pin stays in versions.env as the ready component;
# the delta is 1 line away.

# Python-tool installs via uv tool into the dev user's home: ansible-core
# (engine — provides ansible/ansible-playbook/ansible-galaxy shims) bundled
# with the `ansible` metapackage (community collections) in the same venv,
# plus oci-cli (OCI control plane) as its own tool. All arch-neutral (pure
# Python). The ansible-core-as-primary pattern is required because the
# `ansible` metapackage only ships an `ansible-community` info script; the
# real engine entry points come from ansible-core.
#
# The uv cache is emptied IN THIS LAYER, for the reason the Go gate layer gives:
# a later rm leaves every byte of it in this diff. The tools are already
# unpacked into their venvs, so the cache is a second copy of what stays. The
# nightly scan's secret finding lives in the INSTALLED venv copy of an ansible
# docs sample (community/aws sts_session_token.py) — waived, path-scoped and
# expiring, in .ci/trivyignore.yaml. This cleanup removes only the cached
# duplicate of that same file.
USER ${USERNAME}
# hadolint ignore=DL3013
RUN "/home/dev/.local/bin/uv" tool install --python "${PYTHON_PACKAGE}" \
      --with "ansible==${ANSIBLE_VERSION}" \
      "ansible-core==${ANSIBLE_CORE_VERSION}" \
 && "/home/dev/.local/bin/uv" tool install --python "${PYTHON_PACKAGE}" "oci-cli==${OCI_CLI_VERSION}" \
 && "/home/dev/.local/bin/uv" cache clean \
 && rm -rf "/home/dev/.cache/uv"
# NOTE: no ansible/oci --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Convenience: path shims for zsh so interactive logins see all of the
# installed toolchains without per-user config. Written to /etc/zsh/zshenv
# so every zsh (interactive or not) picks it up.
USER root
# The single quotes are the point: these lines are WRITTEN to a file, and
# $PATH must expand when zsh SOURCES it, never while this layer builds.
# hadolint ignore=SC2016
RUN { \
      echo '# Set by gophersys/base Dockerfile.'; \
      echo 'export PATH=/home/dev/.local/bin:/home/dev/.cargo/bin:/home/dev/go-sdk/bin:/home/dev/go/bin:/usr/local/lib/docker/cli-plugins:${PATH}'; \
      echo 'export GOROOT=/home/dev/go-sdk'; \
      echo 'export GOPATH=/home/dev/go'; \
      echo 'export NVM_DIR=/home/dev/.nvm'; \
      echo '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"'; \
    } >> /etc/zsh/zshenv

# Node on PATH for every user and every shell.
#
# nvm installs node under the dev user's home and is sourced only from
# /etc/zsh/zshenv, so `node` resolved in an interactive zsh and nowhere else: not
# in bash, and not for root. An earlier attempt symlinked into /usr/local/bin and
# verified itself with `node --version` in the SAME zsh that already had nvm
# sourced, so the check passed while creating nothing.
#
# ENV PATH applies to every process in the image whatever its shell or user, so
# there is nothing to source and nothing to verify in a shell that lies.
ENV PATH="/home/${USERNAME}/.nvm/versions/node/v${NODE_VERSION}/bin:${PATH}"

# -------------------------------------------------------------------------
# Final image identity.
# -------------------------------------------------------------------------
LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys IDP base: Ubuntu 24.04 + shells/langs/infra/desktop/USB-BLE toolchain"
LABEL org.opencontainers.image.licenses="MIT"

USER ${USERNAME}
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
