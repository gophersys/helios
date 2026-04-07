# Concord Validation Runner
#
# Generic test runner that downloads product-specific test packages from
# MinIO at startup. The test code is NOT baked into this image — it's
# downloaded at runtime based on the TEST_PACKAGE_VERSION env var.
#
# This image contains:
#   - Python 3.10 + pytest
#   - corekinect framework (test, hardware, cloud, protocols)
#   - corectl CLI
#   - gRPC + protobuf runtime
#
# Environment variables (set by K8s Job):
#   PRODUCT_SLUG          - Product identifier (e.g., "alpha_b0")
#   TEST_PACKAGE_VERSION  - Test package version to download (e.g., "1.2.0" or "dev-abc12345")
#   CONCORD_API_URL       - Concord API for downloading test packages
#   CONCORD_API_KEY       - API key for auth
#   STAGE                 - Validation stage to run (smoke, nightly, fuota)
#   CONCORD_RUN_ID        - Session ID for result reporting
#   MTIB_ADDRESS          - MTIB server address
#   DEVICE_SNR            - Device serial number
#   PIPELINE_ID           - Build pipeline ID (for firmware artifacts)

FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    iputils-ping \
    curl \
    ca-certificates \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install corekinect framework ──
COPY libs/protocols/mtib /libs/protocols/mtib
COPY libs/python /libs/python
ENV PYTHONPATH="/app:/libs:/libs/python:/libs/protocols"

# ── Install corectl CLI ──
COPY tools/corectl /tmp/corectl
RUN pip3 install /tmp/corectl && rm -rf /tmp/corectl

# ── Install Python dependencies ──
COPY deploy/runner/requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt \
    && pip3 cache purge

# ── Entrypoint: download test package and run ──
COPY deploy/runner/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ARG APP_VERSION=0.0.0
ENV APP_VERSION=${APP_VERSION}
ENV STAGE=fuota
ENV ARTIFACTS_DIR=/var/log/validation

ENTRYPOINT ["/app/entrypoint.sh"]
