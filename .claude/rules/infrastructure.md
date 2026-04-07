# Infrastructure Layer

The `infrastructure/` directory is the **cluster provisioning** layer — everything needed to take a Kubernetes cluster from zero to ready for application deployment.

## Separation of Concerns

- **`infrastructure/`** = Cluster setup: namespaces, RBAC, cert-manager, storage classes, node labels, workload types, networking
- **`deploy/`** = Application deployment: Helm charts, ctl.sh, Dockerfiles, values files

These are completely separate. `deploy/` deploys **on top of** a cluster that `infrastructure/` has prepared. Never mix them.

## Structure

```
infrastructure/
├── ctl.sh              # CLI: bootstrap, status, validate, diff
├── project.json        # Nx project with test target
├── tests/              # TDD test scripts for all manifests
├── rbac/               # Canonical role mapping (role-mapping.yaml)
└── clusters/
    ├── office/         # K3s HA cluster (10.4.45.x)
    │   ├── cluster.yaml    # Cluster identity + workload types + node inventory
    │   ├── bootstrap.sh    # Idempotent 0→ready script
    │   ├── nodes/          # Node label definitions
    │   ├── namespaces/
    │   ├── rbac/
    │   ├── storage/
    │   ├── networking/
    │   └── secrets/
    └── eks/            # AWS EKS (placeholder)
```

## Commands

```bash
npx nx test infrastructure                        # Run all tests
./infrastructure/ctl.sh office bootstrap           # Set up office cluster
./infrastructure/ctl.sh office status              # Check cluster readiness
./infrastructure/ctl.sh office validate            # Dry-run manifests
```

## Workload Types (5 node types)

Every cluster defines 5 abstract workload types. Helm chart templates use `nodeSelector: { concord.corekinect.com/workload-<type>: "true" }` to place pods on the right nodes. A single physical node can serve multiple workload types.

| Type | Purpose | Helm services | Office nodes |
|---|---|---|---|
| **platform** | Application services | http-api, frontend, docs, git-poller, pypi | servers, agent01-02 |
| **data** | Stateful storage | postgres, minio | server03, agent03 |
| **build** | General-purpose builds | build-service, build-workers | concordproxy, wanda |
| **worker** | Ephemeral job execution | validation-runner, manufacturing-jobs | agent01-03 |
| **edge** | Hardware-attached | mtib-server | verdin-imx8mm-* (ARM64, always on-premise) |

### Node Labels

bootstrap.sh applies two label types per node:
- `concord.corekinect.com/workload=<primary>` — for simple nodeSelector
- `concord.corekinect.com/workload-<type>=true` — for each supported workload type (multi-role)

### Helm Integration

Each deployment template uses the `concord.workloadNodeSelector` helper:
```yaml
spec:
  {{- include "concord.workloadNodeSelector" (dict "workload" "platform" "extra" .Values.httpApi.nodeSelector) | nindent 6 }}
```

Override per-component placement via `nodeSelector:` in Helm values files.

## RBAC: Platform Role → K8s ClusterRole

| Platform Role | ClusterRole | Staging | Production |
|---|---|---|---|
| ADMIN | `concord-super-admin` | Full | Full |
| MAINTAINER | `concord-namespace-admin` / `readonly` | Full | **Read-only** |
| DEVELOPER | `concord-namespace-admin` / `readonly` | Full | Read-only |
| OPERATOR | `concord-namespace-readonly` | Read-only | None |

Kubeconfigs: `./infrastructure/ctl.sh office kubeconfig create --user <email> --role <ROLE>`
See `rbac-kubeconfig.md` for full details.

## Data Protection

All stateful services (postgres, minio, pypi) have:
- **PVC annotations**: `helm.sh/resource-policy: keep` — survives `helm uninstall`
- **PV reclaim policy**: `Retain` — data stays on disk even if PVC is deleted
- **Automated backups**: PostgreSQL daily to MinIO, MinIO weekly mirror to hostPath
- **Pre-upgrade backups**: Automatic `pg_dump` before every Helm upgrade
- **Production stop guard**: `./deploy/ctl.sh production stop` requires `--confirm-delete`

See `data-protection.md` for full backup/restore procedures.

## Adding a New Cluster

1. Create `infrastructure/clusters/<name>/` with `cluster.yaml` and `bootstrap.sh`
2. Define all 5 workload types in `cluster.yaml` with node assignments
3. Copy RBAC manifests from an existing cluster as baseline
4. Add cluster-specific storage classes and networking config
5. Run `npx nx test infrastructure` to verify
