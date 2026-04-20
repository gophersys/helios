# providers/oracle/modules/compute

OCI compute-unit fulfillment — a single VM instance satisfying the
[compute-unit v1 contract](../../../compute-unit/contract.yaml) on
Oracle Cloud Infrastructure.

Shapes covered:

| Shape | Arch | Flex? | Use |
|---|---|---|---|
| `VM.Standard.A1.Flex` | arm64 | yes | **Irreplaceable free-tier** — always set `prevent_destroy = true`. |
| `VM.Standard.E4.Flex` | amd64 | yes | Paid x86 flexible. |
| `VM.Standard.E5.Flex` | amd64 | yes | Paid x86 AMD EPYC flex. |
| `VM.Standard.E2.1.Micro` | amd64 | no | Always-free micro. |

## Usage

```hcl
module "server_00" {
  source = "../../providers/oracle/modules/compute"

  name                = "server-00"
  arch                = "arm64"
  cpu_count           = 2
  memory_gb           = 12
  disk_gb             = 47
  role                = "cluster"
  network             = "tailnet"

  compartment_ocid    = var.compartment_ocid
  availability_domain = "FEQI:PHX-AD-1"
  subnet_ocid         = var.subnet_ocid
  shape               = "VM.Standard.A1.Flex"
  image_ocid          = var.ubuntu_24_arm64_image_ocid

  tailnet_auth_key    = var.tailnet_auth_key
  ssh_public_key      = var.ssh_public_key

  # NON-NEGOTIABLE for A1.Flex — nearly impossible to re-acquire capacity.
  prevent_destroy = true
}
```

## Contract inputs

| Contract var | Type | Required | Default |
|---|---|---|---|
| `name` | string | ✓ | — |
| `arch` | string | ✓ | — |
| `cpu_count` | number | ✓ | — |
| `memory_gb` | number | ✓ | — |
| `disk_gb` | number | ✓ | — |
| `storage_class` | string |   | `ssd` |
| `network` | string |   | `tailnet` |
| `os` | string |   | `linux-ubuntu` |
| `role` | string |   | `cluster` |
| `tags` | map(string) |   | `{}` |
| `tailnet_auth_key` | string (sens.) |   | `""` |
| `ssh_public_key` | string |   | `""` |

## Oracle-specific extensions

| Var | Type | Required | Default |
|---|---|---|---|
| `compartment_ocid` | string | ✓ | — |
| `availability_domain` | string | ✓ | — |
| `subnet_ocid` | string | ✓ | — |
| `shape` | string | ✓ | — |
| `image_ocid` | string |   | `""` (must be set on create; ignored on imports) |
| `prevent_destroy` | bool |   | `false` |
| `assign_public_ip` | bool |   | `null` (derived from network) |
| `hostname_label` | string |   | `""` (derived from name) |

## Outputs

All five contract outputs (`id`, `private_ip`, `public_ip`,
`tailnet_name`, `fqdn`) plus `shape` and `availability_domain` for
operational introspection.

## A1.Flex protection

A1.Flex (Ampere Altra ARM, always-free) capacity is severely
constrained in OCI and re-acquiring a destroyed instance's slot can
take weeks or fail outright. The module enforces protection by
duplicating the `oci_core_instance` resource into a protected and a
destroyable variant, guarded by `count = var.prevent_destroy ? 1 : 0`.
The protected variant carries `lifecycle { prevent_destroy = true }`.

There is no in-place toggle — to move an A1.Flex instance between the
two variants would require a `terraform state mv`. Don't.

## Import

Pre-existing instances import cleanly because `lifecycle.ignore_changes`
covers every provision-time-only field (`source_details`, `metadata`,
VNIC `hostname_label`, `defined_tags`). Example:

```bash
# For a protected A1.Flex:
terraform import \
  'module.server_00.oci_core_instance.protected[0]' \
  'ocid1.instance.oc1.phx.<instance-ocid>'

# For a destroyable E4.Flex / E2.1.Micro:
terraform import \
  'module.agent_01.oci_core_instance.destroyable[0]' \
  'ocid1.instance.oc1.phx.<instance-ocid>'
```

After import, `terraform plan` should show zero changes — a good
sign your module inputs match reality.

## Verbs

| Verb | Meaning |
|---|---|
| `validate` | shellcheck + terraform fmt/init/validate + contract.yaml cross-check |
| `fmt` | `terraform fmt -recursive` |
| `docs-generate` | Placeholder (terraform-docs wire-up deferred) |
| `help` | Usage |
