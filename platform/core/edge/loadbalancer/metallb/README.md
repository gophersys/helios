# platform/core/edge/loadbalancer/metallb

MetalLB provides `type: LoadBalancer` IPs on bare-metal / homelab clusters that
have no cloud load balancer. On the homelab it hands out LAN IPs from the pool
`10.168.0.240–250` (ingress-nginx = `.240`).

> **Migration status (Phase 1 — DORMANT).** `pool.yaml` is the live
> `IPAddressPool` + `L2Advertisement`, relocated byte-identical from
> `homelab/kubernetes/metallb/`. Not yet Argo-managed. New leaf per decision 5
> (the template had no loadbalancer/ home). See `docs/migration-homelab-to-idp.md`.

## Policy note
MetalLB's speaker needs `hostNetwork` + `NET_RAW`, which restricted PodSecurity
rejects — so it requires a standing platform-component PolicyException when
Kyverno enforce lands (Phase 4-5). Documented, not yet applied.
