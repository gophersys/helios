# NOTE: no `# syntax=` directive, deliberately. It made every cold builder
# pull the dockerfile frontend from docker.io — the LAST Docker Hub
# dependency on the build path, and a 502 from auth.docker.io killed a
# build through it (run 2026-08-18). The builder's own built-in frontend
# (BuildKit v0.32) supersedes dockerfile:1.7, and no feature here needs
# the external one.
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

# The base OS at a DIGEST, never at the moving tag: the commit decides the
# image. Value-less like every other pin of this family — the digest arrives as
# a generated --build-arg from versions.env, the ONE home. It is declared above
# the FROM because a FROM can interpolate only an ARG declared before it.
ARG UBUNTU_BASE_REF

# No --platform here: it pinned the userland to the BUILD host while buildx
# labelled the result with the TARGET, which is how a mislabelled arm64 image
# was published once. Plain FROM makes the userland follow the target.
FROM ubuntu:24.04@${UBUNTU_BASE_REF}

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
ARG NVM_SHA256_NOARCH
ARG NODE_VERSION
ARG NPM_VERSION
ARG PNPM_VERSION
ARG BUN_VERSION
ARG BUN_SHA256_AMD64
ARG BUN_SHA256_ARM64

# Python.
ARG PYTHON_PACKAGE
ARG UV_VERSION
ARG UV_SHA256_NOARCH

# Go + gate tools (ADR-0018 + ADR-0020).
ARG GO_VERSION
ARG GO_SHA256_AMD64
ARG GO_SHA256_ARM64
ARG GOFUMPT_VERSION
ARG GOLANGCI_LINT_VERSION
ARG GOVULNCHECK_VERSION
ARG GOSEC_VERSION
ARG HNSLINT_VERSION
ARG GREMLINS_VERSION
ARG BENCHSTAT_REF
# sqlc generates eden's persistence layer; its `verify` verb re-generates and
# diffs, so an image without it turns that drift check into a 127 (blueprint P0-4).
# The ARC pools run THIS image, so it is the copy that puts the check in a lane.
ARG SQLC_VERSION
ARG DELVE_VERSION

# Parsing + QA.
# The shell linter comes from the archive, so it has a version row and no digest
# row — apt answers for its own bytes. It governs `ctl.sh validate` as well as
# the image: the verb refuses to lint at any other version (ledger #117).
ARG SHELLCHECK_VERSION
ARG YQ_VERSION
ARG YQ_SHA256_AMD64
ARG YQ_SHA256_ARM64
ARG HADOLINT_VERSION
ARG HADOLINT_SHA256_AMD64
ARG HADOLINT_SHA256_ARM64
ARG KUBECONFORM_VERSION
ARG KUBECONFORM_SHA256_AMD64
ARG KUBECONFORM_SHA256_ARM64
ARG GITLEAKS_VERSION
ARG GITLEAKS_SHA256_AMD64
ARG GITLEAKS_SHA256_ARM64

# Infra CLIs.
ARG KUBECTL_VERSION
ARG KUBECTL_SHA256_AMD64
ARG KUBECTL_SHA256_ARM64
ARG HELM_VERSION
ARG HELM_SHA256_AMD64
ARG HELM_SHA256_ARM64
ARG K9S_VERSION
ARG K9S_SHA256_AMD64
ARG K9S_SHA256_ARM64
ARG K3D_VERSION
ARG K3D_SHA256_AMD64
ARG K3D_SHA256_ARM64
ARG KIND_VERSION
ARG KIND_SHA256_AMD64
ARG KIND_SHA256_ARM64
ARG TAILSCALE_VERSION
ARG TAILSCALE_SHA256_AMD64
ARG TAILSCALE_SHA256_ARM64
ARG BW_VERSION
ARG BW_SHA256_AMD64
ARG BW_SHA256_ARM64
ARG GH_VERSION
ARG GH_SHA256_AMD64
ARG GH_SHA256_ARM64
ARG NATS_VERSION
ARG NATS_SHA256_AMD64
ARG NATS_SHA256_ARM64

