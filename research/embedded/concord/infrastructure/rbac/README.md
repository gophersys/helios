# Concord RBAC — Platform Role → Kubernetes Mapping

The Concord platform defines 4 user roles in the application layer (Prisma schema). These map to Kubernetes ClusterRoles for direct cluster access via `kubectl`.

## Role Mapping

| Platform Role | K8s ClusterRole | K8s Group | Scope |
|---|---|---|---|
| **ADMIN** | `concord-super-admin` | `concord-admins` | Cluster-wide — full access |
| **MAINTAINER** | `concord-namespace-admin` | `concord-maintainers` | Namespace — full CRUD in staging/production/validation/devops |
| **DEVELOPER** | `concord-namespace-readonly` | `concord-developers` | Namespace — full access in staging, read-only in production/devops |
| **OPERATOR** | `concord-namespace-readonly` | `concord-operators` | Namespace — read-only in staging only |

## Service Accounts

| Service Account | K8s ClusterRole | Scope |
|---|---|---|
| `concord-api` | `concord-api-system-monitor` | Cluster-wide — monitors nodes, creates jobs, manages pods |

## Files

- `role-mapping.yaml` — Canonical source of truth for the mapping
- `../clusters/<cluster>/rbac/clusterroles.yaml` — K8s ClusterRole definitions
- `../clusters/<cluster>/rbac/bindings-<ns>.yaml` — RoleBindings per namespace
- `../clusters/<cluster>/rbac/service-accounts.yaml` — SA + ClusterRoleBindings

## Adding a New User

1. Add the user to the appropriate K8s group (via your identity provider or kubeconfig)
2. The RoleBindings reference groups, so the user automatically gets the right access
3. Also create the user in the Concord app (Prisma) with the matching platform role
