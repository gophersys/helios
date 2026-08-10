# platform/core

The non-negotiable cluster bootstrap. Every cluster installs every core component
during bring-up, at the pinned version that this tree records.

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

`edge/` groups the ingress controller, the tunnel, the DNS and the TLS into 1
pluggable abstraction. A cluster picks its edge stack in `identity.yaml:edge`,
and an app does not know which stack it picked. The free-tier default is
Cloudflare Tunnel, Cloudflare DNS and a Cloudflare Origin Certificate for the
public scope, and Tailscale for a service scoped to the tailnet. See
`edge/README.md` and `edge/CATALOG.md` for the provider matrix and the
combinations that are known to work.

## Install order (fixed)

1. `cni` — every other component needs pod networking.
2. `storage` — the PVs for anything stateful, including the cert-manager Secrets
   and the observability stack.
3. `secrets-operator` — ESO with the Bitwarden backend. Every later component
   that needs a credential, for example an API token for a DNS provider or a
   tunnel token, reads it from ESO.
4. `edge/tls/cert-manager` — the cert-manager operator.
5. `edge/ingress-controller` — traefik, for L7 routing inside the cluster.
6. `edge/tls/<issuer>` — the concrete TLS providers for the edge configuration of
   the cluster: cloudflare-origin, letsencrypt-dns01, acm or tailscale-cert.
7. `edge/dns/<provider>` — external-dns and the provider configuration:
   cloudflare, route53 or tailscale-magicdns.
8. `edge/tunnel/<provider>` — the entry point for the traffic: cloudflare-tunnel,
   cloud-loadbalancer or tailscale-funnel.
9. `metrics-server` — the HPA and `kubectl top`.
10. `network-policies` — the baseline NetworkPolicy manifests.
11. `policy` — the Kyverno install and the ClusterPolicies. It comes after the
    steps above, so that a validating policy does not reject the install of a
    component that is still in progress.
12. `namespace-provisioner` — the Kyverno generators. It needs Kyverno, step 11.

## Status

Every component is a stub. An implementation lands as `prod` bootstraps through
this tree.
