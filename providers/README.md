# providers

Terraform — **how** to create compute. Consumed by cluster bring-up and by
individual machine declarations that ask for a cloud-provisioned host.

## The compute-unit abstraction

Every machine (in `machines/*` or `clusters/instances/*/nodes/*`) declares
what it needs in a provider-neutral form:

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

The provider's Terraform module reads this and does the right cloud-specific
thing. That means:
- Swapping clouds = change the `provider:` line; platform code is untouched.
- Free-tier stacking (OCI A1.Flex + AWS t4g + Hetzner ARM) is declarative.

See `providers/compute-unit/` for the interface definition.

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

Each provider directory is a self-contained Terraform root module library:
multiple sibling modules that cluster roots can
`module "..." { source = "../../providers/<provider>/<module>" }`.

Providers do not carry state of their own — consumers own state. Providers
are pure libraries.
