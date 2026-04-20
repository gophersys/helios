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
Apps include an `ExternalSecret` manifest in their chart:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: <app>-bw-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: bitwarden-cluster
    kind: ClusterSecretStore
  target:
    name: <app>-secrets
  data:
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: <bw-item-name>
        property: apikey
```

The chart archetypes in `charts/` emit this automatically from Helm values:

```yaml
secrets:
  OPENAI_API_KEY:
    bw_item: fintel-openai-key
    property: apikey
```

### Naming convention in Bitwarden
- `<app>-<purpose>` for app-specific items.
- `<platform>-<component>-<purpose>` for platform-level items.
- See `infrastructure/docs/secrets-guide.md` (TBD) for the full schema.

## Guarantees (TBD)

- Refresh interval ≤ 1h for app secrets, ≤ 5m for cert-bearing secrets.
- The Bitwarden vault is the only source of truth; app deploy rollback
  does not replay historical secret versions automatically.

## Caveats (TBD)

- Bitwarden API rate limits apply — very large fan-out of ExternalSecret
  refreshes can rate-limit.
- Rotation is a platform operation, not an app operation.

## Example (TBD)

Minimal working snippet once finalized.
