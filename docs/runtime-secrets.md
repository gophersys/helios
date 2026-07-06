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
