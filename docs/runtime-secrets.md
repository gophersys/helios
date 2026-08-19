# Runtime secrets

Credential material that lives **only in the cluster or on an app PVC, never in
git**. You recreate each one from Vaultwarden, where the items follow
`shared/<service>/<purpose>`. This is the full inventory behind debt-register
D4 and D5.

> Why are these imperative? The ESO `vaultwarden` ClusterSecretStore returns the
> **notes** blob of an item (`jsonPath $.data.data[0].notes`). That fits a
> multi-line configuration, for example WireGuard, but it does not fit a login
> with single fields. Single-value credentials are therefore created
> imperatively, in the same way as the existing `gluetun-wireguard` secret. Every
> command below assumes that you exported `BW_SESSION` and that `KUBECONFIG`
> points at the homelab.

## k8s Secrets (namespace `media` unless stated otherwise)

### `gluetun-wireguard` — ProtonVPN WireGuard for the torrent VPN
Vault item: `shared/protonvpn/wireguard` (the notes hold the WireGuard
configuration). The full recreation procedure is in the header of
`apps/music/qbittorrent/20-deployment.yaml`.

### `homepage-secrets` — credentials for the Homepage dashboard widgets
```sh
PKEY=$(kubectl -n media exec deploy/prowlarr -- sh -c \
  'grep -oE "<ApiKey>[a-f0-9]+</ApiKey>" /config/config.xml | sed "s/<[^>]*>//g"')
kubectl -n media create secret generic homepage-secrets \
  --from-literal=HOMEPAGE_VAR_PROWLARR_KEY="$PKEY" \
  --from-literal=HOMEPAGE_VAR_QBIT_PASS="bypass" \
  --dry-run=client -o yaml | kubectl apply -f -
```
`HOMEPAGE_VAR_QBIT_PASS` is a placeholder. The qBittorrent widget authenticates
through the in-cluster subnet bypass, not through this value.

### `filebrowser-admin` — the Filebrowser admin password
```sh
kubectl -n media create secret generic filebrowser-admin \
  --from-literal=password="$(bw get password shared/filebrowser/admin)" \
  --dry-run=client -o yaml | kubectl apply -f -
```
Then apply it to the app with `apps/music/filebrowser/reset-admin/job.yaml`. Read
its header first: the running server locks the database, so scale the deployment
to 0 before you run the job.

### `operator-oauth` (namespace `tailscale`) — OAuth for the Tailscale operator
Vault item: `shared/tailscale/oauth-k8s-operator`. The recreation procedure is in
`platform/services/networking/tailscale-operator/README.md`.

### `workspaces-github-app` (namespace `workspaces-prod`) — REMOVED 2026-08-19
Both the Secret and its namespace are gone with `apps/workspaces/`. It gave
workspaces-api a **gophersys-arc** App identity so it could open GitOps PRs. Do
not recreate it. The App key it came from (`shared/github/arc-app`) is still live
and still in use — see `arc-github-app` below. The personal PAT
(`workspaces-github`) was already retired before the removal.


### `arc-github-app` (namespace `arc-runners`) — GitHub App for self-hosted CI and CD promotion
The **gophersys-arc** GitHub App authenticates the org self-hosted runner pool
(`arc-org`, ARC). It also authenticated the image promotion from the
`gophersys/workspaces` repo into this one; that deployment was removed on
2026-08-19, so the promotion has no target here, while the App and the pool are
unaffected. Vault item: **`shared/github/arc-app`** (App ID, Client ID,
Installation ID and the private key).
```sh
kubectl -n arc-runners create secret generic arc-github-app \
  --from-literal=github_app_id=4235192 \
  --from-literal=github_app_installation_id=144912786 \
  --from-file=github_app_private_key=<key.pem>   # from bw: shared/github/arc-app
```
The same App key is also set as repository secrets on `gophersys/workspaces`
(`ARC_APP_ID`, `ARC_APP_PRIVATE_KEY`). Those repository secrets are untouched;
the deployment they promoted into is what was removed.

## Secrets for the platform, the backups and the edge

### `bw-cli-credentials` (namespace `external-secrets`) — THE seed secret
This is the one secret that anchors the whole chain from ESO to Vaultwarden. It
holds the personal API key and the master password. It is created by hand. The
full recreation procedure and the security notes are in
`platform/core/secrets-operator/manifests/README.md` ("The one seed secret").

