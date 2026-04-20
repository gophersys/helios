# platform/core/storage

Persistent volume provisioner. Without this, stateful workloads can't
schedule.

## Default implementation

Pick per cluster based on topology:

- **k3s clusters** (like `prod`): `local-path-provisioner` (default in
  k3s) for single-node-pinned volumes; **Longhorn** when HA is needed across
  multiple agent nodes.
- **managed clusters** (EKS, OKE, AKS): the cloud's native CSI driver
  (`ebs.csi.aws.com`, `blockstorage.csi.oci.oracle.com`, `disk.csi.azure.com`).

StorageClass naming convention (stable across clusters):
- `standard` — default, balanced perf/cost
- `fast` — SSD/NVMe, high IOPS
- `replicated` — HA-replicated (Longhorn) when available

## Fulfills
- Implicit: PVC/StorageClass API. No app-visible contract file (K8s standard).

## Dependencies
- `platform/core/cni/` (for distributed provisioners that need pod traffic).

## Status

STUB.

## TODO (when populating)
- Write per-cluster StorageClass overlays.
- Pick Longhorn vs local-path for `prod` (likely start local-path, move
  to Longhorn when adding stateful workloads beyond development).
- Document backup integration (platform/services/backup via Velero with
  CSI snapshot support).
