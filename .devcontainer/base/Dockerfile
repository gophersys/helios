FROM ubuntu:22.04

# ----------------------------------------------------
#                                      Build Arguments
# ----------------------------------------------------
# Default docker arguments
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Environment versions
ARG NVM_VERSION=0.40.3
ARG NODE_VERSION=22.19.0
ARG NPM_VERSION=11.6.0
ARG NX_VERSION=22
ARG DOCKER_COMPOSE_VERSION=2.39.3
ARG K9S_VERSION=0.50.9
ARG HELM_VERSION=3.19.0

# ----------------------------------------------------
#                                      System Packages
# ----------------------------------------------------
RUN DEBIAN_FRONTEND=noninteractive apt update && apt upgrade -y && \
    apt install -y zsh \
    curl \
    git \
    libc6-dev \
    apt-transport-https \
    ca-certificates \
    software-properties-common \
    unzip \
    build-essential \
    net-tools \
    usbutils \
    netcat \
    protobuf-compiler \
    gettext \
    jq \
    iputils-ping \
    htop \
    speedtest-cli \
    wget \
    gpg \
    gnupg \
    make \
    python3 \
    python3-pip \
    python3-venv \
    lsb-release \
    vim \
    btop \
    sudo && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Setup shell - install Oh My Zsh
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended && \
    chsh -s $(which zsh)

# Verify zsh is installed and switch to it for subsequent RUN commands
RUN ls -la /usr/bin/zsh && which zsh && echo "Zsh found at: $(which zsh)"
SHELL ["/usr/bin/zsh", "-c"]

# Set the working directory
WORKDIR /tmp

# ----------------------------------------------------
#                                             Node, Nx
# ----------------------------------------------------
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0

RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v${NVM_VERSION}/install.sh | bash && \
    source ~/.zshrc && \
    nvm install v${NODE_VERSION} && \
    npm install -g npm@${NPM_VERSION} && \
    npm install -g nx@${NX_VERSION} && \
    corepack enable && \
    corepack prepare yarn@4.9.4 --activate

# Set up Node.js and yarn environment for non-interactive shells
ENV NVM_DIR=/root/.nvm
ENV NODE_PATH=/root/.nvm/versions/node/v${NODE_VERSION}/lib/node_modules
ENV PATH=/root/.nvm/versions/node/v${NODE_VERSION}/bin:/root/.yarn/bin:$PATH

# Create symlinks for yarn and node to make them available globally
RUN ln -sf /root/.nvm/versions/node/v${NODE_VERSION}/bin/node /usr/local/bin/node && \
    ln -sf /root/.nvm/versions/node/v${NODE_VERSION}/bin/npm /usr/local/bin/npm && \
    ln -sf /root/.yarn/bin/yarn /usr/local/bin/yarn

# ----------------------------------------------------
#                                               Docker
# ----------------------------------------------------
RUN case "${TARGETPLATFORM}" in \
    "linux/amd64") \
    # Install Docker CLI for amd64
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - && \
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    # Install Docker Compose for amd64
    curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-Linux-x86_64" -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose && \
    apt-get clean && rm -rf /var/lib/apt/lists/* \
    ;; \
    "linux/arm64") \
    # Install Docker CLI for arm64
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - && \
    add-apt-repository "deb [arch=arm64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    # Install Docker Compose for arm64
    curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-Linux-aarch64" -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose && \
    apt-get clean && rm -rf /var/lib/apt/lists/* \
    ;; \
    esac

# ----------------------------------------------------
#                                               Python
# ----------------------------------------------------

# Set the PYTHONPATH to include the libs directory
ENV PYTHONPATH="/workspaces/concord/libs:/workspaces/concord/libs/python/"

# Install Python packages
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install grpcio-tools==1.75.0 prisma==0.15.0

