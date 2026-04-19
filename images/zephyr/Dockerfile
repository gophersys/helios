# syntax=docker/dockerfile:1.7
#
# images/zephyr — Zephyr RTOS build host on top of images/python.
#
# Installs the upstream Zephyr system dependencies, the `west` meta-tool
# (via pip/uv into a venv), and the Zephyr SDK for cross-compilation.
#
# The SDK archive is large (~1GB). We install a minimal subset of toolchains
# to keep the image reasonable — expand the ZSDK_TOOLCHAINS arg if a
# downstream project needs an arch that isn't included.
ARG BASE_TAG=latest
FROM ghcr.io/gophersys/python:${BASE_TAG}

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="Zephyr RTOS build host: west + Zephyr SDK"

USER root

# Zephyr's documented Ubuntu host dependencies.
# https://docs.zephyrproject.org/latest/develop/getting_started/index.html
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ccache \
      device-tree-compiler \
      dfu-util \
      file \
      gperf \
      libmagic1 \
      libsdl2-dev \
      libusb-1.0-0 \
      ninja-build \
      python3-dev \
      python3-venv \
      wget \
      xz-utils \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

ARG ZSDK_VERSION=0.17.0
ARG ZSDK_TOOLCHAINS="arm-zephyr-eabi riscv64-zephyr-elf"

ENV ZEPHYR_SDK_INSTALL_DIR=/opt/zephyr-sdk \
    ZEPHYR_BASE=/workspace/zephyr \
    WEST_VENV=/opt/west-venv \
    PATH=/opt/west-venv/bin:${PATH}

# Zephyr SDK — minimal bundle + selected toolchains only.
RUN mkdir -p "${ZEPHYR_SDK_INSTALL_DIR}" \
 && cd /tmp \
 && wget -q "https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZSDK_VERSION}/zephyr-sdk-${ZSDK_VERSION}_linux-x86_64_minimal.tar.xz" \
 && tar -C "${ZEPHYR_SDK_INSTALL_DIR}" --strip-components=1 -xJf "zephyr-sdk-${ZSDK_VERSION}_linux-x86_64_minimal.tar.xz" \
 && rm "zephyr-sdk-${ZSDK_VERSION}_linux-x86_64_minimal.tar.xz" \
 && cd "${ZEPHYR_SDK_INSTALL_DIR}" \
 && ./setup.sh -t "${ZSDK_TOOLCHAINS}" -h -c

# west + Zephyr's python requirements in an isolated venv so they don't
# collide with project-level tooling. uv runs the install for speed.
RUN uv venv "${WEST_VENV}" \
 && "${WEST_VENV}/bin/pip" install --no-cache-dir \
      west \
      pyelftools \
      pyyaml \
      cryptography \
      intelhex \
      packaging \
      pykwalify \
      colorama \
      anytree \
      canopen \
 && "${WEST_VENV}/bin/west" --version \
 && chmod -R a+rx "${WEST_VENV}"

USER dev
WORKDIR /home/dev
