---
contract: databases
version: 0.1.0-draft
fulfilled_by: platform/services/databases/*
---

# databases

## Abstract

An app requests a database when it declares a CR. The platform provisions the
database and emits the connection credentials as a Kubernetes Secret, which the
app mounts as env vars. 2 kinds are supported today: PostgreSQL (the default) and
Redis.

## Interface (TBD)

### PostgreSQL
An app declares a `Database` CR (CNPG):

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: <project>-<app>-db             # e.g., codectl-api-db
  namespace: <project>-<env>           # e.g., codectl-prod
spec:
  cluster:
    name: shared-postgres              # cluster-level CNPG control plane
  name: <project>_<app>                # DB name (underscored — Postgres identifier)
  owner: <project>_<app>
```

The platform emits the Secret `<project>-<app>-db-credentials` with the keys
`host`, `port`, `user`, `password`, `dbname` and `uri`.

### Redis
An app declares a `Cache` CR (TBD — it maps to the Dragonfly operator or a
similar operator):

```yaml
apiVersion: platform.gophersys/v1
kind: Cache
metadata:
  name: <project>-<app>-cache          # e.g., codectl-api-cache
  namespace: <project>-<env>
spec:
  size: small                          # small | medium | large
  persistence: false
```

It emits the Secret `<project>-<app>-cache-credentials` with `host`, `port` and
`password`.

## Guarantees (TBD)

- HA with a primary and 1 or more replicas (PostgreSQL, when the cluster has 3 or
  more nodes).
- PITR through WAL plus a daily PV snapshot (PostgreSQL only).
- Schema migrations are the app's responsibility. The platform does not run them.

## Caveats (TBD)

- `shared-postgres` is isolated per tenant at the logical level, but the tenants
  share the underlying compute. At high volume one tenant can affect another.
- Redis is not durable by default. An app that needs persistence must request
  `persistence: true` and accept the I/O cost.

## Example (TBD)