# ----------------------------------------------------
#                                             Protobuf
# ----------------------------------------------------
RUN case "${TARGETPLATFORM}" in \
    "linux/amd64") \
    PROTOC_ZIP="protoc-32.1-linux-x86_64.zip" && \
    curl -LO "https://github.com/protocolbuffers/protobuf/releases/download/v32.1/${PROTOC_ZIP}" && \
    unzip -o ${PROTOC_ZIP} -d /usr/local && \
    rm ${PROTOC_ZIP} \
    ;; \
    "linux/arm64") \
    PROTOC_ZIP="protoc-32.1-linux-aarch_64.zip" && \
    curl -LO "https://github.com/protocolbuffers/protobuf/releases/download/v32.1/${PROTOC_ZIP}" && \
    unzip -o ${PROTOC_ZIP} -d /usr/local && \
    rm ${PROTOC_ZIP} \
    ;; \
    esac

ENV PATH="/usr/local/bin:${PATH}"

# ----------------------------------------------------
#                                              Kubectl
# ----------------------------------------------------
RUN case "${TARGETPLATFORM}" in \
    "linux/amd64") \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256" && \
    echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/ && \
    rm kubectl.sha256 ;; \
    "linux/arm64") \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl" && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl.sha256" && \
    echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/ && \
    rm kubectl.sha256 ;; \
    esac

# ----------------------------------------------------
#                                                  K9s
# ----------------------------------------------------
RUN case "${TARGETPLATFORM}" in \
    "linux/amd64") \
    curl -sLO https://github.com/derailed/k9s/releases/download/v${K9S_VERSION}/k9s_linux_amd64.tar.gz && \
    tar -xzf k9s_linux_amd64.tar.gz -C /tmp && \
    rm k9s_linux_amd64.tar.gz && \
    mv /tmp/k9s /usr/local/bin ;;\
    "linux/arm64") \
    curl -sLO https://github.com/derailed/k9s/releases/download/v${K9S_VERSION}/k9s_linux_arm64.tar.gz && \
    tar -xzf k9s_linux_arm64.tar.gz -C /tmp && \
    rm k9s_linux_arm64.tar.gz && \
    mv /tmp/k9s /usr/local/bin ;; \
    esac

# ----------------------------------------------------
#                                                 Helm
# ----------------------------------------------------
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/v${HELM_VERSION}/scripts/get-helm-3 && \
    chmod 700 get_helm.sh && \
    ./get_helm.sh && \
    rm ./get_helm.sh

# ----------------------------------------------------
#                                                 Vault
# ----------------------------------------------------
RUN wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
RUN gpg --no-default-keyring --keyring /usr/share/keyrings/hashicorp-archive-keyring.gpg --fingerprint
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list

# Install vault
RUN apt-get update -y && apt-get install -y vault && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------
#                                    Security Tooling
# ----------------------------------------------------
# Trivy — container image vulnerability scanner (used by .ci/stages/image-scan.sh)
ARG TRIVY_VERSION=0.62.1
RUN case "${TARGETPLATFORM}" in \
    "linux/amd64") \
    curl -sfL https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz \
      | tar xzf - -C /usr/local/bin trivy ;; \
    "linux/arm64") \
    curl -sfL https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-ARM64.tar.gz \
      | tar xzf - -C /usr/local/bin trivy ;; \
    esac

# CI security tools (used by .ci/stages/)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install pip-audit detect-secrets bandit mutmut

# ----------------------------------------------------
#                                    Playwright (E2E)
# ----------------------------------------------------
# Install Chromium + system deps for E2E tests and Chrome DevTools MCP.
# Symlink to /usr/local/bin/google-chrome so chrome-devtools-mcp finds it.
RUN npx playwright install chromium && \
    npx playwright install-deps chromium && \
    CHROME_BIN=$(find /root/.cache/ms-playwright -name chrome -path '*/chrome-linux64/*' | head -1) && \
    ln -sf "$CHROME_BIN" /usr/local/bin/google-chrome