### `cloudflare-api-token` (namespace `cert-manager`) — the DNS-01 solver token
A Cloudflare API token (Zone:DNS:Edit) that the `letsencrypt-homelab`
ClusterIssuer uses. See the header of
`platform/core/edge/tls/cert-manager/cluster-issuer.yaml`. Vault item:
**`shared/cloudflare/api-token`** (confirmed present 2026-08-09 — an earlier
revision of this document stated incorrectly that no vault item existed).
Related items: `shared/cloudflare/tunnel`, `shared/cloudflare/zone-id` and
`shared/cloudflare/access-google-oauth`. Recreate it with:
```sh
kubectl -n cert-manager create secret generic cloudflare-api-token \
  --from-literal=api-token="$CLOUDFLARE_API_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### `grafana-admin` (namespace `observability`) — the Grafana admin login
The `obs` Helm release consumes it (`admin.existingSecret=grafana-admin`, keys
`admin-user` and `admin-password`). The password is **generated at creation**
with `openssl rand`, and it is not in the vault. If you recreate the Secret you
only mint a new password. Read the current one with
`kubectl -n observability get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d`.
The recreation procedure is in
`platform/services/observability/chart/README.md`.

### `minio-creds` (namespace `minio`) — the MinIO root credentials
The root credentials of the in-cluster S3 target (`apps/minio/`). Vault item:
`shared/minio/longhorn-backups` — a **historical item name**: it was created for
the Longhorn backup target, which was removed on 2026-08-19, and it now holds the
MinIO root credential for a server whose only consumer is the `music-backups`
restic repository. Renaming the vault item means changing every reference here
and in `apps/minio/README.md`; it has not been done.
```sh
kubectl -n minio create secret generic minio-creds \
  --from-literal=MINIO_ROOT_USER="$(bw get username shared/minio/longhorn-backups)" \
  --from-literal=MINIO_ROOT_PASSWORD="$(bw get password shared/minio/longhorn-backups)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### MinIO IAM: the `music-studio` user (no k8s secret) — restic for music-studio
This is not a k8s Secret. It is imperative state inside MinIO: the user
`music-studio` and the policy `music-backups-rw`, which gives read and write on
the bucket `music-backups` only. It was created through an ad-hoc `mc` pod (the
pattern is in `apps/minio/README.md`). Only restic on Mateo's Mac consumes it,
through the tailnet-private `s3.mateosegura.com`. Vault items:
`project/music-studio/minio/{access-key,secret-key}`, plus
`project/music-studio/restic/password` for the encryption of the repository.
After a MinIO rebuild, recreate this state with `mc admin user add`,
`policy create` and `policy attach`.

### `longhorn-minio-backup` (namespace `longhorn-system`) — REMOVED 2026-08-19
Both the Secret and its namespace are gone with Longhorn. It held the S3
credentials that `BackupTarget/default` used to reach MinIO. Do not recreate it.
The vault item it read (`shared/minio/longhorn-backups`) still backs `minio-creds`
above and must stay.

### `tunnel-token` (namespace `cloudflare-tunnel`) — the Cloudflare tunnel token
The token of the `eden-home` Zero Trust tunnel, issued in the Cloudflare
dashboard. `platform/core/edge/tunnel/cloudflare-tunnel/deployment.yaml` consumes
it. Store the token at `shared/cloudflare/tunnel-token` in the notes field:
```sh
kubectl -n cloudflare-tunnel create secret generic tunnel-token \
  --from-literal=token="$(bw get notes shared/cloudflare/tunnel-token)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Passwords the app manages (not k8s Secrets)

### The qBittorrent WebUI password
It lives as a hash in the config PVC (`qBittorrent.conf`), and a PVC rebuild
resets it. Apply it again from the vault (`shared/qbittorrent/webui`):
```sh
bw get password shared/qbittorrent/webui | kubectl -n media exec -i \
  deploy/qbittorrent -c qbittorrent -- sh -c \
  'read -r P; curl -s -X POST http://localhost:8080/api/v2/app/setPreferences \
   --data-urlencode "json={\"web_ui_password\":\"$P\"}"'
```
In-cluster access bypasses the authentication (`WebUI\AuthSubnetWhitelist`,
enforced by the qbittorrent config initContainer). This password is only for
external and UI login.
