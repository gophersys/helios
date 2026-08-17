# syntax=docker/dockerfile:1.7
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
# every consuming project reaches for. Child images (flutter, zephyr) add
# domain-specific toolchains on top.
#
# Conventions enforced by this Dockerfile:
#   - Every tool version is an ARG at the top with a "latest LTS as of" comment.
#   - No hardcoded versions in RUN statements — always reference an ARG.
#   - Architecture-aware: every binary install resolves ARCH from TARGETPLATFORM.
#   - oh-my-zsh is the default shell; SHELL switches to zsh after install so
#     later RUN layers run under zsh.
#   - Non-root `dev` user (uid 1000). The ubuntu 24.04 default `ubuntu` user
#     at uid 1000 is removed first.

# The base OS at a DIGEST, never at the moving tag: the commit decides the
# image. This ARG is declared above the FROM because a FROM can interpolate only
# an ARG declared before it — below it the expansion is empty, the FROM becomes
# `ubuntu:24.04@`, and the build dies in the publish job. versions.env holds the
# same value for the cloud family, and `bash ./ctl.sh base-currency` reports the
# night upstream moves it. It is the INDEX digest, so buildx still chooses the
# manifest for the platform it builds.
ARG UBUNTU_BASE_REF=sha256:561618e2c15bf2397621dd04f96926663a3b5616c189cf7e38db7e82f5c538ea   # ubuntu:24.04 index digest as of 2026-08-16

# No --platform here. It pinned the userland to the BUILD host's architecture
# while buildx labelled the result with the TARGET platform, which is how the
# published linux/arm64 image came to be an amd64 Ubuntu userland carrying
# aarch64 Go binaries. Plain FROM makes the userland follow the target.
FROM ubuntu:24.04@${UBUNTU_BASE_REF}

# Buildx-injected platform var. Declared so RUN layers can branch on arch.
ARG TARGETPLATFORM

# -------------------------------------------------------------------------
# Tool versions — all pinned ARGs. Every value below is the latest LTS or
# latest stable release as of 2026-04-19. Bump a value by editing the ARG;
# never hardcode a version in a RUN line.
# -------------------------------------------------------------------------

# Shell — zsh via apt, oh-my-zsh via the official installer URL.
ARG ZSH_VERSION=5.9                                                    # latest LTS as of 2026-04-19
ARG OH_MY_ZSH_INSTALL_URL=https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh

# Node toolchain — nvm installs the pinned Node LTS, corepack enables yarn and pnpm.
#
# The nvm digest covers the INSTALLER SCRIPT only. node itself is fetched by that
# script, and node's own download is out of scope of this change. _NOARCH says the
# 1 asset serves every platform.
ARG NVM_VERSION=0.40.4                                                 # latest LTS as of 2026-04-19
ARG NVM_SHA256_NOARCH=4b7412c49960c7d31e8df72da90c1fb5b8cccb419ac99537b737028d497aba4f  # computed-at-pin: 2026-08-17
ARG NODE_VERSION=24.15.0                                               # latest LTS as of 2026-04-19 (Krypton)
ARG NPM_VERSION=11.19.0                                                # latest LTS as of 2026-08-17
ARG PNPM_VERSION=11.22.0                                               # what corepack pnpm@latest resolved on 2026-08-16

# Bun — the JavaScript runtime the Oh My Pi (`omp`) harness requires (its CLI shebang is
# `#!/usr/bin/env bun`, engines.bun >= 1.3.14). Baked into the base image because spawned
# agent pods dogfood this same image family and must run `omp` without a network install.
ARG BUN_VERSION=1.3.14                                                 # latest stable as of 2026-06-13
ARG BUN_SHA256_AMD64=951ee2aee855f08595aeec6225226a298d3fea83a3dcd6465c09cbccdf7e848f  # upstream-published: https://github.com/oven-sh/bun/releases/download/bun-v1.3.14/SHASUMS256.txt

# Python — apt-provided 3.12 + uv for user-space package mgmt.
#
# The uv digest covers the INSTALLER SCRIPT only, for the reason the nvm row gives:
# the uv binary is fetched by that script.
ARG PYTHON_PACKAGE=python3.12                                          # latest LTS as of 2026-04-19
ARG UV_VERSION=0.11.7                                                  # latest LTS as of 2026-04-19
ARG UV_SHA256_NOARCH=efed99618cb5c31e4e36a700ab7c3698e83c0ae0f3c336714043d0f932c8d32c  # computed-at-pin: 2026-08-17

