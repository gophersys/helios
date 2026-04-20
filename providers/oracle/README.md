# providers/oracle

Oracle Cloud Infrastructure Terraform modules. Fulfill the `compute-unit`
interface for OCI.

## Planned modules

- `modules/compartment/` — compartments + tenancy-level defaults.
- `modules/vcn/` — VCN, subnets, gateways, security lists.
- `modules/compute/` — VM.Standard.A1.Flex (ARM), VM.Standard.E4.Flex (x86),
  VM.Standard.E2.1.Micro. Shape-selection logic honors the `compute_unit`
  interface.
- `modules/oke/` — OKE managed cluster + node pools (only when the
  `cluster-cloud-oracle-oke` template is used).
- `modules/dns/` — OCI DNS zones.
- `modules/object-storage/` — bucket for state + Velero backups.

## ARM instance protection — NON-NEGOTIABLE

The A1.Flex instances (server-00, agent-00 today) are **irreplaceable**.
OCI free-tier A1.Flex capacity is nearly impossible to re-acquire.

- The `modules/compute/` module MUST use `moved` blocks rather than allow
  destroy/recreate on any A1.Flex resource.
- The module MUST set `prevent_destroy = true` on A1.Flex resources.
- CI must `terraform plan | grep -E '(destroy|replace).*A1\.Flex'` and
  hard-fail on any match.

## Status

STUB. Populate with modules ported from the pre-rebuild `cloud/oracle/`
tree, refactored to the `compute_unit` interface.
