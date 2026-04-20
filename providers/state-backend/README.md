# providers/state-backend

Terraform remote state backend for every infrastructure module in the
brain ecosystem. Stored in **OCI Object Storage** via its
S3-compatible API — no Terraform Cloud, no AWS S3, no local state.

- **Bucket:** `gophersys-tfstate`
- **Namespace:** `ax0uzamxfteg`
- **Region:** `us-phoenix-1`
- **Endpoint:**
  `https://ax0uzamxfteg.compat.objectstorage.us-phoenix-1.oraclecloud.com`
- **Auth:** OCI Customer Secret Key (S3-compat credentials), sourced
  from BW item `OCI S3 Customer Secret Key (Terraform State)` and
  presented to terraform as `AWS_ACCESS_KEY_ID` +
  `AWS_SECRET_ACCESS_KEY` env vars.
- **Locking:** terraform-1.10+ S3-native lockfile (`use_lockfile =
  true` in backend.hcl). No DynamoDB dependency.

## Lifecycle

- **Bootstrap (one-shot):** `bash ./ctl.sh bootstrap` creates the
  bucket via `oci-cli`. Idempotent — no-op if the bucket already
  exists. Gated (mutating).
- **Use:** consuming modules pin this file via
  `terraform init -backend-config=<path-to>/backend.hcl -backend-config=key=<module-path>/terraform.tfstate`.
  The `backend.hcl` at this directory's root is the source of truth.
- **Destroy:** `bash ./ctl.sh destroy --force` tears down the bucket
  (refuses without `--force`, and even then only when empty). Almost
  never the right move.

## Key convention

Every consumer emits its state at a path that mirrors the module's
location in the repo. E.g.:

| Module | State key |
|---|---|
| `providers/oracle/modules/compute` | `providers/oracle/compute/terraform.tfstate` |
| `providers/aws/modules/compute`    | `providers/aws/compute/terraform.tfstate` |
| `clusters/instances/prod`          | `clusters/prod/terraform.tfstate` |

Path-keyed, flat, predictable. No env suffix in the key — the bucket
is shared across environments; modules targeting specific environments
(staging, lab) simply use a different state key.

## How consumers wire it

```hcl
terraform {
  backend "s3" {}   # values supplied at init via -backend-config
}
```

Init:

```bash
# from the consuming module's directory
terraform init \
  -backend-config=../../state-backend/backend.hcl \
  -backend-config=key=providers/oracle/compute/terraform.tfstate
```

Required env before running terraform (typically loaded from the
`secrets-load` ctl.sh verb in consumer projects):

- `AWS_ACCESS_KEY_ID`     — OCI Customer Secret Key access key id
- `AWS_SECRET_ACCESS_KEY` — OCI Customer Secret Key secret

## Verbs

| Verb | Meaning | Mutates |
|---|---|---|
| `status` | Check bucket reachability + object count. | no |
| `info` | Print `backend.hcl` + usage snippet. | no |
| `validate` | Shellcheck + syntactic validation of backend.hcl. | no |
| `fmt` | `terraform fmt` on any .tf/.hcl files. | yes (in-place) |
| `bootstrap` | Create the bucket if missing. | yes |
| `destroy` | Delete the bucket (requires `--force`, only if empty). | yes |
| `help` | Usage. | no |

## Why OCI Object Storage

- Already where most compute lives (OCI Phoenix).
- Free tier covers the state workload (<1 GB expected).
- S3-compatible, so terraform's canonical `s3` backend works out of
  the box; no Terraform Cloud dependency.
- No third-party hosting of our infrastructure state.
- Native locking via terraform 1.10+ `use_lockfile = true` —
  DynamoDB not required.

## Migration from legacy `code-kit-tfstate`

A legacy bucket `code-kit-tfstate` exists in the same compartment from
the previous infrastructure lineage. It is NOT consumed by any module
in this tree. Leave it in place until explicitly decommissioned; new
modules always point at `gophersys-tfstate`.
