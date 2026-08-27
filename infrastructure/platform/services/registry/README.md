# platform/services/registry

Optional internal OCI registry for cluster-local image pulls. Useful when:
- Air-gapped environments (homelab with intermittent internet).
- Pull-through cache for ghcr.io / Docker Hub rate limiting.
- Private images that don't belong on a public registry.

## Default implementation

**Harbor** (Helm chart: `harbor/harbor`). Harbor gives us:
- Pull-through caching.
- Vulnerability scanning (Trivy integration).
- RBAC + project isolation.
- Image signing (Cosign / Notary).

Alternative: plain `distribution/distribution` if we only need pull-through
with no UI.

## Fulfills
- No contract today — apps use `ghcr.io` directly. Only relevant when/if we
  adopt `pull-through cache` or want signed-image enforcement fleet-wide.

## Dependencies
- `platform/core/storage/` — image blob storage.
- `platform/core/ingress/` + `cert-manager/` — push/pull over TLS.

## Status

STUB — deferred. ghcr.io is fine for now.
