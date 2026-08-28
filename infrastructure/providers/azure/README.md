# providers/azure

Azure Terraform modules. Fulfill the `compute-unit` interface for Azure.

## Planned modules

- `modules/resource-group/` — resource group + tag conventions.
- `modules/vnet/` — virtual network with subnets, NSGs, peering hooks.
- `modules/compute/` — VM Scale Sets honoring the `compute_unit` interface.
- `modules/aks/` — AKS control plane + node pools (when using
  `cluster-cloud-azure-aks` template). Workload Identity enabled by default.
- `modules/acr/` — container registries.
- `modules/dns/` — Azure DNS zones + App Service managed certs.
- `modules/blob/` — Blob storage for state / backups.

## Status

STUB. No Azure resources today. Adopt if/when an Azure-resident workload
arrives.
