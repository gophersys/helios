# Prowlarr setup runbook

Prowlarr's indexer + download-client configuration lives in its own SQLite DB on
the `prowlarr-config` PVC — it is **UI/PVC state, not GitOps-able**. This runbook
is the reproducible source of truth for that config (debt-register D2).

> Why not automated? Prowlarr **2.4.0**'s config API fights headless setup:
> adding the qBittorrent download client trips an upstream test-path
> `NullReferenceException` against qBittorrent **5.2.2**, and indexer-add runs a
> synchronous site-test that hangs from the cluster's egress. Both work fine in
> the Web UI, which is the supported path — so this is a runbook, not a script.
> `?forceSave=true` does **not** skip either test in 2.4.0.

## Access the UI
```sh
kubectl -n media port-forward deploy/prowlarr 9696:9696   # http://localhost:9696
```
(or `https://prowlarr.mateosegura.com` once its DNS record exists).

## 1. Add indexers  (makes search work)
UI → **Indexers → Add Indexer** → pick public torrent indexers, e.g.
`The Pirate Bay`, `1337x`, `YTS`, `LimeTorrents` → **Save** on each (Prowlarr
tests the site; public ones need no credentials). Prowlarr's **Search** tab is
now functional.

## 2. qBittorrent download client  (auto-push grabs to qBit)
UI → **Settings → Download Clients → + → qBittorrent**:
- **Host** `qbittorrent`  ·  **Port** `8080`  ·  **Category** `prowlarr`
- **Username / Password** blank — in-cluster clients are auth-bypassed
  (qBittorrent `WebUI\AuthSubnetWhitelist=10.42.0.0/16`, enforced by the
  qbittorrent initContainer).
- **Test → Save.**

The `prowlarr` category is auto-created in qBittorrent; to pre-create it:
```sh
kubectl -n media exec deploy/qbittorrent -c qbittorrent -- \
  curl -s -X POST http://localhost:8080/api/v2/torrents/createCategory \
  --data-urlencode category=prowlarr --data-urlencode savePath=/downloads/prowlarr
```

### If the download-client Test errors (`Object reference not set …`)
That is the known 2.4.0 ↔ 5.2.2 NRE. Options, cleanest first:
1. **Pin qBittorrent** to a Prowlarr-compatible release (edit
   `apps/music/qbittorrent/20-deployment.yaml`
   `image: lscr.io/linuxserver/qbittorrent:<tag>`), redeploy, re-test.
2. Until then, **search still works** — grab a result in Prowlarr and add its
   magnet to qBittorrent manually, or set the client up when versions align.

## Verify
- Search: UI **Search** → query `debian` → results with seeders.
- Grab (if client wired): search result → **Grab** → appears in qBittorrent
  under the `prowlarr` category, downloading over the VPN.

## Download client (qBittorrent) — API recreation

The UI works, but if scripting: the critical, easily-missed field is the
top-level `categories: []`. Without it Prowlarr's `ValidateCategories` throws a
NullReferenceException and the add fails with a 400 (this looked like a
qBit-5.2 incompatibility but wasn't). Working request:

```
POST /api/v1/downloadclient   (X-Api-Key: <key>)
{
  "enable": true, "protocol": "torrent", "priority": 1,
  "categories": [],                      # <-- REQUIRED, else NRE
  "name": "qBittorrent", "implementation": "QBittorrent",
  "configContract": "QBittorrentSettings",
  "fields": [ {"name":"host","value":"qbittorrent"}, {"name":"port","value":8080},
              {"name":"username","value":"admin"}, {"name":"password","value":"<qbit-webui-pw>"},
              {"name":"category","value":"prowlarr"} ]
}
```
Returns `201` with the test passing. qBit auth is subnet-bypassed in-cluster, but
passing real creds also works.
