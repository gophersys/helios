# syntax=docker/dockerfile:1.7
#
# images/node — Node.js toolchain (via nvm) on top of images/base.
#
# Provides: node (LTS), npm, corepack-managed yarn + pnpm. The yarn channel
# is enabled through corepack so projects can pin their own yarn version
# via `packageManager` in package.json without reinstalling node.
FROM ghcr.io/gophersys/base:latest

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="Node.js LTS via nvm, corepack-managed yarn/pnpm"

USER root

ENV NVM_DIR=/usr/local/nvm \
    NODE_VERSION=20.17.0

# nvm installed to a shared path so both the dev user and CI runner pick
# up the same toolchain. The shim-script pattern keeps PATH sane for
# non-login shells used by CI runners.
RUN mkdir -p "${NVM_DIR}" \
 && curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash \
 && . "${NVM_DIR}/nvm.sh" \
 && nvm install "${NODE_VERSION}" \
 && nvm alias default "${NODE_VERSION}" \
 && nvm use default \
 && ln -sf "${NVM_DIR}/versions/node/v${NODE_VERSION}/bin/node" /usr/local/bin/node \
 && ln -sf "${NVM_DIR}/versions/node/v${NODE_VERSION}/bin/npm"  /usr/local/bin/npm \
 && ln -sf "${NVM_DIR}/versions/node/v${NODE_VERSION}/bin/npx"  /usr/local/bin/npx \
 && corepack enable \
 && corepack prepare yarn@stable --activate \
 && corepack prepare pnpm@latest --activate \
 && node --version \
 && npm --version \
 && yarn --version \
 && pnpm --version

USER dev
WORKDIR /home/dev
