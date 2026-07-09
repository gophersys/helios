# platform/core/ingress

HTTP(S) ingress controller. Terminates in-cluster traffic; apps declare
`Ingress` resources to become reachable.

---

## Deployed today (homelab) — the source of truth

**`ingress-nginx`** is the live controller (the single `IngressClass: nginx`).
Everything HTTP enters here — from the Cloudflare tunnel (public `home.` /
`workspaces.`, on `:80`) or the MetalLB VIP `10.168.0.240` (tailnet-private
hostnames, TLS via cert-manager DNS-01). Installed via **raw upstream manifests
(`kubectl apply`)**, not Helm, and not currently Argo-managed — its pinned
version is tracked in `docs/debt-register.md` (D9) with the reinstall command.
Traefik was evaluated and **removed**. See `docs/cluster-topology.md`.

---

## Target design (prod, not yet deployed)

The original prod intent was **Traefik** (`traefik/traefik`) for CRD-based
routing (IngressRoute/Middleware) and a built-in ACME resolver, with
`ingress-nginx` as the alternative when strict upstream-nginx semantics are
needed. The homelab went the other way (ingress-nginx) — this section records
the design option, not what runs.

## Fulfills
- `contracts/ingress.md` — how apps expose HTTPS routes with automatic TLS + DNS.

## Dependencies
- `platform/core/cni/` (pod networking)
- `platform/core/cert-manager/` (TLS issuance for the tailnet-private hosts)

## TODO (when a prod cluster bootstraps)
- Pin the chart version + parameterize the default TLS resolver per cluster.
- Put the controller dashboard behind the `identity-sso` service (future).
