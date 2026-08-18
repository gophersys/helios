# proxmox

`proxmox.mateosegura.com` → the Proxmox VE web UI of **pve-00**, so the
hypervisor is one click from the `home.mateosegura.com` portal instead of a
remembered `https://100.x:8006`.

There is no workload here. The Service is selectorless and its EndpointSlice is
written by hand, because the backend is a machine on the LAN.

## The 3 nodes are standalone, not a cluster

Measured 2026-08-18 over Tailscale SSH:

```
pve-00   pvecm status -> "Corosync config /etc/pve/corosync.conf does not exist"
pve-01   pvecm status -> same
pve-03   pvecm status -> same
```

So there is no single UI that shows all 3. Each node serves only itself, and one
hostname can only point at one of them. `proxmox.` is bound to **pve-00** — the
MS-A2, the always-on node, and the node with the most VMs (`qm list`: k3s-cp-0,
k3s-w-0, k3s-w-1, k3s-w-2 + the template). pve-01 and pve-03 are reached from the
portal by tailnet address; see `apps/music/homepage/20-configmap.yaml`.

If these 3 are ever joined into a real PVE cluster, delete the 2 portal tiles and
keep this one: a cluster UI shows every node from any member.

## The addresses

| Node | vmbr0 (what the ingress uses) | tailnet |
| --- | --- | --- |
| pve-00 | 10.168.0.201 | 100.77.217.116 |
| pve-01 | 10.168.0.202 | 100.124.246.39 |
| pve-03 | 10.168.0.203 | 100.126.209.124 |

The LAN address is the load-bearing one: the ingress-nginx pod has a route to
10.168.0.0/24 and none to 100.64.0.0/10.

## Known blocker — pve-00 black-holes its own LAN

**This ingress cannot serve until pve-00 is fixed.** From the ingress-nginx pod:

```
10.168.0.201:8006  http=000  curl_rc=28   (timeout)
10.168.0.202:8006  http=200  curl_rc=0
10.168.0.203:8006  http=200  curl_rc=0
```

pveproxy is healthy — `curl https://10.168.0.201:8006/` **on pve-00** returns
200, and `pve-firewall` is disabled. The break is routing. pve-00 accepts tailnet
routes (`RouteAll: true`) and has accepted a route for its own LAN:

```
# pve-00
ip rule                  ->  5270: from all lookup 52
ip route show table 52   ->  10.168.0.0/24 dev tailscale0        <-- this line
ip route get 10.168.0.221 -> dev tailscale0 table 52 src 100.77.217.116
```

Every reply to a 10.168.0.x host therefore leaves over tailscale0 with a tailnet
source address and is dropped. ARP still answers, so the node looks present while
ping, ssh and :8006 all time out from the LAN. pve-01 and pve-03 do not carry
that route in table 52, which is why they answer.

This is a machine defect, not a defect of this app — pve-00 is currently
unreachable from its own LAN for every protocol, which also affects anything else
that talks to it over 10.168.0.201. Fixing it is an imperative change to a
machine and needs authorization; it is not GitOps. Once it is fixed, re-run the
probe above and expect `http=200`.

## Exposure

Declared `tailnet` in `contracts/exposure.yaml`. The A record is DNS-only
(grey-cloud) to 10.168.0.240, the MetalLB VIP, so the name resolves publicly —
which is what lets Let's Encrypt issue a real certificate over DNS-01 — while the
address is reachable only on the tailnet or the home LAN.

There is no gate in front of it beyond the tailnet, and the backend is
root-equivalent on 4 running VMs. It must never move to a `public-*` class.

## Adding pve-01 or pve-03 later

Copy `10-service.yaml` with the node's own name and vmbr0 address, add a second
Ingress for its hostname, and declare that hostname in
`contracts/exposure.yaml`. Nothing else changes.

## pve-00 LAN reachability — FIXED 2026-08-18

The route defect above was fixed the same day: `tailscale set --accept-routes=false`
on pve-00 removed the `10.168.0.0/24 dev tailscale0` line from table 52. Verified:
`GET https://10.168.0.201:8006/` from the ingress-nginx pod returns 200 (HEAD
returns 501 — pveproxy behaviour, identical on pve-01), and `verify-access` is
15/15. pve-00 still advertises 10.168.0.0/24 as a second subnet router; whether
to keep dual advertisement (failover) or single-home it on pve-01 is an open
topology decision, recorded in NEEDS-MATEO.
