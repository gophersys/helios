# providers/oracle

Reusable Terraform modules for Oracle Cloud Infrastructure (OCI). Intended
contents once populated:

- `modules/compartment/` — compartments + tenancy-level defaults.
- `modules/vcn/` — VCN, subnets, gateways, security lists.
- `modules/compute/` — compute instances (Always-Free-tier friendly A1
  shapes preferred where possible).
- `modules/oke/` — OKE managed cluster + node pools.
- `modules/dns/` — OCI DNS zones.

TODO: modules not yet written. The previous infrastructure layout had an
extensive OCI module set — re-port and prune as real consumers arrive.
