#!/bin/bash
set -euo pipefail

echo "=== Helios Agent Runtime ==="
echo "Starting OMP agent runtime..."

# Verify OMP is available
if ! command -v omp &>/dev/null; then
    echo "ERROR: omp binary not found"
    exit 1
fi

OMP_VERSION=$(omp --version 2>/dev/null || echo "unknown")
echo "OMP version: $OMP_VERSION"

# Create required directories
mkdir -p "${OMP_AGENT_DIR:-/etc/omp/agent}"
mkdir -p "${OMP_PROJECT_DIR:-/etc/omp/project}"
mkdir -p /var/lib/omp/sessions
mkdir -p /var/lib/omp/reports

# Copy default config if not present
if [ ! -f "${OMP_AGENT_DIR}/config.yml" ] && [ -f /etc/omp/project/config.yml ]; then
    cp /etc/omp/project/config.yml "${OMP_AGENT_DIR}/config.yml"
fi

# Export any env file credentials
if [ -f "${OMP_AGENT_DIR}/.env" ]; then
    set -a
    source "${OMP_AGENT_DIR}/.env"
    set +a
fi

echo "Agent runtime configuration:"
echo "  Agent dir: ${OMP_AGENT_DIR}"
echo "  Project dir: ${OMP_PROJECT_DIR}"
echo "  Port: ${PORT:-8080}"

# Start the Go agent runtime
exec agentd