# platform

Everything that runs **on** clusters. Two tiers:

## `core/`

Non-negotiable cluster bootstrap. **Every cluster gets every core component**
at bring-up — no opt-in, no version skew. If a component is in `core/`, it's
because nothing above can work without it.

- `cni/` — pod networking
- `ingress/` — HTTP(S) ingress controller
- `cert-manager/` — TLS cert issuance (Let's Encrypt + internal CA)
- `storage/` — persistent volume provisioner
- `secrets-operator/` — External Secrets Operator with Bitwarden provider
- `metrics-server/` — node/pod metrics for HPA + kubectl top
- `network-policies/` — default-deny baselines per namespace

## `services/`

Opt-in, version-pinned shared services. A cluster declares in
`clusters/instances/<c>/identity.yaml` which `services` it wants; the overlay
at `clusters/instances/<c>/overlays/` supplies cluster-specific values.

- `observability/` — Grafana + Prometheus + Loki + Tempo
- `databases/postgresql/` + `databases/redis/`
- `messaging/nats/`
- `registry/` — internal OCI registry (optional)
- `admin-dashboard/` — single pane of glass
- `identity-sso/` — Dex/Keycloak (future)
- `backup/` — Velero
- `cost/` — OpenCost

## Contract relationship

Apps never talk to platform components directly. They consume declared
interfaces in `contracts/` (CRDs, env conventions, labels). Swapping an
implementation in `platform/services/` is invisible to apps as long as the
contract is preserved.

## Status

Today: **every leaf is a stub** — `README.md` only, no manifests. Populated
in later passes as real clusters demand each component. See each leaf's
README for "default implementation we'd pick when populating" and contract
linkage.