# Go — official tarball. Matches the workspace `go.work` toolchain directive so the agent-pod
# image bakes it rather than auto-downloading the toolchain on first `go` invocation per pod.
ARG GO_VERSION=1.26.5                                                  # latest LTS as of 2026-08-12
ARG GO_SHA256_AMD64=5c2c3b16caefa1d968a94c1daca04a7ca301a496d9b086e17ad77bb81393f053  # upstream-published: https://go.dev/dl/?mode=json&include=all

# Rust — rustup channel, not a pinned version.
ARG RUST_CHANNEL=stable                                                # latest LTS as of 2026-04-19

# Infra CLIs.
#
# Every binary download here is compared against the digest declared beside its
# version. The 2 lines move together: a version bump whose digest is not bumped
# with it FAILS at that RUN line, naming the pin.
ARG KUBECTL_VERSION=1.35.4                                             # latest LTS as of 2026-04-19
ARG KUBECTL_SHA256_AMD64=b529430df69a688fd61b64ad2299edb5fd71cb58be2a4779dba624c7d3510efd  # upstream-published: https://dl.k8s.io/release/v1.35.4/bin/linux/amd64/kubectl.sha256
ARG HELM_VERSION=4.1.4                                                 # latest LTS as of 2026-04-19
ARG HELM_SHA256_AMD64=70b2c30a19da4db264dfd68c8a3664e05093a361cefd89572ffb36f8abfa3d09  # upstream-published: https://get.helm.sh/helm-v4.1.4-linux-amd64.tar.gz.sha256sum
ARG ANSIBLE_VERSION=13.5.0                                             # latest LTS as of 2026-04-19
ARG ANSIBLE_CORE_VERSION=2.20.4                                        # latest LTS as of 2026-04-20
ARG TAILSCALE_VERSION=1.96.4                                           # latest LTS as of 2026-04-19
ARG TAILSCALE_SHA256_AMD64=a1cba18826b1f91cb25ef7f5b8259b5258339b42db7867af9269e21829ea78cc  # upstream-published: https://pkgs.tailscale.com/stable/tailscale_1.96.4_amd64.tgz.sha256
ARG BW_VERSION=2026.3.0                                                # latest LTS as of 2026-04-19
ARG BW_SHA256_AMD64=640d928bef91b2b81aa021777995230681204f5582315ef943ba72db2cbd283d  # computed-at-pin: 2026-08-17
ARG GH_VERSION=2.90.0                                                  # latest LTS as of 2026-04-19
ARG GH_SHA256_AMD64=b2aef7b23ec6899bf27f37a32c57a7935d0a178568ac33dc9bb03842f724195a  # upstream-published: https://github.com/cli/cli/releases/download/v2.90.0/gh_2.90.0_checksums.txt
ARG K9S_VERSION=0.51.0                                                 # latest LTS as of 2026-08-17
ARG K9S_SHA256_AMD64=c3752ad51a5a4015a113819c4eeb6e55a4d0e4b8e652494797532f6fc8161dd7  # upstream-published: https://github.com/derailed/k9s/releases/download/v0.51.0/checksums.sha256
ARG NATS_VERSION=0.3.2                                                 # latest LTS as of 2026-04-19
ARG NATS_SHA256_AMD64=be942b5c3815d572b0836b1656e6c27e6306cf5633e439fbba8dd19c77288ba7  # computed-at-pin: 2026-08-17
ARG OCI_CLI_VERSION=3.79.0                                             # latest LTS as of 2026-04-20

# The 2 docker cli-plugins. They arrive as release binaries and not as apt
# packages, so nothing but the digest says the bytes are the ones upstream
# published. This pair carried the only 2 verified downloads in the repository
# before this change; the vocabulary moved from the asset spelling
# (_X86_64/_AARCH64) to the PLATFORM spelling, value unchanged, so that 1
# vocabulary covers all 26 digests. The _ARM64 and _AARCH64 rows went with the
# `linux/arm64)` case arms they fed — SANCTIONED_PLATFORMS is linux/amd64 alone,
# and a digest nothing compares is a check that cannot fail. F3 restores the arm
# and the row together.
ARG DOCKER_COMPOSE_VERSION=5.1.3                                       # latest LTS as of 2026-04-19
ARG DOCKER_COMPOSE_SHA256_AMD64=a0298760c9772d2c06888fc8703a487c94c3c3b0134adeef830742a2fc7647b4  # upstream-published: https://github.com/docker/compose/releases/download/v5.1.3/checksums.txt
ARG DOCKER_BUILDX_VERSION=0.36.1                                       # latest stable as of 2026-08-13
ARG DOCKER_BUILDX_SHA256_AMD64=48af8a397ebd60178778bf63611dbcebe5f5e7a9be90eb9147b24b9587455778  # upstream-published: https://github.com/docker/buildx/releases/download/v0.36.1/checksums.txt