# Docker cli-plugins (version + release-asset digest).
ARG DOCKER_COMPOSE_VERSION
ARG DOCKER_COMPOSE_SHA256_AMD64
ARG DOCKER_COMPOSE_SHA256_ARM64
ARG DOCKER_BUILDX_VERSION
ARG DOCKER_BUILDX_SHA256_AMD64
ARG DOCKER_BUILDX_SHA256_ARM64

# Protocols.
ARG BUF_VERSION
ARG BUF_SHA256_AMD64
ARG BUF_SHA256_ARM64
ARG GRPCURL_VERSION
ARG GRPCURL_SHA256_AMD64
ARG GRPCURL_SHA256_ARM64

# The CI fold.
ARG RUNNER_VERSION
ARG RUNNER_SHA256_AMD64
ARG RUNNER_SHA256_ARM64
ARG CICTL_VERSION
ARG CLAUDE_CODE_VERSION
ARG OMP_VERSION
ARG CODEX_VERSION

# Non-root dev user identity.
# THE ARG IS READ BY THE PARSER AND NOT BY A SHELL. Every use of ${USERNAME}
# below is an ENV, a USER or a RUN that runs BEFORE the SHELL switches to zsh,
# and that is now a rule the gate holds rather than a habit: zsh auto-sets
# USERNAME to the effective user, so a ${USERNAME} in a RUN under zsh reads the
# layer's uid and never this value. `zsh_username_run_references` in ctl.sh
# fails `validate` naming the file and the line (ledger #105). The 5 RUN uses
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
 && : "${GOFUMPT_VERSION:?not in versions.env}" \
 && : "${GOLANGCI_LINT_VERSION:?not in versions.env}" \
 && : "${GOVULNCHECK_VERSION:?not in versions.env}" \
 && : "${GOSEC_VERSION:?not in versions.env}" \
 && : "${HNSLINT_VERSION:?not in versions.env}" \
 && : "${GREMLINS_VERSION:?not in versions.env}" \
 && : "${BENCHSTAT_REF:?not in versions.env}" \
 && : "${SQLC_VERSION:?not in versions.env}" \
 && : "${DELVE_VERSION:?not in versions.env}" \
 && : "${YQ_VERSION:?not in versions.env}" \
 && : "${YQ_SHA256_AMD64:?not in versions.env}" \
 && : "${YQ_SHA256_ARM64:?not in versions.env}" \
 && : "${SHELLCHECK_VERSION:?not in versions.env}" \
 && : "${HADOLINT_VERSION:?not in versions.env}" \
 && : "${HADOLINT_SHA256_AMD64:?not in versions.env}" \
 && : "${HADOLINT_SHA256_ARM64:?not in versions.env}" \
 && : "${KUBECONFORM_VERSION:?not in versions.env}" \
 && : "${KUBECONFORM_SHA256_AMD64:?not in versions.env}" \
 && : "${KUBECONFORM_SHA256_ARM64:?not in versions.env}" \
 && : "${GITLEAKS_VERSION:?not in versions.env}" \
 && : "${GITLEAKS_SHA256_AMD64:?not in versions.env}" \
 && : "${GITLEAKS_SHA256_ARM64:?not in versions.env}" \
 && : "${KUBECTL_VERSION:?not in versions.env}" \
 && : "${KUBECTL_SHA256_AMD64:?not in versions.env}" \
 && : "${KUBECTL_SHA256_ARM64:?not in versions.env}" \
 && : "${HELM_VERSION:?not in versions.env}" \
 && : "${HELM_SHA256_AMD64:?not in versions.env}" \
 && : "${HELM_SHA256_ARM64:?not in versions.env}" \
 && : "${K9S_VERSION:?not in versions.env}" \
 && : "${K9S_SHA256_AMD64:?not in versions.env}" \
 && : "${K9S_SHA256_ARM64:?not in versions.env}" \
 && : "${K3D_VERSION:?not in versions.env}" \
 && : "${K3D_SHA256_AMD64:?not in versions.env}" \
 && : "${K3D_SHA256_ARM64:?not in versions.env}" \
 && : "${KIND_VERSION:?not in versions.env}" \
 && : "${KIND_SHA256_AMD64:?not in versions.env}" \
 && : "${KIND_SHA256_ARM64:?not in versions.env}" \
 && : "${TAILSCALE_VERSION:?not in versions.env}" \
 && : "${TAILSCALE_SHA256_AMD64:?not in versions.env}" \
 && : "${TAILSCALE_SHA256_ARM64:?not in versions.env}" \
 && : "${BW_VERSION:?not in versions.env}" \
 && : "${BW_SHA256_AMD64:?not in versions.env}" \
 && : "${BW_SHA256_ARM64:?not in versions.env}" \
 && : "${GH_VERSION:?not in versions.env}" \
 && : "${GH_SHA256_AMD64:?not in versions.env}" \
 && : "${GH_SHA256_ARM64:?not in versions.env}" \
 && : "${NATS_VERSION:?not in versions.env}" \
 && : "${NATS_SHA256_AMD64:?not in versions.env}" \
 && : "${NATS_SHA256_ARM64:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_VERSION:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_SHA256_AMD64:?not in versions.env}" \
 && : "${DOCKER_COMPOSE_SHA256_ARM64:?not in versions.env}" \
 && : "${DOCKER_BUILDX_VERSION:?not in versions.env}" \
 && : "${DOCKER_BUILDX_SHA256_AMD64:?not in versions.env}" \
 && : "${DOCKER_BUILDX_SHA256_ARM64:?not in versions.env}" \
 && : "${BUF_VERSION:?not in versions.env}" \
 && : "${BUF_SHA256_AMD64:?not in versions.env}" \
 && : "${BUF_SHA256_ARM64:?not in versions.env}" \
 && : "${GRPCURL_VERSION:?not in versions.env}" \
 && : "${GRPCURL_SHA256_AMD64:?not in versions.env}" \
 && : "${GRPCURL_SHA256_ARM64:?not in versions.env}" \
 && : "${RUNNER_VERSION:?not in versions.env}" \
 && : "${RUNNER_SHA256_AMD64:?not in versions.env}" \
 && : "${RUNNER_SHA256_ARM64:?not in versions.env}" \
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
      "shellcheck=${SHELLCHECK_VERSION}*" \
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
# The verified fetcher, above every download layer that uses it. The
# components under /opt/delta reach it at the same absolute path, so a
# component and a RUN line fetch through the same 1 file.
#
# Editing the helper therefore rebuilds this image from here down. It changes
# rarely, and the alternative — a copy per image — is the defect.
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

