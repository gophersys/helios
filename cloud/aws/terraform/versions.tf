terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state in the same OCI Object Storage bucket as Oracle infra.
  # Separate key to avoid collisions.
  # To use a different backend (S3, local, etc.), replace this block.
  backend "s3" {
    # Configured via backend.tf (gitignored) — see setup instructions in README
    # or pass -backend-config flags to `terraform init`.
    skip_region_validation = true
  }
}
