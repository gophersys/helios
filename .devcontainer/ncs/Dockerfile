FROM containers.ad.corekinect.com/concord-devcontainer-base:latest

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# ----------------------------------------------------
#                                      Build Arguments
# ----------------------------------------------------
# Default docker arguments
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Environment versions
ARG NRF_CLI_VERSION=10.24.2
ARG JLINK_VERSION=V872a
ARG ZEPHYR_SDK_VERSION=0.17.4

# ----------------------------------------------------
#                                             nrfjprog
# ----------------------------------------------------
RUN case "${TARGETPLATFORM}" in \
  "linux/amd64") \
  NRF_CLI_DEB="nrf-command-line-tools_${NRF_CLI_VERSION}_amd64.deb" \
  ;; \
  "linux/arm64") \
  NRF_CLI_DEB="nrf-command-line-tools_${NRF_CLI_VERSION}_arm64.deb" \
  ;; \
  *) echo "Unsupported architecture: ${TARGETPLATFORM}" && exit 1 ;; \
  esac && \
  curl -o nrf-cli-tools.deb "https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/desktop-software/nrf-command-line-tools/sw/versions-10-x-x/10-24-2/${NRF_CLI_DEB}" && \
  dpkg -i nrf-cli-tools.deb || true && \
  apt-get install -f -y && \
  rm nrf-cli-tools.deb

# ----------------------------------------------------
#                                                JLink
# ----------------------------------------------------
WORKDIR /tmp

# Install common dependencies
RUN apt-get update && \
  apt-get upgrade -y && \
  apt-get install -y x11-common && \
  apt-get install -y \
  libxcb-icccm4 \
  libxcb-image0 \
  libxcb-keysyms1 \
  libxcb-render-util0 \
  libxcb-render0 \
  libxcb-shape0 \
  libxkbcommon-x11-0 \
  curl \
  libudev-dev \
  udev \
  libice6 || apt-get --fix-broken install -y && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# Download and install JLink package based on architecture, resolving any missing dependencies
RUN ARCH="$(uname -m)" && \
  case "${ARCH}" in \
  aarch64) \
  JLINK_DEB="JLink_Linux_${JLINK_VERSION}_arm64.deb" \
  ;; \
  x86_64) \
  JLINK_DEB="JLink_Linux_${JLINK_VERSION}_x86_64.deb" \
  ;; \
  *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
  esac && \
  echo '#!/bin/sh\nexit 0' > /usr/bin/udevadm && \
  chmod +x /usr/bin/udevadm && \
  curl -fsSL -o ${JLINK_DEB} -d "accept_license_agreement=accepted&submit=Download+software" "https://www.segger.com/downloads/jlink/${JLINK_DEB}" && \
  dpkg -i ${JLINK_DEB} || true && \
  apt-get update && apt-get install -y -f && \
  rm -f ${JLINK_DEB}

# ----------------------------------------------------
#                                          Other Tools
# ----------------------------------------------------
RUN --mount=type=cache,target=/root/.cache/pip \
  pip3 install esptool==4.7.0

# ----------------------------------------------------
#                                         Zephyr & NCS
# ----------------------------------------------------

# From -> https://developer.nordicsemi.com/nRF_Connect_SDK/doc/latest/nrf/installation/installing.html

# Set up environment variables to prevent interactive timezone configuration
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Common installation for all architectures
RUN apt-get update && apt-get upgrade -y && apt-get autoremove -y && \
  apt-get install -y --no-install-recommends \
  git \
  groovy \
  cmake \
  ninja-build \
  gperf \
  ccache \
  dfu-util \
  device-tree-compiler \
  wget \
  python3-dev \
  python3-pip \
  python3-setuptools \
  python3-tk \
  python3-wheel \
  python3-venv \
  xz-utils \
  file \
  make \
  gcc \
  libsdl2-dev \
  libmagic1 \
  libxcb-render0 \
  libxcb-render-util0 \
  libxcb-shape0 \
  libxcb-icccm4 \
  libxcb-keysyms1 \
  libxcb-image0 \
  libxkbcommon-x11-0 \
  udev \
  expect \
  screen \
  minicom && \
  ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# Install the west tool system-wide
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install west