# yq — multi-arch binary from Mike Farah's releases. Installed under
# /home/dev/.local/bin to stay out of /usr.
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

# nvm + Node LTS + corepack (yarn, pnpm). The nvm installer inspects $SHELL
# and refuses to run when it sees zsh, so we override $SHELL for this RUN
# and invoke the whole block under bash.
#
# The cleanup tail is in-layer cache hygiene (size lever 1, risk R4): the
# nvm download cache (31.2 MB) and the npm cache (30.7 MB) are write-only at
# runtime and a removal in a later layer would save zero bytes. The corepack
# store under ~/.cache/node STAYS: it is where the activated yarn and pnpm
# live, not a cache — and it is what the smoke reads to compare PNPM_VERSION.
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
      corepack prepare pnpm@${PNPM_VERSION} --activate; \
      nvm cache clear; \
      npm cache clean --force; \
      rm -rf \"\${HOME}/.npm\" /tmp/node-compile-cache"

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

# Go gate tools (ADR-0018 + ADR-0020), installed as the dev user into
# ${GOPATH}/bin so every gate verb resolves its tool (FAIL-NOT-SKIP).
# CGO_ENABLED=0 inline: the tools are pure Go, and the gate's `go test -race`
# still gets cgo from build-essential.
#
# THE CACHE CLEANUP IS THE POINT OF THIS LAYER. base/Dockerfile's copy of it
# measured 2.06 GB, of which ~1.6 GB was the module and build cache the RUN
# never removed — the 7 binaries were ~200 MB. `go clean` handles the
# read-only module tree; the rm afterwards mops what remains.
#
# -ldflags="-s -w" is size lever 3 (risk R4): it drops the symbol and DWARF
# tables from the 8 GATE binaries, which nobody debugs — a panic still
# prints its stack trace. dlv is deliberately NOT here and NOT stripped
# (components/delve.sh): the debugger must remain debuggable.
#
# THE 8TH IS sqlc, AND IT IS THE BIGGEST — 53,477,536 bytes stripped, measured
# 2026-08-26 by installing v1.31.1 in ghcr.io/gophersys/base at CGO_ENABLED=0.
# This image's budget has room for it: images.yaml carries 5.75 GB against
# 5,273,882,624 unpacked bytes last measured (run 32202500436), so the addition
# is 11% of the 476 MB of headroom. Re-measure rather than reusing that
# arithmetic the next time a binary is added.
USER ${USERNAME}
RUN CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install -ldflags="-s -w" mvdan.cc/gofumpt@v${GOFUMPT_VERSION} \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install -ldflags="-s -w" "github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v${GOLANGCI_LINT_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install -ldflags="-s -w" "golang.org/x/vuln/cmd/govulncheck@v${GOVULNCHECK_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install -ldflags="-s -w" "github.com/securego/gosec/v2/cmd/gosec@v${GOSEC_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install -ldflags="-s -w" "github.com/go-gremlins/gremlins/cmd/gremlins@v${GREMLINS_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install -ldflags="-s -w" "golang.org/x/perf/cmd/benchstat@${BENCHSTAT_REF}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install -ldflags="-s -w" "github.com/gophersys/hnslint/cmd/hnslint@v${HNSLINT_VERSION}" \
 && CGO_ENABLED=0 GOWORK=off GOFLAGS=-mod=mod GOBIN="${GOPATH}/bin" go install -ldflags="-s -w" "github.com/sqlc-dev/sqlc/cmd/sqlc@v${SQLC_VERSION}" \
 && go clean -modcache \
 && go clean -cache \
 && rm -rf "${GOPATH}/pkg/mod" "/home/dev/.cache/go-build"
USER root

# -------------------------------------------------------------------------
# Infra CLIs. Each is TARGETPLATFORM-aware — base/Dockerfile's blocks,
# copied faithfully. terraform, AWS and ansible/oci are NOT here: dropped by
# decision, their ready components sit in _delta/components/.
# -------------------------------------------------------------------------
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${KUBECTL_SHA256_AMD64}"; SHA256_PIN=KUBECTL_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${KUBECTL_SHA256_ARM64}"; SHA256_PIN=KUBECTL_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" /usr/local/bin/kubectl \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/bin/kubectl

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

# k3d — the default local Kubernetes substrate for the ADR-0020
# integration/load lanes (k3s-in-docker; single static binary).
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${K3D_SHA256_AMD64}"; SHA256_PIN=K3D_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${K3D_SHA256_ARM64}"; SHA256_PIN=K3D_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/k3d-io/k3d/releases/download/v${K3D_VERSION}/k3d-linux-${ARCH}" /usr/local/bin/k3d \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/bin/k3d

# kind — the second Kubernetes substrate target.
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64; SHA256="${KIND_SHA256_AMD64}"; SHA256_PIN=KIND_SHA256_AMD64 ;; \
      linux/arm64) ARCH=arm64; SHA256="${KIND_SHA256_ARM64}"; SHA256_PIN=KIND_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/kubernetes-sigs/kind/releases/download/v${KIND_VERSION}/kind-linux-${ARCH}" /usr/local/bin/kind \
      "${SHA256}" "${SHA256_PIN}" \
 && chmod +x /usr/local/bin/kind

# gitleaks — the secret-scan tool for the ADR-0020 security dimension.
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

# hadolint — single binary; asset names are lowercase "linux" as of 2.14.
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

# kubeconform — Kubernetes manifest schema validation.
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

# Bun — JavaScript runtime for the Oh My Pi (`omp`) harness. Installed to
# /usr/local/bin so it is on PATH for every shell and user.
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

# Convenience: path shims for zsh so interactive logins see all of the
# installed toolchains without per-user config. No cargo path: Rust moved to
# the category deltas that need it.
# The single quotes are the point: these lines are WRITTEN to a file, and
# $PATH must expand when zsh SOURCES it, never while this layer builds.
# hadolint ignore=SC2016
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
RUN K9S_VERSION="${K9S_VERSION}" K9S_SHA256_AMD64="${K9S_SHA256_AMD64}" \
    K9S_SHA256_ARM64="${K9S_SHA256_ARM64}" bash /opt/delta/components/k9s.sh

# Comforts kept by the census: bat, htop, btop, httpie.
RUN bash /opt/delta/components/comforts.sh

# The Go debugger, pinned by DELVE_VERSION.
RUN DELVE_VERSION="${DELVE_VERSION}" bash /opt/delta/components/delve.sh

# buf + grpcurl, pinned by BUF_VERSION / GRPCURL_VERSION.
RUN BUF_VERSION="${BUF_VERSION}" BUF_SHA256_AMD64="${BUF_SHA256_AMD64}" \
    BUF_SHA256_ARM64="${BUF_SHA256_ARM64}" \
    GRPCURL_VERSION="${GRPCURL_VERSION}" GRPCURL_SHA256_AMD64="${GRPCURL_SHA256_AMD64}" \
    GRPCURL_SHA256_ARM64="${GRPCURL_SHA256_ARM64}" \
    bash /opt/delta/components/protocols.sh

# The docker buildx cli-plugin — closes the measured base-runner gap.
# The prefix names the component's FULL pin contract. The ARGs reach the
# script through the RUN environment either way (the pin gate above runs on
# exactly that mechanism); the prefix is the call site documenting its
# component, and an understated one misleads.
RUN DOCKER_BUILDX_VERSION="${DOCKER_BUILDX_VERSION}" DOCKER_BUILDX_SHA256_AMD64="${DOCKER_BUILDX_SHA256_AMD64}" \
    DOCKER_BUILDX_SHA256_ARM64="${DOCKER_BUILDX_SHA256_ARM64}" \
    bash /opt/delta/components/buildx.sh

# The CI fold: Actions runner + .NET deps + cictl.
RUN RUNNER_VERSION="${RUNNER_VERSION}" RUNNER_SHA256_AMD64="${RUNNER_SHA256_AMD64}" \
    RUNNER_SHA256_ARM64="${RUNNER_SHA256_ARM64}" \
    CICTL_VERSION="${CICTL_VERSION}" bash /opt/delta/components/runner.sh

# The harness bake runs as the dev user: claude lands in ~/.local/bin and the
# npm globals in the nvm prefix, both dev-owned and both on the ENV PATH.
USER ${USERNAME}
RUN CLAUDE_CODE_VERSION="${CLAUDE_CODE_VERSION}" OMP_VERSION="${OMP_VERSION}" CODEX_VERSION="${CODEX_VERSION}" \
    bash /opt/delta/components/agents.sh
USER root

# The scripts have done their work; the image does not ship them.
RUN rm -rf /opt/delta

# The runner semantics, carried from the deleted runner/Dockerfile.
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
