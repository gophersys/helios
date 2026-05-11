# infrastructure — knowledge

The cluster provisioning layer. Takes a raw Kubernetes cluster (K3s in the office, EKS in AWS) from zero to "ready to receive application deploys". This is completely separate from `deploy/`, which ships the Concord apps onto an already-bootstrapped cluster.

Refresh this file when: a new cluster target appears (e.g., a second office cluster), the bootstrap order changes, a new cluster dependency is added (cert-manager, vault, external-secrets, otel collector), the RBAC role mapping changes, the kubeconfig generator gains a new role, or the secrets-sync mechanism changes shape.

## Location

```
infrastructure/
├── ctl.sh                  # entry point — bootstrap, status, validate, diff, kubeconfig, secrets
├── project.json            # nx project (test target)
├── README.md
├── rbac/
│   └── role-mapping.yaml   # canonical platform-Role → K8s ClusterRole mapping
├── dependencies/
│   └── cert-manager/values.yaml
├── tests/                  # bash TDD scripts (bootstrap, secrets, manifests, rbac, cluster-yaml)
└── clusters/
    ├── office/             # K3s, in-office, edge nodes
    │   ├── cluster.yaml
    │   ├── bootstrap.sh    # idempotent 0 → ready
    │   ├── teardown.sh     # destructive
    │   ├── kubeconfigs/    # generate.sh (create/list/revoke/batch) + generated/ (gitignored)
    │   ├── namespaces/
    │   ├── nodes/labels.yaml
    │   ├── rbac/
    │   ├── networking/     # cert-manager-ca.yaml, ingress class, certificates/
    │   ├── storage/
    │   └── secrets/        # .env templates + create-all.sh + sync to K8s
    └── eks/                # AWS, dev / future-prod target
        ├── cluster.yaml
        ├── bootstrap.sh
        ├── teardown.sh
        ├── rbac/
        └── secrets/
```

## Two target clusters

| Cluster | Where | Role | Trust model |
|---|---|---|---|
| `office` | Office, K3s on bare metal | Hosts staging + production today, plus the edge Verdin nodes | Internal CA, internal DNS (`*.concord.ad.corekinect.com`), no public ingress |
| `eks` | AWS, EKS | Dev/scratch experiments; potential future prod target | Public LB, ACM-issued TLS, IAM-anchored auth |

Bootstrapping a new cluster of either kind is `./infrastructure/ctl.sh <cluster> bootstrap`. The `cluster.yaml` in that cluster's directory is the source of truth for identity, namespaces, nodes, workloads, and what dependencies to install.

## What `bootstrap.sh` does, in order

Both office and eks scripts follow the same skeleton:

1. **Namespaces** — `staging`, `production`, `devops` (for CI), `cert-manager`, …
2. **Node labels** — applied from `cluster.yaml::nodes` (control-plane vs agent vs edge). Edge nodes get `concord.corekinect.com/workload-edge=true` (and a `kubernetes.io/arch=arm64` from the K3s join, not from us).
3. **Cluster dependencies** — `helm install` for each, using `dependencies/<name>/values.yaml`. Today: `cert-manager`. Slots reserved for future: otel collector, vault.
4. **Post-install manifests** — `cert-manager-ca.yaml` (self-signed bootstrap → 10-year CA → ClusterIssuer), TLS certificates per namespace.
5. **RBAC** — applies ClusterRoles + RoleBindings from `clusters/office/rbac/` referencing `rbac/role-mapping.yaml`.
6. **Storage verification** — checks the expected StorageClasses exist (`local-path` for K3s, `gp3` for EKS).
7. **Secrets** — runs `clusters/office/secrets/create-all.sh` which reads per-env `.env` files and creates K8s Secrets via `kubectl apply` of generated manifests.

`bootstrap.sh --dry-run` previews everything without applying. `teardown.sh` reverses the order and is destructive (`helm uninstall`, `kubectl delete namespace`).

The scripts are idempotent: re-running `bootstrap.sh` is the canonical "drift recovery" mechanism. If somebody manually fiddled labels, certs, or secrets, re-bootstrap restores the declared state. There is no separate `reconcile` command — bootstrap is reconcile.

## RBAC model

`rbac/role-mapping.yaml` is the canonical mapping from a platform Role (`ADMIN`, `MAINTAINER`, `DEVELOPER`, `OPERATOR`) to one or more K8s `ClusterRole`s. Current mapping (verify against `infrastructure/rbac/role-mapping.yaml` before relying on this — it changes occasionally):

| Role | Staging | Production | Validation | Devops |
|---|---|---|---|---|
| ADMIN | Full (cluster-wide) | Full | Full | Full |
| MAINTAINER | Full namespace | Full namespace | Full namespace | Full namespace |
| DEVELOPER | Full namespace | Read-only | Read-only | Read-only |
| OPERATOR | Read-only on workloads | None | Read-only on workloads | None |

ADMIN gets the `concord-super-admin` ClusterRole (cluster-wide); the other roles get namespace-scoped ClusterRoles applied via RoleBinding per namespace. `infrastructure/rbac/role-mapping.yaml` is the authoritative table.

The `kubeconfigs/generate.sh` script bakes a user's effective bindings into a single `KUBECONFIG` file by minting a ServiceAccount, granting the right `ClusterRole`s, and emitting a kubeconfig that uses the ServiceAccount token. Two CLI forms:

- `infrastructure/ctl.sh office kubeconfig create --user <email> --role <ADMIN|...>` — single user.
- `infrastructure/ctl.sh office kubeconfig batch` — generate for everyone listed in cluster.yaml.

