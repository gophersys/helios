# platform/core

Non-negotiable cluster bootstrap. Every cluster installs every core
component during bring-up, at the pinned version recorded in this tree.

| Component                 | Role                                             |
|---------------------------|--------------------------------------------------|
| `cni/`                    | Pod networking                                   |
| `ingress/`                | HTTP(S) ingress controller                       |
| `cert-manager/`           | TLS cert issuance (ACME + internal CA)           |
| `storage/`                | Persistent volume provisioner                    |
| `secrets-operator/`       | External Secrets Operator + Bitwarden provider   |
| `metrics-server/`         | Node/pod metrics for HPA + `kubectl top`         |
| `network-policies/`       | Default-deny baselines per namespace             |
| `policy/`                 | Kyverno — admission control + cluster-wide safety rails |
| `namespace-provisioner/`  | Auto-provisioning of labels, NetPols, Quotas on new namespaces |

## Install order (fixed)

1. `cni` — everything else needs pod networking.
2. `ingress` — ACME HTTP-01 challenges route through here.
3. `cert-manager` — issues TLS for the ingress itself + downstream apps.
4. `storage` — PVs for anything stateful, including Prometheus / Loki /
   cert-manager secrets.
5. `secrets-operator` — ESO + Bitwarden backend; everything after this
   can request secrets.
6. `metrics-server` — HPA + `kubectl top` work after this lands.
7. `network-policies` — baseline NetworkPolicy manifests for new namespaces.
8. `policy` — Kyverno install + policy CRs. Comes after the above so
   validating policies don't reject in-progress component installs.
9. `namespace-provisioner` — Kyverno generators that provision new
   namespace side-effects. Requires Kyverno (from step 8).

## Status

Every component is a stub. Implementations land when the first cluster
(likely `app-prod`) is being bootstrapped through this tree.
