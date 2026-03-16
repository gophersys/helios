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
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

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
RUN pip3 install prisma==0.15.0

# Generate Prisma clients (both Go and Python)
# Keep working directory as /concord to maintain relative path context
WORKDIR /concord
RUN export NVM_DIR="$HOME/.nvm" && \
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && \
    cd prisma && \
    yarn && \
    yarn prisma generate

# Download Prisma query engine binary
RUN cd prisma && prisma py fetch

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
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------
#                                                  App
# ----------------------------------------------------

# By installing these first you save a lot of time when making changes to the source code
# and rebuilding the application
WORKDIR /app
COPY ./apps/backend/http-api/setup.py setup.py
RUN pip3 install -e . && \
    pip3 install prisma==0.15.0 && \
    pip3 cache purge

# Copy the generated Prisma client from the builder stage
COPY --from=prisma-builder /concord/libs/python/database /libs/python/database

# Copy Prisma binaries directly from monorepo node_modules
COPY ./node_modules/prisma/query-engine-debian-openssl-3.0.x /app/prisma-query-engine-debian-openssl-3.0.x
COPY ./node_modules/prisma/libquery_engine-debian-openssl-3.0.x.so.node /app/libquery_engine-debian-openssl-3.0.x.so.node

# Make binaries executable
RUN chmod +x /app/prisma-query-engine-debian-openssl-3.0.x && \
    chmod +x /app/libquery_engine-debian-openssl-3.0.x.so.node

# ----------------------------------------------------
#                                               App
# ----------------------------------------------------
WORKDIR /app

# Copy the Python libraries used by the app
COPY ./libs/python /libs/python

# Copy the protocols used by the app
COPY ./libs/protocols/mtib /libs/protocols/mtib

# Set the PYTHONPATH to include the libs directory
ENV PYTHONPATH="/libs:/libs/python:/libs/protocols"

# Set Prisma binary cache directory
ENV PRISMA_BINARY_CACHE_DIR="/root/.cache/prisma-python/binaries"

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

# Prisma schema + migrations for init container migration
COPY ./prisma/schema.prisma /prisma/schema.prisma
COPY ./prisma/migrations /prisma/migrations

# Copy the app itself
COPY ./apps/backend/http-api/assets assets
COPY ./apps/backend/http-api/config config
COPY ./apps/backend/http-api/src src

# Copy firmware build scripts (served via /v2/builds/scripts/<product> endpoint)
COPY ./apps/firmware/products/alpha/scripts /app/firmware/products/alpha/scripts

# Keep the container running
CMD ["python3", "src/main.py"]