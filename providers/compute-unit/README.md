# providers/compute-unit

The **cloud-neutral compute-unit contract**. Every machine declares
its needs in this shape; a provider-specific module (`providers/<cloud>/modules/compute/`)
fulfills it.

## Why

A single-operator setup running workloads across OCI + AWS + Hetzner
+ bare-metal needs one abstraction to reason about compute. Without
it, every host is cloud-specific and cross-cloud workflows (e.g.,
OCI A1.Flex + AWS t4g hybrid K3s mesh) turn into bespoke glue.

## Authoritative contract

The machine-readable contract lives at [`contract.yaml`](./contract.yaml).
Human-readable summary below — `contract.yaml` wins in case of drift.

### Required inputs (every provider declares these)

| Name | Type | Description |
|---|---|---|
| `name` | string | Unique human-readable instance name (kebab-case, 1–30 chars). |
| `arch` | string | `amd64` or `arm64`. |
| `cpu_count` | number | Integer vCPU count. |
| `memory_gb` | number | GB of RAM. |
| `disk_gb` | number | Root disk GB. |

### Optional inputs (defaults shown)

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

Given a compute-unit request, a provider's module:

1. Picks the **cheapest shape** in that cloud that satisfies `arch +
   cpu_count + memory_gb + disk_gb`.
2. Provisions with the right OS image for `os`.
3. Attaches to a subnet consistent with `network`, attaches/declines a
   public IP accordingly.
4. Applies `tags` as cloud-native tags.
5. If `tailnet_auth_key` is non-empty, pre-seeds cloud-init to run
   `tailscale up --auth-key=...` on first boot.
6. Outputs the contract's required outputs.

Cloud-specific variables (availability domain, subnet OCID, VPC ID,
Hetzner server type, etc.) are declared as additional variables on
the provider module — they extend, they don't replace, the contract.

## Fulfillment matrix

| Shape request             | `oracle`        | `aws`           | `hetzner` | `bare-metal` |
|---------------------------|-----------------|-----------------|-----------|--------------|
| arm64, 2c/12g             | A1.Flex 2/12    | t4g.large       | CAX21     | —            |
| arm64, 2c/2g              | —               | t4g.small       | CAX11     | —            |
| x86, 1c/16g               | E4.Flex 1/16    | t3a.xlarge      | —         | —            |
| x86, 1c/1g (bastion)      | E2.1.Micro      | t3a.nano        | CPX11     | —            |
| bare-metal                | —               | —               | —         | any-declared |

## Validation

- This module's `./ctl.sh validate` verifies `contract.yaml` parses
  cleanly and the README's variable/output tables agree with the
  authoritative contract.
- Each provider module's `./ctl.sh validate` cross-checks its own
  `variables.tf` + `outputs.tf` against `contract.yaml`, failing the
  build if a required variable/output is missing or typed wrongly.

## Status

**v1 contract locked.** The first implementation
(`providers/oracle/modules/compute/`) lands next. Additions to the
contract are minor-version bumps (new optional var/output) or major
(renaming, type change).
