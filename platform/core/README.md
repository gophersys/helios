# platform/core

Non-negotiable cluster bootstrap. Every cluster installs every core
component during bring-up, at the pinned version recorded in this tree.

| Component                 | Role                                                                      |
|---------------------------|---------------------------------------------------------------------------|
| `cni/`                    | Pod networking                                                            |
| `storage/`                | Persistent volume provisioner                                             |
| `secrets-operator/`       | External Secrets Operator + Bitwarden provider                            |
| `edge/`                   | Pluggable ingress stack — tunnel + ingress-controller + DNS + TLS         |
| `metrics-server/`         | Node/pod metrics for HPA + `kubectl top`                                  |
| `network-policies/`       | Default-deny baselines per namespace                                      |
| `policy/`                 | Kyverno — admission control + cluster-wide safety rails                   |
| `namespace-provisioner/`  | Auto-provisioning of labels, NetPols, Quotas on new namespaces            |

## The edge layer

`edge/` bundles ingress-controller + tunnel + DNS + TLS into a single
pluggable abstraction. A cluster picks its edge stack in
`identity.yaml:edge`; apps are unaware of the choice. Free-tier default:
Cloudflare Tunnel + CF DNS + CF Origin Cert for public, Tailscale for
tailnet-scoped services. See `edge/README.md` + `edge/CATALOG.md` for
the provider matrix and known-good combinations.

## Install order (fixed)

1. `cni` — everything else needs pod networking.
2. `storage` — PVs for anything stateful, including cert-manager Secrets
   and the observability stack.
3. `secrets-operator` — ESO + Bitwarden backend; every later component
   that needs credentials (API tokens for DNS providers, tunnel tokens)
   pulls from ESO.
4. `edge/tls/cert-manager` — cert-manager operator.
5. `edge/ingress-controller` — traefik (in-cluster L7 routing).
6. `edge/tls/<issuer>` — concrete TLS providers per the cluster's edge
   config (cloudflare-origin / letsencrypt-dns01 / acm / tailscale-cert).
7. `edge/dns/<provider>` — external-dns + provider config
   (cloudflare / route53 / tailscale-magicdns).
8. `edge/tunnel/<provider>` — the traffic entry point (cloudflare-tunnel
   / cloud-loadbalancer / tailscale-funnel).
9. `metrics-server` — HPA + `kubectl top`.
10. `network-policies` — baseline NetworkPolicy manifests.
11. `policy` — Kyverno install + ClusterPolicies. Comes after the above
    so validating policies don't reject in-progress component installs.
12. `namespace-provisioner` — Kyverno generators. Requires Kyverno (11).

## Status

Every component is a stub. Implementations land as `prod` is
bootstrapped through this tree.
