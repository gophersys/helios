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

## pve-00 black-holed its own LAN — incident, resolved 2026-08-18

Building this app found pve-00 unreachable from the LAN for every protocol.
`:8006` timed out from the ingress-nginx pod while pve-01 and pve-03 answered,
and ARP still resolved, so the node looked present:

```
10.168.0.201:8006  http=000  curl_rc=28   (timeout)
10.168.0.202:8006  http=200  curl_rc=0
10.168.0.203:8006  http=200  curl_rc=0
```

pveproxy was healthy the whole time (the same GET **on** pve-00 returned 200, and
`pve-firewall` was disabled). The break was routing: pve-00 accepted tailnet
routes (`RouteAll: true`) and pve-01 advertises this same subnet, so pve-00
installed a route to its own LAN over the tailnet —

```
ip rule                   ->  5270: from all lookup 52
ip route show table 52    ->  10.168.0.0/24 dev tailscale0      <-- this line
ip route get 10.168.0.221 ->  dev tailscale0 table 52 src 100.77.217.116
```

— and every reply to a `10.168.0.x` host left over `tailscale0` with a tailnet
source address and was dropped.

**Fixed** with `tailscale set --accept-routes=false` on pve-00. Verified after
the change: table 52 no longer carries `10.168.0.0/24`, `GET
https://10.168.0.201:8006/` from the ingress-nginx pod returns **200** (a HEAD
returns 501 — pveproxy behaviour, identical on pve-01), and `bash ctl.sh
verify-access` is 15/15.

**It can come back silently.** The fix is a Tailscale pref on a host that has no
identity file in this repo, so nothing in git reproduces it: re-provision pve-00,
or run one `tailscale up --accept-routes`, and the black-hole returns with no
symptom other than this hostname timing out. That, and the open question of
whether pve-00 should keep advertising `10.168.0.0/24` alongside pve-01, are
recorded in **D22** of `docs/debt-register.md`.

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
