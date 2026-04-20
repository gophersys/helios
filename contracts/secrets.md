---
contract: secrets
version: 0.1.0-draft
fulfilled_by: platform/core/secrets-operator/
---

# secrets

## Abstract

Apps request secrets from Bitwarden by name; the platform materializes them
as Kubernetes `Secret`s via External Secrets Operator. Apps never hold
Bitwarden credentials — they just consume the resulting K8s Secret.

## Interface (TBD)

### Declaration
Apps include an `ExternalSecret` manifest in their chart (auto-emitted
by the chart archetype from `values.secrets[]`):

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: <project>-<app>-bw-secrets         # e.g., codectl-api-bw-secrets
  namespace: <project>-<env>               # e.g., codectl-prod
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: bitwarden-cluster
    kind: ClusterSecretStore
  target:
    name: <project>-<app>-secrets          # e.g., codectl-api-secrets
  data:
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: <project>-openai              # Bitwarden item name
        property: apikey
```

The chart archetypes in `charts/` emit this automatically from Helm values:

```yaml
secrets:
  - { key: OPENAI_API_KEY, bwItem: codectl-openai, bwProperty: apikey, mode: env }
```

### Naming convention in Bitwarden

- `<project>-<purpose>` — project-wide items shared across the project's
  apps (e.g., `codectl-db`, `fintel-openai`). The typical case — apps
  within a project can share credentials.
- `<project>-<app>-<purpose>` — app-specific items where an app needs
  credentials nobody else in the project should see
  (e.g., `codectl-api-internal-token`, `fintel-grader-nats-creds`).
- `platform-<component>-<purpose>` — platform-level items
  (e.g., `platform-eso-bitwarden-token`).

See `infrastructure/docs/secrets-guide.md` (TBD) for the full schema.

## Guarantees (TBD)

- Refresh interval ≤ 1h for app secrets, ≤ 5m for cert-bearing secrets.
- The Bitwarden vault is the only source of truth; app deploy rollback
  does not replay historical secret versions automatically.
- Emitted Kubernetes Secrets are namespaced to `<project>-<env>` and
  never leak across projects.

## Caveats (TBD)

- Bitwarden API rate limits apply — very large fan-out of ExternalSecret
  refreshes can rate-limit.
- Rotation is a platform operation, not an app operation.
- Project-wide items (`<project>-<purpose>`) are visible to every app in
  every env of that project — do NOT store prod-only secrets here. Use
  `<project>-<app>-<purpose>` with env in the item name for tighter
  scoping (e.g., `codectl-api-db-prod`).

## Example (TBD)

Minimal working snippet once finalized.
