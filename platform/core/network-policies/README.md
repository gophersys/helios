# platform/core/network-policies

Baseline NetworkPolicy manifests applied to every namespace. The defaults
are conservative: deny-all ingress/egress, then allow DNS + cluster-API +
same-namespace traffic. Apps explicitly open what they need.

## Default implementation

Raw kustomize manifests (no Helm — these are plain K8s objects). Installed
via a NamespaceClass / namespace template so every new namespace gets them
automatically.

Default policies per namespace:
- `deny-all-ingress` — deny ingress unless allowed explicitly.
- `deny-all-egress` — deny egress unless allowed explicitly.
- `allow-dns` — egress to kube-dns on UDP/TCP 53.
- `allow-same-namespace` — ingress + egress within the namespace.
- `allow-metrics-scrape` — ingress from Prometheus namespace on metrics ports.

Apps override in their own Helm values with additional allow-rules.

## Fulfills
- Implicit: least-privilege networking baseline.

## Dependencies
- `platform/core/cni/` with NetworkPolicy support (Cilium satisfies this).

## Status

STUB.

## TODO (when populating)
- Write base kustomize set.
- Wire namespace-admission-webhook (Kyverno? Gatekeeper?) that rejects
  namespaces created without these policies.
- Document how apps request exceptions (e.g. a Postgres namespace needs
  ingress from multiple app namespaces).
