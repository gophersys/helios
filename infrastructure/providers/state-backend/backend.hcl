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

# State locking is DISABLED — OCI's S3-compat API returns HTTP 501
# "AWS chunked encoding not supported" on the PUT that terraform
# issues to take a lock. Single-operator context makes the risk of
# concurrent mutation minimal. If we ever want locking back, options
# are: (1) a DynamoDB-compat offering, (2) a wrapper script that
# oci-cli's conditional-put works around the chunked-encoding
# mismatch. Tracked as a follow-up.
# use_lockfile = true
