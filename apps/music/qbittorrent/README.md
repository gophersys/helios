# qbittorrent — VPN-isolated torrent client (homelab)

qBittorrent behind a **Gluetun / ProtonVPN WireGuard kill-switch**, on the
homelab k3s cluster. It is for private, non-commercial use. It is part of the
`media` stack, which continues to grow.

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
Create `gluetun-wireguard` imperatively from the vault item
`shared/protonvpn/wireguard`:
```bash
WG=$(bw get notes "shared/protonvpn/wireguard")
kubectl -n media create secret generic gluetun-wireguard \
  --from-literal=WIREGUARD_PRIVATE_KEY="$(printf '%s' "$WG" | awk -F' = ' '/^PrivateKey/{print $2}')" \
  --from-literal=WIREGUARD_ADDRESSES="$(printf '%s' "$WG" | awk -F' = ' '/^Address/{print $2}' | cut -d, -f1 | tr -d ' ')"
```

## Verify that the VPN is up and does not leak the home IP
```bash
POD=$(kubectl -n media get pod -l app=qbittorrent -o jsonpath='{.items[0].metadata.name}')
kubectl -n media exec "$POD" -c gluetun -- wget -qO- http://127.0.0.1:8000/v1/publicip/ip
# expect a ProtonVPN datacenter IP, never the home WAN IP
```

## Troubleshooting

### The Web UI returns 503, or Prowlarr cannot push a download

The pod stays at `2/3`, and gluetun enters CrashLoopBackOff with:

```
ERROR [vpn] adding IPv6 rule: adding ip rule 101: from all to all table 51820: file exists
```

**Why it does not recover on its own:** Kubernetes shares the ip rules across the
whole pod, and the *network namespace of the pod survives a container restart*.
One abrupt exit of gluetun leaves rule 101 in place, and every restart after that
hits the same "file exists" error, with no end. We saw this on 2026-08-02 at 937
restarts.

The `lifecycle.postStart` hook on the gluetun container now clears the rule
before it installs its own rule, so this must not happen again. If it does
happen, **delete the pod**. Do not restart the container, because only a new pod
gets a new network namespace:

```bash
kubectl -n media delete pod -l app=qbittorrent
```

Then run the VPN check above again. Expect `3/3 Running` with 0 restarts.

### Prowlarr shows a red cloud: "Failed to connect to qBittorrent, check your settings"

**That message is misleading. It is usually not a connection problem.** Check the
Prowlarr log for the real status code:

```
HTTP request failed: [409:Conflict] [POST] at [http://qbittorrent:8080/api/v2/torrents/add]
```

**A 409 Conflict with an 8-byte `Conflict` body means that the torrent is already
in qBittorrent.** The match is by *info-hash*, not by name. Two indexers often
list the same torrent under different titles, so a release that looks new can be
a byte-identical duplicate of something already downloaded. qBittorrent names the
existing torrent:

```bash
POD=$(kubectl -n media get pod -l app=qbittorrent -o jsonpath='{.items[0].metadata.name}')
kubectl -n media exec "$POD" -c qbittorrent -- grep -i "duplicate" /config/qBittorrent/logs/qbittorrent.log | tail -3
# -> "Detected an attempt to add a duplicate torrent. ... Existing torrent: <name>"
```

To fix it, remove the existing torrent, or accept that you already have it. There
is **no setting that makes a duplicate add succeed**. Verified 2026-08-02: with
`merge_trackers` enabled, the new trackers do merge into the existing torrent,
but the API still returns 409. Prowlarr v2.5.1 does not treat 409 as a special
case, and it reports every 409 as a connection failure.

Confirm that the connection is genuinely fine before you change any setting:

```bash
PRO=$(kubectl -n media get pod -l app=prowlarr -o jsonpath='{.items[0].metadata.name}')
kubectl -n media exec "$PRO" -- sh -c 'K=$(sed -n "s:.*<ApiKey>\(.*\)</ApiKey>.*:\1:p" /config/config.xml); \
  curl -s -X POST -H "X-Api-Key: $K" http://localhost:9696/api/v1/downloadclient/testall'
# -> "isValid": true  means auth + reachability are fine; the 409 is about the torrent
```

## Known follow-ups
- **Port sync:** the forwarded port of Proton (NAT-PMP, dynamic) is not yet
  pushed into the listen port of qBittorrent. Downloads work, and seeding stays
  below the best rate until somebody wires this.
- **First login:** the temporary admin password is in
  `kubectl -n media logs <pod> -c qbittorrent`. Set a permanent password in the
  WebUI immediately.
- **Host header:** if the WebUI returns 401 behind the proxy, disable the Host
  header validation (Options → WebUI), or add the domain to the allowlist.
