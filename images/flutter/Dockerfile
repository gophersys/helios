# syntax=docker/dockerfile:1.7
#
# images/flutter — Flutter SDK on top of images/node.
#
# Flutter is installed from the official google-hosted tarball (stable
# channel). Node is present because Flutter's dev tooling (FVM scripts,
# codegen runners, and many first-party plugins) drive npm/yarn under the
# hood, and it's easier to bake it in than bolt it on per project.
#
# This image covers Android builds only. iOS builds require macOS runners
# and are not in scope for a Linux container.
FROM ghcr.io/gophersys/node:latest

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="Flutter stable SDK + Android toolchain layer"

USER root

# Flutter + Android system deps. xz-utils and file come from base already
# via tzdata/locales; listed here for documentation but not reinstalled.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      clang \
      cmake \
      libglu1-mesa \
      libgtk-3-dev \
      ninja-build \
      openjdk-17-jdk-headless \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

ARG FLUTTER_VERSION=3.24.5
ARG FLUTTER_CHANNEL=stable

ENV FLUTTER_HOME=/opt/flutter \
    FLUTTER_ROOT=/opt/flutter \
    PATH=/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin:${PATH} \
    PUB_CACHE=/home/dev/.pub-cache

RUN curl -fsSL \
      "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-${FLUTTER_CHANNEL}.tar.xz" \
      -o /tmp/flutter.tar.xz \
 && mkdir -p /opt \
 && tar -C /opt -xJf /tmp/flutter.tar.xz \
 && rm /tmp/flutter.tar.xz \
 && git config --global --add safe.directory /opt/flutter \
 && chown -R dev:dev /opt/flutter \
 && su dev -c "flutter --version" \
 && su dev -c "flutter config --no-analytics" \
 && su dev -c "flutter precache --universal --linux --no-ios"

USER dev
WORKDIR /home/dev