# Dev QA.
ARG HADOLINT_VERSION=2.14.0                                            # latest LTS as of 2026-04-19
ARG HADOLINT_SHA256_AMD64=6bf226944684f56c84dd014e8b979d27425c0148f61b3bd99bcc6f39e9dc5a47  # upstream-published: https://github.com/hadolint/hadolint/releases/download/v2.14.0/hadolint-linux-x86_64.sha256
ARG KUBECONFORM_VERSION=0.8.0                                          # latest release as of 2026-08-10
ARG KUBECONFORM_SHA256_AMD64=9bc2bffbf71f261128533edaf912153948b7ff238f9a531ae6d34466ec287883  # upstream-published: https://github.com/yannh/kubeconform/releases/download/v0.8.0/CHECKSUMS

# Local Kubernetes substrates for the ADR-0020 host-leveraging integration/load lanes.
ARG K3D_VERSION=5.9.0                                                  # latest LTS as of 2026-06-13
ARG K3D_SHA256_AMD64=06d8f25bc3a971c4eb29e0ff08429b180402db0f4dec838c9eac427e296800a0  # computed-at-pin: 2026-08-17
ARG KIND_VERSION=0.32.0                                                # latest LTS as of 2026-06-13
ARG KIND_SHA256_AMD64=50030de23cf40a18505f20426f6a8506bedf13c6e509244bd1fa9463721b0f54  # upstream-published: https://github.com/kubernetes-sigs/kind/releases/download/v0.32.0/kind-linux-amd64.sha256sum

# Go gate tools (ADR-0018 + ADR-0020), installed via `go install ...@vX.Y.Z`. Pinned by ARG so
# the no-hardcoded-version-in-RUN rule holds and a bump is a one-line edit. These make every
# gate dimension runnable inside the image, so an absent tool is impossible (FAIL-NOT-SKIP).
ARG GOFUMPT_VERSION=0.10.0                                             # latest LTS as of 2026-06-13
ARG GOLANGCI_LINT_VERSION=2.12.2                                       # latest LTS as of 2026-06-13
ARG GOVULNCHECK_VERSION=1.1.4                                          # latest LTS as of 2026-06-13
ARG GOSEC_VERSION=2.28.0                                               # latest LTS as of 2026-08-17
ARG HNSLINT_VERSION=0.1.0                                              # latest as of 2026-08-11 — gophersys/hnslint
ARG GREMLINS_VERSION=0.6.0                                             # latest LTS as of 2026-06-13 — needs >=0.6.0 for unleash --exclude-files (the mutate gate uses it)
# golang.org/x/perf has no semver tags; @latest is the canonical install form (no version digits,
# so it does not trip the no-hardcoded-version-in-RUN grep) — refreshed when the toolchain bumps.
ARG BENCHSTAT_REF=latest                                               # x/perf is untagged; track @latest
ARG GITLEAKS_VERSION=8.30.1                                            # latest LTS as of 2026-06-13
ARG GITLEAKS_SHA256_AMD64=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  # upstream-published: https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt

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
# The verified fetcher, above every download layer that uses it. flutter,
# zephyr, zephyr-devbox and base-runner inherit it through their FROM and add
# no COPY of their own — the body of a verb lives 1 time, and this is that
# rule applied to the fetch-and-compare body.
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
# ecosystem; installed under /home/dev/.local/bin to stay out of /usr.
ARG YQ_VERSION=4.53.3                                                  # latest LTS as of 2026-08-17
ARG YQ_SHA256_AMD64=fa52a4e758c63d38299163fbdd1edfb4c4963247918bf9c1c5d31d84789eded4  # upstream-published: https://github.com/mikefarah/yq/releases/download/v4.53.3/checksums
RUN mkdir -p "/home/${USERNAME}/.local/bin" \
 && case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${ARCH}" \
      "/home/${USERNAME}/.local/bin/yq" \
      "${YQ_SHA256_AMD64}" YQ_SHA256_AMD64 \
 && chmod +x "/home/${USERNAME}/.local/bin/yq"
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
 && "/home/${USERNAME}/.local/bin/uv" --version

