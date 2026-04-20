# platform/secrets-external-operator

External Secrets Operator (ESO) with Bitwarden as the upstream provider.
Applications declare `ExternalSecret` resources; ESO materializes
Kubernetes `Secret`s from the Bitwarden vault.

Status: stub. The upstream Bitwarden provider for ESO is maintained as a
separate helm chart + CRDs — needs to be wired per-cluster.

TODO:
- Pin ESO chart version.
- Deploy the Bitwarden Secrets Manager backend (service account + access
  token stored encrypted at cluster bootstrap).
- Add a SecretStore per cluster pointing at the tenant-scoped Bitwarden
  org.
- Document the ExternalSecret manifest the standard chart archetypes
  expect.
