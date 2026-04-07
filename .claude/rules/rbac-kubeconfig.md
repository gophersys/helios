---
paths:
  - "infrastructure/**/*"
---

# RBAC & Kubeconfig Rules

Concord has **two independent auth layers** that share the same role names:

| Layer | Protects | Auth Method |
|-------|----------|-------------|
| **K8s RBAC** | Cluster ops (`kubectl`, pod logs, secrets) | Client certificate kubeconfig |
| **Concord API** | Application (UI, API endpoints, validation runs) | CoreCloud JWT + API keys |

## Kubeconfig Generation

```bash
# Generate for one user
./infrastructure/ctl.sh office kubeconfig create --user chris@corekinect.com --role DEVELOPER

# Generate for entire team
./infrastructure/ctl.sh office kubeconfig batch

# List all generated kubeconfigs
./infrastructure/ctl.sh office kubeconfig list

# Revoke a user's access
./infrastructure/ctl.sh office kubeconfig revoke --user chris@corekinect.com
```

Generated files go to `infrastructure/clusters/office/kubeconfigs/generated/` (gitignored).

## Access Matrix (Enforced)

| Role | Staging | Production | Dev | Validation |
|------|---------|------------|-----|------------|
| ADMIN | Full | Full | Full | Full |
| MAINTAINER | Full | **Read-only** | Full | Full |
| DEVELOPER | Full | Read-only | Full | Read-only |
| OPERATOR | Read-only | None | None | None |

"Full" = get, list, watch, create, update, delete, exec, logs
"Read-only" = get, list, watch only
"None" = no access

## How It Works

1. `generate.sh` creates a private key + CSR with `CN=<email>` and `O=<k8s-group>`
2. CSR is submitted to K8s CertificateSigningRequest API and auto-approved
3. Signed certificate + key are bundled into a kubeconfig file
4. The group in the certificate matches existing RoleBindings (e.g., `concord-developers`)

## Role → Group → Binding Chain

```
Platform Role: DEVELOPER
  → K8s Group: concord-developers
    → RoleBinding: concord-developer-full (staging) → ClusterRole: concord-namespace-admin
    → RoleBinding: concord-viewer-readonly (production) → ClusterRole: concord-namespace-readonly
```

## Certificate Lifecycle

- Default validity: 365 days
- Override with: `--days 730`
- Revocation: delete CSR + delete kubeconfig file (K8s has no CRL)
- Renewal: run `create` again — auto-replaces old CSR

## Rules

- **Only ADMINs** can generate kubeconfigs (requires cluster CA access)
- Generated kubeconfigs are **gitignored** — never commit private keys
- Default namespace in generated kubeconfigs is `staging` (safe default)
- Team roster in `generate.sh batch` must match `prisma/seed/platform.py` TEAM list
