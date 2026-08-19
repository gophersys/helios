# platform/core/storage

The provisioning of persistent volumes. Without it, a stateful workload cannot
schedule.

---

## What is deployed today on the homelab — the source of truth

**1 provisioner: `local-path`, the k3s default.** It gives node-local volumes for
data that you can download again, or that is already pinned to a node. Every
workload on this cluster uses it deliberately — the `media` stack, `eden` and the
`config-backup` CronJob. If a node is lost, the data is pulled again. MinIO is
the one exception, and it is not a PVC at all: it writes a hostPath on the NVMe
of k3s-w-1.

### Longhorn — REMOVED 2026-08-19

Longhorn v1.12.0 gave replicated storage with 3 replicas. It was removed because:

- **0 volumes.** Its only consumer was the `observability` stack, and that was
  removed on 2026-08-09. Nothing else ever asked for the `longhorn` StorageClass.
- **Untracked drift.** It was installed from the **raw upstream manifests with
  `kubectl apply`**, not Helm and not Argo, so its running version lived in prose
  only — one of the 4 imperative components in debt-register D9.
- **Cost with no return.** A manager, a CSI plugin, an attacher, a provisioner, a
  resizer, a snapshotter, the UI and an engine-image DaemonSet, on every node, to
  replicate nothing. It was also the most privileged component on the cluster.

Mateo's decision, 2026-08-19. `local-path` is the storage story here. Replicated
storage is not solved and is **deliberately not solved**: reintroduce a
replicated provisioner when a workload exists whose data cannot be re-fetched and
cannot be pinned to a node — and decide it then, rather than keep 8 controllers
warm against the possibility.

**Backups:** a daily `config-backup` CronJob writes a tar of the media config
PVCs to the NVMe. The in-cluster **MinIO** (`apps/minio/`) is still up: its
remaining consumer is the `music-backups` restic repository that Mateo's Mac
pushes over the tailnet. Its `longhorn-backups` bucket is orphaned.

> Note: this cluster does **not** use the StorageClass names `standard`, `fast`
> and `replicated` that the section below describes. Those names are the target
> convention for many clusters, and they are not what k3s ships. The live
> StorageClass is `local-path`, and it is the only one.

---

## Target design (for many clusters, not deployed yet)

The naming convention for a StorageClass, stable across every future cluster:
- `standard` — the default, with a balance of performance and cost
- `fast` — SSD or NVMe, with high IOPS
- `replicated` — replicated for HA, where a replicating CSI driver is available

Per substrate: k3s uses local-path today and maps `replicated` to nothing — see
the removal note above. A managed cluster (EKS, OKE or AKS) uses the native CSI
driver of its cloud.

## Contracts fulfilled
- Implicit: the PVC and StorageClass API. There is no contract file that an app
  sees, because this is a Kubernetes standard.

## TODO, when a prod cluster bootstraps
- Write a StorageClass overlay for each cluster. It maps the names above onto the
  provisioner of that substrate.
