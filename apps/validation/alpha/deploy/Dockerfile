# Alpha Validation Test Runner
#
# Standalone container for running validation tests in K8s.
# Firmware artifacts are fetched from MinIO via PIPELINE_ID env var.
#
# Build:
#   npx nx build validation-alpha -c staging
#
# Push:
#   npx nx push validation-alpha -c staging
#
# Trigger:
#   POST /v2/validation/runs with pipeline_id, mtib_address, device_snr

FROM ubuntu:22.04

# ─────────────────────────────────────────────────────────────────────────────
# System Dependencies
# ─────────────────────────────────────────────────────────────────────────────

WORKDIR /

RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    iputils-ping \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────────────────
# Python Dependencies (cached layer)
# ─────────────────────────────────────────────────────────────────────────────

WORKDIR /app

# Install dependencies first (cache-friendly)
COPY apps/validation/alpha/setup.py setup.py
RUN pip3 install -e . && \
    pip3 install pytest-timeout>=2.0.0 && \
    pip3 cache purge

# ─────────────────────────────────────────────────────────────────────────────
# Libraries (shared with http-api)
# ─────────────────────────────────────────────────────────────────────────────

# gRPC protocols for MTIB
COPY libs/protocols/mtib /libs/protocols/mtib
COPY libs/protocols/mtib_v2 /libs/protocols/mtib_v2

# Python libraries
COPY libs/python /libs/python

# Set PYTHONPATH
ENV PYTHONPATH="/app:/libs:/libs/python:/libs/protocols"

# ─────────────────────────────────────────────────────────────────────────────
# Validation App
# ─────────────────────────────────────────────────────────────────────────────

WORKDIR /app

# Test infrastructure
COPY apps/validation/alpha/conftest.py conftest.py
COPY apps/validation/alpha/pytest.ini pytest.ini
COPY apps/validation/alpha/catalog.yaml catalog.yaml
COPY apps/validation/alpha/run.py run.py

# Test code
COPY apps/validation/alpha/tests tests
COPY apps/validation/alpha/fixtures fixtures

# Modem firmware (only asset not in pipeline builds)
COPY apps/manufacturing/alpha/assets/mfw_nrf91x1_2.0.2.zip /app/firmware/modem/mfw_nrf91x1_2.0.2.zip

# ─────────────────────────────────────────────────────────────────────────────
# Build Metadata
# ─────────────────────────────────────────────────────────────────────────────

ARG APP_VERSION=0.0.0
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_TIME=unknown
ARG ENVIRONMENT=development

ENV APP_VERSION=${APP_VERSION}
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}
ENV BUILD_TIME=${BUILD_TIME}
ENV ENVIRONMENT=${ENVIRONMENT}

# ─────────────────────────────────────────────────────────────────────────────
# Runtime
# ─────────────────────────────────────────────────────────────────────────────

# Default stage (can be overridden via env var or CMD)
ENV STAGE=gate

# Artifacts directory
ENV ARTIFACTS_DIR=/var/log/validation

# Entry point: ValidationRunner with preflight, reporting, artifacts
#
# Environment variables (set by K8s Job template):
#   STAGE                 - Test stage (gate, nightly, integration, smoke)
#   CONCORD_RUN_ID        - Validation run ID for reporting
#   CONCORD_API_URL       - Concord API base URL
#   CONCORD_API_KEY       - API key for reporting
#   PIPELINE_ID           - CI pipeline ID (for firmware artifacts)
#   MTIB_ADDRESS          - MTIB server address (host:port)
#   DEVICE_SNR            - J-Link probe serial number
#   DEVICE_ID             - Device ID hex string
#   FIXTURE_PROFILE_PATH  - Path to fixture profile JSON
#   VAL_1_0_API_*         - CoreCloud API credentials

CMD ["python3", "run.py"]
