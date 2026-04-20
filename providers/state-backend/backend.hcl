# backend.hcl — OCI Object Storage (S3-compat) remote backend config.
#
# Consumed by every terraform module that stores state in this backend:
#
#   terraform init \
#     -backend-config=<path-to-this-file> \
#     -backend-config=key=<module-path>/terraform.tfstate
#
# Credentials are supplied via AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
# env vars (sourced from the BW item "OCI S3 Customer Secret Key
# (Terraform State)" at runtime; never committed to git).

bucket = "gophersys-tfstate"
region = "us-phoenix-1"

endpoints = {
  s3 = "https://ax0uzamxfteg.compat.objectstorage.us-phoenix-1.oraclecloud.com"
}

# OCI's S3-compat endpoint doesn't match AWS's signature-validation or
# metadata conventions; skip every implicit AWS-specific handshake.
skip_credentials_validation = true
skip_region_validation      = true
skip_metadata_api_check     = true
skip_requesting_account_id  = true
skip_s3_checksum            = true
use_path_style              = true

# Terraform-1.10+ native locking via a sibling lockfile object in the
# bucket — no DynamoDB / no extra infra needed. Stops concurrent
# apply/plan from corrupting state.
use_lockfile = true
