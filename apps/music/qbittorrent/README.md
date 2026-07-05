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

## Known follow-ups
- **Port sync:** Proton's forwarded port (NAT-PMP, dynamic) is not yet pushed into
  qBittorrent's listen port — downloads work; seeding is suboptimal until wired.
- **First login:** temp admin password is in `kubectl -n media logs <pod> -c qbittorrent`;
  set a permanent one in the WebUI immediately.
- **Host-header:** if the WebUI 401s behind the proxy, disable Host header validation
  (Options → WebUI) or whitelist the domain.
