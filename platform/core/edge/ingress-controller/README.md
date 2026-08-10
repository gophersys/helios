# platform/core/ingress

The HTTP and HTTPS ingress controller. It terminates the traffic inside the
cluster. An app declares an `Ingress` resource to become reachable.

---

## What is deployed today on the homelab — the source of truth

**`ingress-nginx`** is the live controller, and it holds the single
`IngressClass: nginx`. All HTTP enters here: from the Cloudflare tunnel, for the
public `home.` and `workspaces.` hosts on `:80`, or from the MetalLB VIP
`10.168.0.240`, for the tailnet-private hostnames with TLS from cert-manager
DNS-01. It is installed from the **raw upstream manifests with `kubectl
apply`**, not with Helm, and Argo does not manage it today.
`docs/debt-register.md` (D9) tracks its pinned version and the command to install
it again. Traefik was evaluated and **removed**. See
`docs/cluster-topology.md`.

---

## Target design (for prod, not deployed yet)

The original intent for prod was **Traefik** (`traefik/traefik`), for CRD-based
routing with IngressRoute and Middleware, and for its built-in ACME resolver.
`ingress-nginx` was the alternative for a case that needs the exact semantics of
upstream nginx. The homelab chose ingress-nginx instead. This section records the
design option. It is not what runs.

## Fulfills
- `contracts/ingress.md` — how apps expose HTTPS routes with automatic TLS + DNS.

## Dependencies
- `platform/core/cni/` (pod networking)
- `platform/core/cert-manager/` (TLS issuance for the tailnet-private hosts)

## TODO (when a prod cluster bootstraps)
- Pin the chart version + parameterize the default TLS resolver per cluster.
- Put the controller dashboard behind the `identity-sso` service (future).
