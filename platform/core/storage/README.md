# platform/core/storage

Persistent volume provisioning. Without this, stateful workloads can't schedule.

---

## Deployed today (homelab) — the source of truth

Two provisioners run side by side:

- **local-path** (k3s default) — node-local volumes for data that is either
  re-downloadable or already node-pinned (the whole `media` + `embedded-lab`
  stacks use this deliberately; a lost node just re-pulls).
- **Longhorn v1.12.0** — replicated (3-replica) storage for volumes that must
  survive a node. In use by `observability` (grafana/prometheus/loki/tempo).
  Installed via **raw upstream manifests (`kubectl apply`)**, not Helm — its
  pinned version + reinstall command are tracked in `docs/debt-register.md` (D9);
  the staged 1.7.2→1.12.0 upgrade runbook is `docs/runbooks/longhorn-upgrade.md`.

**Backups:** Longhorn's `BackupTarget/default` writes to in-cluster **MinIO**
(`apps/minio/`, hostPath NVMe on k3s-w-1 — off-Longhorn by design). Separately, a
daily `config-backup` CronJob tars the media config PVCs to the NVMe.

> Note: this cluster does **not** use the `standard`/`fast`/`replicated`
> StorageClass naming below — that's the multi-cluster target convention, not
> what k3s ships. `local-path` and `longhorn` are the live StorageClasses.

---

## Target design (multi-cluster, not yet deployed)

StorageClass naming convention (stable across future clusters):
- `standard` — default, balanced perf/cost
- `fast` — SSD/NVMe, high IOPS
- `replicated` — HA-replicated (Longhorn) when available

Per-substrate: k3s → local-path + Longhorn; managed clusters (EKS/OKE/AKS) → the
cloud's native CSI driver.

## Fulfills
- Implicit: PVC/StorageClass API. No app-visible contract file (K8s standard).

## TODO (when a prod cluster bootstraps)
- Write per-cluster StorageClass overlays mapping the names above onto the
  substrate's provisioner.
