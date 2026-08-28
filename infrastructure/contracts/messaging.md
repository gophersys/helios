---
contract: messaging
version: 0.1.0-draft
fulfilled_by: platform/services/messaging/nats/
---

# messaging

## Abstract

An app publishes and consumes messages through NATS (JetStream). Each app gets a
dedicated NATS account with its own credentials. Publication and subscription
across accounts is explicit and gated.

## Interface (TBD)

### Request an account
An app declares a `NatsAccount` CR (the CRD is TBD, and is probably custom):

```yaml
apiVersion: platform.gophersys/v1
kind: NatsAccount
metadata:
  name: <project>-<app>                  # e.g., fintel-grader
  namespace: <project>-<env>             # e.g., fintel-prod
spec:
  account: <project>_<app>               # underscore form for NATS account name
  streams:                               # optional JetStream streams to create
    - name: <project>.<app>.events       # fintel.grader.events
      subjects: ["<project>.<app>.>"]
      retention: limits
      max_age: 7d
  key_value_stores: []
  object_stores: []
```

The platform emits the Secret `<project>-<app>-nats-creds`, which contains:
- `nats.creds` — the bundle of the NATS JWT and the nkey
- `NATS_URL` — the ingress URL of the cluster, for example
  `nats://nats.<cluster-domain>:4222`

An app mounts `nats.creds` and uses any NATS client library. The subject naming
convention: every subject of a project-app carries the prefix
`<project>.<app>.`, so that routing across projects and apps stays explicit.

### Traffic across accounts
Declare it with `NatsExport` and `NatsImport` CRs (TBD). There is no implicit
access: app A exports a subject explicitly, and app B imports it explicitly.

## Guarantees (TBD)

- At-least-once delivery for a stream that JetStream persists.
- Best-effort publication and subscription for a temporary subject that is not a
  stream.
- Isolation per account, so that the noisy traffic of one app cannot starve
  another app.

## Caveats (TBD)

- There is a message size limit. The default is 1 MB, and you can override it per
  stream.
- JetStream storage uses `platform/core/storage/`. If an app exceeds its quota,
  that is the app's problem, not the platform's.

## Example (TBD)
