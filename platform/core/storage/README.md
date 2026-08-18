# platform/core/storage

The provisioning of persistent volumes. Without it, a stateful workload cannot
schedule.

---

## What is deployed today on the homelab — the source of truth

2 provisioners run at the same time:

- **local-path**, the k3s default. It gives node-local volumes for data that you
  can download again, or that is already pinned to a node. The whole `media`
  stack uses it deliberately. If a node is lost, the data is pulled again.
- **Longhorn v1.12.0**. It gives replicated storage with 3 replicas, for a volume
  that must survive the loss of a node. `observability` uses it for grafana,
  prometheus, loki and tempo. It is installed from the **raw upstream manifests
  with `kubectl apply`**, not with Helm. `docs/debt-register.md` (D9) tracks its
  pinned version and the command to install it again. The runbook for the staged
  upgrade from 1.7.2 to 1.12.0 is `docs/runbooks/longhorn-upgrade.md`.

**Backups:** the `BackupTarget/default` of Longhorn writes to the in-cluster
**MinIO** (`apps/minio/`, a hostPath on the NVMe of k3s-w-1, off Longhorn by
design). Separately, a daily `config-backup` CronJob writes a tar of the media
config PVCs to the NVMe.

> Note: this cluster does **not** use the StorageClass names `standard`, `fast`
> and `replicated` that the section below describes. Those names are the target
> convention for many clusters, and they are not what k3s ships. The live
> StorageClasses are `local-path` and `longhorn`.

---

## Target design (for many clusters, not deployed yet)

The naming convention for a StorageClass, stable across every future cluster:
- `standard` — the default, with a balance of performance and cost
- `fast` — SSD or NVMe, with high IOPS
- `replicated` — replicated for HA, through Longhorn, where Longhorn is available

Per substrate: k3s uses local-path and Longhorn. A managed cluster (EKS, OKE or
AKS) uses the native CSI driver of its cloud.

## Contracts fulfilled
- Implicit: the PVC and StorageClass API. There is no contract file that an app
  sees, because this is a Kubernetes standard.

## TODO, when a prod cluster bootstraps
- Write a StorageClass overlay for each cluster. It maps the names above onto the
  provisioner of that substrate.
