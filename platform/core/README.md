# platform/core

Non-negotiable cluster bootstrap. Every cluster installs every core component
during bring-up, at the pinned version recorded in this tree.

| Component           | Role                                           |
|---------------------|------------------------------------------------|
| `cni/`              | Pod networking                                 |
| `ingress/`          | HTTP(S) ingress controller                     |
| `cert-manager/`     | TLS cert issuance (ACME + internal CA)         |
| `storage/`          | Persistent volume provisioner                  |
| `secrets-operator/` | External Secrets Operator + Bitwarden provider |
| `metrics-server/`   | Node/pod metrics for HPA + `kubectl top`       |
| `network-policies/` | Default-deny baselines per namespace           |

## Install order (fixed)

1. `cni`
2. `ingress`
3. `cert-manager`
4. `storage`
5. `secrets-operator`
6. `metrics-server`
7. `network-policies`

## Status

Every component is a stub. Implementations land when the first cluster is
being bootstrapped through this tree.