Generated kubeconfigs land in `clusters/office/kubeconfigs/generated/` (gitignored — they carry token material).

## Secrets sync

Production secrets aren't stored in this repo. They live in Bitwarden (the canonical store) and a developer's local `clusters/office/secrets/{shared,staging,production}.env` files (gitignored).

`secrets/create-all.sh` reads those `.env` files and writes K8s `Secret` resources for `concord-secrets`, `bitbucket-ssh-key`, `build-service-credentials`, `coreops-credentials`, etc. Idempotent — re-running rotates the values.

For day-to-day rotation, prefer `nx run platform:sync-secrets -c <env>` (the deploy-layer wrapper). It calls into the same scripts.

Per-secret rotation flow is in [`deploy/secrets.md`](deploy/secrets.md). Rule: [`rules/secrets-handling.md`](../rules/secrets-handling.md).

Note: `coreops-credentials` is a deliberate **second** Secret in addition to the `COREOPS_*` keys inside `concord-secrets`. The runner-pod templates (`apps/backend/http-api/assets/templates/{manufacturing_deployment,manufacturing_job,validation_job}.yaml`) consume the standalone `coreops-credentials` Secret directly because they don't share `concord-secrets`' scope. Don't remove either — both are load-bearing.

Note: `PRODUCTION_SMOKE_API_KEY` (in `.env.example`) is NOT synced as a K8s Secret by `create-all.sh`. It's only read by `.ci/stages/smoke.sh` on the production smoke path, supplied as a Bitbucket Pipelines variable in CI. It's listed in `.env.example` so a workstation operator running production smoke locally knows to set it.

## Common operations

| Need | Command |
|---|---|
| Bring up a fresh office cluster | `./infrastructure/ctl.sh office bootstrap` |
| Bring up a fresh EKS cluster | `./infrastructure/ctl.sh eks bootstrap` |
| Preview changes | `./infrastructure/ctl.sh office bootstrap --dry-run` |
| Check cluster health | `./infrastructure/ctl.sh office status` |
| Re-apply node labels | `./infrastructure/ctl.sh office bootstrap` (idempotent) |
| Generate a single kubeconfig | `./infrastructure/ctl.sh office kubeconfig create --user X --role DEVELOPER` |
| Generate all kubeconfigs | `./infrastructure/ctl.sh office kubeconfig batch` |
| Apply secrets | `./infrastructure/ctl.sh office secrets sync` (or `nx run platform:sync-secrets -c <env>`) |
| Run TDD checks | `nx run infrastructure:test` |
| Validate cluster.yaml schema | `./infrastructure/ctl.sh office validate` |

`infrastructure/ctl.sh` is invoked directly, not via an Nx wrapper. Bootstrap is rare enough that the friction of typing the script path is a feature, not a bug; the `nx-only` rule applies to application build/test/deploy operations, not to cluster bootstrap.

## How to onboard a new edge Verdin node

End-to-end flow lives in [`deploy/verdin-edge.md`](deploy/verdin-edge.md). The infrastructure-side touches:

1. Append the node entry to `clusters/office/cluster.yaml::nodes.edge` (hostname, ip).
2. Append the node entry to `clusters/office/nodes/labels.yaml::nodes.edge` with `workloads: [edge]`.
3. Re-run `bootstrap.sh` (or apply labels manually one-shot).

The platform-side (Discover + Register + Slot-bind in the UI) is owned by the http-api endpoints under `/v2/nodes/*`. The infrastructure layer only ensures the Verdin's labels survive a cluster bounce.

The `/onboard-mtib` skill walks the full flow end-to-end.

## What does NOT live here

- Application deploys — `deploy/` owns that.
- The dev compose stack — `deploy/development/`.
- Helm chart for Concord apps — `deploy/production/helm/concord/`.
- Image builds — `deploy/ctl.sh::cmd_build` per service.
- The CI platform (nightly/weekly cronjobs, ci-admin dashboard) — `deploy/ci/`, separate Helm chart in `devops` namespace.

## Common failure modes

- **`bootstrap.sh` partially applies, then fails on cert-manager** — usually the K3s API hasn't fully come up yet. Wait 30s, re-run. The script is idempotent.
- **Generated kubeconfig works for one command, then fails 401** — the ServiceAccount token rotated. Regenerate.
- **Edge Verdin labels disappear after a node reboot** — K3s reload sometimes drops labels that aren't in a static manifest. The `bootstrap.sh --labels-only` mode (if present, otherwise full bootstrap) re-applies; verify by adding the node to `labels.yaml` so future bootstraps catch it.
- **`secrets/create-all.sh` fails: "missing value for X"** — the per-env `.env` file is incomplete. Diff against `.env.example` and fill in from Bitwarden.
- **`role-mapping.yaml` change doesn't take effect** — the kubeconfig is baked at generation time. Existing kubeconfigs use the bindings at the time they were issued. Regenerate to pick up new role mappings.

## Related knowledge

- [`deploy/overview.md`](deploy/overview.md) — what runs on top of the cluster after infrastructure is done.
- [`deploy/helm.md`](deploy/helm.md) — the Concord application chart.
- [`deploy/secrets.md`](deploy/secrets.md) — secret inventory + rotation flow.
- [`deploy/network.md`](deploy/network.md) — ingress, TLS, internal DNS.
- [`deploy/verdin-edge.md`](deploy/verdin-edge.md) — Verdin edge onboarding (platform side).
- [`../rules/secrets-handling.md`](../rules/secrets-handling.md) — what counts as a secret and where it lives.
