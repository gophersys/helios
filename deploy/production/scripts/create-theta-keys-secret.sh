#!/bin/bash
# Create theta-mcuboot-keys K8s secret using Alpha's encryption keys
# Run this from a machine with kubectl access to the staging cluster

set -e

NAMESPACE="${1:-staging}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Alpha keys location (use same keys for FUOTA compatibility)
ALPHA_KEYS_DIR="${REPO_ROOT}/apps/firmware/products/alpha/alpha_mfg_fw"

if [ ! -f "${ALPHA_KEYS_DIR}/encryption_key.pem" ]; then
    echo "ERROR: Alpha encryption_key.pem not found at ${ALPHA_KEYS_DIR}"
    exit 1
fi

if [ ! -f "${ALPHA_KEYS_DIR}/comms_encryption_key.pem" ]; then
    echo "ERROR: Alpha comms_encryption_key.pem not found at ${ALPHA_KEYS_DIR}"
    exit 1
fi

echo "Creating theta-mcuboot-keys secret in namespace: ${NAMESPACE}"
echo "Using keys from: ${ALPHA_KEYS_DIR}"

kubectl create secret generic theta-mcuboot-keys \
    --namespace="${NAMESPACE}" \
    --from-file=encryption_key.pem="${ALPHA_KEYS_DIR}/encryption_key.pem" \
    --from-file=comms_encryption_key.pem="${ALPHA_KEYS_DIR}/comms_encryption_key.pem" \
    --dry-run=client -o yaml | kubectl apply -f -

echo "Secret created successfully!"
kubectl get secret theta-mcuboot-keys -n "${NAMESPACE}" -o jsonpath='{.data}' | jq -r 'keys[]'
