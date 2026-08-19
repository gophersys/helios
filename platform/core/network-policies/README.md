# platform/core/network-policies

The baseline NetworkPolicy manifests, applied to every namespace. The defaults
are restrictive: deny all ingress and all egress, then allow DNS, the cluster API
and the traffic inside the same namespace. An app opens explicitly what it needs.

## Default implementation

Raw kustomize manifests. There is no Helm, because these are plain Kubernetes
objects. A NamespaceClass or a namespace template installs them, so that every
new namespace gets them automatically.

Default policies per namespace:
- `deny-all-ingress` — deny ingress unless allowed explicitly.
- `deny-all-egress` — deny egress unless allowed explicitly.
- `allow-dns` — egress to kube-dns on UDP/TCP 53.
- `allow-same-namespace` — ingress + egress within the namespace.
- `allow-metrics-scrape` — ingress from Prometheus namespace on metrics ports.

An app adds more allow rules in its own Helm values.

## Fulfills
- Implicit: least-privilege networking baseline.

## Dependencies
- `platform/core/cni/` with NetworkPolicy support (Cilium satisfies this).

## Status

STUB.

## TODO, when we populate this component
- Write the base kustomize set.
- Refuse a namespace created without these policies. **Not with Kyverno or
  Gatekeeper** — neither is coming back (`.claude/rules/50-cluster-architecture.md`
  §4). The in-tree shape is a `ValidatingAdmissionPolicy` on `CREATE namespaces`,
  alongside the 2 in `platform/core/policy/`. Note the limit before you write it:
  a VAP cannot look up another object, so it cannot ask whether the NetworkPolicy
  exists — it can only require the label or annotation that the provisioner would
  key on. Unbuilt.
- Document how an app requests an exception. An example is a Postgres namespace
  that needs ingress from several app namespaces.
