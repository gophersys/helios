# Multi-stage build to reduce final image size
FROM ubuntu:22.04 AS prisma-builder

# ----------------------------------------------------
#                                      Build Arguments
# ----------------------------------------------------
ARG NVM_VERSION=0.40.3
ARG NODE_VERSION=22.19.0
ARG NPM_VERSION=11.6.0

# ----------------------------------------------------
#                                             System
# ----------------------------------------------------
WORKDIR /

# Install minimal tools needed for Prisma generation
RUN apt-get update && \
    apt-get install -y \
    curl \
    git \
    python3 \
    python3-pip \
    openssl \
    ca-certificates \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Internal CA certificates (office network)
COPY deploy/ca-certs/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

# ----------------------------------------------------
#                                             Node, Nx
# ----------------------------------------------------
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v${NVM_VERSION}/install.sh | bash && \
    export NVM_DIR="$HOME/.nvm" && \
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && \
    nvm install v${NODE_VERSION} && \
    npm install -g npm@${NPM_VERSION} && \
    corepack enable && \
    corepack prepare yarn@4.9.4 --activate

# Set up Node.js and yarn environment
ENV NVM_DIR=/root/.nvm
ENV PATH=/root/.nvm/versions/node/v${NODE_VERSION}/bin:/root/.yarn/bin:$PATH

# ----------------------------------------------------
#                                           ORM Client
# ----------------------------------------------------
WORKDIR /concord

# Copy prisma schema and package files for client generation
COPY ./prisma/schema.prisma ./prisma/schema.prisma
COPY ./nx.json nx.json
COPY ./package.json package.json

# Install Prisma Python client generator
RUN pip3 install --no-cache-dir prisma==0.15.0

# Generate Prisma clients (both Go and Python)
# Keep working directory as /concord to maintain relative path context
WORKDIR /concord
RUN export NVM_DIR="$HOME/.nvm" && \
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && \
    cd prisma && \
    yarn && \
    yarn prisma generate

# Download Prisma query engine binary.
# prisma-client-python 0.15.0 needs a standalone query-engine binary (binary mode).
# Prisma 5.17's npm package ships only the library (.so.node) version, so we
# download the standalone binary directly from Prisma's release CDN.
# The engine hash is locked to prisma-client-python 0.15.0's expected version.
ARG PRISMA_ENGINE_HASH=393aa359c9ad4a4bb28630fb5613f9c281cde053
RUN curl -fsSL "https://binaries.prisma.sh/all_commits/${PRISMA_ENGINE_HASH}/debian-openssl-3.0.x/query-engine.gz" \
      | gunzip > /tmp/prisma-query-engine && \
    chmod +x /tmp/prisma-query-engine && \
    curl -fsSL "https://binaries.prisma.sh/all_commits/${PRISMA_ENGINE_HASH}/debian-openssl-3.0.x/schema-engine.gz" \
      | gunzip > /tmp/prisma-schema-engine && \
    chmod +x /tmp/prisma-schema-engine

# ----------------------------------------------------
#                                           Final Stage
# ----------------------------------------------------
FROM ubuntu:22.04

# ----------------------------------------------------
#                                             System
# ----------------------------------------------------
WORKDIR /

# Update and install only necessary runtime tools
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    openssl \
    git \
    openssh-client \
    ca-certificates \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Internal CA certificates (office network)
COPY deploy/ca-certs/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

# ----------------------------------------------------
#                                       Dependencies
# ----------------------------------------------------
WORKDIR /app
COPY ./apps/backend/http-api/setup.py setup.py
RUN pip3 install --no-cache-dir -e . && \
    pip3 install --no-cache-dir prisma==0.15.0

# ----------------------------------------------------
#                                       App + Libraries
# ----------------------------------------------------
WORKDIR /app
ARG CACHE_BUST=0

COPY ./libs/python /libs/python
COPY --from=prisma-builder /concord/libs/python/database /libs/python/database
COPY --from=prisma-builder /tmp/prisma-query-engine /app/prisma-query-engine-debian-openssl-3.0.x
COPY --from=prisma-builder /tmp/prisma-schema-engine /app/prisma-schema-engine-debian-openssl-3.0.x

# Pre-warm prisma nodeenv + CLI cache (avoids runtime downloads in init container)
RUN python3 -c "from prisma.cli import setup; setup()" 2>&1 || \
    python3 -m prisma version 2>&1 || true

COPY ./libs/protocols/mtib /libs/protocols/mtib

ENV PYTHONPATH="/libs:/libs/python:/libs/protocols"
ENV PRISMA_QUERY_ENGINE_BINARY="/app/prisma-query-engine-debian-openssl-3.0.x"
ENV PRISMA_SCHEMA_ENGINE_BINARY="/app/prisma-schema-engine-debian-openssl-3.0.x"

# Build metadata (injected by ctl.sh / Nx containerize)
ARG APP_VERSION=0.0.0
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG GIT_DIRTY=false
ARG BUILD_TIME=unknown
ARG BUILD_HOST=unknown
ARG ENVIRONMENT=development
ENV APP_VERSION=${APP_VERSION}
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}
ENV GIT_DIRTY=${GIT_DIRTY}
ENV BUILD_TIME=${BUILD_TIME}
ENV BUILD_HOST=${BUILD_HOST}
ENV ENVIRONMENT=${ENVIRONMENT}

# Prisma schema + migrations + seed for init container
COPY ./prisma/schema.prisma /prisma/schema.prisma
COPY ./prisma/migrations /prisma/migrations
COPY ./prisma/seed /prisma/seed

# Copy the app itself
COPY ./apps/backend/http-api/assets assets
COPY ./apps/backend/http-api/config config
COPY ./apps/backend/http-api/src src

# Copy firmware build scripts (served via /v2/builds/scripts/<product> endpoint)
COPY ./apps/firmware/products/alpha/scripts /app/firmware/products/alpha/scripts

EXPOSE 9001

# Security: run as non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
# The app needs write access to /prisma for migrations (init container) and /app for runtime
RUN chown -R appuser:appgroup /app /prisma
USER appuser

CMD ["python3", "-u", "src/main.py"]