---
contract: secrets
version: 0.1.0-draft
fulfilled_by: platform/core/secrets-operator/
---

# secrets

## Abstract

An app requests a secret from Bitwarden by name. The platform materializes the
secret as a Kubernetes `Secret` through the External Secrets Operator. An app
never holds a Bitwarden credential. It consumes the resulting Kubernetes Secret
only.

## Interface (TBD)

### Declaration
An app includes an `ExternalSecret` manifest in its chart. The chart archetype
emits it automatically from `values.secrets[]`:

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

The chart archetypes in `charts/` emit this automatically from the Helm values:

```yaml
secrets:
  - { key: OPENAI_API_KEY, bwItem: codectl-openai, bwProperty: apikey, mode: env }
```

### Naming convention in Bitwarden

- `<project>-<purpose>` — an item for the whole project, shared by the apps of
  that project, for example `codectl-db` and `fintel-openai`. This is the typical
  case, because the apps in a project can share a credential.
- `<project>-<app>-<purpose>` — an item for one app, where that app needs a
  credential that nobody else in the project may see, for example
  `codectl-api-internal-token` and `fintel-grader-nats-creds`.
- `platform-<component>-<purpose>` — an item at platform level, for example
  `platform-eso-bitwarden-token`.

See `infrastructure/docs/secrets-guide.md` (TBD) for the full schema.

## Guarantees (TBD)

- The refresh interval is 1h or less for an app secret, and 5m or less for a
  secret that carries a certificate.
- The Bitwarden vault is the only source of truth. A rollback of an app deploy
  does not replay a historical version of a secret automatically.
- An emitted Kubernetes Secret is namespaced to `<project>-<env>` and never
  crosses into another project.

## Caveats (TBD)

- The Bitwarden API applies rate limits. A very large number of concurrent
  ExternalSecret refreshes can hit those limits.
- Rotation is a platform operation, not an app operation.
- An item for the whole project (`<project>-<purpose>`) is visible to every app
  in every env of that project. Do NOT store a prod-only secret there. Use
  `<project>-<app>-<purpose>` with the env in the item name for a tighter scope,
  for example `codectl-api-db-prod`.

## Example (TBD)

A minimal working snippet, once the contract is final.
