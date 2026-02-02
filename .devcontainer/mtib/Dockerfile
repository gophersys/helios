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
ARG JLINK_VERSION=V794e

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
    apt-get install -y x11-common \
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
    libice6 \
    minicom \
    i2c-tools \
    gpiod \
    python3-tk || apt-get --fix-broken install -y && \
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