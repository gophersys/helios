# charts/ingress-app

Stateless app that is always exposed via Ingress with cert-manager-issued
TLS. Thin wrapper around `stateless-app` with sensible defaults for the
ingress path.

Status: stub.

TODO: implement. The chart should reject values where `ingress.enabled`
is false — the whole point of this archetype is that ingress is
mandatory.
