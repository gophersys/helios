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
    which nrfjprog && \
    nrfjprog --version && \
    echo "nrfjprog verification successful"

WORKDIR /root

# ----------------------------------------------------------------------------------
#                                                            System dependencies
# --------------------------------------------------------------------------------*/
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y \
    unzip \
    python3-tk \
    libgpiod-dev \
    python3-libgpiod \
    python3.10-venv \
    i2c-tools \
    vim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------------------------------------
#                                                            Python dependencies
# --------------------------------------------------------------------------------*/
WORKDIR /app

# Install Python dependencies first (cached layer)
COPY apps/edge/mtib-server-v2/setup.py setup.py
RUN pip install -e . && \
    pip cache purge

# Copy FluidNC assets (for motion support)
COPY apps/edge/mtib-server-v2/assets/ctl.sh /app/assets/ctl.sh
WORKDIR /app/assets
RUN chmod +x ctl.sh && \
    ./ctl.sh
COPY apps/edge/mtib-server-v2/assets/config.yaml /app/assets/config.yaml

# ----------------------------------------------------------------------------------
#                                                            Application code
# --------------------------------------------------------------------------------*/
# Copy shared Python libraries (corekinect)
COPY libs/python /libs/python

# Copy V2 protocol stubs
COPY libs/protocols/mtib_v2 /libs/protocols/mtib_v2

# Python namespace packages (PEP 420) - no __init__.py needed

# Set PYTHONPATH for library imports
ENV PYTHONPATH="/libs:${PYTHONPATH}"
ENV PYTHONPATH="/libs/python/:${PYTHONPATH}"

WORKDIR /app

# Copy the V2 server source
COPY apps/edge/mtib-server-v2/src src

# gRPC server port
EXPOSE 50052

ENTRYPOINT ["python3", "src/main.py"]
