# providers/compute-unit

The **cloud-neutral compute unit interface**. Every machine declares its
needs in this shape; a provider-specific module fulfills it.

## Why

A person running many clusters across AWS + OCI + Hetzner + bare-metal
needs one abstraction to reason about compute. Without it, every host is
cloud-specific and cross-cloud workflows (e.g., OCI A1.Flex + AWS t4g
hybrid K3s mesh) become bespoke code.

## Schema (v0, draft)

Every machine's `identity.yaml` may include:

```yaml
hardware:
  provider: oracle | aws | azure | hetzner | bare-metal
  compute_unit:
    arch: amd64 | arm64
    cores: <int>
    memory_gb: <int>
    storage_gb: <int>
    storage_class: ssd | nvme | hdd       # optional; defaults to ssd
    network: public | tailnet | private   # how the host is reachable
    os: linux-debian | linux-fedora | windows-server | macos
    tags: []                              # optional free-form tags
```

## What each provider does

Given a `compute_unit`, the provider's Terraform module:
1. Picks the **cheapest shape** that satisfies `arch + cores + memory_gb +
   storage_gb` in its cloud.
2. Provisions with the right OS image.
3. Registers the machine with Tailscale (if `network: tailnet`) via
   pre-auth key from Bitwarden.
4. Runs the bootstrap Ansible playbook (`machines/scripts/bootstrap.sh`).
5. Outputs: `hostname`, `tailnet_ip`, `public_ip` (if any), `ssh_key_path`.

## Fulfillment matrix (planned)

| Shape request             | `oracle`        | `aws`            | `hetzner`  | `bare-metal` |
|---------------------------|-----------------|------------------|------------|--------------|
| arm64, 2c/12g             | A1.Flex 2/12    | t4g.large         | CAX21      | —            |
| arm64, 2c/2g              | —               | t4g.small         | CAX11      | —            |
| x86, 1c/16g               | E4.Flex 1/16    | t3a.xlarge        | —          | —            |
| x86, 1c/1g (bastion)      | E2.1.Micro      | t3a.nano          | CPX11      | —            |
| bare-metal                | —               | —                 | —          | any-declared |

## Status

STUB — this is the schema we're committing to; implementations land when
the first cluster is being provisioned through Terraform.
