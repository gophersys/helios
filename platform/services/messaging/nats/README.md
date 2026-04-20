# platform/services/messaging/nats

NATS with JetStream — pub/sub, durable queues, key-value, object store, all
in one cluster.

## Default implementation

**NATS** (Helm chart: `nats-io/nats`). JetStream enabled with persistent
storage. One account per tenant app, one set of JWT credentials per account,
emitted as ExternalSecret.

## Fulfills
- `contracts/messaging.md`.

## Dependencies
- `platform/core/storage/` — JetStream persistence.
- `platform/core/secrets-operator/` — account JWTs out to apps.

## Status

STUB.

## TODO (when populating)
- Pin NATS chart version.
- Define account allocation workflow (per-app account vs per-feature
  account).
- Document credential emission in `contracts/messaging.md`.
- Decide whether to expose a NATS admin UI (Synadia Platform is nice; may
  be overkill for fleet-of-one).
