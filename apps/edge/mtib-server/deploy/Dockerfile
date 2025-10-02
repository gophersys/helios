FROM ubuntu:22.04

# Install common dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    curl \
    udev \
    python3 \
    python3-pip \
    screen \
    iputils-ping \
    usbutils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# ----------------------------------------------------------------------------------
#                                                                              JLink
# --------------------------------------------------------------------------------*/
RUN ARCH="$(uname -m)" && \
    case "${ARCH}" in \
    aarch64) \
    JLINK_DEB="JLink_Linux_V796j_arm64.deb" \
    ;; \
    x86_64) \
    JLINK_DEB="JLink_Linux_V796j_x86_64.deb" \
    ;; \
    *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
    esac && \
    echo '#!/bin/sh\nexit 0' > /usr/bin/udevadm && \
    chmod +x /usr/bin/udevadm && \
    curl -fsSL -o ${JLINK_DEB} -d "accept_license_agreement=accepted&submit=Download+software" "https://www.segger.com/downloads/jlink/${JLINK_DEB}" && \
    dpkg -i ${JLINK_DEB} || true && \
    apt-get update && apt-get install -y -f && \
    rm -f ${JLINK_DEB}

# Remove udev mock
RUN rm /usr/bin/udevadm

# ----------------------------------------------------------------------------------
#                                                                           nrfjprog
# --------------------------------------------------------------------------------*/
RUN ARCH="$(uname -m)" && \
    case "${ARCH}" in \
    aarch64) \
    NRF_CLI_DEB="nrf-command-line-tools_10.24.2_arm64.deb" \
    ;; \
    x86_64) \
    NRF_CLI_DEB="nrf-command-line-tools_10.24.2_amd64.deb" \
    ;; \
    *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
    esac && \
    curl -o nrf-cli-tools.deb "https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/desktop-software/nrf-command-line-tools/sw/versions-10-x-x/10-24-2/${NRF_CLI_DEB}" && \
    dpkg -i nrf-cli-tools.deb || true && \
    apt-get install -f -y && \
    # Install the required J-Link dependency for nrf command line tools
    # Check what J-Link deb files are available and install the appropriate one
    if [ -f "/opt/nrf-command-line-tools/share/JLink_Linux_V794e_arm64.deb" ]; then \
    apt install /opt/nrf-command-line-tools/share/JLink_Linux_V794e_arm64.deb --fix-broken || true; \
    elif [ -f "/opt/nrf-command-line-tools/share/JLink_Linux_V794e_x86_64.deb" ]; then \
    apt install /opt/nrf-command-line-tools/share/JLink_Linux_V794e_x86_64.deb --fix-broken || true; \
    else \
    echo "No J-Link deb found in /opt/nrf-command-line-tools/share/, listing available files:"; \
    ls -la /opt/nrf-command-line-tools/share/ || true; \
    fi && \
    echo "Installed nrf-command-line-tools" && \
    rm nrf-cli-tools.deb && \
    # Verify nrfjprog is properly installed and accessible
    which nrfjprog && \
    nrfjprog --version && \
    echo "nrfjprog verification successful"

WORKDIR /root

# ----------------------------------------------------------------------------------
#                                                            App python dependencies
# --------------------------------------------------------------------------------*/
# Install other dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y \
    unzip \
    python3-tk \
    libgpiod-dev \
    python3-libgpiod \
    python3.10-venv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN apt update && apt install -y \
    i2c-tools vim 

# ----------------------------------------------------------------------------------
#                                                            App python dependencies
# --------------------------------------------------------------------------------*/

WORKDIR /app

# By installing these first you save a lot of time when making changes to the source code
# and rebuilding the application
COPY apps/edge/mtib-server/setup.py setup.py
RUN pip install -e . && \
    pip cache purge

# Copy the assets
COPY apps/edge/mtib-server/assets /app/assets
WORKDIR /app/assets

# Generate the fluidnc firmware assets
RUN chmod +x ctl.sh && \
    ./ctl.sh

# Copy the libraries used by the app
COPY libs/python /libs/python

# Copy the protocols used by the app
COPY libs/protocols/mtib /libs/protocols/mtib

# Set the PYTHONPATH to include the libs directory
ENV PYTHONPATH="/libs:${PYTHONPATH}"
ENV PYTHONPATH="/libs/python/:${PYTHONPATH}"

WORKDIR /app

# Copy the app itself
COPY apps/edge/mtib-server/src src

# Keep the container running
ENTRYPOINT ["python3", "src/main.py"]