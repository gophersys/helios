# platform/core/cert-manager

TLS certificate issuance. Issues certs to ingress resources via ACME (Let's
Encrypt) by default, or an internal CA for non-public clusters.

## Default implementation

**cert-manager** (Helm chart: `jetstack/cert-manager`).

- Two ClusterIssuers installed per cluster: `letsencrypt-prod` and
  `letsencrypt-staging`.
- DNS-01 where a DNS provider credential is wired (Route53, Cloud DNS,
  Azure DNS); HTTP-01 otherwise.
- Internal CA (cmctl-generated root) for clusters with no public DNS.

## Fulfills
- `contracts/ingress.md` — transparent TLS for every ingress the cluster
  serves.

## Dependencies
- `platform/core/ingress/` — its ACME HTTP-01 solver uses the ingress
  controller to serve the challenge response.
- `platform/core/secrets-operator/` — for storing DNS provider credentials
  pulled from Bitwarden.

## Status

STUB.

## TODO (when populating)
- Pin cert-manager chart version.
- Per-cluster ClusterIssuer parameterization (domain, contact email, solver).
- Document how to request a cert in app Helm values.
