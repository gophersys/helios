# providers/azure

Reusable Terraform modules for Azure. Intended contents once populated:

- `modules/resource-group/` — resource group + tag conventions.
- `modules/vnet/` — virtual network with subnets, NSGs, peering hooks.
- `modules/aks/` — AKS control plane + node pools. Workload Identity
  enabled by default.
- `modules/acr/` — container registries.
- `modules/dns/` — Azure DNS zones + App Service managed certs.

TODO: modules not yet written. First module arrives when the first Azure
cluster is created.
