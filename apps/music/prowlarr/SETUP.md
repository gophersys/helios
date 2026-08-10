# Prowlarr setup runbook

The indexer and download-client configuration of Prowlarr lives in its own SQLite
database on the `prowlarr-config` PVC. It is **state in the UI and on the PVC, and
GitOps cannot manage it**. This runbook is the reproducible source of truth for
that configuration (debt-register D2).

> Why is it not automated? The configuration API of Prowlarr **2.4.0** blocks a
> headless setup. When you add the qBittorrent download client, the upstream test
> path throws a `NullReferenceException` against qBittorrent **5.2.2**. When you
> add an indexer, Prowlarr runs a synchronous site test, and that test does not
> return from the egress of the cluster. Both actions work correctly in the Web
> UI, which is the supported path. This is therefore a runbook, not a script.
> `?forceSave=true` does **not** skip either test in 2.4.0.

## Open the UI
```sh
kubectl -n media port-forward deploy/prowlarr 9696:9696   # http://localhost:9696
```
You can also use `https://prowlarr.mateosegura.com`, once its DNS record exists.

## 1. Add the indexers, so that search works
UI → **Indexers → Add Indexer** → choose the public torrent indexers, for example
`The Pirate Bay`, `1337x`, `YTS` and `LimeTorrents` → press **Save** on each one.
Prowlarr tests the site, and a public site needs no credentials. The **Search**
tab of Prowlarr then works.

## 1b. The FlareSolverr proxy, for indexers behind Cloudflare
Some public indexers (1337x, LimeTorrents, EZTV and others) sit behind a
Cloudflare challenge that Prowlarr cannot solve directly.
`apps/music/flaresolverr/` runs a headless-Chrome solver for them. Wire it as an
indexer proxy. **This configuration lives only in the SQLite database on the
`prowlarr-config` PVC (debt-register D2), so recreate it here:**
UI → **Settings → Indexers → + (Add Indexer Proxy) → FlareSolverr**:
- **Name** `flaresolverr`  ·  **Tags** `flaresolverr`
- **Host** `http://flaresolverr.media.svc.cluster.local:8191`  → **Test → Save.**

Then add the `flaresolverr` tag to each indexer that sits behind Cloudflare (edit
the indexer → **Tags** `flaresolverr`), so that Prowlarr routes its requests
through the solver. An indexer without the tag is not affected.

## 2. The qBittorrent download client, to push a grab to qBittorrent
UI → **Settings → Download Clients → + → qBittorrent**:
- **Host** `qbittorrent`  ·  **Port** `8080`  ·  **Category** `prowlarr`
- Leave **Username** and **Password** empty. An in-cluster client bypasses the
  authentication, because qBittorrent has
  `WebUI\AuthSubnetWhitelist=10.42.0.0/16`, and the qbittorrent initContainer
  enforces that setting.
- **Test → Save.**

qBittorrent creates the `prowlarr` category automatically. To create it in
advance:
```sh
kubectl -n media exec deploy/qbittorrent -c qbittorrent -- \
  curl -s -X POST http://localhost:8080/api/v2/torrents/createCategory \
  --data-urlencode category=prowlarr --data-urlencode savePath=/downloads/prowlarr
```

### If the download-client Test gives an error (`Object reference not set …`)
That is the known NRE between 2.4.0 and 5.2.2. The options, best first:
1. **Pin qBittorrent** to a release that Prowlarr supports. Edit
   `apps/music/qbittorrent/20-deployment.yaml`, field
   `image: lscr.io/linuxserver/qbittorrent:<tag>`, deploy again, and test again.
2. Until then, **search still works**. Grab a result in Prowlarr and add its
   magnet link to qBittorrent by hand, or set up the client when the versions
   match.

## Verify
- Search: UI **Search** → query `debian` → results appear with seeders.
- Grab, if the client is wired: a search result → **Grab** → the torrent appears
  in qBittorrent under the `prowlarr` category, and it downloads over the VPN.

## Recreate the download client (qBittorrent) through the API

The UI works. If you script the setup instead, the critical field is the
top-level `categories: []`, and it is easy to miss. Without it the
`ValidateCategories` function of Prowlarr throws a NullReferenceException, and
the add fails with a 400. This looked like an incompatibility with qBittorrent
5.2, and it was not. The working request:

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
It returns `201`, and the test passes. In the cluster the qBittorrent
authentication is bypassed by subnet, but real credentials also work.
