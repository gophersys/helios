# providers/state-backend

**Where Terraform state lives.** Every other provider's Terraform root
modules use a backend declared here.

## Default

OCI Object Storage (pre-existing bucket `brain-terraform-state`). Chosen
because:
- OCI Always-Free tier includes 20 GB Object Storage (plenty for state).
- S3-compatible API works with Terraform's `s3` backend via
  `endpoint` override.
- Isolated from any single cluster's blast radius.

## Contents

When populated, this directory will hold:
- `backend.tf` snippets to be included by consumer modules.
- Per-environment backend configs (`app-prod.hcl`, `lab.hcl`, etc.)
  declaring the state key path.
- Bootstrap scripts to (re-)create the bucket if ever lost.

## Locking

OCI Object Storage does not support DynamoDB-style locking natively. We use
OCI's built-in conditional object PUT for a crude lock — see bootstrap
notes when populated.

## Status

STUB. The bucket exists (from legacy infra); the module wrappers need to
be written.