# Update PATH to include pip installed binaries
ENV PATH="${PATH}:/usr/local/bin"

# Download the Zephyr SDK and verify a succesful  download
WORKDIR /usr/local
RUN case "${TARGETPLATFORM}" in \
  "linux/amd64") \
  wget https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz && \
  wget -O - https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/sha256.sum | shasum --check --ignore-missing && \
  tar xf zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz > /dev/null && \
  rm zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz \
  ;; \
  "linux/arm64") \
  wget https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-aarch64_minimal.tar.xz && \
  wget -O - https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/sha256.sum | shasum --check --ignore-missing && \
  tar xf zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-aarch64_minimal.tar.xz > /dev/null && \
  rm zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-aarch64_minimal.tar.xz \
  ;; \
  esac

# Run the Zephyr SDK bundle setup script
WORKDIR /usr/local/zephyr-sdk-${ZEPHYR_SDK_VERSION}

# Install only the supported toolchains, and the host tools
RUN ./setup.sh -t xtensa-espressif_esp32_zephyr-elf \
  -t xtensa-espressif_esp32s2_zephyr-elf \
  -t xtensa-espressif_esp32s3_zephyr-elf \
  -t arm-zephyr-eabi \
  -h \
  -c

# Create the ncs directory and set it as the working directory
RUN mkdir /ncs
WORKDIR /ncs

# Perform the west init, this will be cached as a separate layer
RUN west init -m https://github.com/nrfconnect/sdk-nrf --mr v2.7.0 && \ 
  west update

# Modify the west.yml using the awk command to add espressif, nxp & stm32 support
RUN awk '/name-allowlist:/{ \
  print; \
  getline; \
  while ($0 < "          - hal_nxp" && $1 != "") { \
  print; \
  getline; \
  }; \
  print "          - hal_espressif # Added by CoreKinect"; \
  print "          - hal_nxp # Added by CoreKinect"; \
  print "          - hal_stm32 # Added by CoreKinect"; \
  print; \
  next \
  }1' nrf/west.yml > nrf/temp.yml && \
  mv nrf/temp.yml nrf/west.yml

# Perform west update and zephyr-export
RUN west update && \
  west zephyr-export

# Modify the anytree version in requirements-extras.txt
RUN sed -i 's/anytree*/anytree==2.8.0/' /ncs/zephyr/scripts/requirements-extras.txt

# Install additional Python dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
  pip3 install --user -r zephyr/scripts/requirements.txt \
                      -r nrf/scripts/requirements.txt \
                      -r bootloader/mcuboot/scripts/requirements.txt

# Add OpenOCD binaries to the PATH
# Note: OpenOCD binary path - update if ZEPHYR_SDK_VERSION ARG changes
ENV PATH="/usr/local/zephyr-sdk-0.17.4/sysroots/x86_64-pokysdk-linux/usr/bin:${PATH}"

# USB device permissions are fixed at runtime by ctl.sh (fix_usb_permissions function)
# which sets 666 permissions on J-Link (1366) and Nordic (1915) USB devices

# Fetch espressif blobs
RUN west blobs fetch hal_espressif

# Automatically source the Zephyr environment
RUN echo 'source /ncs/zephyr/zephyr-env.sh' >> ~/.profile && \
  echo 'source /ncs/zephyr/zephyr-env.sh' >> ~/.zshrc

# ----------------------------------------------------
#                                              Locales
# ----------------------------------------------------
# This package is required to set up and generate locales in Debian/Ubuntu.
RUN apt update && apt install -y locales && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# The locale-gen command reads the /etc/locale.gen file to determine which locales to generate.
# Uncommenting a specific locale in this file and then running locale-gen will generate that locale.
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

# Setting these environment variables will ensure that processes run in the container use the desired locale.
# This can prevent issues with software that expects specific locales.
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Set ZEPHYR_BASE as a persistent environment variable
# This ensures west build commands work in all contexts
ENV ZEPHYR_BASE=/ncs/zephyr