---
contract: messaging
version: 0.1.0-draft
fulfilled_by: platform/services/messaging/nats/
---

# messaging

## Abstract

Apps publish and consume messages via NATS (JetStream). Each app gets a
dedicated NATS account with its own credentials; cross-account pub/sub is
explicit and gated.

## Interface (TBD)

### Requesting an account
Apps declare a `NatsAccount` CR (TBD CRD, likely custom):

```yaml
apiVersion: platform.gophersys/v1
kind: NatsAccount
metadata:
  name: <app>
spec:
  streams:                       # optional JetStream streams to create
    - name: <app>.events
      subjects: ["<app>.>"]
      retention: limits
      max_age: 7d
  key_value_stores: []
  object_stores: []
```

The platform emits Secret `<app>-nats-creds` containing:
- `nats.creds` — NATS JWT + nkey bundle
- `NATS_URL` — cluster ingress URL (e.g., `nats://nats.<cluster-domain>:4222`)

Apps mount `nats.creds` and use any NATS client library.

### Cross-account traffic
Declared via `NatsExport` / `NatsImport` CRs (TBD). No implicit access —
app A explicitly exports a subject, app B explicitly imports.

## Guarantees (TBD)

- At-least-once delivery for JetStream-persisted streams.
- Pub/sub best-effort for ephemeral (non-stream) subjects.
- Per-account isolation — one app's noisy traffic can't starve another.

## Caveats (TBD)

- Message size limit (default 1 MB; overridable per stream).
- JetStream storage uses `platform/core/storage/` — exceeding quota is the
  app's problem, not the platform's.

## Example (TBD)
