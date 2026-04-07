FROM python:3.12-slim

# Build metadata (injected by Nx containerize / ctl.sh)
ARG APP_VERSION=dev
ARG ENVIRONMENT=development
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_TIME=unknown
ARG BUILD_HOST=unknown

# Orchestrator dependencies: git (clone repos), docker CLI (spawn builder
# containers), openssh-client (SSH auth for Bitbucket)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git openssh-client ca-certificates curl gnupg && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Context is monorepo root (set by project.json containerize target)
COPY apps/backend/build-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/python/ /app/libs/python/
COPY apps/backend/build-service/sdk/ /app/sdk/
COPY apps/backend/build-service/src/ src/

# Build metadata as env vars (for /health endpoint introspection)
ENV APP_VERSION=${APP_VERSION} \
    ENVIRONMENT=${ENVIRONMENT} \
    GIT_COMMIT=${GIT_COMMIT} \
    GIT_BRANCH=${GIT_BRANCH} \
    BUILD_TIME=${BUILD_TIME} \
    BUILD_HOST=${BUILD_HOST} \
    PYTHONPATH=/app/src:/app/libs/python

EXPOSE 9002

CMD ["python3", "-u", "-m", "src.main"]
