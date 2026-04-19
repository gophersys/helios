# syntax=docker/dockerfile:1.7
#
# images/rust — Rust stable via rustup on top of images/base.
#
# rustup installs the `stable` toolchain globally. Cargo's target cache
# lives under the dev user's home so bind mounts survive container
# rebuilds during local dev.
FROM ghcr.io/gophersys/base:latest

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="Rust stable via rustup"

USER root

# Extra toolchain pieces Rust commonly needs: a linker (gcc + libc headers
# from build-essential), pkg-config for crates that wrap C libs, and
# libssl-dev for native-tls consumers. We keep them here and not in base
# so the base image stays generic.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      libssl-dev \
      pkg-config \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:${PATH}

ARG RUST_CHANNEL=stable

RUN mkdir -p "${RUSTUP_HOME}" "${CARGO_HOME}" \
 && curl -fsSL https://sh.rustup.rs -o /tmp/rustup-init.sh \
 && sh /tmp/rustup-init.sh -y \
      --no-modify-path \
      --default-toolchain "${RUST_CHANNEL}" \
      --profile minimal \
      --component rustfmt \
      --component clippy \
 && rm /tmp/rustup-init.sh \
 && chmod -R a+rwx "${RUSTUP_HOME}" "${CARGO_HOME}" \
 && rustc --version \
 && cargo --version

USER dev
WORKDIR /home/dev
