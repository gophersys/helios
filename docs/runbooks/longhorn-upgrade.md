# Runbook — Longhorn v1.7.2 → v1.12.0 (staged)

Longhorn is on **v1.7.2 (EOL)**, installed from **raw manifests**
(`kubectl apply`, not Helm). The latest version is **v1.12.0**. Longhorn enforces
**one minor version at a time**, and it does **not support a downgrade**. The
safety procedure is therefore **backup and fix-forward**, never rollback.

> ✅ **RESOLVED (2026-07-08): the backup target is configured** — the in-cluster
> MinIO. See "Backup target" below. Full backups of all 4 volumes finished before
> the upgrade.
> (Historical blocker: this cluster originally had no backups outside the
> cluster. An in-cluster snapshot does NOT survive a failure of Longhorn, etcd or
> the disk, so a backup target was mandatory first.)

## Backup target (as configured)
Longhorn 1.12 holds this in the **`BackupTarget/default` CR** (namespace
`longhorn-system`), not in the legacy `settings.longhorn.io backup-target`, which
is empty, as expected.
- `spec.backupTargetURL: s3://longhorn-backups@us-east-1/` (bucket
  `longhorn-backups`; the region label is a formality, because MinIO ignores it).
- `spec.credentialSecret: longhorn-minio-backup` — keys `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY` and
  `AWS_ENDPOINTS: http://minio.minio.svc.cluster.local:9000`.
- Backing store: `apps/minio/` (hostPath NVMe on k3s-w-1, off Longhorn by
  design).

Recreate the secret and the bucket per `apps/minio/README.md` and
`docs/runtime-secrets.md`. Then apply the BackupTarget CR again, or set it in the
Longhorn UI at Settings → Backup Target.

## State (as of 2026-07-07)
- 8 nodes (k3s v1.35.5). Every Longhorn node is Ready and Schedulable.
- 4 volumes, all `attached` and `healthy`, with 3 replicas each. The PVCs are all
  in namespace `observability`: grafana 5Gi, prometheus-server 20Gi,
  storage-loki-0 10Gi, storage-tempo-0 10Gi (about 45Gi provisioned).
- `concurrent-automatic-engine-upgrade-per-node-limit=0`, so you must **upgrade
  the engine images by hand**.
- Kubernetes 1.35 is in range for every step, because each step needs 1.25 or
  higher. There are V1 filesystem volumes only, so every breaking change across
  1.8 to 1.12 for the V2 engine, the block disk and the V2 backing image is
  **not applicable** here.

## Path (target the latest patch of each minor version, to avoid `.0` regressions)
`1.7.2 → 1.8.2 → 1.9.2 → 1.10.2 → 1.11.3 → 1.12.0`
(1.8.0 has a broken image tag. 1.10.0 and 1.11.0 have regressions that the
patches above fix.)

## Pre-flight (once)
1. **Configure a backup target and run full backups** of all 4 volumes. Each one
   must reach `Completed`. *(This step is mandatory.)*
2. Record the replica counts, then scale the Longhorn-backed workloads to 0 for a
   clean, crash-consistent state:
   `kubectl -n observability scale deploy grafana prometheus-server --replicas=0`
   `kubectl -n observability scale sts loki tempo --replicas=0`
3. Snapshot every volume, as an in-cluster safety net.
4. **Health gate:** every volume is `healthy`, every Longhorn node is Ready and
   Schedulable, and no backup or restore is in progress.

## Procedure per minor version (repeat for each step, in order)
1. Verify the health gate again. Never start on a degraded volume.
2. Download the target manifest and **remove the `--upgrade-version-check` flag**
   from the longhorn-manager DaemonSet
   (`sed -i '/--upgrade-version-check/d'`).
3. `kubectl apply --server-side --force-conflicts -f longhorn-<VER>.yaml`
4. Watch `rollout status ds/longhorn-manager` and `get volumes.longhorn.io -w`.
   No volume may become Faulted.
5. **Upgrade the engine image on every volume** (in the UI: *Volume → Upgrade
   Engine*, or set `concurrent-automatic-engine-upgrade-per-node-limit=1`
   temporarily, wait, then set it back to `0`). Do this before the next minor
   version. Engines that are 2 minor versions behind the manager are not
   supported.
6. **Verification gate — all green before the next minor version:** the manager,
   UI and CSI images are at the target version; every volume is `healthy` with
   `currentImage` set to the new engine; the reference count of the old
   engineimage is 0; and no volume is faulted.

## ⚠️ Extra gate — step 3 (1.9.2 → 1.10.2): CRD storage-version migration
1.10 **removes `v1beta1`**. Any Longhorn CRD that still lists `v1beta1` in
`.status.storedVersions` crash-loops the manager. After the whole cluster is on
1.9.2, migrate each CRD: touch every CR, because an annotation write forces a
re-store at `v1beta2`. Then verify that **every** Longhorn CRD shows
`["v1beta2"]` only. This cluster was created at 1.7.2, so it is probably already
clean. Verify that explicitly before you apply 1.10.2.

## After the upgrade
Restore the observability replica counts. Confirm that the PVCs bind again and
that the volumes attach again and are healthy. Confirm that every image is
`:v1.12.0` and that only the v1.12.0 engineimage CR remains.

## Risk and window
The top risks are: (1) no backup target — remove this risk first; (2) the CRD
gate between 1.9 and 1.10; (3) a forgotten engine upgrade in a step. Each step
takes **about 20 to 40 minutes, and the total is about 3 to 4.5 hours**. Spread
the work over several sessions, one minor version per evening, so that each
version runs for a while and any regression is easy to attribute. Data at risk:
about 45Gi of observability history (Prometheus, Loki, Tempo), which is
replaceable because the backups exist.

---
## ✅ COMPLETED 2026-07-08 — 1.7.2 → 1.12.0 (all 5 minor versions)
Executed autonomously with MinIO as the backup target. There was no data loss,
and observability never went down. Path: 1.7.2 → 1.8.2 → 1.9.2 → 1.10.2 → 1.11.3
→ 1.12.0.

### ⚠️ CRITICAL LESSON (this supersedes the "server-side apply" note above)
**Apply Longhorn's CRDs CLIENT-side (`kubectl apply -f`), NOT with
`--server-side`.** The longhorn-manager sets `spec.conversion` (the webhook) on
each CRD at runtime. A `kubectl apply --server-side --force-conflicts` of the
manifest produces an invalid CRD, because the CRDs in the manifest carry no
`conversion` block (`spec.conversion.webhookClientConfig Forbidden ... strategy
Required`). The CRD schema therefore stays on the old version with no message
while the new manager rolls out, and the **manager enters CrashLoopBackOff** with
`strict decoding error: unknown field spec.backupBlockSize`. This caused a
failure on the 1.10.2 step. The fix: split the manifest, apply the CRDs
client-side with `kubectl apply -f <crds>`, and apply the rest server-side. The
remaining steps used this split from the start and were clean. The `v1beta1`
CRD-migration gate did nothing, because the cluster was created at 1.7.2 and is
therefore native v1beta2.
