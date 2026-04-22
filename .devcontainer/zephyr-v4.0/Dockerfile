# Zephyr v4.0 LTS devcontainer
# Based on concord-devcontainer-base
FROM containers.ad.corekinect.com/concord-devcontainer-base:latest

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# ----------------------------------------------------
#                                      Build Arguments
# ----------------------------------------------------
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Environment versions - Vanilla Zephyr v4.0 LTS
ARG ZEPHYR_SDK_VERSION=0.17.0
ARG ZEPHYR_VERSION=v4.0.0

# ----------------------------------------------------
#                                      Zephyr Packages
# ----------------------------------------------------
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    cmake \
    ninja-build \
    gperf \
    ccache \
    dfu-util \
    device-tree-compiler \
    xz-utils \
    file \
    gcc-multilib \
    g++-multilib \
    libsdl2-dev \
    libmagic1 \
    expect \
    screen \
    minicom \
    locales && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# ----------------------------------------------------
#                                                 West
# ----------------------------------------------------
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install west esptool==4.7.0

ENV PATH="${PATH}:/usr/local/bin:/root/.local/bin"

# ----------------------------------------------------
#                                          Zephyr SDK
# ----------------------------------------------------
WORKDIR /usr/local

# Download full SDK (not minimal) to get all toolchains
RUN case "${TARGETPLATFORM}" in \
  "linux/amd64"|"") \
  wget -q https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64.tar.xz && \
  tar xf zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64.tar.xz > /dev/null && \
  rm zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64.tar.xz \
  ;; \
  "linux/arm64") \
  wget -q https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-aarch64.tar.xz && \
  tar xf zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-aarch64.tar.xz > /dev/null && \
  rm zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-aarch64.tar.xz \
  ;; \
  esac

# Run SDK setup - install ESP32 and ARM toolchains
WORKDIR /usr/local/zephyr-sdk-${ZEPHYR_SDK_VERSION}
RUN ./setup.sh -t xtensa-espressif_esp32_zephyr-elf \
  -t xtensa-espressif_esp32s2_zephyr-elf \
  -t xtensa-espressif_esp32s3_zephyr-elf \
  -t arm-zephyr-eabi \
  -h \
  -c

# ----------------------------------------------------
#                                   Vanilla Zephyr
# ----------------------------------------------------
RUN mkdir /zephyrproject
WORKDIR /zephyrproject

# Initialize vanilla Zephyr (not NCS)
RUN west init -m https://github.com/zephyrproject-rtos/zephyr --mr ${ZEPHYR_VERSION} && \
  west update

# Export Zephyr CMake package
RUN west zephyr-export

# Install Python requirements (uv is 10-100x faster than pip at resolution)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install uv && \
    uv pip install --system -r zephyr/scripts/requirements.txt

# Fetch ESP32 blobs (required for WiFi)
RUN west blobs fetch hal_espressif

# ----------------------------------------------------
#                                         Environment
# ----------------------------------------------------
# Set ZEPHYR_BASE
ENV ZEPHYR_BASE=/zephyrproject/zephyr

# Add SDK to PATH
ENV PATH="/usr/local/zephyr-sdk-${ZEPHYR_SDK_VERSION}/sysroots/x86_64-pokysdk-linux/usr/bin:${PATH}"

# Auto-source Zephyr environment
RUN echo 'export ZEPHYR_BASE=/zephyrproject/zephyr' >> ~/.zshrc && \
    echo 'source /zephyrproject/zephyr/zephyr-env.sh 2>/dev/null || true' >> ~/.zshrc && \
    echo 'export ZEPHYR_BASE=/zephyrproject/zephyr' >> ~/.profile && \
    echo 'source /zephyrproject/zephyr/zephyr-env.sh 2>/dev/null || true' >> ~/.profile

WORKDIR /workspaces/concord
