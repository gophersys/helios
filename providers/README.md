# providers

Terraform: **how** to create compute. The cluster bring-up consumes it, and so
does an individual machine declaration that asks for a host from a cloud.

## The compute-unit abstraction

Every machine, in `machines/*` or in `clusters/instances/*/nodes/*`, declares
what it needs in a form that does not name a provider:

```yaml
hardware:
  provider: oracle            # which provider fulfills this
  compute_unit:
    arch: arm64
    cores: 2
    memory_gb: 12
    storage_gb: 50
    network: "tailnet"        # "public" | "tailnet" | "private"
```

The Terraform module of the provider reads this block and performs the correct
action for its cloud. There are 2 results:
- To change cloud you change the `provider:` line. The platform code does not
  change.
- You can combine the free tiers of several clouds (OCI A1.Flex, AWS t4g and
  Hetzner ARM) with a declaration.

See `providers/compute-unit/` for the definition of the interface.

## Provider modules

| Provider              | Status | Purpose                                     |
|-----------------------|--------|---------------------------------------------|
| `compute-unit/`       | stub   | The cloud-neutral compute interface         |
| `oracle/`             | stub   | VCN, compartments, A1.Flex/E4.Flex/E2.Micro, OKE |
| `aws/`                | stub   | VPC, EC2, EKS, IAM, Route53, ACM, S3-state  |
| `azure/`              | stub   | Resource groups, networking, AKS            |
| `hetzner/`            | stub   | Hetzner Cloud — cheap ARM (future)          |
| `bare-metal/`         | stub   | No-op provider for on-prem / homelab hosts  |
| `kubernetes-manual/`  | stub   | K3s install + kubeconfig emission           |
| `state-backend/`      | stub   | Where Terraform state itself lives          |

Each provider directory is a self-contained library of Terraform root modules. It
holds several modules at the same level, and a cluster root uses one with
`module "..." { source = "../../providers/<provider>/<module>" }`.

A provider carries no state of its own. The consumer owns the state. A provider
is a pure library.
