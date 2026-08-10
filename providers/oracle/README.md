# providers/oracle

Oracle Cloud Infrastructure Terraform modules. Fulfill the `compute-unit`
interface for OCI.

## Modules

| Module | Status | Purpose |
|---|---|---|
| `modules/compute/` | **live** | OCI VM fulfilling the compute-unit v1 contract. Covers A1.Flex (ARM), E4.Flex (x86), E2.1.Micro. |
| `modules/compartment/` | planned | Compartments + tenancy-level defaults. |
| `modules/vcn/` | planned | VCN, subnets, gateways, security lists. |
| `modules/oke/` | planned | OKE managed cluster + node pools (only when `cluster-cloud-oracle-oke` template is used). |
| `modules/dns/` | planned | OCI DNS zones. |
| `modules/object-storage/` | planned | Bucket for app-layer state + Velero backups. Separate from `providers/state-backend/`, which owns the Terraform state bucket. |

## ARM instance protection — NON-NEGOTIABLE

The A1.Flex instances (server-00, agent-00 today) are **irreplaceable**.
OCI free-tier A1.Flex capacity is nearly impossible to re-acquire.

`modules/compute/` enforces this by duplicating the `oci_core_instance`
resource into `protected` (with `lifecycle.prevent_destroy = true`) and
`destroyable` variants, count-guarded by `var.prevent_destroy`. See
[`modules/compute/README.md`](./modules/compute/README.md#a1flex-protection)
for the mechanism. CI-level guard (`terraform plan | grep` hardfail) is
a planned addition.

## Live imports (2026-04)

Imported into terraform state against `gophersys-tfstate`:

| Instance | Shape | Variant | Status |
|---|---|---|---|
| `server-00` | A1.Flex ARM | protected | plan = zero-diff |
| `agent-00` | A1.Flex ARM | protected | plan = zero-diff |
| `agent-01` | E4.Flex x86 | destroyable | plan = zero-diff (currently STOPPED) |
