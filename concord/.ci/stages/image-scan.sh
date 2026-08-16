#!/usr/bin/env bash
# Container image vulnerability scanning.
# Gate: fails if HIGH or CRITICAL CVEs found in built images.
# Requires: trivy (https://aquasecurity.github.io/trivy/)
# Install: curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

log_stage "image-scan — container vulnerability analysis"

# Check if trivy is available
if ! command -v trivy &>/dev/null; then
  log_warn "trivy not installed — skipping image scan"
  log_info "Install: curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
  log_stage_end
  exit 0
fi

FAILED=false

# Images to scan (must be built first)
IMAGES=(
  "concord/http-api:latest"
  "concord/git-poller:latest"
  "concord/build-service:latest"
  "concord/frontend:latest"
)

for image in "${IMAGES[@]}"; do
  # Skip images that don't exist locally
  if ! docker image inspect "$image" &>/dev/null; then
    log_info "Image $image not found locally — skipping"
    continue
  fi

  log_info "Scanning $image..."
  if ! trivy image \
      --severity HIGH,CRITICAL \
      --exit-code 1 \
      --no-progress \
      --ignore-unfixed \
      "$image" 2>&1; then
    log_error "Vulnerabilities found in $image"
    FAILED=true
  else
    log_ok "$image — clean"
  fi
done

if $FAILED; then
  log_error "Image scan FAILED — fix or update base images"
  exit 1
fi

log_stage_end
