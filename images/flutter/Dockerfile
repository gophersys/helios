# syntax=docker/dockerfile:1.7
#
# images/flutter — Flutter SDK + Android toolchain on top of gophersys/base.
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
ARG JAVA_VERSION=17                                                    # latest LTS as of 2026-04-19
ARG ANDROID_CMDLINE_TOOLS_VERSION=14742923                             # latest LTS as of 2026-04-19
ARG ANDROID_PLATFORM_VERSION=34                                        # latest LTS as of 2026-04-19
ARG ANDROID_BUILDTOOLS_VERSION=34.0.0                                  # latest LTS as of 2026-04-19
ARG FLUTTER_VERSION=3.41.7                                             # latest LTS as of 2026-04-19
ARG FLUTTER_CHANNEL=stable                                             # latest LTS as of 2026-04-19

ARG USERNAME=dev

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
      linux/amd64|linux/arm64) : ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p "${ANDROID_SDK_ROOT}/cmdline-tools" \
 && curl -fsSL "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_CMDLINE_TOOLS_VERSION}_latest.zip" \
      -o /tmp/cmdline-tools.zip \
 && unzip -q /tmp/cmdline-tools.zip -d "${ANDROID_SDK_ROOT}/cmdline-tools" \
 && mv "${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools" "${ANDROID_SDK_ROOT}/cmdline-tools/latest" \
 && rm /tmp/cmdline-tools.zip \
 && yes | "${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager" --licenses >/dev/null \
 && "${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager" \
      "platform-tools" \
      "platforms;android-${ANDROID_PLATFORM_VERSION}" \
      "build-tools;${ANDROID_BUILDTOOLS_VERSION}" \
 && chown -R "${USERNAME}:${USERNAME}" "${ANDROID_SDK_ROOT}"

# -------------------------------------------------------------------------
# Flutter SDK — official google-hosted tarball, pinned channel.
# -------------------------------------------------------------------------
ENV FLUTTER_HOME=/opt/flutter \
    FLUTTER_ROOT=/opt/flutter \
    PUB_CACHE=/home/dev/.pub-cache

# hadolint ignore=DL4006
RUN curl -fsSL \
      "https://storage.googleapis.com/flutter_infra_release/releases/${FLUTTER_CHANNEL}/linux/flutter_linux_${FLUTTER_VERSION}-${FLUTTER_CHANNEL}.tar.xz" \
      -o /tmp/flutter.tar.xz \
 && mkdir -p /opt \
 && tar -C /opt -xJf /tmp/flutter.tar.xz \
 && rm /tmp/flutter.tar.xz \
 && git config --global --add safe.directory /opt/flutter \
 && chown -R "${USERNAME}:${USERNAME}" /opt/flutter \
 && su "${USERNAME}" -c "flutter --version" \
 && su "${USERNAME}" -c "flutter config --no-analytics --android-sdk ${ANDROID_SDK_ROOT}" \
 && su "${USERNAME}" -c "flutter precache --universal --linux --no-ios" \
 && (su "${USERNAME}" -c "flutter doctor -v" || true)

ENV GOPHERSYS_DEVCONTAINER=flutter

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys flutter layer: Flutter ${FLUTTER_VERSION} + Android SDK ${ANDROID_PLATFORM_VERSION}"

USER ${USERNAME}
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
