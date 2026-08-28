# providers/compute-unit

The **cloud-neutral compute-unit contract**. Every machine declares its needs in
this shape, and a provider-specific module
(`providers/<cloud>/modules/compute/`) fulfills the request.

## Why

One operator runs workloads across OCI, AWS, Hetzner and bare metal. That needs 1
abstraction to reason about compute. Without it, every host is specific to its
cloud, and a workflow across clouds becomes custom code. An example of such a
workflow is a hybrid K3s mesh of OCI A1.Flex and AWS t4g nodes.

## The authoritative contract

The machine-readable contract is at [`contract.yaml`](./contract.yaml). The
summary below is for a human reader. If the 2 differ, `contract.yaml` wins.

### Required inputs (every provider declares these)

| Name | Type | Description |
|---|---|---|
| `name` | string | Unique human-readable instance name (kebab-case, 1–30 chars). |
| `arch` | string | `amd64` or `arm64`. |
| `cpu_count` | number | Integer vCPU count. |
| `memory_gb` | number | GB of RAM. |
| `disk_gb` | number | Root disk GB. |

### Optional inputs (the defaults are shown)

| Name | Type | Default | Notes |
|---|---|---|---|
| `storage_class` | string | `ssd` | `nvme` / `hdd` may fall back to ssd per-provider. |
| `network` | string | `tailnet` | `public` / `tailnet` / `private`. |
| `os` | string | `linux-ubuntu` | `linux-debian` / `linux-fedora` / `windows-server`. |
| `role` | string | `cluster` | `cluster` / `service` / `builder` or project-specific. |
| `tags` | map(string) | `{}` | Applied as cloud tags + Ansible inventory vars. |
| `tailnet_auth_key` | string (sensitive) | `""` | Empty disables Tailscale join. |
| `ssh_public_key` | string | `""` | Seeded into cloud-init. |

### Required outputs (every provider emits these)

| Name | Description |
|---|---|
| `id` | Provider-native resource ID (OCID / EC2 instance ID / etc.). |
| `private_ip` | Internal VCN/VPC IP. |
| `public_ip` | External IP (empty string when none). |
| `tailnet_name` | Tailscale hostname in `mateosegura.ts.net`; empty if not joined. |
| `fqdn` | Stable resolvable name — usually the tailnet FQDN. |

## Provider responsibilities

For a compute-unit request, the module of a provider must:

1. Pick the **least expensive shape** in that cloud that satisfies `arch`,
   `cpu_count`, `memory_gb` and `disk_gb`.
2. Provision with the correct OS image for `os`.
3. Attach the instance to a subnet that matches `network`, and attach or refuse a
   public IP to match.
4. Apply `tags` as native cloud tags.
5. If `tailnet_auth_key` is not empty, prepare cloud-init to run
   `tailscale up --auth-key=...` at the first boot.
6. Emit every required output of the contract.

A variable that is specific to one cloud — an availability domain, a subnet OCID,
a VPC ID, a Hetzner server type — is declared as an extra variable on the
provider module. Those variables extend the contract. They do not replace it.

## Fulfillment matrix

| Shape request             | `oracle`        | `aws`           | `hetzner` | `bare-metal` |
|---------------------------|-----------------|-----------------|-----------|--------------|
| arm64, 2c/12g             | A1.Flex 2/12    | t4g.large       | CAX21     | —            |
| arm64, 2c/2g              | —               | t4g.small       | CAX11     | —            |
| x86, 1c/16g               | E4.Flex 1/16    | t3a.xlarge      | —         | —            |
| x86, 1c/1g (bastion)      | E2.1.Micro      | t3a.nano        | CPX11     | —            |
| bare-metal                | —               | —               | —         | any-declared |

## Validation

- The `./ctl.sh validate` of this module verifies that `contract.yaml` parses
  cleanly, and that the variable and output tables in this README agree with the
  authoritative contract.
- The `./ctl.sh validate` of each provider module compares its own
  `variables.tf` and `outputs.tf` against `contract.yaml`. It fails the build if
  a required variable or output is missing, or if the type is wrong.

## Status

**The v1 contract is locked.** The first implementation
(`providers/oracle/modules/compute/`) lands next. An addition to the contract is
a minor version bump (a new optional variable or output). A rename or a type
change is a major version bump.
