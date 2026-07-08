# Runbook — Longhorn v1.7.2 → v1.12.0 (staged)

Longhorn is on **v1.7.2 (EOL)**, installed via **raw manifests** (`kubectl apply`, not Helm).
Latest is **v1.12.0**. Longhorn enforces **one-minor-at-a-time** upgrades and
**downgrades are unsupported** — the safety posture is **backup + fix-forward**, never rollback.

> ⚠️ **BLOCKER: no backup target is configured** (`settings.longhorn.io backup-target` is empty).
> There are **no off-cluster backups**. Configure an S3/NFS target and take full backups of all
> 4 volumes **before** starting. In-cluster snapshots do NOT survive a Longhorn/etcd/disk failure.

## State (as of 2026-07-07)
- 8 nodes (k3s v1.35.5), all Longhorn nodes Ready+Schedulable.
- 4 volumes, all `attached`+`healthy`, 3 replicas each. PVCs (all ns `observability`):
  grafana 5Gi, prometheus-server 20Gi, storage-loki-0 10Gi, storage-tempo-0 10Gi (~45Gi provisioned).
- `concurrent-automatic-engine-upgrade-per-node-limit=0` → **engine images are manual-upgrade**.
- k8s 1.35 is in-range for every step (each needs ≥1.25). Only V1 filesystem volumes → all the
  V2-engine / block-disk / V2-backing-image breaking changes across 1.8–1.12 are **N/A** here.

## Path (target latest patch of each minor — avoids `.0` regressions)
`1.7.2 → 1.8.2 → 1.9.2 → 1.10.2 → 1.11.3 → 1.12.0`
(1.8.0 has a broken image tag; 1.10.0/1.11.0 have regressions fixed in the patches above.)

## Pre-flight (once)
1. **Configure a backup target + run full backups** of all 4 volumes → each `Completed`. *(non-negotiable)*
2. Record replica counts, then scale the Longhorn-backed workloads to 0 (clean, crash-consistent):
   `kubectl -n observability scale deploy grafana prometheus-server --replicas=0`
   `kubectl -n observability scale sts loki tempo --replicas=0`
3. Snapshot every volume (in-cluster safety net).
4. **Health gate:** all volumes `healthy`, all Longhorn nodes Ready+Schedulable, no in-progress backup/restore.

## Per-minor procedure (repeat for each step in order)
1. Re-verify the health gate (never start on a degraded volume).
2. Download the target manifest and **strip the `--upgrade-version-check` flag** from the
   longhorn-manager DaemonSet (`sed -i '/--upgrade-version-check/d'`).
3. `kubectl apply --server-side --force-conflicts -f longhorn-<VER>.yaml`
4. Watch `rollout status ds/longhorn-manager` + `get volumes.longhorn.io -w` (none may go Faulted).
5. **Upgrade the engine image on every volume** (UI *Volume → Upgrade Engine*, or temporarily set
   `concurrent-automatic-engine-upgrade-per-node-limit=1`, wait, set back to `0`). Required before
   the next minor — leaving engines two minors behind the manager is unsupported.
6. **Verification gate (all green before the next minor):** manager/UI/CSI images = target version;
   every volume `healthy` with `currentImage` = new engine; old engineimage refcount → 0; no faulted volumes.

## ⚠️ Extra gate — Step 3 (1.9.2 → 1.10.2): CRD storage-version migration
1.10 **removes `v1beta1`**; any Longhorn CRD still listing `v1beta1` in `.status.storedVersions`
crash-loops the manager. After the cluster is fully on 1.9.2, migrate each CRD by touching every CR
(annotation write forces re-store at `v1beta2`), then verify **every** Longhorn CRD shows
`["v1beta2"]` only. (This cluster was born at 1.7.2 so it's likely already clean — verify explicitly
before applying 1.10.2.)

## Post-upgrade
Restore observability replica counts; confirm PVCs re-bind + volumes re-attach healthy; confirm all
images `:v1.12.0` and only the v1.12.0 engineimage CR remains.

## Risk & window
Top risks: (1) no backup target — mitigate first; (2) the 1.9→1.10 CRD gate; (3) forgetting the
per-step engine upgrade. **~20–40 min/step, ~3–4.5h total** — recommended spread over multiple
sessions (one minor per evening) so each version soaks and any regression is easy to attribute.
Data at risk: ~45Gi observability history (Prometheus/Loki/Tempo) — replaceable given backups.

---
## ✅ COMPLETED 2026-07-08 — 1.7.2 → 1.12.0 (all 5 minors)
Executed autonomously with MinIO as the backup target. Zero data loss, observability
never went down. Path: 1.7.2 → 1.8.2 → 1.9.2 → 1.10.2 → 1.11.3 → 1.12.0.

### ⚠️ CRITICAL LESSON (supersedes the "server-side apply" note above)
**Apply Longhorn's CRDs CLIENT-side (`kubectl apply -f`), NOT `--server-side`.**
The longhorn-manager sets each CRD's `spec.conversion` (webhook) at runtime.
`kubectl apply --server-side --force-conflicts` of the manifest — whose CRDs carry
no `conversion` block — produces an invalid CRD (`spec.conversion.webhookClientConfig
Forbidden ... strategy Required`), so the CRD schema silently stays on the old
version while the new manager rolls → **manager CrashLoopBackOff** with
`strict decoding error: unknown field spec.backupBlockSize`. Fix that bit us on the
1.10.2 step: split the manifest, `kubectl apply -f <crds>` (client-side) + apply the
rest server-side. The remaining steps used this split from the start and were clean.
The `v1beta1` CRD-migration gate was a no-op (cluster born at 1.7.2 = native v1beta2).
