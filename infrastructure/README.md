# Concord Infrastructure

Cluster provisioning layer — takes a Kubernetes cluster from zero to ready for application deployment.

Completely separate from `deploy/` (application deployment). Infrastructure prepares the cluster; `deploy/` deploys apps on top.

## Quick Start

```bash
# Bootstrap the office cluster (idempotent)
./infrastructure/ctl.sh office bootstrap

# Check readiness
./infrastructure/ctl.sh office status

# Generate kubeconfigs for the team
./infrastructure/ctl.sh office kubeconfig batch

# Create a single kubeconfig
./infrastructure/ctl.sh office kubeconfig create --user new@corekinect.com --role DEVELOPER
```

## Structure

```
infrastructure/
├── ctl.sh                  # CLI: bootstrap, status, validate, diff, kubeconfig, secrets
├── project.json            # Nx project (test target)
├── rbac/
│   └── role-mapping.yaml   # Canonical role → ClusterRole mapping
├── tests/                  # TDD test scripts
├── dependencies/           # Helm chart values (cert-manager, etc.)
└── clusters/
    └── office/
        ├── cluster.yaml        # Cluster identity, workloads, nodes
        ├── bootstrap.sh        # Idempotent 0→ready
        ├── teardown.sh         # Destructive removal
        ├── kubeconfigs/
        │   ├── generate.sh     # Kubeconfig generator (create/list/revoke/batch)
        │   └── generated/      # Output dir (gitignored — contains private keys)
        ├── namespaces/         # Namespace manifests
        ├── rbac/               # ClusterRoles + RoleBindings
        ├── storage/            # StorageClass definitions
        ├── networking/         # Certs, TLS, ingress
        └── secrets/            # .env → K8s secrets
```

## RBAC

Role-scoped kubeconfigs enforce least-privilege access:

| Role | Staging | Production | Generated With |
|------|---------|------------|----------------|
| ADMIN | Full | Full | `--role ADMIN` |
| MAINTAINER | Full | Read-only | `--role MAINTAINER` |
| DEVELOPER | Full | Read-only | `--role DEVELOPER` |
| OPERATOR | Read-only | None | `--role OPERATOR` |

## Data Protection

- PVCs annotated `helm.sh/resource-policy: keep` — survive `helm uninstall`
- PVs set to `Retain` — data persists even if PVC deleted
- Daily postgres backups to MinIO (`backups/postgres/<env>/`)
- Pre-upgrade auto-backup before every `helm upgrade`
- Weekly MinIO mirror to hostPath
- Production stop requires `--confirm-delete`

## Production Hardening Status

### Done

| Item | Status | Details |
|------|--------|---------|
| Secrets overlay | **DONE** | `values-*-secrets.yaml` (gitignored), committed files have placeholders only |
| Network policies | **DONE** | Postgres, MinIO, http-api isolated. Helm-managed, toggle via `networkPolicies.enabled` |
| Backup verification | **DONE** | Weekly CronJob `concord-backup-verify` — restores latest dump, validates table count |
| Resource quotas | **DONE** | Staging: 6 CPU / 8Gi. Production: 8 CPU / 10Gi. Helm-managed |
| Pod security | **DONE** | `baseline` enforced, `restricted` warn-only. Build-service exempted (needs Docker socket) |
| RBAC kubeconfigs | **DONE** | 6 team kubeconfigs generated. MAINTAINER read-only in production |

### Remaining

| Item | Status | What's Needed |
|------|--------|---------------|
| Rotate admin kubeconfig | **MANUAL** | Distribute per-user kubeconfigs, then rotate K3s server token on a server node: `k3s token rotate --server https://10.4.45.11:6443` |
| DNS + TLS migration | **BLOCKED** | Waiting on sysadmin for AD CA wildcard cert. CSR ready at `infrastructure/clusters/office/networking/certs/` |
| Backup failure alerts | **TODO** | Add webhook notification (Slack/email) on CronJob failure. Consider Prometheus alerting |
| SealedSecrets | **OPTIONAL** | Current overlay files work but require manual distribution. SealedSecrets would allow encrypted secrets in git |
