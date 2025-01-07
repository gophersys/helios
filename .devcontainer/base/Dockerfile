FROM ubuntu:22.04

# Install global dependencies needed for downloading, installing & building software
RUN apt update && \
    apt install -y \
    curl \
    git \
    libc6-dev \
    zsh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Down oh my zsh and set it as default shell
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/2056aeeeaddd977eb205619c6f236b94dac896be/tools/install.sh)"
RUN chsh -s $(which zsh)

# Switch to zsh for all subsequent RUN commands
SHELL ["/usr/bin/zsh", "-c"]

# -----------------------------------------------------------------------------------------------------
#                                                                                                    Nx
# ---------------------------------------------------------------------------------------------------*/

# Install Node Version Manager and Node.js
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && \
    echo 'export NVM_DIR="/root/.nvm"' >> /root/.profile && \
    echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> /root/.profile && \
    echo 'export NVM_DIR="/root/.nvm"' >> /root/.bashrc && \
    echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> /root/.bashrc && \
    . /root/.nvm/nvm.sh && \
    nvm install v22.12.0 && \
    nvm alias default v22.12.0 && \
    npm install -g npm@11.0.0 && \
    npm install -g nx

# Create symbolic links for node and npm in /usr/local/bin with full paths
RUN ln -sf "/root/.nvm/versions/node/v22.12.0/bin/node" "/usr/local/bin/node" && \
    ln -sf "/root/.nvm/versions/node/v22.12.0/bin/npm" "/usr/local/bin/npm" && \
    ln -sf "/root/.nvm/versions/node/v22.12.0/bin/nx" "/usr/local/bin/nx"

# Verify the installation
RUN node --version && npm --version && nx --version

# -----------------------------------------------------------------------------------------------------
#                                                                                                    Go
# ---------------------------------------------------------------------------------------------------*/

ARG GO_VERSION=1.23.4
RUN ARCH="" && \
    case "$(uname -m)" in \
    x86_64) ARCH="amd64" ;; \
    aarch64) ARCH="arm64" ;; \
    *) echo "Unsupported architecture" && exit 1 ;; \
    esac && \
    curl -LO "https://golang.org/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" \
    && tar -C /usr/local -xzf go${GO_VERSION}.linux-${ARCH}.tar.gz \
    && rm go${GO_VERSION}.linux-${ARCH}.tar.gz

# Set up environment
ENV GOPATH /go
ENV PATH $GOPATH/bin:/usr/local/go/bin:$PATH
RUN mkdir -p "$GOPATH/src" "$GOPATH/bin" && chmod -R 777 "$GOPATH"

# -----------------------------------------------------------------------------------------------------
#                                                                                                Docker
# ---------------------------------------------------------------------------------------------------*/

# Install Docker CLI (not the full Docker Engine)
RUN apt-get update && \
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common gnupg lsb-release && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce-cli \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Docker Compose
RUN curl -L "https://github.com/docker/compose/releases/download/v2.7.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose

# -----------------------------------------------------------------------------------------------------
#                                                                                           Other tools
# ---------------------------------------------------------------------------------------------------*/
WORKDIR /

# Update and install all necessary tools in one layer
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    make \
    python3 \
    python3-pip \
    screen \
    stlink-tools \
    net-tools \
    usbutils \
    iputils-ping \
    astyle \
    unzip \
    protobuf-compiler \
    python3-venv \
    && apt-get clean \ 
    && rm -rf /var/lib/apt/lists/* 

# -----------------------------------------------------------------------------------------------------
#                                                                                                Protoc
# ---------------------------------------------------------------------------------------------------*/

# Determine architecture and download the appropriate version of protoc
RUN ARCH="$(uname -m)" && \
    case "${ARCH}" in \
    aarch64) PROTOC_ZIP="protoc-29.1-linux-aarch_64.zip" ;; \
    x86_64) PROTOC_ZIP="protoc-29.1-linux-x86_64.zip" ;; \
    *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
    esac && \
    curl -LO "https://github.com/protocolbuffers/protobuf/releases/download/v29.1/${PROTOC_ZIP}" && \
    unzip -o ${PROTOC_ZIP} -d /usr/local && \
    rm ${PROTOC_ZIP}

ENV PATH="/usr/local/bin:${PATH}"

# -----------------------------------------------------------------------------------------------------
#                                                                                         nRF CLI Tools
# ---------------------------------------------------------------------------------------------------*/

# Get .deb package and install based on architecture
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
    rm nrf-cli-tools.deb

# -----------------------------------------------------------------------------------------------------
#                                                                                                 JLink
# ---------------------------------------------------------------------------------------------------*/
WORKDIR /tmp

# Install common dependencies first
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
    JLINK_DEB="JLink_Linux_V810i_arm64.deb" \
    ;; \
    x86_64) \
    JLINK_DEB="JLink_Linux_V810i_x86_64.deb" \
    ;; \
    *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
    esac && \
    echo '#!/bin/sh\nexit 0' > /usr/bin/udevadm && \
    chmod +x /usr/bin/udevadm && \
    curl -fsSL -o ${JLINK_DEB} -d "accept_license_agreement=accepted&submit=Download+software" "https://www.segger.com/downloads/jlink/${JLINK_DEB}" && \
    dpkg -i ${JLINK_DEB} || true && \
    apt-get update && apt-get install -y -f && \
    rm -f ${JLINK_DEB}

# Setup config folder to avoid "Terms of Use" pop up window of JLink on every board flash
COPY assets/segger /root/.config/SEGGER

# Remove udev mock
RUN rm /usr/bin/udevadm

# -----------------------------------------------------------------------------------------------------
#                                                                                                Python
# ---------------------------------------------------------------------------------------------------*/

# Set the PYTHONPATH to include the libs directory
ENV PYTHONPATH="/workspaces/concord/libs:${PYTHONPATH}"
ENV PYTHONPATH="/workspaces/concord/libs/python/:${PYTHONPATH}"

# Install grpcio-tools
RUN pip3 install grpcio-tools==1.68.1

# -----------------------------------------------------------------------------------------------------
#                                                                                               Kubectl
# ---------------------------------------------------------------------------------------------------*/
RUN ARCH="$(uname -m)" && \
    case "${ARCH}" in \
    aarch64) KUBECTL_ARCH="arm64" ;; \
    x86_64) KUBECTL_ARCH="amd64" ;; \
    *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
    esac && \
    KUBECTL_VERSION=$(curl -L -s https://dl.k8s.io/release/stable.txt) && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/kubectl

# -----------------------------------------------------------------------------------------------------
#                                                                                                   K9s
# ---------------------------------------------------------------------------------------------------*/
RUN ARCH="$(uname -m)" && \
    case "${ARCH}" in \
    aarch64) K9S_ARCH="arm64" ;; \
    x86_64) K9S_ARCH="amd64" ;; \
    *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
    esac && \
    K9S_VERSION=$(curl -s https://api.github.com/repos/derailed/k9s/releases/latest | grep 'tag_name' | cut -d '"' -f 4) && \
    curl -LO "https://github.com/derailed/k9s/releases/download/${K9S_VERSION}/k9s_Linux_${K9S_ARCH}.tar.gz" && \
    tar -xzf "k9s_Linux_${K9S_ARCH}.tar.gz" k9s && \
    chmod +x k9s && \
    mv k9s /usr/local/bin/k9s && \
    rm "k9s_Linux_${K9S_ARCH}.tar.gz"