# platform

Everything that runs **on** a cluster. There are 2 tiers.

## `core/`

The non-negotiable cluster bootstrap. **Every cluster gets every core
component** at bring-up. There is no opt-in, and there is no difference of
version between clusters. A component is in `core/` because no layer above it can
work without it.

- `cni/` — pod networking
- `ingress/` — HTTP(S) ingress controller
- `cert-manager/` — TLS cert issuance (Let's Encrypt + internal CA)
- `storage/` — persistent volume provisioner
- `secrets-operator/` — External Secrets Operator with Bitwarden provider
- `metrics-server/` — node/pod metrics for HPA + kubectl top
- `network-policies/` — default-deny baselines per namespace

## `services/`

The opt-in shared services, with a pinned version. A cluster declares the
`services` that it wants in `clusters/instances/<c>/identity.yaml`. The overlay
at `clusters/instances/<c>/overlays/` supplies the values for that cluster.

- `observability/` — Grafana + Prometheus + Loki + Tempo
- `databases/postgresql/` + `databases/redis/`
- `messaging/nats/`
- `registry/` — internal OCI registry (optional)
- `admin-dashboard/` — one view of every machine and cluster
- `identity-sso/` — Dex or Keycloak (future)
- `backup/` — Velero
- `cost/` — OpenCost

## The relationship to the contracts

An app never talks to a platform component directly. It consumes the declared
interfaces in `contracts/`: the CRDs, the env var conventions and the labels. A
change of implementation in `platform/services/` is invisible to an app, while
the contract stays the same.

## Status

Today **every leaf is a stub**. There is a `README.md` and no manifest. They are
populated in later passes, as a real cluster needs each component. The README of
each leaf names the default implementation that we would pick when we populate
it, and it names the contracts that the component fulfills.
