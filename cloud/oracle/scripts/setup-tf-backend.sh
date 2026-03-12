#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# setup-tf-backend.sh — Create OCI Object Storage bucket for Terraform state
#
# Creates a free-tier Object Storage bucket and Customer Secret Key for
# S3-compatible access, then generates the backend.tf file.
#
# Prerequisites:
#   - OCI CLI configured (~/.oci/config)
#   - OCI_COMPARTMENT_OCID set (or in .env)
#   - OCI_TENANCY_OCID set (or in .env)
#   - OCI_USER_OCID set (or in .env)
#
# Usage:
#   ./setup-tf-backend.sh              # create bucket + generate backend.tf
#   ./setup-tf-backend.sh --status     # check if bucket exists
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ORACLE_DIR}/.env"

BUCKET_NAME="infra-tfstate"
TF_DIR="${ORACLE_DIR}/terraform"
BACKEND_FILE="${TF_DIR}/backends/backend.tf"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { printf "[tf-backend] %s\n" "$*"; }
ok()    { printf "[tf-backend] %s\n" "$*"; }
warn()  { printf "[tf-backend] WARN: %s\n" "$*"; }
die()   { printf "[tf-backend] ERROR: %s\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Load env
# ---------------------------------------------------------------------------
if [[ -z "${OCI_TENANCY_OCID:-}" && -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

[[ -z "${OCI_TENANCY_OCID:-}" ]] && die "OCI_TENANCY_OCID not set"
[[ -z "${OCI_COMPARTMENT_OCID:-}" ]] && die "OCI_COMPARTMENT_OCID not set"
[[ -z "${OCI_USER_OCID:-}" ]] && die "OCI_USER_OCID not set"

REGION="${OCI_REGION:-us-phoenix-1}"

# ---------------------------------------------------------------------------
# Get Object Storage namespace (required for S3 endpoint)
# ---------------------------------------------------------------------------
get_namespace() {
    oci os ns get --query 'data' --raw-output 2>/dev/null \
        || die "Failed to get Object Storage namespace"
}

# ---------------------------------------------------------------------------
# Check if bucket exists
# ---------------------------------------------------------------------------
bucket_exists() {
    oci os bucket get \
        --namespace-name "$1" \
        --bucket-name "${BUCKET_NAME}" \
        &>/dev/null
}

# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--status" ]]; then
    NS=$(get_namespace)
    if bucket_exists "${NS}"; then
        ok "Bucket '${BUCKET_NAME}' exists in namespace '${NS}'"
        if [[ -f "${BACKEND_FILE}" ]]; then
            ok "backend.tf exists at ${BACKEND_FILE}"
        else
            warn "backend.tf not found — run without --status to generate"
        fi
    else
        warn "Bucket '${BUCKET_NAME}' does not exist"
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 1: Get namespace
# ---------------------------------------------------------------------------
info "Getting Object Storage namespace..."
NAMESPACE=$(get_namespace)
ok "Namespace: ${NAMESPACE}"

# ---------------------------------------------------------------------------
# Step 2: Create bucket (idempotent)
# ---------------------------------------------------------------------------
if bucket_exists "${NAMESPACE}"; then
    ok "Bucket '${BUCKET_NAME}' already exists"
else
    info "Creating bucket '${BUCKET_NAME}'..."
    oci os bucket create \
        --compartment-id "${OCI_COMPARTMENT_OCID}" \
        --namespace-name "${NAMESPACE}" \
        --name "${BUCKET_NAME}" \
        --storage-tier Standard \
        --versioning Enabled \
        --query 'data.name' \
        --raw-output 2>/dev/null \
        || die "Failed to create bucket"
    ok "Bucket created with versioning enabled"
fi

# ---------------------------------------------------------------------------
# Step 3: Create Customer Secret Key for S3-compatible access
# ---------------------------------------------------------------------------
info "Creating S3-compatible credentials..."

# Check for existing key
EXISTING_KEY=$(oci iam customer-secret-key list \
    --user-id "${OCI_USER_OCID}" \
    --query "data[?\"display-name\"=='terraform-state'].id | [0]" \
    --raw-output 2>/dev/null || echo "")

# Ensure backends directory exists
mkdir -p "$(dirname "${BACKEND_FILE}")"

if [[ -n "${EXISTING_KEY}" && "${EXISTING_KEY}" != "null" ]]; then
    warn "Customer Secret Key 'terraform-state' already exists"
    warn "If you need new credentials, delete the existing key first in OCI Console"
    warn "Skipping credential generation — update backend.tf manually if needed"

    if [[ ! -f "${BACKEND_FILE}" ]]; then
        S3_ENDPOINT="https://${NAMESPACE}.compat.objectstorage.${REGION}.oraclecloud.com"
        cat > "${BACKEND_FILE}" <<EOF
# Auto-generated by setup-tf-backend.sh
# S3 credentials must be added manually (existing key found)
terraform {
  backend "s3" {
    endpoint = "${S3_ENDPOINT}"
    bucket   = "${BUCKET_NAME}"
    key      = "oracle/terraform.tfstate"
    region   = "${REGION}"

    # Add your Customer Secret Key credentials here
    access_key = "REPLACE_WITH_ACCESS_KEY"
    secret_key = "REPLACE_WITH_SECRET_KEY"

    skip_region_validation      = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}
EOF
        warn "backend.tf generated with placeholder credentials"
    fi
else
    # Create new key
    KEY_RESPONSE=$(oci iam customer-secret-key create \
        --user-id "${OCI_USER_OCID}" \
        --display-name "terraform-state" \
        --output json 2>/dev/null) \
        || die "Failed to create Customer Secret Key"

    ACCESS_KEY=$(echo "${KEY_RESPONSE}" | jq -r '.data.id')
    SECRET_KEY=$(echo "${KEY_RESPONSE}" | jq -r '.data.key')

    [[ -z "${ACCESS_KEY}" || "${ACCESS_KEY}" == "null" ]] && die "Empty access key"
    [[ -z "${SECRET_KEY}" || "${SECRET_KEY}" == "null" ]] && die "Empty secret key"

    ok "S3 credentials created"

    # ---------------------------------------------------------------------------
    # Step 4: Generate backend.tf
    # ---------------------------------------------------------------------------
    S3_ENDPOINT="https://${NAMESPACE}.compat.objectstorage.${REGION}.oraclecloud.com"

    cat > "${BACKEND_FILE}" <<EOF
# Auto-generated by setup-tf-backend.sh — do not commit credentials
# Access key and secret key are OCI Customer Secret Keys for S3-compatible access
terraform {
  backend "s3" {
    endpoint = "${S3_ENDPOINT}"
    bucket   = "${BUCKET_NAME}"
    key      = "oracle/terraform.tfstate"
    region   = "${REGION}"

    access_key = "${ACCESS_KEY}"
    secret_key = "${SECRET_KEY}"

    skip_region_validation      = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}
EOF

    ok "backend.tf written to ${BACKEND_FILE}"

    echo ""
    warn "IMPORTANT: backend.tf contains secrets — it is gitignored"
    warn "Save these credentials securely:"
    echo "  Access Key: ${ACCESS_KEY}"
    echo "  Secret Key: ${SECRET_KEY}"
    echo ""
    info "To migrate existing state: cd ${TF_DIR} && terraform init -migrate-state"
fi

echo ""
ok "Terraform backend ready — OCI Object Storage (free tier)"
ok "  Bucket: ${BUCKET_NAME}"
ok "  Region: ${REGION}"
ok "  Endpoint: https://${NAMESPACE}.compat.objectstorage.${REGION}.oraclecloud.com"
