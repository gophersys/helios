# providers/state-backend

The Terraform remote state backend for every infrastructure module in the brain
ecosystem. The state is stored in **OCI Object Storage**, through its
S3-compatible API. There is no Terraform Cloud, no AWS S3 and no local state.

- **Bucket:** `gophersys-tfstate`
- **Namespace:** `ax0uzamxfteg`
- **Region:** `us-phoenix-1`
- **Endpoint:**
  `https://ax0uzamxfteg.compat.objectstorage.us-phoenix-1.oraclecloud.com`
- **Auth:** an OCI Customer Secret Key (S3-compatible credentials). It comes from
  the Bitwarden item `OCI S3 Customer Secret Key (Terraform State)`, and
  terraform receives it as the env vars `AWS_ACCESS_KEY_ID` and
  `AWS_SECRET_ACCESS_KEY`.
- **Locking:** the S3-native lockfile of terraform 1.10 or later
  (`use_lockfile = true` in backend.hcl). There is no dependency on DynamoDB.

## Lifecycle

- **Bootstrap, one time:** `bash ./ctl.sh bootstrap` creates the bucket with
  `oci-cli`. It is idempotent and does nothing if the bucket exists. It is a
  gated verb, because it mutates.
- **Use:** a consuming module pins this file with
  `terraform init -backend-config=<path-to>/backend.hcl -backend-config=key=<module-path>/terraform.tfstate`.
  The `backend.hcl` at the root of this directory is the source of truth.
- **Destroy:** `bash ./ctl.sh destroy --force` deletes the bucket. It refuses
  without `--force`, and even with `--force` it acts only when the bucket is
  empty. This is almost never the correct action.

## Key convention

Every consumer writes its state to a path that mirrors the location of the module
in the repo. For example:

| Module | State key |
|---|---|
| `providers/oracle/modules/compute` | `providers/oracle/compute/terraform.tfstate` |
| `providers/aws/modules/compute`    | `providers/aws/compute/terraform.tfstate` |
| `clusters/instances/prod`          | `clusters/prod/terraform.tfstate` |

The keys are path-based, flat and predictable. A key carries no env suffix,
because all the environments share the bucket. A module that targets a specific
environment (staging or lab) uses a different state key.

## How a consumer wires it

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

Export these env vars before you run terraform. In a consumer project, the
`secrets-load` ctl.sh verb usually loads them:

- `AWS_ACCESS_KEY_ID`     — the access key id of the OCI Customer Secret Key
- `AWS_SECRET_ACCESS_KEY` — the secret of the OCI Customer Secret Key
- `AWS_REQUEST_CHECKSUM_CALCULATION=when_required`
- `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required`

### Why the 2 `AWS_*_CHECKSUM_*` env vars are necessary

AWS SDK v2, which the s3 backend of Terraform 1.10 and later uses, sets both
checksum env vars to `when_supported` by default. Every `PutObject` then uses the
HTTP `Transfer-Encoding: chunked` with a trailing `x-amz-checksum-sha256` header.
That is an integrity feature, and AWS itself parses it. The S3-compatible layer
of OCI Object Storage returns HTTP 501
`NotImplemented: AWS chunked encoding not supported`, because Oracle has not
implemented the chunked-trailer format.

When you set both env vars to `when_required`, the SDK appends the trailer only
when the TARGET service demands it, for example S3 Express. For a normal bucket
PUT or GET, SDK v2 uses a plain body framed by `Content-Length`, and OCI supports
that.

These env vars are the configuration setting that AWS documents for an S3
endpoint that AWS does not host. They become unnecessary on the day that OCI
implements support for chunked encoding. Until then, every terraform command
against `gophersys-tfstate` must export them.

### Why `use_lockfile` is off

The native `use_lockfile = true` path of Terraform 1.10 and later acquires the
lock through a conditional S3 PUT, and that PUT *also* uses chunked encoding. The
s3 backend module controls it, not the SDK, so the env vars above do not help.
OCI returns 501 on that path too. The 2 options for real locking are therefore: a
service compatible with DynamoDB, which costs money and adds infrastructure, or
wait until OCI completes its support for chunked encoding.

There is 1 operator, so the risk of 2 concurrent applies is very small. Locking
is therefore disabled, and the env-var setting above only has to cover the normal
PUT and GET of the state file.

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

- Most of the compute already runs there (OCI Phoenix).
- The free tier covers this state workload. We expect less than 1 GB.
- It is S3-compatible, so the canonical `s3` backend of terraform works with no
  extra work, and there is no dependency on Terraform Cloud.
- No third party hosts the state of our infrastructure.
- Native locking through `use_lockfile = true` in terraform 1.10 and later, so
  DynamoDB is not required.

## Migration from the legacy `code-kit-tfstate`

A legacy bucket `code-kit-tfstate` exists in the same compartment, from the
previous infrastructure lineage. No module in this tree consumes it. Leave it in
place until somebody decommissions it explicitly. A new module always points at
`gophersys-tfstate`.
