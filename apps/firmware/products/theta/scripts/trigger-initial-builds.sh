#!/bin/bash
# Trigger initial Theta firmware builds via Concord API
# Run this after deploying to staging to seed the build artifacts
#
# Usage:
#   CONCORD_API_URL=https://staging.concord.local CONCORD_API_KEY=ck_xxx ./trigger-initial-builds.sh
#
# This creates pipelines (like the git poller does) which spawn multiple builds:
#   - theta_fw: release + debug variants (nrf52840 + nrf9160)
#   - theta_mfg_fw: mfg variant

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Config
API_URL="${CONCORD_API_URL:-http://localhost:9001}"
API_KEY="${CONCORD_API_KEY:-}"

if [ -z "$API_KEY" ]; then
    echo -e "${RED}Error: CONCORD_API_KEY not set${NC}"
    echo "Usage: CONCORD_API_KEY=ck_xxx ./trigger-initial-builds.sh"
    exit 1
fi

# Get latest commit SHA from theta_fw
echo -e "${CYAN}Fetching latest commit SHA from theta_fw...${NC}"
COMMIT_SHA=$(git ls-remote git@bitbucket.org:corekinect/theta_fw.git refs/heads/main | cut -f1)
if [ -z "$COMMIT_SHA" ]; then
    echo -e "${RED}Failed to get commit SHA${NC}"
    exit 1
fi
echo "Latest commit: ${COMMIT_SHA:0:8}"

# Pipeline configurations to trigger
PIPELINES=(
    # Production firmware pipeline (theta_fw)
    "{\"product\":\"theta_fw\",\"board\":\"theta_c0\",\"branch\":\"main\",\"commitSha\":\"$COMMIT_SHA\",\"triggerType\":\"manual\",\"buildVariant\":\"debug\",\"name\":\"Theta FW Initial Build\"}"
    # Manufacturing firmware pipeline (theta_mfg_fw)
    "{\"product\":\"theta_mfg_fw\",\"board\":\"theta_c0\",\"branch\":\"main\",\"triggerType\":\"manual\",\"name\":\"Theta MFG FW Initial Build\"}"
)

echo -e "\n${CYAN}Triggering initial Theta pipelines...${NC}"
echo "API URL: $API_URL"

for pipeline_json in "${PIPELINES[@]}"; do
    product=$(echo "$pipeline_json" | jq -r '.product')
    board=$(echo "$pipeline_json" | jq -r '.board')

    echo -e "\n${CYAN}Creating pipeline: ${product} (${board})${NC}"

    response=$(curl -s -k -X POST "${API_URL}/v2/ci/pipelines" \
        -H "Authorization: Bearer ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$pipeline_json")

    # Check response
    if echo "$response" | jq -e '.data.id' > /dev/null 2>&1; then
        pipeline_id=$(echo "$response" | jq -r '.data.id')
        expected=$(echo "$response" | jq -r '.data.expectedBuilds // "?"')
        echo -e "${GREEN}Created pipeline: ${pipeline_id} (${expected} builds)${NC}"
    else
        error=$(echo "$response" | jq -r '.errors[0] // .error // "Unknown error"')
        echo -e "${RED}Failed: ${error}${NC}"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi
done

echo -e "\n${GREEN}Done! Check pipeline status at ${API_URL}/ci/pipelines${NC}"
echo -e "${YELLOW}Note: Builds will be picked up by the build worker (DaemonSet on build nodes)${NC}"
echo -e ""
echo -e "${YELLOW}IMPORTANT: Before builds can succeed, encryption keys must be added to Bitbucket repos:${NC}"
echo -e "${YELLOW}  - theta_mfg_fw: Add encryption_key.pem and comms_encryption_key.pem to repo root${NC}"
echo -e "${YELLOW}  - theta_fw: Add comms_encryption_key.pem to repo root${NC}"
echo -e "${YELLOW}  Use the same keys as Alpha for FUOTA compatibility${NC}"
