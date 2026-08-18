# NOTE: no `# syntax=` directive, deliberately. It made every cold builder
# pull the dockerfile frontend from docker.io — the LAST Docker Hub
# dependency on the build path, and a 502 from auth.docker.io killed a
# build through it (run 2026-08-18). The builder's own built-in frontend
# (BuildKit v0.32) supersedes dockerfile:1.7, and no feature here needs
# the external one.
#
# flutter — Flutter SDK + Android toolchain on top of gophersys/base.
#
# Scope is Android + Linux desktop targets. iOS builds require macOS and are
# explicitly out of scope. Every version is pinned as an ARG at the top.

ARG BASE_TAG=latest
FROM ghcr.io/gophersys/base:${BASE_TAG}

# Buildx-injected platform vars for multi-arch awareness.
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# -------------------------------------------------------------------------
# Tool versions — latest LTS / stable as of 2026-04-19.
# -------------------------------------------------------------------------
ARG JAVA_VERSION=21                                                    # latest LTS as of 2026-04-19
ARG ANDROID_CMDLINE_TOOLS_VERSION=14742923                             # latest LTS as of 2026-04-19
ARG ANDROID_CMDLINE_TOOLS_SHA256_NOARCH=04453066b540409d975c676d781da1477479dde3761310f1a7eb92a1dfb15af7  # computed-at-pin: 2026-08-17
ARG ANDROID_PLATFORM_VERSION=36                                        # latest LTS as of 2026-04-19
ARG ANDROID_BUILDTOOLS_VERSION=36.1.0                                  # latest LTS as of 2026-04-19
ARG FLUTTER_VERSION=3.47.0                                             # latest LTS as of 2026-08-17
ARG FLUTTER_CHANNEL=stable                                             # latest LTS as of 2026-04-19
ARG FLUTTER_SHA256_AMD64=26cd99d3d94b1367e6b50535a18aeef0282c10a535bbe3ec493534dcdab75296  # computed-at-pin: 2026-08-17

# NOTE: the non-root user is hardcoded as `dev` throughout this Dockerfile
# (matching the base image's invariant). An ARG USERNAME is intentionally NOT
# used here because the parent image's SHELL is zsh-with-pipefail, and zsh
# unconditionally auto-sets the special parameter $USERNAME to the effective
# logname. See zephyr/Dockerfile for the full rationale. This file DID use
# ${USERNAME} from zsh-as-root RUN layers until 2026-08-17: both chowns below
# resolved to `chown -R root:root`, so /opt/flutter and /opt/android-sdk shipped
# root-owned, and `flutter --version` as `dev` exited 128 with "detected dubious
# ownership in repository at '/opt/flutter'" on the first smoke run that ever
# executed it.

# -------------------------------------------------------------------------
# System deps for Flutter + Android. openjdk version is driven by JAVA_VERSION.
# -------------------------------------------------------------------------
USER root
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      file \
      libglu1-mesa \
      ninja-build \
      "openjdk-${JAVA_VERSION}-jdk-headless" \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------------------
# Android cmdline-tools + platform + build-tools + platform-tools.
# Multi-arch-aware: Google ships a single archive; the cmdline-tools run on
# both amd64 and arm64 via the same JAR. We only branch for sanity-check.
# -------------------------------------------------------------------------
ENV ANDROID_SDK_ROOT=/opt/android-sdk \
    ANDROID_HOME=/opt/android-sdk \
    PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin:${PATH}

# hadolint ignore=DL4006
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) : ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p "${ANDROID_SDK_ROOT}/cmdline-tools" \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_CMDLINE_TOOLS_VERSION}_latest.zip" \
      /tmp/cmdline-tools.zip \
      "${ANDROID_CMDLINE_TOOLS_SHA256_NOARCH}" ANDROID_CMDLINE_TOOLS_SHA256_NOARCH \
 && unzip -q /tmp/cmdline-tools.zip -d "${ANDROID_SDK_ROOT}/cmdline-tools" \
 && mv "${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools" "${ANDROID_SDK_ROOT}/cmdline-tools/latest" \
 && rm /tmp/cmdline-tools.zip \
 && ( for _ in $(seq 1 100); do echo y; done ) \
      | "${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager" --licenses >/dev/null \
 && "${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager" \
      "platform-tools" \
      "platforms;android-${ANDROID_PLATFORM_VERSION}" \
      "build-tools;${ANDROID_BUILDTOOLS_VERSION}" \
 && chown -R dev:dev "${ANDROID_SDK_ROOT}"

# -------------------------------------------------------------------------
# Flutter SDK — official google-hosted tarball, pinned channel.
#
# safe.directory is --system and not --global: this RUN layer is root, so
# --global writes /root/.gitconfig, which the `dev` runtime user cannot even
# read. The SDK ships as a git checkout and every flutter invocation shells out
# to git, so the exception has to reach whichever uid runs the tool.
# -------------------------------------------------------------------------
ENV FLUTTER_HOME=/opt/flutter \
    FLUTTER_ROOT=/opt/flutter \
    PUB_CACHE=/home/dev/.pub-cache

# hadolint ignore=DL4006
RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://storage.googleapis.com/flutter_infra_release/releases/${FLUTTER_CHANNEL}/linux/flutter_linux_${FLUTTER_VERSION}-${FLUTTER_CHANNEL}.tar.xz" \
      /tmp/flutter.tar.xz \
      "${FLUTTER_SHA256_AMD64}" FLUTTER_SHA256_AMD64 \
 && mkdir -p /opt \
 && tar -C /opt -xJf /tmp/flutter.tar.xz \
 && rm /tmp/flutter.tar.xz \
 && git config --system --add safe.directory /opt/flutter \
 && chown -R dev:dev /opt/flutter
# NOTE: no flutter --version / flutter doctor / flutter precache smoke here —
# Flutter SDK uses the bundled dart runtime (native arch) which fails under
# QEMU cross-arch build; flutter config/precache/doctor run in post-build
# smoke test instead.

ENV GOPHERSYS_DEVCONTAINER=flutter

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys flutter layer: Flutter ${FLUTTER_VERSION} + Android SDK ${ANDROID_PLATFORM_VERSION}"

USER dev
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
