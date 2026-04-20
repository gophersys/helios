# platform/core/secrets-operator

External Secrets Operator (ESO) with the Bitwarden Secrets Manager provider.
Apps declare `ExternalSecret` CRs; ESO materializes Kubernetes `Secret`
objects from the Bitwarden vault.

## Default implementation

**external-secrets** (Helm chart: `external-secrets/external-secrets`) +
**Bitwarden Secrets Manager backend** (separate chart/CRDs for the SDK).

Per-cluster:
- One `ClusterSecretStore` pointing at the tenant Bitwarden organization.
- A cluster-bootstrap secret holding the ESO service-account access token
  (provisioned out-of-band; see `docs/secrets-guide.md`).

## Fulfills
- `contracts/secrets.md` — how apps request Bitwarden items as Kubernetes
  Secrets.

## Dependencies
- `platform/core/cni/` (for ESO pod reachability).
- Out-of-band: Bitwarden organization set up, service account + access
  token issued (stored encrypted at cluster bootstrap time).

## Status

STUB.

## TODO (when populating)
- Pin ESO chart version.
- Wire the Bitwarden SDK container (runs as a sidecar to ESO).
- Document `ExternalSecret` canonical shape — what labels/annotations the
  chart archetypes expect.
- Decide on refresh interval (default 1h for app secrets, 5m for cert-bearing
  secrets).
