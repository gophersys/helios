# Runtime secrets

Credential material that lives **only in the cluster / on app PVCs — never in
git**. Each is recreated from Vaultwarden (items follow `shared/<service>/<purpose>`).
This is the honest inventory behind debt-register D4/D5.

> Why imperative? The ESO `vaultwarden` ClusterSecretStore returns an item's
> **notes** blob (`jsonPath $.data.data[0].notes`), which fits multi-line configs
> (e.g. WireGuard) but not single-field logins. So single-value credentials are
> created imperatively, matching the existing `gluetun-wireguard` pattern. All
> commands assume `BW_SESSION` is exported and `KUBECONFIG` points at homelab.

## k8s Secrets (ns `media` unless noted)

### `gluetun-wireguard` — ProtonVPN WireGuard for the torrent VPN
Vault: `shared/protonvpn/wireguard` (notes = the WireGuard config). Full
recreation is in `apps/music/qbittorrent/20-deployment.yaml`'s header.

### `homepage-secrets` — Homepage dashboard widget credentials
```sh
PKEY=$(kubectl -n media exec deploy/prowlarr -- sh -c \
  'grep -oE "<ApiKey>[a-f0-9]+</ApiKey>" /config/config.xml | sed "s/<[^>]*>//g"')
kubectl -n media create secret generic homepage-secrets \
  --from-literal=HOMEPAGE_VAR_PROWLARR_KEY="$PKEY" \
  --from-literal=HOMEPAGE_VAR_QBIT_PASS="bypass" \
  --dry-run=client -o yaml | kubectl apply -f -
```
(`HOMEPAGE_VAR_QBIT_PASS` is a placeholder — the qBit widget authenticates via
the in-cluster subnet bypass, not this value.)

### `filebrowser-admin` — Filebrowser admin password
```sh
kubectl -n media create secret generic filebrowser-admin \
  --from-literal=password="$(bw get password shared/filebrowser/admin)" \
  --dry-run=client -o yaml | kubectl apply -f -
```
Then apply it to the app with `apps/music/filebrowser/reset-admin/job.yaml`
(see its header — the running server locks the DB, so scale to 0 first).

### `operator-oauth` (ns `tailscale`) — Tailscale operator OAuth
Vault: `shared/tailscale/oauth-k8s-operator`. Recreation is documented in
`platform/services/networking/tailscale-operator/README.md`.

### `workspaces-github-app` (ns `workspaces-prod`) — GitHub App auth for create/destroy
workspaces-api authenticates to GitHub as the **gophersys-arc** App (mints
short-lived installation tokens at runtime) — the personal PAT (`workspaces-github`)
is **retired**. Recreate from the App key at `shared/github/arc-app`:
```sh
kubectl -n workspaces-prod create secret generic workspaces-github-app \
  --from-literal=github_app_id=4235192 \
  --from-literal=github_app_installation_id=144912786 \
  --from-file=github_app_private_key=<key.pem>   # bw: shared/github/arc-app
```
Optional (deployment mounts with optional:true): without it the API is read-only.


### `arc-github-app` (ns `arc-runners`) — GitHub App for self-hosted CI + CD promotion
The **gophersys-arc** GitHub App authenticates the org self-hosted runner pool
(`arc-org`, ARC) and the workspaces→infra image promotion. Vault:
**`shared/github/arc-app`** (App ID, Client ID, Installation ID, private key).
```sh
kubectl -n arc-runners create secret generic arc-github-app \
  --from-literal=github_app_id=4235192 \
  --from-literal=github_app_installation_id=144912786 \
  --from-file=github_app_private_key=<key.pem>   # from bw: shared/github/arc-app
```
The same App key is also set as repo secrets on `gophersys/workspaces`
(`ARC_APP_ID`, `ARC_APP_PRIVATE_KEY`) so its build can promote the deployment.

## Platform / backup / edge Secrets

### `minio-creds` (ns `minio`) — MinIO root credentials
Backs the Longhorn S3 backup target (`apps/minio/`). Vault: `shared/minio/longhorn-backups`.
```sh
kubectl -n minio create secret generic minio-creds \
  --from-literal=MINIO_ROOT_USER="$(bw get username shared/minio/longhorn-backups)" \
  --from-literal=MINIO_ROOT_PASSWORD="$(bw get password shared/minio/longhorn-backups)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### MinIO IAM: `music-studio` user (no k8s secret) — music-studio restic
Not a k8s Secret — imperative MinIO-internal IAM state (user `music-studio` +
policy `music-backups-rw`, RW on bucket `music-backups` only), created via an
ad-hoc `mc` pod (pattern in `apps/minio/README.md`). Consumed only by restic on
Mateo's Mac (via tailnet-private `s3.mateosegura.com`). Vault:
`project/music-studio/minio/{access-key,secret-key}` (+
`project/music-studio/restic/password` for repo encryption). On a MinIO
rebuild, recreate with `mc admin user add` / `policy create` / `policy attach`.

### `longhorn-minio-backup` (ns `longhorn-system`) — Longhorn → MinIO S3 creds
The S3 credentials Longhorn's `BackupTarget/default` uses to reach MinIO (same
Vault item; access-key = MinIO root user, secret = root password).
```sh
kubectl -n longhorn-system create secret generic longhorn-minio-backup \
  --from-literal=AWS_ACCESS_KEY_ID="$(bw get username shared/minio/longhorn-backups)" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$(bw get password shared/minio/longhorn-backups)" \
  --from-literal=AWS_ENDPOINTS="http://minio.minio.svc.cluster.local:9000" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### `tunnel-token` (ns `cloudflare-tunnel`) — Cloudflare tunnel token
The `eden-home` Zero-Trust tunnel's token (issued in the CF dashboard). Consumed by
`platform/core/edge/tunnel/cloudflare-tunnel/deployment.yaml`. Store the token at
`shared/cloudflare/tunnel-token` (notes field):
```sh
kubectl -n cloudflare-tunnel create secret generic tunnel-token \
  --from-literal=token="$(bw get notes shared/cloudflare/tunnel-token)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## App-managed passwords (not k8s Secrets)

### qBittorrent WebUI password
Lives hashed in the config PVC (`qBittorrent.conf`), reset on a PVC rebuild.
Re-apply from vault (`shared/qbittorrent/webui`):
```sh
bw get password shared/qbittorrent/webui | kubectl -n media exec -i \
  deploy/qbittorrent -c qbittorrent -- sh -c \
  'read -r P; curl -s -X POST http://localhost:8080/api/v2/app/setPreferences \
   --data-urlencode "json={\"web_ui_password\":\"$P\"}"'
```
In-cluster access is auth-bypassed (`WebUI\AuthSubnetWhitelist`, enforced by the
qbittorrent config initContainer); this password is only for external/UI login.
