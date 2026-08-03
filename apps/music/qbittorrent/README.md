# qbittorrent — VPN-isolated torrent client (homelab)

qBittorrent behind a **Gluetun / ProtonVPN WireGuard kill-switch**, on the homelab
k3s cluster. Private, non-commercial use. Part of the (growing) `media` stack.

## Architecture

```
Pod (ns: media, pinned to pve-00)
  ├─ gluetun        ProtonVPN WireGuard + kill-switch firewall  ──▶ 🌍 via VPN (home IP hidden)
  └─ qbittorrent    shares gluetun's netns → all egress tunneled; Web UI :8080
        │
        ├─ config    PVC (local-path, pve-00)
        └─ downloads PVC (local-path, pve-00 954GB NVMe)

Web UI:  torrent.mateosegura.com ──(DNS-only A → 10.168.0.240)──▶ ingress-nginx ─▶ svc :8080
         TLS: cert-manager DNS-01 (letsencrypt-homelab).  Reachable on the tailnet only.
```

## Files
| File | What |
|------|------|
| `00-namespace.yaml` | `media` namespace |
| `10-storage.yaml`   | config + downloads PVCs (local-path, pve-00) |
| `20-deployment.yaml`| qbittorrent + gluetun sidecar |
| `30-service.yaml`   | ClusterIP :8080 |
| `40-ingress.yaml`   | `torrent.mateosegura.com` + TLS |

## The secret (NOT in git)
`gluetun-wireguard` is created imperatively from vault `shared/protonvpn/wireguard`:
```bash
WG=$(bw get notes "shared/protonvpn/wireguard")
kubectl -n media create secret generic gluetun-wireguard \
  --from-literal=WIREGUARD_PRIVATE_KEY="$(printf '%s' "$WG" | awk -F' = ' '/^PrivateKey/{print $2}')" \
  --from-literal=WIREGUARD_ADDRESSES="$(printf '%s' "$WG" | awk -F' = ' '/^Address/{print $2}' | cut -d, -f1 | tr -d ' ')"
```

## Verify the VPN is up (and NOT leaking home IP)
```bash
POD=$(kubectl -n media get pod -l app=qbittorrent -o jsonpath='{.items[0].metadata.name}')
kubectl -n media exec "$POD" -c gluetun -- wget -qO- http://127.0.0.1:8000/v1/publicip/ip
# expect a ProtonVPN datacenter IP, never the home WAN IP
```

## Troubleshooting

### 503 from the Web UI / Prowlarr can't push a download

The pod sits at `2/3` and gluetun CrashLoopBackOffs with:

```
ERROR [vpn] adding IPv6 rule: adding ip rule 101: from all to all table 51820: file exists
```

**Why it never self-heals:** Kubernetes shares ip rules across the whole
pod, and the pod's *network namespace survives a container restart*. One
abrupt gluetun exit leaves rule 101 behind, and every restart after it hits
the same "file exists" — forever. (Seen 2026-08-02 at 937 restarts.)

The `lifecycle.postStart` hook on the gluetun container now clears the rule
before it installs its own, so this should not recur. If it ever does, the
fix is to **delete the pod** — not restart the container — because only a
new pod gets a fresh network namespace:

```bash
kubectl -n media delete pod -l app=qbittorrent
```

Then re-run the VPN check above; expect `3/3 Running` with 0 restarts.

### Prowlarr shows a red cloud: "Failed to connect to qBittorrent, check your settings"

**That message is misleading — it is usually not a connection problem.** Check
Prowlarr's log for the real status code:

```
HTTP request failed: [409:Conflict] [POST] at [http://qbittorrent:8080/api/v2/torrents/add]
```

**409 Conflict with an 8-byte `Conflict` body means the torrent is already in
qBittorrent** — matched by *info-hash*, not by name. Two indexers routinely list
the same torrent under different titles, so a release that looks new can be a
byte-identical duplicate of something already downloaded. qBittorrent names the
culprit explicitly:

```bash
POD=$(kubectl -n media get pod -l app=qbittorrent -o jsonpath='{.items[0].metadata.name}')
kubectl -n media exec "$POD" -c qbittorrent -- grep -i "duplicate" /config/qBittorrent/logs/qbittorrent.log | tail -3
# -> "Detected an attempt to add a duplicate torrent. ... Existing torrent: <name>"
```

The fix is to remove the existing torrent (or accept that you already have it);
there is **no setting that makes a duplicate add succeed**. Verified 2026-08-02:
enabling `merge_trackers` does merge the new trackers into the existing torrent,
but the API still returns 409. Prowlarr v2.5.1 does not special-case 409 and
reports every one as a connection failure.

Confirm the connection is genuinely fine before chasing settings:

```bash
PRO=$(kubectl -n media get pod -l app=prowlarr -o jsonpath='{.items[0].metadata.name}')
kubectl -n media exec "$PRO" -- sh -c 'K=$(sed -n "s:.*<ApiKey>\(.*\)</ApiKey>.*:\1:p" /config/config.xml); \
  curl -s -X POST -H "X-Api-Key: $K" http://localhost:9696/api/v1/downloadclient/testall'
# -> "isValid": true  means auth + reachability are fine; the 409 is about the torrent
```

## Known follow-ups
- **Port sync:** Proton's forwarded port (NAT-PMP, dynamic) is not yet pushed into
  qBittorrent's listen port — downloads work; seeding is suboptimal until wired.
- **First login:** temp admin password is in `kubectl -n media logs <pod> -c qbittorrent`;
  set a permanent one in the WebUI immediately.
- **Host-header:** if the WebUI 401s behind the proxy, disable Host header validation
  (Options → WebUI) or whitelist the domain.
