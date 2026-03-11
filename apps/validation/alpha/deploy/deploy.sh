#!/bin/bash
# Build, push, and optionally trigger validation tests
#
# Usage:
#   ./deploy.sh                    # Build + push staging image
#   ./deploy.sh --trigger          # Also trigger a test run via API
#   ./deploy.sh --production       # Build + push production image
#
# Prerequisites:
#   - Docker logged into containers.ad.corekinect.com
#   - kubectl configured for staging/production cluster
#   - CONCORD_API_KEY env var set (for --trigger)
#
# After push, the image is available for K8s Jobs created by:
#   POST /v2/validation/runs/<run_id>/trigger

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

cd "$REPO_ROOT"

# Parse args
ENV="staging"
TRIGGER=false

for arg in "$@"; do
    case $arg in
        --production)
            ENV="production"
            shift
            ;;
        --trigger)
            TRIGGER=true
            shift
            ;;
        *)
            ;;
    esac
done

IMAGE="containers.ad.corekinect.com/concord-validation-alpha:$ENV"

echo "=================================="
echo "Alpha Validation Deploy"
echo "=================================="
echo "Environment: $ENV"
echo "Image:       $IMAGE"
echo ""

# Step 1: Build
echo "Building image..."
npx nx build validation-alpha -c "$ENV"

# Step 2: Push
echo "Pushing image..."
npx nx push validation-alpha -c "$ENV"

echo ""
echo "Image pushed: $IMAGE"
echo ""

# Step 3: Trigger (optional)
if [ "$TRIGGER" = true ]; then
    echo "Triggering test run..."

    if [ -z "$CONCORD_API_KEY" ]; then
        echo "ERROR: CONCORD_API_KEY not set"
        exit 1
    fi

    API_URL="${CONCORD_API_URL:-https://staging.concord.local}"

    # This would create a run and trigger it
    # For now, just print instructions
    echo ""
    echo "To trigger a validation run:"
    echo ""
    echo "1. Create a run:"
    echo "   curl -X POST $API_URL/v2/validation/runs \\"
    echo "     -H 'Authorization: ApiKey \$CONCORD_API_KEY' \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"name\":\"Gate test\",\"productId\":\"...\",\"nodeId\":\"...\",\"serialNumber\":\"0964\"}'"
    echo ""
    echo "2. Trigger the run:"
    echo "   curl -X POST $API_URL/v2/validation/runs/<RUN_ID>/trigger \\"
    echo "     -H 'Authorization: ApiKey \$CONCORD_API_KEY' \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"firmwareVersion\":\"0.5.0\",\"pipelineId\":\"...\",\"stage\":\"gate\"}'"
fi

echo ""
echo "Done!"
