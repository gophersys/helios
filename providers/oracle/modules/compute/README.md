# providers/oracle/modules/compute

The OCI implementation of a compute unit. It creates 1 VM instance that satisfies
the [compute-unit v1 contract](../../../compute-unit/contract.yaml) on Oracle
Cloud Infrastructure.

The shapes that it covers:

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

The module emits all 5 contract outputs (`id`, `private_ip`, `public_ip`,
`tailnet_name` and `fqdn`), plus `shape` and `availability_domain` for
operational inspection.

## Protection of an A1.Flex instance

A1.Flex capacity (Ampere Altra ARM, always free) is very limited in OCI. To get
the slot of a destroyed instance again can take weeks, and it can fail
completely. The module therefore duplicates the `oci_core_instance` resource into
a protected variant and a destroyable variant, and guards them with
`count = var.prevent_destroy ? 1 : 0`. The protected variant carries
`lifecycle { prevent_destroy = true }`.

There is no switch that changes an instance in place. To move an A1.Flex instance
between the 2 variants you would need a `terraform state mv`. Do not do that.

## Import

An instance that already exists imports without an error, because
`lifecycle.ignore_changes` covers every field that applies only at provision
time: `source_details`, `metadata`, the VNIC `hostname_label` and `defined_tags`.
An example:

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

After the import, `terraform plan` must show 0 changes. That result shows that
the module inputs match the real instance.

## Verbs

| Verb | Meaning |
|---|---|
| `validate` | shellcheck + terraform fmt/init/validate + contract.yaml cross-check |
| `fmt` | `terraform fmt -recursive` |
| `docs-generate` | Placeholder (terraform-docs wire-up deferred) |
| `help` | Usage |