# Go — official tarball, TARGETPLATFORM-aware. Installed under /home/dev/go
# so /usr is not touched.
ENV GOROOT=/home/${USERNAME}/go-sdk \
    GOPATH=/home/${USERNAME}/go \
    PATH=/home/${USERNAME}/go-sdk/bin:/home/${USERNAME}/go/bin:/home/${USERNAME}/.local/bin:${PATH}
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p "${GOROOT}" "${GOPATH}/bin" \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" /tmp/go.tgz \
      "${GO_SHA256_AMD64}" GO_SHA256_AMD64 \
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
 && rm -rf "${GOPATH}/pkg/mod" "/home/${USERNAME}/.cache/go-build"
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
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" /usr/local/bin/kubectl \
      "${KUBECTL_SHA256_AMD64}" KUBECTL_SHA256_AMD64 \
 && chmod +x /usr/local/bin/kubectl
# NOTE: no kubectl version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" /tmp/helm.tgz \
      "${HELM_SHA256_AMD64}" HELM_SHA256_AMD64 \
 && tar -C /tmp -xzf /tmp/helm.tgz \
 && mv "/tmp/linux-${ARCH}/helm" /usr/local/bin/helm \
 && rm -rf /tmp/helm.tgz "/tmp/linux-${ARCH}"
# NOTE: no helm version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/derailed/k9s/releases/download/v${K9S_VERSION}/k9s_Linux_${ARCH}.tar.gz" /tmp/k9s.tgz \
      "${K9S_SHA256_AMD64}" K9S_SHA256_AMD64 \
 && tar -C /tmp -xzf /tmp/k9s.tgz k9s \
 && mv /tmp/k9s /usr/local/bin/k9s \
 && rm /tmp/k9s.tgz
# NOTE: no k9s version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# k3d — the default local Kubernetes substrate for the ADR-0020 integration/load lanes
# (k3s-in-docker; single static binary, TARGETPLATFORM-aware).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/k3d-io/k3d/releases/download/v${K3D_VERSION}/k3d-linux-${ARCH}" /usr/local/bin/k3d \
      "${K3D_SHA256_AMD64}" K3D_SHA256_AMD64 \
 && chmod +x /usr/local/bin/k3d
# NOTE: no k3d version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# kind — the second Kubernetes substrate target (Kubernetes-in-docker; static binary).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/kubernetes-sigs/kind/releases/download/v${KIND_VERSION}/kind-linux-${ARCH}" /usr/local/bin/kind \
      "${KIND_SHA256_AMD64}" KIND_SHA256_AMD64 \
 && chmod +x /usr/local/bin/kind
# NOTE: no kind version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# gitleaks — the secret-scan tool for the ADR-0020 security dimension (single binary release).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${ARCH}.tar.gz" /tmp/gitleaks.tgz \
      "${GITLEAKS_SHA256_AMD64}" GITLEAKS_SHA256_AMD64 \
 && tar -C /tmp -xzf /tmp/gitleaks.tgz gitleaks \
 && mv /tmp/gitleaks /usr/local/bin/gitleaks \
 && rm /tmp/gitleaks.tgz
# NOTE: no gitleaks version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" /tmp/gh.tgz \
      "${GH_SHA256_AMD64}" GH_SHA256_AMD64 \
 && tar -C /tmp -xzf /tmp/gh.tgz \
 && mv "/tmp/gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh \
 && rm -rf /tmp/gh.tgz "/tmp/gh_${GH_VERSION}_linux_${ARCH}"
# NOTE: no gh --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Tailscale — the static binary bundle is TARGETPLATFORM-aware.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://pkgs.tailscale.com/stable/tailscale_${TAILSCALE_VERSION}_${ARCH}.tgz" /tmp/ts.tgz \
      "${TAILSCALE_SHA256_AMD64}" TAILSCALE_SHA256_AMD64 \
 && tar -C /tmp -xzf /tmp/ts.tgz \
 && mv "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}/tailscale" /usr/local/bin/tailscale \
 && mv "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}/tailscaled" /usr/local/bin/tailscaled \
 && rm -rf /tmp/ts.tgz "/tmp/tailscale_${TAILSCALE_VERSION}_${ARCH}"
