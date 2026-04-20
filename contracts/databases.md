---
contract: databases
version: 0.1.0-draft
fulfilled_by: platform/services/databases/*
---

# databases

## Abstract

Apps request a database by declaring a CR; the platform provisions it and
emits connection credentials as a Kubernetes Secret the app mounts as env
vars. Two kinds supported today: PostgreSQL (default) and Redis.

## Interface (TBD)

### PostgreSQL
Apps declare a `Database` CR (CNPG):

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: <app>-db
spec:
  cluster:
    name: shared-postgres        # cluster-level CNPG control plane
  name: <app>
  owner: <app>
```

The platform emits Secret `<app>-db-credentials` with keys:
`host`, `port`, `user`, `password`, `dbname`, `uri`.

### Redis
Apps declare a `Cache` CR (TBD — maps to Dragonfly operator or similar):

```yaml
apiVersion: platform.gophersys/v1
kind: Cache
metadata:
  name: <app>-cache
spec:
  size: small                    # small | medium | large
  persistence: false
```

Emits Secret `<app>-cache-credentials` with `host`, `port`, `password`.

## Guarantees (TBD)

- HA with primary + ≥1 replica (PostgreSQL, when cluster has ≥3 nodes).
- PITR via WAL + daily PV snapshot (PostgreSQL only).
- Schema migrations are the app's responsibility — platform does not run
  them.

## Caveats (TBD)

- `shared-postgres` is logically isolated per tenant but shares underlying
  compute. Noisy neighbors are possible at high volume.
- Redis is not durable by default — apps that need persistence must request
  `persistence: true` and accept the I/O cost.

## Example (TBD)
