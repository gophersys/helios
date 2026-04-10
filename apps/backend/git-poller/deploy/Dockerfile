FROM python:3.12-slim

ARG APP_VERSION=dev
ARG ENVIRONMENT=development
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_TIME=unknown
ARG BUILD_HOST=unknown

ENV APP_VERSION=${APP_VERSION} \
    ENVIRONMENT=${ENVIRONMENT} \
    GIT_COMMIT=${GIT_COMMIT} \
    GIT_BRANCH=${GIT_BRANCH} \
    BUILD_TIME=${BUILD_TIME} \
    BUILD_HOST=${BUILD_HOST}

RUN apt-get update && \
    apt-get install -y --no-install-recommends git openssh-client ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Internal CA certificates (office network)
COPY deploy/ca-certs/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

WORKDIR /app
COPY apps/backend/git-poller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/python/ /app/libs/python/
COPY apps/backend/git-poller/src/ src/

ENV PYTHONPATH="/app/src:/app/libs/python:/app/libs/protocols:/app/libs"
EXPOSE 9003

# Security: run as non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

CMD ["python3", "-u", "-m", "main"]