# NOTE: no tailscale version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Bitwarden CLI — native binary zip (no Node runtime required). amd64 has
# no arch suffix in the upstream asset name.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) BW_ASSET="bw-oss-linux-${BW_VERSION}.zip" ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/bitwarden/clients/releases/download/cli-v${BW_VERSION}/${BW_ASSET}" /tmp/bw.zip \
      "${BW_SHA256_AMD64}" BW_SHA256_AMD64 \
 && unzip -q /tmp/bw.zip -d /usr/local/bin \
 && chmod +x /usr/local/bin/bw \
 && rm /tmp/bw.zip
# NOTE: no bw --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# hadolint — single binary. Asset names switched to lowercase "linux" between
# 2.12 and 2.14.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) HADOLINT_ASSET="hadolint-linux-x86_64" ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/${HADOLINT_ASSET}" \
      /usr/local/bin/hadolint \
      "${HADOLINT_SHA256_AMD64}" HADOLINT_SHA256_AMD64 \
 && chmod +x /usr/local/bin/hadolint
# NOTE: no hadolint --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# kubeconform — Kubernetes manifest schema validation. Single binary tarball,
# TARGETPLATFORM-aware. Needed by every repo that validates manifests in CI;
# baking it here is what lets those jobs drop their no-sudo download step.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-${ARCH}.tar.gz" \
      /tmp/kubeconform.tar.gz \
      "${KUBECONFORM_SHA256_AMD64}" KUBECONFORM_SHA256_AMD64 \
 && tar -xzf /tmp/kubeconform.tar.gz -C /usr/local/bin kubeconform \
 && chmod +x /usr/local/bin/kubeconform \
 && rm -f /tmp/kubeconform.tar.gz
# NOTE: no kubeconform -v smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# NATS CLI — single binary zip, TARGETPLATFORM-aware.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/nats-io/natscli/releases/download/v${NATS_VERSION}/nats-${NATS_VERSION}-linux-${ARCH}.zip" /tmp/nats.zip \
      "${NATS_SHA256_AMD64}" NATS_SHA256_AMD64 \
 && unzip -q /tmp/nats.zip -d /tmp/nats \
 && mv "/tmp/nats/nats-${NATS_VERSION}-linux-${ARCH}/nats" /usr/local/bin/nats \
 && rm -rf /tmp/nats /tmp/nats.zip
# NOTE: no nats --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# Bun — JavaScript runtime for the Oh My Pi (`omp`) harness. Single static binary zip.
# Installed to /usr/local/bin so it is on PATH for every shell and user (the dev user's
# npm-global `omp` shebang resolves `bun` here).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-${ARCH}.zip" /tmp/bun.zip \
      "${BUN_SHA256_AMD64}" BUN_SHA256_AMD64 \
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
      linux/amd64) ARCH=x86_64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
      /usr/local/lib/docker/cli-plugins/docker-compose \
      "${DOCKER_COMPOSE_SHA256_AMD64}" DOCKER_COMPOSE_SHA256_AMD64 \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
# NOTE: no docker compose version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

# docker buildx plugin, fetched as a release binary for the same reason compose
# is: the apt package version is whatever the repo holds at build time, and the
# pin has to be the ARG. The runner image is the CLIENT of the remote arm64
# builder — a job dials the builder over SSH and drives `docker buildx build`
# from inside this image — so the plugin belongs here and not in the job.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/docker/buildx/releases/download/v${DOCKER_BUILDX_VERSION}/buildx-v${DOCKER_BUILDX_VERSION}.linux-${ARCH}" \
      /usr/local/lib/docker/cli-plugins/docker-buildx \
      "${DOCKER_BUILDX_SHA256_AMD64}" DOCKER_BUILDX_SHA256_AMD64 \
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
RUN "/home/${USERNAME}/.local/bin/uv" tool install --python "${PYTHON_PACKAGE}" \
      --with "ansible==${ANSIBLE_VERSION}" \
      "ansible-core==${ANSIBLE_CORE_VERSION}" \
 && "/home/${USERNAME}/.local/bin/uv" tool install --python "${PYTHON_PACKAGE}" "oci-cli==${OCI_CLI_VERSION}" \
 && "/home/${USERNAME}/.local/bin/uv" cache clean \
 && rm -rf "/home/${USERNAME}/.cache/uv"
# NOTE: no ansible/oci --version smoke here — fails under QEMU cross-arch build; verify in post-build smoke test

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
