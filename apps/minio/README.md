# minio

In-cluster **S3 backup target**. Two consumers:

- **Longhorn** — `BackupTarget/default` points at `s3://longhorn-backups@us-east-1/`
  (volume backups: currently the observability stack).
- **music-studio** — restic repository in bucket `music-backups`, pushed from
  Mateo's Mac over the tailnet via `s3.mateosegura.com` (see `30-ingress.yaml`;
  client side lives in github.com/MateoSegura/music-studio).

## Why here, not on Longhorn
Storage is `hostPath /mnt/media/minio` on **k3s-w-1**'s NVMe, deliberately **not**
a Longhorn volume — a backup target must not depend on the thing it protects.
`strategy: Recreate` + a node pin keep the single replica bound to that disk.

## Access & isolation
- Service `minio.minio.svc:9000` (S3 API) / `:9001` (console).
- Off-cluster: `https://s3.mateosegura.com` — tailnet-private ingress
  (grey-cloud A record → 10.168.0.240; LE DNS-01 cert). S3 API only.
- NetworkPolicy (`25-networkpolicy.yaml`): default-deny ingress; only
  `longhorn-system` and `ingress-nginx` may reach `:9000`, plus same-namespace
  admin pods. The console is reachable only via
  `kubectl -n minio port-forward svc/minio 9001`.
- Container runs root (hostPath writes) but drops ALL caps + seccomp
  RuntimeDefault. Non-root/RO-rootfs is deferred (needs a pre-chown).

## Secrets (imperative — see docs/runtime-secrets.md)
- `minio-creds` (ns `minio`) — `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`.
- `longhorn-minio-backup` (ns `longhorn-system`) — the S3 creds Longhorn uses
  to reach MinIO (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_ENDPOINTS`).
Both are vaulted at `shared/minio/longhorn-backups`.

The `music-backups` bucket has its own scoped MinIO user (`music-studio`,
RW on that bucket only — no k8s secret needed; the creds live only on the
consuming Mac's Keychain). Vaulted at `project/music-studio/minio/access-key`
+ `project/music-studio/minio/secret-key`.

## Bucket bootstrap (one-time, on a fresh cluster)
The `longhorn-backups` bucket must exist before Longhorn can back up. It already
does on this cluster; on a rebuild, create it idempotently with a throwaway `mc`
pod (kept as a documented command rather than an Argo Job, to avoid a failing
image-pull blocking the netpol/deployment sync):
```sh
kubectl -n minio run mc --rm -it --restart=Never --image=minio/mc:latest --env=AK="$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d)" --env=SK="$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d)" -- sh -c 'mc alias set local http://minio:9000 "$AK" "$SK" && mc mb --ignore-existing local/longhorn-backups'
```
Then (re)point the Longhorn `BackupTarget` — see
`docs/runbooks/longhorn-upgrade.md` → "Backup target".
