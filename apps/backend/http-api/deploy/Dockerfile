# Multi-stage build to reduce final image size
FROM node:22-bookworm AS prisma-builder

# ----------------------------------------------------
#                                             System
# ----------------------------------------------------
WORKDIR /

# Install tools needed for Prisma generation
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    openssl \
    ca-certificates \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Internal CA certificates (office network)
COPY deploy/ca-certs/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

# Enable corepack for yarn
RUN corepack enable && corepack prepare yarn@4.9.4 --activate

# ----------------------------------------------------
#                                           ORM Client
# ----------------------------------------------------
WORKDIR /concord

# Copy prisma schema and package files for client generation
COPY ./prisma/schema.prisma ./prisma/schema.prisma
COPY ./nx.json nx.json
COPY ./package.json package.json

# Install Prisma Python client generator
RUN pip3 install --no-cache-dir --break-system-packages prisma==0.15.0

# Generate Prisma clients (both Go and Python)
# Keep working directory as /concord to maintain relative path context
WORKDIR /concord
RUN cd prisma && \
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

# Standalone Prisma CLI install (resolves all deps into one flat tree).
# Used by the init container to run migrations — no Yarn PnP, no nodeenv.
RUN npm install --prefix /prisma-standalone prisma@5.17.0

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
    curl \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Docker CLI — needed by DockerExecutor to spawn test runner containers
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
    | tar xz --strip-components=1 -C /usr/local/bin docker/docker

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

# Copy Node.js + Prisma CLI from the builder stage for database migrations.
# The init container runs `node /app/prisma-cli/build/index.js migrate deploy`
# directly — bypasses prisma-client-python's nodeenv entirely.
# No internet needed, no cache dirs, no user permission issues.
# Copy Node.js + standalone Prisma CLI for database migrations.
# Init container runs: node /app/prisma-cli/node_modules/prisma/build/index.js
# No prisma-python nodeenv, no internet, no cache permissions.
COPY --from=prisma-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=prisma-builder /prisma-standalone/node_modules /app/prisma-cli/node_modules

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

EXPOSE 9001

# Security: run as non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
# The app needs write access to /prisma for migrations (init container) and /app for runtime
RUN chown -R appuser:appgroup /app /prisma
USER appuser

CMD ["python3", "-u", "src/main.py"]