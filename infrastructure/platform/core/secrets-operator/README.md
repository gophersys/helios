# platform/core/secrets-operator

The External Secrets Operator (ESO) with the Bitwarden Secrets Manager provider.
An app declares an `ExternalSecret` CR, and ESO materializes a Kubernetes
`Secret` object from the Bitwarden vault.

## Default implementation

**external-secrets**, from the Helm chart
`external-secrets/external-secrets`, plus the **Bitwarden Secrets Manager
backend**, which has its own chart and CRDs for the SDK.

For each cluster:
- 1 `ClusterSecretStore` that points at the Bitwarden organization of the tenant.
- 1 cluster-bootstrap secret that holds the access token of the ESO service
  account. You provision it outside this repo. See `docs/secrets-guide.md`.

## Fulfills
- `contracts/secrets.md` — how apps request Bitwarden items as Kubernetes
  Secrets.

## Dependencies
- `platform/core/cni/` (for ESO pod reachability).
- Out-of-band: Bitwarden organization set up, service account + access
  token issued (stored encrypted at cluster bootstrap time).

## Status

STUB.

## TODO, when we populate this component
- Pin the version of the ESO chart.
- Wire the Bitwarden SDK container. It runs as a sidecar to ESO.
- Document the canonical shape of an `ExternalSecret`: the labels and the
  annotations that the chart archetypes expect.
- Decide the refresh interval. The default is 1h for an app secret, and 5m for a
  secret that carries a certificate.
